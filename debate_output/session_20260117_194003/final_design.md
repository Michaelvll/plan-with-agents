# Final Agreed Design

**Task:** Design a simple task queue system for background job processing

Requirements:
- Support job submission with priority levels
- Handle retries on failure with exponential backoff
- Provide job status tracking (pending, running, completed, failed)
- Single-server deployment (no distributed requirements)
- Use SQLite for persistence
- Python implementation

**Status:** debating

---

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture with Version-Based Lease Authority:**

```
┌─────────────────┐
│   Client Code   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskQueue API  │
│  (Public Facade)│
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────────┐
│ Queue Manager   │────▶│   SQLite DB      │
│ (Job Lifecycle) │     │ (WAL Mode)       │
└────────┬────────┘     └──────────────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │
│  (Thread-based) │
│  + Lease Auth   │
└─────────────────┘
```

## Data Models

### Database Schema (SQLite with WAL)

```sql
-- Enable WAL mode for concurrent reads/writes
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;

CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    payload BLOB NOT NULL,
    result BLOB,
    error_message TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at REAL,
    timeout_seconds REAL,
    
    -- Lease authority with monotonic version counter
    claimed_by TEXT,
    claimed_at REAL,
    lease_expires_at REAL,
    lease_token TEXT,
    lease_version INTEGER DEFAULT 0,  -- Source of truth for lease ownership
    last_heartbeat_at REAL,
    
    CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
);

-- Composite index for efficient job claiming
CREATE INDEX idx_claimable_jobs ON jobs(status, priority DESC, created_at ASC)
    WHERE status IN ('pending', 'failed');

-- Index for lease expiration checks
CREATE INDEX idx_lease_expiration ON jobs(lease_expires_at)
    WHERE status = 'running' AND lease_expires_at IS NOT NULL;

-- Index for retry scheduling
CREATE INDEX idx_retry_ready ON jobs(next_retry_at)
    WHERE status = 'failed' AND next_retry_at IS NOT NULL;

CREATE TABLE job_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    event_type TEXT NOT NULL,  -- 'created', 'claimed', 'completed', 'failed', 'heartbeat', 'recovered', 'version_mismatch', 'abandoned'
    message TEXT,
    worker_name TEXT,
    lease_version INTEGER,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

-- Weekly archive partitions (optimal for 7-90 day retention)
CREATE TABLE job_archive (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    completed_at REAL NOT NULL,
    archive_partition TEXT NOT NULL,  -- Format: YYYY-WW for weekly partitions
    result_summary TEXT,
    error_message TEXT,
    retry_count INTEGER,
    execution_duration_seconds REAL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Weekly partitions balance precision vs overhead
CREATE INDEX idx_archive_partition ON job_archive(archive_partition, completed_at);
CREATE INDEX idx_archive_task_performance ON job_archive(task_name, execution_duration_seconds);

CREATE TABLE dead_letter_queue (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    priority INTEGER NOT NULL,
    payload BLOB NOT NULL,
    error_message TEXT,
    failure_count INTEGER NOT NULL,
    first_failed_at REAL NOT NULL,
    last_failed_at REAL NOT NULL,
    moved_at REAL NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE TABLE cleanup_metadata (
    key TEXT PRIMARY KEY,
    last_cleanup_at REAL NOT NULL,
    records_cleaned INTEGER NOT NULL,
    cleanup_duration_seconds REAL,
    partition_cleaned TEXT
);

-- NEW: Throughput monitoring table
CREATE TABLE performance_metrics (
    metric_date TEXT PRIMARY KEY,  -- YYYY-MM-DD
    jobs_submitted INTEGER DEFAULT 0,
    jobs_completed INTEGER DEFAULT 0,
    jobs_failed INTEGER DEFAULT 0,
    avg_execution_time REAL,
    p95_execution_time REAL,
    max_queue_depth INTEGER DEFAULT 0,
    last_updated REAL NOT NULL
);
```

### Python Data Classes

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional, Dict
import time
import uuid

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Job:
    job_id: str
    task_name: str
    func: Callable
    args: tuple
    kwargs: dict
    priority: int = 0
    status: JobStatus = JobStatus.PENDING
    result: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[float] = None
    timeout_seconds: Optional[float] = None
    claimed_by: Optional[str] = None
    claimed_at: Optional[float] = None
    lease_expires_at: Optional[float] = None
    lease_token: Optional[str] = None
    lease_version: int = 0
    last_heartbeat_at: Optional[float] = None
    
    def __post_init__(self):
        if not (0 <= self.priority <= 10):
            raise ValueError("Priority must be between 0 and 10")

@dataclass
class JobResult:
    job_id: str
    status: JobStatus
    result: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: float = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    next_retry_at: Optional[float] = None
    
    @property
    def is_done(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)
    
    @property
    def is_terminal(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED) or \
               (self.status == JobStatus.FAILED and self.next_retry_at is None)
    
    @property
    def will_retry(self) -> bool:
        return self.status == JobStatus.FAILED and self.next_retry_at is not None

@dataclass
class LeaseContext:
    """
    Lease authority token with version-based ownership verification.
    
    The lease_version is the SOURCE OF TRUTH for ownership. SQLite's
    atomic UPDATE WHERE lease_version = ? ensures only one worker
    can successfully write results, even under network partitions.
    """
    job_id: str
    lease_token: str
    lease_version: int  # Monotonic counter, never reused
    worker_name: str
    claimed_at: float = field(default_factory=time.time)
    last_heartbeat_success: float = field(default_factory=time.time)
    consecutive_heartbeat_failures: int = 0
    is_valid: bool = True
    abandon_reason: Optional[str] = None
    
    def record_heartbeat_success(self):
        """Reset failure counter on successful heartbeat."""
        self.last_heartbeat_success = time.time()
        self.consecutive_heartbeat_failures = 0
    
    def record_heartbeat_failure(self, threshold: int) -> bool:
        """
        Increment failure counter and check if threshold exceeded.
        
        Returns True if lease should be abandoned.
        """
        self.consecutive_heartbeat_failures += 1
        return self.consecutive_heartbeat_failures >= threshold
    
    def abandon(self, reason: str):
        """Mark lease as abandoned (worker stops trying to write results)."""
        self.is_valid = False
        self.abandon_reason = reason
```

## Core Interfaces

### 1. TaskQueue API (Public Interface)

```python
import threading
import logging
from typing import Callable, Optional, Any, Dict

class TaskQueue:
    """Main interface for background job processing."""
    
    def __init__(self, 
                 db_path: str = "taskqueue.db",
                 num_workers: int = 4,
                 poll_interval: float = 0.5,
                 lease_duration: float = 300.0,
                 heartbeat_interval: float = 30.0,
                 heartbeat_failure_threshold: int = 3,
                 enable_recovery: bool = True,
                 retention_days: int = 7,
                 cleanup_interval_hours: int = 12,
                 cleanup_batch_size: int = 500,
                 max_write_retries: int = 3):
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            lease_duration: Seconds before a claimed job lease expires
            heartbeat_interval: Seconds between lease renewals (30s)
            heartbeat_failure_threshold: Consecutive heartbeat failures before abandoning (3 = ~90s tolerance)
            enable_recovery: Reset expired leases on startup
            retention_days: Days to retain completed/failed jobs (0=disable cleanup)
            cleanup_interval_hours: Hours between cleanup runs (12h = twice daily)
            cleanup_batch_size: Number of jobs to delete per transaction (500 = balance throughput vs blocking)
            max_write_retries: Times to retry on SQLITE_BUSY (3 = handle brief contention)
        """
        self.db = DatabaseManager(db_path, max_write_retries=max_write_retries)
        self.queue_manager = QueueManager(
            self.db, 
            lease_duration=lease_duration,
            heartbeat_interval=heartbeat_interval,
            heartbeat_failure_threshold=heartbeat_failure_threshold
        )
        self.worker_pool = WorkerPool(
            num_workers, 
            self.queue_manager, 
            poll_interval
        )
        
        if enable_recovery:
            recovered = self.queue_manager.recover_expired_leases()
            if recovered > 0:
                logging.warning(f"Recovered {recovered} jobs with expired leases on startup")
        
        self.worker_pool.start()
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        
        # Background cleanup thread
        if retention_days > 0:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                args=(retention_days, cleanup_interval_hours, cleanup_batch_size),
                daemon=True,
                name="TaskQueue-Cleanup"
            )
            self._cleanup_thread.start()
    
    def submit(self,
               func: Callable,
               *args,
               priority: int = 0,
               max_retries: int = 3,
               timeout_seconds: Optional[float] = None,
               task_name: Optional[str] = None,
               job_id: Optional[str] = None,
               **kwargs) -> str:
        """Submit a job to the queue."""
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError("Queue is shut down")
        
        if job_id is None:
            job_id = str(uuid.uuid4())
        
        if task_name is None:
            task_name = func.__name__
        
        job = Job(
            job_id=job_id,
            task_name=task_name,
            func=func,
            args=args,
            kwargs=kwargs,
            priority=priority,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds
        )
        
        return self.queue_manager.enqueue(job)
    
    def get_status(self, job_id: str) -> JobResult:
        """Get current job status and result."""
        return self.queue_manager.get_job_status(job_id)
    
    def get_result(self, job_id: str, timeout: Optional[float] = None) -> Any:
        """Block until job completes and return result."""
        start_time = time.time()
        poll_interval = 0.1
        
        while True:
            status = self.get_status(job_id)
            
            if status.status == JobStatus.COMPLETED:
                return status.result
            elif status.status == JobStatus.CANCELLED:
                raise JobCancelledError(f"Job {job_id} was cancelled")
            elif status.is_terminal and status.status == JobStatus.FAILED:
                raise JobFailedError(f"Job {job_id} failed: {status.error_message}")
            
            if timeout and (time.time() - start_time) >= timeout:
                raise TimeoutError(f"Job {job_id} did not complete within {timeout}s")
            
            time.sleep(poll_interval)
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/failed job (not running)."""
        return self.queue_manager.cancel_job(job_id)
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics by status."""
        return self.queue_manager.get_stats()
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """Stop accepting jobs and shut down workers."""
        with self._shutdown_lock:
            if self._shutdown:
                return
            self._shutdown = True
        
        self.worker_pool.shutdown(wait, timeout)
        self.db.close_all_connections()
    
    def _cleanup_loop(self, retention_days: int, cleanup_interval_hours: int, batch_size: int):
        """Background thread for cleaning old jobs."""
        cleanup_interval = cleanup_interval_hours * 3600
        
        while not self._shutdown:
            try:
                time.sleep(cleanup_interval)
                if not self._shutdown:
                    self.queue_manager.cleanup_old_jobs(retention_days, batch_size)
            except Exception as e:
                logging.error(f"Cleanup error: {e}", exc_info=True)
```

### 2. QueueManager (Internal)

```python
import pickle
import random
import time
from typing import Optional
from datetime import datetime

class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: 'DatabaseManager', 
                 lease_duration: float = 300.0,
                 heartbeat_interval: float = 30.0,
                 heartbeat_failure_threshold: int = 3):
        self.db = db
        self.lease_duration = lease_duration
        self.heartbeat_interval = heartbeat_interval
        self.heartbeat_failure_threshold = heartbeat_failure_threshold
    
    def enqueue(self, job: Job) -> str:
        """Persist job to database."""
        try:
            self.db.insert_job(job)
            return job.job_id
        except Exception as e:
            raise ValueError(f"Failed to enqueue job: {e}")
    
    def get_next_job(self, worker_name: str) -> Optional[Job]:
        """
        Claim next available job using atomic version-increment mechanism.
        
        CRITICAL CORRECTNESS PROPERTY:
        The lease_version increment happens inside a BEGIN IMMEDIATE transaction,
        ensuring that:
        1. Only ONE worker can hold version N at any time
        2. Once version increments to N+1, version N is permanently invalidated
        3. Any writes using version N will fail atomically (WHERE clause mismatch)
        
        This provides TOTAL ORDERING of lease generations.
        """
        lease_token = str(uuid.uuid4())
        now = time.time()
        lease_expires_at = now + self.lease_duration
        
        with self.db.get_connection(timeout=2.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Find claimable job (prioritize: pending > expired leases > failed ready for retry)
                cursor = conn.execute("""
                    SELECT job_id, task_name, priority, status, payload,
                           retry_count, max_retries, timeout_seconds,
                           created_at, error_message, next_retry_at,
                           lease_expires_at, lease_version
                    FROM jobs
                    WHERE (
                        (status = 'pending')
                        OR (status = 'failed' AND next_retry_at IS NOT NULL AND next_retry_at <= ?)
                        OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                    )
                    ORDER BY 
                        CASE 
                            WHEN status = 'pending' THEN 0
                            WHEN status = 'running' THEN 1
                            ELSE 2
                        END,
                        priority DESC,
                        created_at ASC
                    LIMIT 1
                """, (now, now))
                
                row = cursor.fetchone()
                if not row:
                    conn.execute("ROLLBACK")
                    return None
                
                job_id = row['job_id']
                old_status = row['status']
                old_version = row['lease_version'] or 0
                new_version = old_version + 1  # CRITICAL: Increment creates new lease generation
                
                # Atomic claim with version increment (source of truth for ownership)
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'running',
                        started_at = ?,
                        claimed_by = ?,
                        claimed_at = ?,
                        lease_expires_at = ?,
                        lease_token = ?,
                        lease_version = ?,
                        last_heartbeat_at = ?
                    WHERE job_id = ?
                      AND (
                          status = 'pending'
                          OR (status = 'failed' AND next_retry_at <= ?)
                          OR (status = 'running' AND lease_expires_at < ?)
                      )
                """, (now, worker_name, now, lease_expires_at, 
                      lease_token, new_version, now, job_id, now, now))
                
                if cursor.rowcount == 0:
                    conn.execute("ROLLBACK")
                    return None
                
                # Fetch full updated job state
                cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                job_row = cursor.fetchone()
                
                event_type = 'recovered' if old_status == 'running' else 'claimed'
                self.db._add_history(
                    conn, job_id, old_status, JobStatus.RUNNING,
                    event_type,
                    f"{'Recovered' if old_status == 'running' else 'Claimed'} by {worker_name} (v{old_version}→v{new_version})",
                    worker_name,
                    new_version
                )
                
                conn.execute("COMMIT")
                
                # Reconstruct Job object
                func, args, kwargs = pickle.loads(job_row['payload'])
                return Job(
                    job_id=job_row['job_id'],
                    task_name=job_row['task_name'],
                    func=func,
                    args=args,
                    kwargs=kwargs,
                    priority=job_row['priority'],
                    status=JobStatus.RUNNING,
                    retry_count=job_row['retry_count'],
                    max_retries=job_row['max_retries'],
                    timeout_seconds=job_row['timeout_seconds'],
                    created_at=job_row['created_at'],
                    started_at=job_row['started_at'],
                    claimed_by=job_row['claimed_by'],
                    claimed_at=job_row['claimed_at'],
                    lease_token=job_row['lease_token'],
                    lease_version=job_row['lease_version'],
                    lease_expires_at=job_row['lease_expires_at'],
                    last_heartbeat_at=job_row['last_heartbeat_at']
                )
                
            except sqlite3.OperationalError as e:
                conn.execute("ROLLBACK")
                return None
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Error claiming job: {e}", exc_info=True)
                return None
    
    def extend_lease(self, lease_ctx: LeaseContext) -> bool:
        """
        Extend lease for long-running jobs with version verification.
        
        CORRECTNESS: Checks lease_version to ensure heartbeat is from
        current lease holder. Stale workers fail silently here.
        """
        with self.db.get_connection(timeout=5.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                new_expiration = now + self.lease_duration
                
                # Verify version AND token together (defense in depth)
                cursor = conn.execute("""
                    UPDATE jobs
                    SET lease_expires_at = ?,
                        last_heartbeat_at = ?
                    WHERE job_id = ?
                      AND lease_token = ?
                      AND lease_version = ?
                      AND status = 'running'
                """, (new_expiration, now, lease_ctx.job_id, 
                      lease_ctx.lease_token, lease_ctx.lease_version))
                
                if cursor.rowcount == 0:
                    conn.execute("ROLLBACK")
                    return False
                
                self.db._add_history(
                    conn, lease_ctx.job_id, 'running', JobStatus.RUNNING,
                    'heartbeat',
                    f"Lease extended by {lease_ctx.worker_name} (v{lease_ctx.lease_version})",
                    lease_ctx.worker_name,
                    lease_ctx.lease_version
                )
                
                conn.execute("COMMIT")
                return True
                
            except sqlite3.OperationalError as e:
                conn.execute("ROLLBACK")
                logging.warning(f"Heartbeat failed for job {lease_ctx.job_id}: database locked")
                return False
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Heartbeat error for job {lease_ctx.job_id}: {e}", exc_info=True)
                return False
    
    def mark_completed(self, job_id: str, result: Any, 
                       lease_ctx: LeaseContext) -> bool:
        """
        Mark job as completed with lease version validation.
        
        CRITICAL RACE CONDITION PREVENTION:
        
        Scenario: Network partition causes Worker A to lose heartbeat
        1. Worker A (v5): Executing job, network partition occurs
        2. Worker A (v5): Heartbeat failures accumulate, lease expires
        3. Worker B claims job → version increments to v6
        4. Worker B (v6): Completes job, writes result with v6
        5. Worker A (v5): Network recovers, attempts to write result
        
        Step 5 trace:
        - Worker A calls mark_completed with lease_ctx.lease_version = 5
        - UPDATE jobs SET ... WHERE lease_version = 5
        - SQLite evaluates WHERE clause:
          - Current DB state: lease_version = 6 (Worker B updated it)
          - WHERE 6 = 5 → FALSE
          - cursor.rowcount = 0 (no rows matched)
        - Worker A's write is REJECTED atomically
        
        KEY INSIGHT: The version check happens INSIDE the atomic UPDATE,
        not as a separate SELECT. This eliminates TOCTOU race conditions.
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                
                # Version check is the AUTHORITATIVE protection
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = ?,
                        result = ?,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE job_id = ?
                      AND lease_token = ?
                      AND lease_version = ?
                      AND status = 'running'
                """, (now, pickle.dumps(result), job_id, 
                      lease_ctx.lease_token, lease_ctx.lease_version))
                
                if cursor.rowcount == 0:
                    # Diagnostic: Determine why write was rejected
                    cursor = conn.execute("""
                        SELECT status, lease_version, lease_token 
                        FROM jobs 
                        WHERE job_id = ?
                    """, (job_id,))
                    row = cursor.fetchone()
                    
                    if row:
                        if row['lease_version'] != lease_ctx.lease_version:
                            logging.warning(
                                f"Worker {lease_ctx.worker_name} lost lease for job {job_id}: "
                                f"version mismatch (had v{lease_ctx.lease_version}, "
                                f"DB now has v{row['lease_version']})"
                            )
                            self.db._add_history(
                                conn, job_id, row['status'], JobStatus(row['status']),
                                'version_mismatch',
                                f"Stale worker v{lease_ctx.lease_version} rejected, current v{row['lease_version']}",
                                lease_ctx.worker_name,
                                lease_ctx.lease_version
                            )
                        elif row['status'] != 'running':
                            logging.warning(
                                f"Worker {lease_ctx.worker_name} attempted to complete "
                                f"job {job_id} but status is {row['status']}"
                            )
                    
                    conn.execute("ROLLBACK")
                    return False
                
                # Calculate execution duration for monitoring
                cursor = conn.execute("""
                    SELECT started_at FROM jobs WHERE job_id = ?
                """, (job_id,))
                row = cursor.fetchone()
                duration = now - row['started_at'] if row else None
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.COMPLETED,
                    'completed',
                    f"Completed by {lease_ctx.worker_name} in {duration:.2f}s (v{lease_ctx.lease_version})" if duration else f"Completed by {lease_ctx.worker_name}",
                    lease_ctx.worker_name,
                    lease_ctx.lease_version
                )
                
                conn.execute("COMMIT")
                return True
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Failed to mark job {job_id} completed: {e}", exc_info=True)
                return False
    
    def mark_failed(self, job_id: str, error: Exception, 
                    lease_ctx: LeaseContext) -> bool:
        """
        Mark job as failed with retry logic and version validation.
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Verify lease ownership with version
                cursor = conn.execute("""
                    SELECT lease_token, lease_version, retry_count, max_retries, status 
                    FROM jobs WHERE job_id = ?
                """, (job_id,))
                row = cursor.fetchone()
                
                if not row:
                    conn.execute("ROLLBACK")
                    return False
                
                # Check version match
                if (row['lease_token'] != lease_ctx.lease_token or 
                    row['lease_version'] != lease_ctx.lease_version):
                    logging.warning(
                        f"Worker {lease_ctx.worker_name} lost lease for job {job_id} "
                        f"before recording failure (v{lease_ctx.lease_version} != v{row['lease_version']})"
                    )
                    conn.execute("ROLLBACK")
                    return False
                
                retry_count = row['retry_count']
                max_retries = row['max_retries']
                
                should_retry_job = (
                    retry_count < max_retries and 
                    self._should_retry_error(error)
                )
                
                if should_retry_job:
                    next_retry = time.time() + self._calculate_backoff(retry_count)
                    
                    conn.execute("""
                        UPDATE jobs
                        SET status = 'failed',
                            retry_count = retry_count + 1,
                            error_message = ?,
                            next_retry_at = ?,
                            lease_expires_at = NULL,
                            lease_token = NULL
                        WHERE job_id = ?
                    """, (str(error), next_retry, job_id))
                    
                    message = f"Failed, will retry at {next_retry} (attempt {retry_count + 1}/{max_retries})"
                else:
                    conn.execute("""
                        UPDATE jobs
                        SET status = 'failed',
                            retry_count = retry_count + 1,
                            error_message = ?,
                            completed_at = ?,
                            next_retry_at = NULL,
                            lease_expires_at = NULL,
                            lease_token = NULL
                        WHERE job_id = ?
                    """, (str(error), time.time(), job_id))
                    
                    self._move_to_dlq(conn, job_id, retry_count + 1)
                    message = f"Failed permanently after {retry_count + 1} attempts"
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.FAILED,
                    'failed',
                    message, lease_ctx.worker_name,
                    lease_ctx.lease_version
                )
                
                conn.execute("COMMIT")
                return True
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Failed to mark job {job_id} failed: {e}", exc_info=True)
                return False
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if not running."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                cursor = conn.execute("SELECT status FROM jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                
                if not row:
                    conn.execute("ROLLBACK")
                    return False
                
                if row['status'] in ('running', 'completed', 'cancelled'):
                    conn.execute("ROLLBACK")
                    return False
                
                conn.execute("""
                    UPDATE jobs
                    SET status = 'cancelled',
                        completed_at = ?,
                        lease_expires_at = NULL,
                        lease_token = NULL,
                        next_retry_at = NULL
                    WHERE job_id = ?
                """, (time.time(), job_id))
                
                self.db._add_history(
                    conn, job_id, row['status'], JobStatus.CANCELLED,
                    'cancelled',
                    "Cancelled by user", None, None
                )
                
                conn.execute("COMMIT")
                return True
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def get_job_status(self, job_id: str) -> JobResult:
        """Retrieve job status."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT job_id, status, result, error_message, 
                       created_at, completed_at, retry_count, next_retry_at
                FROM jobs
                WHERE job_id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                raise JobNotFoundError(f"Job {job_id} not found")
            
            result = pickle.loads(row['result']) if row['result'] else None
            
            return JobResult(
                job_id=row['job_id'],
                status=JobStatus(row['status']),
                result=result,
                error_message=row['error_message'],
                created_at=row['created_at'],
                completed_at=row['completed_at'],
                retry_count=row['retry_count'],
                next_retry_at=row['next_retry_at']
            )
    
    def get_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT status, COUNT(*) as count
                FROM jobs
                GROUP BY status
            """)
            
            stats = {status.value: 0 for status in JobStatus}
            for row in cursor:
                stats[row['status']] = row['count']
            
            return stats
    
    def recover_expired_leases(self) -> int:
        """Reset jobs with expired leases to pending."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                
                # Get job IDs before reset for history tracking
                cursor = conn.execute("""
                    SELECT job_id, lease_version 
                    FROM jobs 
                    WHERE status = 'running' 
                      AND lease_expires_at < ?
                """, (now,))
                
                expired_jobs = cursor.fetchall()
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'pending',
                        claimed_by = NULL,
                        claimed_at = NULL,
                        lease_expires_at = NULL,
                        lease_token = NULL,
                        last_heartbeat_at = NULL
                    WHERE status = 'running' 
                      AND lease_expires_at < ?
                """, (now,))
                
                count = cursor.rowcount
                
                # Record history for each recovered job
                for row in expired_jobs:
                    self.db._add_history(
                        conn, row['job_id'], 'running', JobStatus.PENDING,
                        'recovered',
                        f"Recovered from expired lease on startup (was v{row['lease_version']})",
                        None,
                        row['lease_version']
                    )
                
                conn.execute("COMMIT")
                return count
                
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def cleanup_old_jobs(self, retention_days: int, batch_size: int):
        """
        Archive and delete old jobs with weekly partition granularity.
        
        IMPROVEMENT: Weekly partitions (vs daily/monthly) provide:
        - Sufficient precision for 7-90 day retention policies
        - Lower partition overhead than daily
        - Cleaner deletion (whole weeks at a time)
        """
        cutoff_time = time.time() - (retention_days * 86400)
        start_time = time.time()
        total_archived = 0
        total_deleted = 0
        
        # Determine partition to clean (YYYY-WW format for ISO week)
        cutoff_date = datetime.fromtimestamp(cutoff_time)
        cutoff_partition = f"{cutoff_date.year}-{cutoff_date.isocalendar()[1]:02d}"
        
        # Phase 1: Archive terminal jobs in batches
        while True:
            with self.db.get_connection() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    
                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO job_archive 
                        (job_id, task_name, status, created_at, completed_at, 
                         archive_partition, result_summary, error_message, retry_count,
                         execution_duration_seconds)
                        SELECT 
                            job_id, 
                            task_name, 
                            status, 
                            created_at, 
                            completed_at,
                            strftime('%Y-', completed_at, 'unixepoch') || 
                            CAST(strftime('%W', completed_at, 'unixepoch') AS INTEGER),
                            substr(CAST(result AS TEXT), 1, 200),
                            error_message,
                            retry_count,
                            completed_at - started_at
                        FROM jobs
                        WHERE completed_at IS NOT NULL
                          AND completed_at < ?
                          AND status IN ('completed', 'cancelled', 'failed')
                          AND job_id NOT IN (SELECT job_id FROM job_archive)
                        LIMIT ?
                    """, (cutoff_time, batch_size))
                    
                    archived = cursor.rowcount
                    total_archived += archived
                    
                    conn.execute("COMMIT")
                    
                    if archived == 0:
                        break
                    
                    time.sleep(0.05)  # Brief yield to other operations
                    
                except Exception as e:
                    conn.execute("ROLLBACK")
                    logging.error(f"Archival batch failed: {e}", exc_info=True)
                    break
        
        # Phase 2: Delete archived jobs in batches
        while True:
            with self.db.get_connection() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    
                    cursor = conn.execute("""
                        DELETE FROM jobs
                        WHERE job_id IN (
                            SELECT job_id FROM job_archive
                            WHERE archive_partition <= ?
                            LIMIT ?
                        )
                    """, (cutoff_partition, batch_size))
                    
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    
                    conn.execute("COMMIT")
                    
                    if deleted == 0:
                        break
                    
                    time.sleep(0.05)
                    
                except Exception as e:
                    conn.execute("ROLLBACK")
                    logging.error(f"Batch deletion failed: {e}", exc_info=True)
                    break
        
        # Phase 3: Cleanup history (keep last 100k entries)
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                cursor = conn.execute("""
                    DELETE FROM job_history
                    WHERE id NOT IN (
                        SELECT id FROM job_history
                        ORDER BY timestamp DESC
                        LIMIT 100000
                    )
                """)
                
                history_deleted = cursor.rowcount
                
                conn.execute("COMMIT")
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"History cleanup failed: {e}", exc_info=True)
                history_deleted = 0
        
        # Record metrics
        duration = time.time() - start_time
        
        with self.db.get_connection() as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO cleanup_metadata 
                    (key, last_cleanup_at, records_cleaned, cleanup_duration_seconds, partition_cleaned)
                    VALUES ('last_cleanup', ?, ?, ?, ?)
                """, (time.time(), total_deleted + history_deleted, duration, cutoff_partition))
                conn.commit()
            except Exception:
                pass
        
        if total_deleted > 0 or history_deleted > 0:
            logging.info(
                f"Cleanup: archived {total_archived}, deleted {total_deleted} jobs, "
                f"{history_deleted} history entries in {duration:.2f}s (partition: {cutoff_partition})"
            )
        
        # Alert if cleanup is taking too long (sign of contention or undersized batch)
        if duration > 180.0:  # 3 minutes
            logging.warning(
                f"Cleanup took {duration:.2f}s - consider increasing cleanup_interval_hours "
                f"or reducing retention_days"
            )
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        if isinstance(error, PermanentError):
            return False
        
        if isinstance(error, RetryableError):
            return True
        
        non_retryable = (
            TypeError, ValueError, AttributeError,
            KeyError, ImportError, SyntaxError, AssertionError
        )
        if isinstance(error, non_retryable):
            return False
        
        retryable = (ConnectionError, TimeoutError, IOError, OSError)
        if isinstance(error, retryable):
            return True
        
        return True
    
    def _calculate_backoff(self, retry_count: int) -> float:
        """Calculate exponential backoff with jitter."""
        base_delay = 1.0
        max_delay = 300.0
        
        delay = base_delay * (2 ** retry_count)
        jitter = random.uniform(0, delay * 0.1)
        
        return min(delay + jitter, max_delay)
    
    def _move_to_dlq(self, conn, job_id: str, failure_count: int):
        """Move permanently failed job to dead letter queue."""
        cursor = conn.execute("""
            SELECT task_name, priority, payload, error_message, created_at
            FROM jobs
            WHERE job_id = ?
        """, (job_id,))
        
        row = cursor.fetchone()
        if not row:
            return
        
        conn.execute("""
            INSERT OR REPLACE INTO dead_letter_queue
            (job_id, task_name, priority, payload, error_message,
             failure_count, first_failed_at, last_failed_at, moved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, row['task_name'], row['priority'], row['payload'],
            row['error_message'], failure_count,
            row['created_at'], time.time(), time.time()
        ))
```

### 3. WorkerPool (Internal)

```python
import threading
import logging
from typing import List, Dict

class WorkerPool:
    """Manages worker threads with lease-context execution."""
    
    def __init__(self, 
                 num_workers: int,
                 queue_manager: QueueManager,
                 poll_interval: float):
        self.num_workers = num_workers
        self.queue_manager = queue_manager
        self.poll_interval = poll_interval
        self.workers: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
        self._active_jobs: Dict[str, Dict] = {}
        self._active_jobs_lock = threading.Lock()
    
    def start(self):
        """Start all worker threads."""
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"TaskQueue-Worker-{i}",
                daemon=False
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        """Main worker loop with lease context management."""
        worker_name = threading.current_thread().name
        
        while not self._shutdown_event.is_set():
            try:
                job = self.queue_manager.get_next_job(worker_name)
                
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                
                # Create lease context with version
                lease_ctx = LeaseContext(
                    job_id=job.job_id,
                    lease_token=job.lease_token,
                    lease_version=job.lease_version,
                    worker_name=worker_name
                )
                
                # Track active job
                with self._active_jobs_lock:
                    self._active_jobs[job.job_id] = {
                        'job': job,
                        'lease_ctx': lease_ctx,
                        'thread': threading.current_thread(),
                        'started_at': time.time()
                    }
                
                try:
                    # Start heartbeat thread
                    heartbeat_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(job, lease_ctx),
                        daemon=True
                    )
                    heartbeat_thread.start()
                    
                    self._execute_job(job, lease_ctx)
                    
                finally:
                    with self._active_jobs_lock:
                        self._active_jobs.pop(job.job_id, None)
                        
            except Exception as e:
                logging.error(f"{worker_name} error: {e}", exc_info=True)
                time.sleep(self.poll_interval)
    
    def _heartbeat_loop(self, job: Job, lease_ctx: LeaseContext):
        """
        Periodically extend lease with failure tracking.
        
        DESIGN RATIONALE:
        - 30s interval: Responsive to issues without excessive DB load
        - Threshold=3: Tolerates ~90s of transient database locks
        - Abandons lease locally (doesn't kill thread): Simpler than cooperative cancellation
        """
        heartbeat_interval = self.queue_manager.heartbeat_interval
        failure_threshold = self.queue_manager.heartbeat_failure_threshold
        
        while job.job_id in self._active_jobs and lease_ctx.is_valid:
            time.sleep(heartbeat_interval)
            
            if job.job_id not in self._active_jobs:
                break
            
            success = self.queue_manager.extend_lease(lease_ctx)
            
            if success:
                lease_ctx.record_heartbeat_success()
            else:
                should_abandon = lease_ctx.record_heartbeat_failure(failure_threshold)
                
                logging.warning(
                    f"Heartbeat failed for job {job.job_id} "
                    f"({lease_ctx.consecutive_heartbeat_failures}/{failure_threshold})"
                )
                
                if should_abandon:
                    lease_ctx.abandon("persistent_heartbeat_failure")
                    logging.error(
                        f"Abandoning lease for job {job.job_id} after "
                        f"{lease_ctx.consecutive_heartbeat_failures} heartbeat failures "
                        f"(~{heartbeat_interval * failure_threshold:.0f}s of issues)"
                    )
                    break
    
    def _execute_job(self, job: Job, lease_ctx: LeaseContext):
        """
        Execute job with lease context awareness.
        
        SIMPLIFICATION: No cooperative cancellation required.
        The version check in mark_completed() is the ONLY necessary guard.
        Thread continues executing even after abandon, but results are discarded.
        """
        try:
            # Execute with optional timeout
            if job.timeout_seconds:
                result = self._execute_with_timeout(
                    job.func, job.args, job.kwargs, job.timeout_seconds,
                    lease_ctx
                )
            else:
                result = job.func(*job.args, **job.kwargs)
            
            # Check if we abandoned the lease during execution
            if not lease_ctx.is_valid:
                logging.warning(
                    f"Job {job.job_id} completed but lease was abandoned "
                    f"({lease_ctx.abandon_reason}), discarding result"
                )
                return
            
            # Attempt to mark completed (version check is the authoritative guard)
            success = self.queue_manager.mark_completed(
                job.job_id, result, lease_ctx
            )
            
            if not success:
                logging.warning(
                    f"Job {job.job_id} completed but failed to record result "
                    "(lease version mismatch - another worker claimed this job)"
                )
            
        except TimeoutError as e:
            if lease_ctx.is_valid:
                self.queue_manager.mark_failed(
                    job.job_id,
                    PermanentError(f"Timeout after {job.timeout_seconds}s"),
                    lease_ctx
                )
        except PermanentError as e:
            if lease_ctx.is_valid:
                self.queue_manager.mark_failed(job.job_id, e, lease_ctx)
        except Exception as e:
            if lease_ctx.is_valid:
                self.queue_manager.mark_failed(job.job_id, e, lease_ctx)
    
    def _execute_with_timeout(self, func: Callable, args: tuple,
                             kwargs: dict, timeout: float,
                             lease_ctx: LeaseContext) -> Any:
        """Execute function with timeout (daemon thread approach)."""
        result_container = []
        exception_container = []
        
        def target():
            try:
                result = func(*args, **kwargs)
                result_container.append(result)
            except Exception as e:
                exception_container.append(e)
        
        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)
        
        if thread.is_alive():
            lease_ctx.abandon("timeout")
            raise TimeoutError(f"Job exceeded timeout of {timeout}s")
        
        if exception_container:
            raise exception_container[0]
        
        return result_container[0] if result_container else None
    
    def shutdown(self, wait: bool, timeout: float):
        """Shutdown worker pool gracefully."""
        self._shutdown_event.set()
        
        if not wait:
            return
        
        start_time = time.time()
        for worker in self.workers:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                logging.warning("Worker shutdown timeout exceeded")
                break
            worker.join(timeout=remaining)
        
        still_running = [w for w in self.workers if w.is_alive()]
        if still_running:
            logging.warning(f"{len(still_running)} workers did not shutdown gracefully")
```

### 4. DatabaseManager (Internal)

```python
import sqlite3
import threading
import pickle
import logging
from contextlib import contextmanager
from typing import Optional

class DatabaseManager:
    """Thread-safe SQLite operations with configurable timeouts and retry logic."""
    
    def __init__(self, db_path: str, max_write_retries: int = 3):
        self.db_path = db_path
        self.max_write_retries = max_write_retries
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_db()
    
    def _get_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """Get thread-local connection with specified timeout."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection(timeout)
        else:
            self._local.conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        
        return self._local.conn
    
    def _create_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """Create new connection with proper SQLite settings."""
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,
            check_same_thread=False,
            timeout=timeout
        )
        conn.row_factory = sqlite3.Row
        
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        return conn
    
    @contextmanager
    def get_connection(self, timeout: float = 5.0):
        """
        Context manager for connection access with configurable timeout.
        
        IMPROVEMENT: Automatically retries on SQLITE_BUSY for write operations.
        """
        conn = self._get_connection(timeout)
        retries = 0
        last_error = None
        
        while retries <= self.max_write_retries:
            try:
                yield conn
                return
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e) and retries < self.max_write_retries:
                    retries += 1
                    last_error = e
                    time.sleep(0.1 * retries)  # Exponential backoff
                    continue
                else:
                    raise
        
        if last_error:
            raise last_error
    
    def _init_db(self):
        """Initialize database schema (idempotent)."""
        with self._init_lock:
            conn = self._create_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Create jobs table with version column
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        priority INTEGER NOT NULL DEFAULT 0,
                        status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
                        payload BLOB NOT NULL,
                        result BLOB,
                        error_message TEXT,
                        created_at REAL NOT NULL,
                        started_at REAL,
                        completed_at REAL,
                        retry_count INTEGER DEFAULT 0,
                        max_retries INTEGER DEFAULT 3,
                        next_retry_at REAL,
                        timeout_seconds REAL,
                        claimed_by TEXT,
                        claimed_at REAL,
                        lease_expires_at REAL,
                        lease_token TEXT,
                        lease_version INTEGER DEFAULT 0,
                        last_heartbeat_at REAL,
                        CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_claimable_jobs 
                    ON jobs(status, priority DESC, created_at ASC)
                    WHERE status IN ('pending', 'failed')
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_lease_expiration
                    ON jobs(lease_expires_at)
                    WHERE status = 'running' AND lease_expires_at IS NOT NULL
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_ready
                    ON jobs(next_retry_at)
                    WHERE status = 'failed' AND next_retry_at IS NOT NULL
                """)
                
                # Create history table with version tracking
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS job_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        old_status TEXT,
                        new_status TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        message TEXT,
                        worker_name TEXT,
                        lease_version INTEGER,
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_history_lookup
                    ON job_history(job_id, timestamp DESC)
                """)
                
                # Archive table with weekly partitions
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS job_archive (
                        job_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        completed_at REAL NOT NULL,
                        archive_partition TEXT NOT NULL,
                        result_summary TEXT,
                        error_message TEXT,
                        retry_count INTEGER,
                        execution_duration_seconds REAL,
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archive_partition
                    ON job_archive(archive_partition, completed_at)
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archive_task_performance
                    ON job_archive(task_name, execution_duration_seconds)
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS dead_letter_queue (
                        job_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        priority INTEGER NOT NULL,
                        payload BLOB NOT NULL,
                        error_message TEXT,
                        failure_count INTEGER NOT NULL,
                        first_failed_at REAL NOT NULL,
                        last_failed_at REAL NOT NULL,
                        moved_at REAL NOT NULL,
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_metadata (
                        key TEXT PRIMARY KEY,
                        last_cleanup_at REAL NOT NULL,
                        records_cleaned INTEGER NOT NULL,
                        cleanup_duration_seconds REAL,
                        partition_cleaned TEXT
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS performance_metrics (
                        metric_date TEXT PRIMARY KEY,
                        jobs_submitted INTEGER DEFAULT 0,
                        jobs_completed INTEGER DEFAULT 0,
                        jobs_failed INTEGER DEFAULT 0,
                        avg_execution_time REAL,
                        p95_execution_time REAL,
                        max_queue_depth INTEGER DEFAULT 0,
                        last_updated REAL NOT NULL
                    )
                """)
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
    
    def insert_job(self, job: Job):
        """Insert new job into database."""
        with self.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                conn.execute("""
                    INSERT INTO jobs (
                        job_id, task_name, priority, status, payload,
                        created_at, max_retries, timeout_seconds
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.job_id, job.task_name, job.priority,
                    job.status.value,
                    pickle.dumps((job.func, job.args, job.kwargs)),
                    job.created_at, job.max_retries, job.timeout_seconds
                ))
                
                self._add_history(
                    conn, job.job_id, None, JobStatus.PENDING,
                    'created', "Job created", None, None
                )
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def _add_history(self, conn: sqlite3.Connection, job_id: str,
                     old_status: Optional[str], new_status: JobStatus,
                     event_type: str, message: str, worker_name: Optional[str],
                     lease_version: Optional[int]):
        """Add job history entry with version tracking."""
        conn.execute("""
            INSERT INTO job_history
            (job_id, timestamp, old_status, new_status, event_type, message, worker_name, lease_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, time.time(),
            old_status.value if isinstance(old_status, JobStatus) else old_status,
            new_status.value, event_type, message, worker_name, lease_version
        ))
    
    def close_all_connections(self):
        """Close thread-local connections."""
        pass
```

## Exception Classes

```python
class JobError(Exception):
    """Base exception for job errors."""
    pass

class RetryableError(JobError):
    """Error that should trigger retry."""
    pass

class PermanentError(JobError):
    """Error that should not be retried."""
    pass

class JobNotFoundError(JobError):
    """Job ID does not exist."""
    pass

class JobFailedError(JobError):
    """Job failed after all retries."""
    pass

class JobCancelledError(JobError):
    """Job was cancelled."""
    pass
```

## Usage Examples

```python
# Initialize with version-based lease protection
queue = TaskQueue(
    db_path="jobs.db",
    num_workers=4,
    poll_interval=0.5,
    lease_duration=300.0,
    heartbeat_interval=30.0,
    heartbeat_failure_threshold=3,
    retention_days=7,
    cleanup_interval_hours=12,  # Twice daily
    cleanup_batch_size=500,  # Smaller batches = less blocking
    max_write_retries=3  # Handle brief database contention
)

# Submit long-running job
def process_large_dataset(dataset_id: str):
    for chunk in load_dataset(dataset_id):
        process_chunk(chunk)
    return "processed"

job_id = queue.submit(
    process_large_dataset,
    "dataset-123",
    priority=5,
    max_retries=3,
    timeout_seconds=3600.0
)

# Shutdown gracefully
queue.shutdown(wait=True, timeout=30.0)
```

---