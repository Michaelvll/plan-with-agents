# Claude Code Debate Session

**Started:** 2026-01-17T19:40:03.257414
**Ended:** 2026-01-17T20:10:23.270303
**Status:** debating
**Rounds:** 4

## Initial Prompt

Design a simple task queue system for background job processing

Requirements:
- Support job submission with priority levels
- Handle retries on failure with exponential backoff
- Provide job status tracking (pending, running, completed, failed)
- Single-server deployment (no distributed requirements)
- Use SQLite for persistence
- Python implementation

---

## Round 1

### 🔵 Agent A

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture:**
1. **API Layer**: Job submission and status query interface
2. **Queue Manager**: Job scheduling, priority management, and state transitions
3. **Worker Pool**: Job execution with retry logic and error handling

**Core Components:**

```
┌─────────────────┐
│   Client Code   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskQueue API  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ Queue Manager   │────▶│   SQLite DB  │
└────────┬────────┘     └──────────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │
│  (Threads)      │
└─────────────────┘
```

## Data Models

### Database Schema (SQLite)

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,  -- Higher = more urgent (0-10)
    status TEXT NOT NULL,  -- pending, running, completed, failed
    payload BLOB NOT NULL,  -- Pickled function args/kwargs
    result BLOB,  -- Pickled result
    error_message TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at REAL,  -- NULL if not scheduled for retry
    INDEX idx_status_priority (status, priority DESC, created_at),
    INDEX idx_next_retry (next_retry_at)
);

CREATE TABLE job_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    message TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
```

### Python Data Classes

```python
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Optional
import time

class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

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
    created_at: float = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    next_retry_at: Optional[float] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()

@dataclass
class JobResult:
    job_id: str
    status: JobStatus
    result: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: float = None
    completed_at: Optional[float] = None
    retry_count: int = 0
```

## Core Interfaces

### 1. TaskQueue API (Public Interface)

```python
class TaskQueue:
    """Main interface for job submission and monitoring."""
    
    def __init__(self, 
                 db_path: str = "taskqueue.db",
                 num_workers: int = 4,
                 poll_interval: float = 0.5):
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
        """
        self.db = DatabaseManager(db_path)
        self.queue_manager = QueueManager(self.db)
        self.worker_pool = WorkerPool(
            num_workers, self.queue_manager, poll_interval
        )
        self.worker_pool.start()
    
    def submit(self,
               func: Callable,
               *args,
               priority: int = 0,
               max_retries: int = 3,
               task_name: Optional[str] = None,
               **kwargs) -> str:
        """
        Submit a job to the queue.
        
        Args:
            func: Callable to execute
            *args: Positional arguments
            priority: 0-10, higher = more urgent
            max_retries: Maximum retry attempts
            task_name: Human-readable task identifier
            **kwargs: Keyword arguments
            
        Returns:
            job_id: Unique job identifier
        """
        pass
    
    def get_status(self, job_id: str) -> JobResult:
        """Get current status and result of a job."""
        pass
    
    def get_result(self, job_id: str, timeout: Optional[float] = None) -> Any:
        """
        Block until job completes and return result.
        
        Args:
            job_id: Job identifier
            timeout: Max seconds to wait (None = infinite)
            
        Returns:
            Job result
            
        Raises:
            TimeoutError: If timeout exceeded
            JobFailedError: If job failed after retries
        """
        pass
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a pending job. Returns False if already running."""
        pass
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """Stop accepting jobs and shut down workers."""
        pass
```

### 2. QueueManager (Internal)

```python
class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
        self._lock = threading.RLock()
    
    def enqueue(self, job: Job) -> str:
        """Persist job to database and return job_id."""
        pass
    
    def get_next_job(self) -> Optional[Job]:
        """
        Fetch highest priority pending job or retry-eligible failed job.
        Uses row-level locking to prevent concurrent workers from
        claiming the same job.
        
        Priority order:
        1. Pending jobs (ordered by priority DESC, created_at ASC)
        2. Failed jobs ready for retry (next_retry_at <= now)
        """
        pass
    
    def mark_running(self, job_id: str):
        """Update job status to RUNNING."""
        pass
    
    def mark_completed(self, job_id: str, result: Any):
        """Update job status to COMPLETED with result."""
        pass
    
    def mark_failed(self, job_id: str, error: Exception):
        """
        Update job status to FAILED.
        If retries remain, schedule retry with exponential backoff.
        """
        pass
    
    def get_job_status(self, job_id: str) -> JobResult:
        """Retrieve job status and results."""
        pass
```

### 3. WorkerPool (Internal)

```python
class WorkerPool:
    """Manages worker threads for job execution."""
    
    def __init__(self, 
                 num_workers: int,
                 queue_manager: QueueManager,
                 poll_interval: float):
        self.num_workers = num_workers
        self.queue_manager = queue_manager
        self.poll_interval = poll_interval
        self.workers: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
    
    def start(self):
        """Start all worker threads."""
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        """
        Main worker loop:
        1. Poll for next job
        2. Execute job
        3. Handle success/failure
        4. Repeat
        """
        while not self._shutdown_event.is_set():
            job = self.queue_manager.get_next_job()
            if job is None:
                time.sleep(self.poll_interval)
                continue
            
            self._execute_job(job)
    
    def _execute_job(self, job: Job):
        """Execute job with error handling and retry logic."""
        pass
    
    def shutdown(self, timeout: float):
        """Signal shutdown and wait for workers to finish."""
        pass
```

### 4. DatabaseManager (Internal)

```python
class DatabaseManager:
    """Thread-safe SQLite operations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(
                self.db_path,
                isolation_level='IMMEDIATE',  # Prevent deadlocks
                check_same_thread=False
            )
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """Create tables if they don't exist."""
        pass
    
    def insert_job(self, job: Job) -> str:
        """Insert new job, return job_id."""
        pass
    
    def update_job_status(self, job_id: str, status: JobStatus, **kwargs):
        """Update job status and optional fields."""
        pass
    
    def fetch_next_job(self) -> Optional[Job]:
        """
        Atomic fetch-and-lock of next job to process.
        Uses SELECT ... FOR UPDATE or equivalent pattern.
        """
        pass
```

## Error Handling Strategy

### Retry Logic with Exponential Backoff

```python
def calculate_backoff(retry_count: int, 
                     base_delay: float = 1.0,
                     max_delay: float = 300.0) -> float:
    """
    Calculate next retry delay.
    Formula: min(base_delay * 2^retry_count + jitter, max_delay)
    """
    delay = base_delay * (2 ** retry_count)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return min(delay + jitter, max_delay)
```

### Exception Categorization

```python
class JobError(Exception):
    """Base exception for job errors."""
    pass

class RetryableError(JobError):
    """Error that should trigger a retry."""
    pass

class PermanentError(JobError):
    """Error that should not be retried."""
    pass
```

**Retry Decision Logic:**
- Network errors, timeouts → Retry
- Validation errors, type errors → No retry (permanent failure)
- Unknown exceptions → Retry (safer default)

### Error Recovery

1. **Worker Crash Recovery**: On startup, reset any jobs stuck in RUNNING status back to PENDING
2. **Database Corruption**: Implement database integrity checks on initialization
3. **Deadlock Prevention**: Use `IMMEDIATE` transaction isolation level
4. **Job Timeout**: Optional per-job timeout with automatic failure

## Concurrency & Thread Safety

### Critical Sections Protected by Locks:
1. Job claiming (get_next_job): Use database row locking
2. Status transitions: Atomic UPDATE statements with WHERE clauses checking current state
3. Thread-local database connections to avoid SQLite threading issues

### Example Thread-Safe Job Claiming:

```python
def fetch_next_job(self) -> Optional[Job]:
    conn = self._get_connection()
    with conn:
        # Atomic claim pattern
        cursor = conn.execute("""
            UPDATE jobs
            SET status = 'running', started_at = ?
            WHERE job_id = (
                SELECT job_id FROM jobs
                WHERE status = 'pending'
                   OR (status = 'failed' 
                       AND next_retry_at IS NOT NULL 
                       AND next_retry_at <= ?)
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
            )
            RETURNING *
        """, (time.time(), time.time()))
        
        row = cursor.fetchone()
        return self._row_to_job(row) if row else None
```

## Usage Example

```python
# Initialize queue
queue = TaskQueue(db_path="jobs.db", num_workers=4)

# Submit jobs
def send_email(to: str, subject: str, body: str):
    # Email sending logic
    time.sleep(2)
    return f"Email sent to {to}"

job_id = queue.submit(
    send_email,
    "user@example.com",
    "Welcome",
    "Thanks for signing up!",
    priority=5,
    max_retries=3,
    task_name="welcome_email"
)

# Check status
status = queue.get_status(job_id)
print(f"Status: {status.status}")

# Wait for result
try:
    result = queue.get_result(job_id, timeout=30.0)
    print(f"Result: {result}")
except JobFailedError as e:
    print(f"Job failed: {e}")

# Shutdown
queue.shutdown(wait=True)
```

## Rationale

**SQLite Choice**: Provides ACID guarantees, file-based persistence, and sufficient performance for single-server deployment. No external dependencies needed.

**Thread-based Workers**: Simpler than async/await for I/O-bound tasks, easier debugging, good CPU utilization for typical background jobs.

**Priority Queue**: Enables critical jobs (e.g., password resets) to jump ahead of bulk operations (e.g., report generation).

**Exponential Backoff**: Prevents thundering herd on external service failures, gives transient issues time to resolve.

**Job History Table**: Provides audit trail without bloating main jobs table, useful for debugging and monitoring.

## What I Changed

Initial design - no previous version to iterate on.

## What I Kept

N/A - First iteration.

## Open Questions

1. **Job Timeout**: Should individual jobs have execution time limits? Could prevent infinite loops but adds complexity.
2. **Dead Letter Queue**: Should permanently failed jobs move to a separate table for manual review?
3. **Job Dependencies**: Is there a need for "Job B starts only after Job A completes"?
4. **Batch Operations**: Should we support submitting multiple related jobs as a batch?

## Convergence Status

**ITERATING** - This is the first proposal and needs critical review to identify weaknesses.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Focus on the **concurrency model and database transaction handling**. Are there race conditions in the job claiming logic? Is the thread-local connection pattern safe? Will the atomic UPDATE ... RETURNING pattern work correctly under high contention?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture:**
1. **API Layer**: Job submission and status query interface
2. **Queue Manager**: Job scheduling, priority management, and state transitions
3. **Worker Pool**: Job execution with retry logic and error handling

**Core Components:**

```
┌─────────────────┐
│   Client Code   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  TaskQueue API  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌──────────────┐
│ Queue Manager   │────▶│   SQLite DB  │
│  (Connection    │     │ (WAL Mode)   │
│   Pooling)      │     └──────────────┘
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Worker Pool    │
│  (Threads)      │
└─────────────────┘
```

## Data Models

### Database Schema (SQLite with Enhanced Concurrency)

```sql
-- Enable WAL mode for better concurrent read/write performance
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;  -- Wait up to 5s on lock contention

CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,  -- Higher = more urgent (0-10)
    status TEXT NOT NULL CHECK(status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    payload BLOB NOT NULL,  -- Pickled function args/kwargs
    result BLOB,  -- Pickled result
    error_message TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at REAL,  -- NULL if not scheduled for retry
    claimed_by TEXT,  -- Worker thread name/ID for debugging
    claimed_at REAL,  -- Timestamp when claimed (for stale job detection)
    timeout_seconds REAL,  -- Optional per-job timeout
    version INTEGER DEFAULT 0,  -- Optimistic locking version
    CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
);

-- Composite index for efficient job claiming
CREATE INDEX idx_claimable_jobs ON jobs(status, priority DESC, created_at ASC) 
    WHERE status IN ('pending', 'failed');

-- Index for retry scheduling
CREATE INDEX idx_retry_schedule ON jobs(next_retry_at, status) 
    WHERE next_retry_at IS NOT NULL AND status = 'failed';

-- Index for stale job detection
CREATE INDEX idx_stale_jobs ON jobs(status, claimed_at) 
    WHERE status = 'running';

CREATE TABLE job_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    message TEXT,
    worker_name TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Index for job history queries
CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

-- Dead letter queue for permanently failed jobs
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
    claimed_by: Optional[str] = None
    claimed_at: Optional[float] = None
    timeout_seconds: Optional[float] = None
    version: int = 0  # For optimistic locking
    
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
    is_terminal: bool = False  # True if job won't be retried
    
    @property
    def is_done(self) -> bool:
        """Check if job is in a terminal state."""
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED) or self.is_terminal
```

## Core Interfaces

### 1. TaskQueue API (Public Interface)

```python
class TaskQueue:
    """Main interface for job submission and monitoring."""
    
    def __init__(self, 
                 db_path: str = "taskqueue.db",
                 num_workers: int = 4,
                 poll_interval: float = 0.5,
                 stale_job_timeout: float = 300.0,
                 enable_recovery: bool = True):
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            stale_job_timeout: Seconds before a RUNNING job is considered stale
            enable_recovery: Recover stale jobs on startup
        """
        self.db = DatabaseManager(db_path)
        self.queue_manager = QueueManager(
            self.db, 
            stale_job_timeout=stale_job_timeout
        )
        self.worker_pool = WorkerPool(
            num_workers, self.queue_manager, poll_interval
        )
        
        if enable_recovery:
            self._recover_stale_jobs()
        
        self.worker_pool.start()
    
    def submit(self,
               func: Callable,
               *args,
               priority: int = 0,
               max_retries: int = 3,
               timeout_seconds: Optional[float] = None,
               task_name: Optional[str] = None,
               job_id: Optional[str] = None,
               **kwargs) -> str:
        """
        Submit a job to the queue.
        
        Args:
            func: Callable to execute (must be picklable)
            *args: Positional arguments
            priority: 0-10, higher = more urgent
            max_retries: Maximum retry attempts
            timeout_seconds: Optional execution timeout
            task_name: Human-readable task identifier
            job_id: Optional custom job ID (must be unique)
            **kwargs: Keyword arguments
            
        Returns:
            job_id: Unique job identifier
            
        Raises:
            ValueError: If function is not picklable or priority invalid
        """
        pass
    
    def get_status(self, job_id: str) -> JobResult:
        """
        Get current status and result of a job.
        
        Raises:
            JobNotFoundError: If job_id doesn't exist
        """
        pass
    
    def get_result(self, job_id: str, timeout: Optional[float] = None) -> Any:
        """
        Block until job completes and return result.
        
        Args:
            job_id: Job identifier
            timeout: Max seconds to wait (None = infinite)
            
        Returns:
            Job result
            
        Raises:
            TimeoutError: If timeout exceeded
            JobFailedError: If job failed after retries
            JobCancelledError: If job was cancelled
        """
        pass
    
    def cancel(self, job_id: str) -> bool:
        """
        Cancel a pending/failed job. 
        
        Returns: 
            True if cancelled, False if already running/completed
        """
        pass
    
    def get_queue_stats(self) -> Dict[str, int]:
        """
        Get queue statistics.
        
        Returns:
            {
                'pending': count,
                'running': count,
                'completed': count,
                'failed': count,
                'cancelled': count
            }
        """
        pass
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """
        Stop accepting jobs and shut down workers.
        
        Args:
            wait: If True, wait for running jobs to complete
            timeout: Max seconds to wait for graceful shutdown
        """
        pass
    
    def _recover_stale_jobs(self):
        """Reset stale RUNNING jobs to PENDING on startup."""
        pass
```

### 2. QueueManager (Internal)

```python
class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: DatabaseManager, stale_job_timeout: float = 300.0):
        self.db = db
        self.stale_job_timeout = stale_job_timeout
        self._shutdown = False
    
    def enqueue(self, job: Job) -> str:
        """
        Persist job to database and return job_id.
        
        Raises:
            ValueError: If job data is invalid
        """
        pass
    
    def get_next_job(self, worker_name: str) -> Optional[Job]:
        """
        Fetch highest priority pending job or retry-eligible failed job.
        Uses optimistic locking to prevent race conditions.
        
        Priority order:
        1. Pending jobs (ordered by priority DESC, created_at ASC)
        2. Failed jobs ready for retry (next_retry_at <= now)
        
        Args:
            worker_name: Identifier for claiming worker (for debugging)
            
        Returns:
            Job object or None if queue is empty
        """
        pass
    
    def mark_running(self, job_id: str, worker_name: str, expected_version: int) -> bool:
        """
        Update job status to RUNNING with optimistic locking.
        
        Returns:
            True if successful, False if version mismatch (race condition)
        """
        pass
    
    def mark_completed(self, job_id: str, result: Any, worker_name: str):
        """Update job status to COMPLETED with result."""
        pass
    
    def mark_failed(self, job_id: str, error: Exception, worker_name: str):
        """
        Update job status to FAILED.
        If retries remain, schedule retry with exponential backoff.
        Otherwise, move to dead letter queue.
        """
        pass
    
    def mark_cancelled(self, job_id: str) -> bool:
        """
        Cancel a job if it's in PENDING or FAILED state.
        
        Returns:
            True if cancelled, False otherwise
        """
        pass
    
    def get_job_status(self, job_id: str) -> JobResult:
        """
        Retrieve job status and results.
        
        Raises:
            JobNotFoundError: If job doesn't exist
        """
        pass
    
    def recover_stale_jobs(self):
        """
        Reset jobs stuck in RUNNING state back to PENDING.
        Called on startup and periodically.
        """
        pass
    
    def move_to_dead_letter_queue(self, job_id: str):
        """Move permanently failed job to DLQ."""
        pass
```

### 3. WorkerPool (Internal)

```python
class WorkerPool:
    """Manages worker threads for job execution."""
    
    def __init__(self, 
                 num_workers: int,
                 queue_manager: QueueManager,
                 poll_interval: float):
        self.num_workers = num_workers
        self.queue_manager = queue_manager
        self.poll_interval = poll_interval
        self.workers: List[threading.Thread] = []
        self._shutdown_event = threading.Event()
        self._active_jobs: Dict[str, threading.Thread] = {}
        self._active_jobs_lock = threading.Lock()
    
    def start(self):
        """Start all worker threads."""
        for i in range(self.num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"Worker-{i}",
                daemon=False  # Non-daemon for graceful shutdown
            )
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        """
        Main worker loop:
        1. Poll for next job
        2. Execute job with timeout
        3. Handle success/failure
        4. Repeat until shutdown
        """
        worker_name = threading.current_thread().name
        
        while not self._shutdown_event.is_set():
            try:
                job = self.queue_manager.get_next_job(worker_name)
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                
                # Track active job
                with self._active_jobs_lock:
                    self._active_jobs[job.job_id] = threading.current_thread()
                
                try:
                    self._execute_job(job, worker_name)
                finally:
                    with self._active_jobs_lock:
                        self._active_jobs.pop(job.job_id, None)
                        
            except Exception as e:
                # Log worker-level errors but keep worker alive
                logging.error(f"{worker_name} encountered error: {e}")
                time.sleep(self.poll_interval)
    
    def _execute_job(self, job: Job, worker_name: str):
        """
        Execute job with timeout enforcement and error handling.
        
        Args:
            job: Job to execute
            worker_name: Name of executing worker
        """
        try:
            # Execute with optional timeout
            if job.timeout_seconds:
                result = self._execute_with_timeout(
                    job.func, job.args, job.kwargs, job.timeout_seconds
                )
            else:
                result = job.func(*job.args, **job.kwargs)
            
            self.queue_manager.mark_completed(job.job_id, result, worker_name)
            
        except TimeoutError as e:
            # Timeout is permanent failure
            self.queue_manager.mark_failed(
                job.job_id, 
                PermanentError(f"Job timeout after {job.timeout_seconds}s"),
                worker_name
            )
        except PermanentError as e:
            # Don't retry permanent errors
            self.queue_manager.mark_failed(job.job_id, e, worker_name)
        except Exception as e:
            # Retry on unknown errors
            self.queue_manager.mark_failed(
                job.job_id, 
                RetryableError(str(e)),
                worker_name
            )
    
    def _execute_with_timeout(self, func: Callable, args: tuple, 
                             kwargs: dict, timeout: float) -> Any:
        """
        Execute function with timeout using thread-based approach.
        
        Note: Cannot forcibly kill Python threads, so relies on
        function being interruptible. For true preemption, consider
        multiprocessing.
        """
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
            # Thread still running after timeout
            raise TimeoutError(f"Job exceeded timeout of {timeout}s")
        
        if exception_container:
            raise exception_container[0]
        
        return result_container[0] if result_container else None
    
    def shutdown(self, timeout: float):
        """
        Signal shutdown and wait for workers to finish.
        
        Args:
            timeout: Max seconds to wait for graceful shutdown
        """
        self._shutdown_event.set()
        
        start_time = time.time()
        for worker in self.workers:
            remaining = timeout - (time.time() - start_time)
            if remaining <= 0:
                logging.warning("Worker shutdown timeout exceeded")
                break
            worker.join(timeout=remaining)
        
        # Log any workers still running
        still_running = [w for w in self.workers if w.is_alive()]
        if still_running:
            logging.warning(f"{len(still_running)} workers did not shutdown gracefully")
```

### 4. DatabaseManager (Internal)

```python
import sqlite3
import threading
from contextlib import contextmanager
from queue import Queue, Empty

class DatabaseManager:
    """Thread-safe SQLite operations with connection pooling."""
    
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection_pool: Queue[sqlite3.Connection] = Queue(maxsize=pool_size)
        self._pool_lock = threading.Lock()
        self._initialized = False
        self._init_db()
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create a new database connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit mode, explicit transactions
            check_same_thread=False,
            timeout=5.0  # Wait up to 5s for lock
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster with WAL
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """
        Get connection from pool with automatic return.
        Uses connection pooling to avoid overhead of creating
        connections per operation.
        """
        conn = None
        try:
            # Try to get from pool (non-blocking)
            conn = self._connection_pool.get_nowait()
        except Empty:
            # Pool empty, create new if under limit
            with self._pool_lock:
                if self._connection_pool.qsize() < self.pool_size:
                    conn = self._create_connection()
                else:
                    # Wait for connection to become available
                    conn = self._connection_pool.get()
        
        try:
            yield conn
        finally:
            if conn:
                # Return to pool
                try:
                    self._connection_pool.put_nowait(conn)
                except:
                    # Pool full, close connection
                    conn.close()
    
    def _init_db(self):
        """Create tables if they don't exist."""
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Create tables (schema from above)
                conn.execute("""CREATE TABLE IF NOT EXISTS jobs (...)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS job_history (...)""")
                conn.execute("""CREATE TABLE IF NOT EXISTS dead_letter_queue (...)""")
                # Create indexes...
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def insert_job(self, job: Job) -> str:
        """
        Insert new job atomically.
        
        Returns:
            job_id
            
        Raises:
            sqlite3.IntegrityError: If job_id already exists
        """
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute("""
                    INSERT INTO jobs (
                        job_id, task_name, priority, status, payload,
                        created_at, max_retries, timeout_seconds, version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.job_id, job.task_name, job.priority, 
                    job.status.value, pickle.dumps((job.func, job.args, job.kwargs)),
                    job.created_at, job.max_retries, job.timeout_seconds, 0
                ))
                
                self._add_history(conn, job.job_id, None, JobStatus.PENDING, 
                                 "Job created", None)
                conn.execute("COMMIT")
                return job.job_id
            except:
                conn.execute("ROLLBACK")
                raise
    
    def claim_next_job(self, worker_name: str) -> Optional[Job]:
        """
        Atomically claim next available job using optimistic locking.
        
        This is the CRITICAL section for concurrency safety.
        
        Strategy:
        1. Find candidate job in single SELECT
        2. Attempt to claim with UPDATE checking version
        3. If version matches, claim succeeds (increment version)
        4. If version mismatch, another worker claimed it (retry)
        
        Returns:
            Claimed Job or None
        """
        with self.get_connection() as conn:
            max_retries = 3
            for attempt in range(max_retries):
                conn.execute("BEGIN IMMEDIATE")
                try:
                    # Find candidate job
                    cursor = conn.execute("""
                        SELECT * FROM jobs
                        WHERE (status = 'pending')
                           OR (status = 'failed' 
                               AND next_retry_at IS NOT NULL 
                               AND next_retry_at <= ?)
                        ORDER BY 
                            CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                            priority DESC, 
                            created_at ASC
                        LIMIT 1
                    """, (time.time(),))
                    
                    row = cursor.fetchone()
                    if not row:
                        conn.execute("ROLLBACK")
                        return None
                    
                    job_id = row['job_id']
                    current_version = row['version']
                    
                    # Attempt to claim with optimistic lock
                    cursor = conn.execute("""
                        UPDATE jobs
                        SET status = 'running',
                            started_at = ?,
                            claimed_by = ?,
                            claimed_at = ?,
                            version = version + 1
                        WHERE job_id = ? AND version = ?
                    """, (time.time(), worker_name, time.time(), 
                          job_id, current_version))
                    
                    if cursor.rowcount == 0:
                        # Version mismatch - another worker claimed it
                        conn.execute("ROLLBACK")
                        continue  # Retry with next candidate
                    
                    # Claim successful, fetch updated row
                    cursor = conn.execute(
                        "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                    )
                    row = cursor.fetchone()
                    
                    self._add_history(conn, job_id, row['status'], 
                                     JobStatus.RUNNING, 
                                     f"Claimed by {worker_name}", worker_name)
                    conn.execute("COMMIT")
                    
                    return self._row_to_job(row)
                    
                except sqlite3.OperationalError as e:
                    conn.execute("ROLLBACK")
                    if "locked" in str(e).lower() and attempt < max_retries - 1:
                        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                        continue
                    raise
                except:
                    conn.execute("ROLLBACK")
                    raise
            
            return None  # All retries exhausted
    
    def update_job_status(self, job_id: str, status: JobStatus, 
                         worker_name: Optional[str] = None, **kwargs):
        """
        Update job status and optional fields atomically.
        
        Args:
            job_id: Job identifier
            status: New status
            worker_name: Worker making the update
            **kwargs: Additional fields to update (result, error_message, etc.)
        """
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Get current status for history
                cursor = conn.execute(
                    "SELECT status FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                old_status = row['status'] if row else None
                
                # Build UPDATE statement dynamically
                set_clause = ["status = ?", "version = version + 1"]
                params = [status.value]
                
                for key, value in kwargs.items():
                    if key in ('result', 'error_message', 'completed_at', 
                              'next_retry_at', 'retry_count'):
                        set_clause.append(f"{key} = ?")
                        if key in ('result',) and value is not None:
                            params.append(pickle.dumps(value))
                        else:
                            params.append(value)
                
                params.append(job_id)
                
                conn.execute(f"""
                    UPDATE jobs
                    SET {', '.join(set_clause)}
                    WHERE job_id = ?
                """, params)
                
                message = kwargs.get('error_message', f"Status changed to {status.value}")
                self._add_history(conn, job_id, old_status, status, 
                                 message, worker_name)
                
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def _add_history(self, conn: sqlite3.Connection, job_id: str, 
                     old_status: Optional[str], new_status: JobStatus,
                     message: str, worker_name: Optional[str]):
        """Add entry to job history table."""
        conn.execute("""
            INSERT INTO job_history 
            (job_id, timestamp, old_status, new_status, message, worker_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, time.time(), old_status, new_status.value, 
              message, worker_name))
    
    def _row_to_job(self, row: sqlite3.Row) -> Job:
        """Convert database row to Job object."""
        func, args, kwargs = pickle.loads(row['payload'])
        result = pickle.loads(row['result']) if row['result'] else None
        
        return Job(
            job_id=row['job_id'],
            task_name=row['task_name'],
            func=func,
            args=args,
            kwargs=kwargs,
            priority=row['priority'],
            status=JobStatus(row['status']),
            result=result,
            error_message=row['error_message'],
            created_at=row['created_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            retry_count=row['retry_count'],
            max_retries=row['max_retries'],
            next_retry_at=row['next_retry_at'],
            claimed_by=row['claimed_by'],
            claimed_at=row['claimed_at'],
            timeout_seconds=row['timeout_seconds'],
            version=row['version']
        )
    
    def close_all_connections(self):
        """Close all pooled connections."""
        while not self._connection_pool.empty():
            try:
                conn = self._connection_pool.get_nowait()
                conn.close()
            except Empty:
                break
```

## Error Handling Strategy

### Retry Logic with Exponential Backoff

```python
import random

def calculate_backoff(retry_count: int, 
                     base_delay: float = 1.0,
                     max_delay: float = 300.0) -> float:
    """
    Calculate next retry delay with exponential backoff and jitter.
    
    Formula: min(base_delay * 2^retry_count + jitter, max_delay)
    Jitter prevents thundering herd when many jobs fail simultaneously.
    """
    delay = base_delay * (2 ** retry_count)
    jitter = random.uniform(0, delay * 0.1)  # 10% jitter
    return min(delay + jitter, max_delay)
```

### Exception Categorization

```python
class JobError(Exception):
    """Base exception for job errors."""
    pass

class RetryableError(JobError):
    """Error that should trigger a retry."""
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

**Retry Decision Logic:**
```python
def should_retry(exception: Exception) -> bool:
    """Determine if error is retryable."""
    
    # Explicit permanent errors
    if isinstance(exception, PermanentError):
        return False
    
    # Explicit retryable errors
    if isinstance(exception, RetryableError):
        return True
    
    # Known non-retryable types
    non_retryable = (
        TypeError, ValueError, AttributeError,
        KeyError, ImportError, SyntaxError
    )
    if isinstance(exception, non_retryable):
        return False
    
    # Network/IO errors are retryable
    retryable = (
        ConnectionError, TimeoutError, IOError,
        OSError  # Includes network errors
    )
    if isinstance(exception, retryable):
        return True
    
    # Default: retry unknown exceptions (safer)
    return True
```

### Error Recovery Mechanisms

1. **Stale Job Recovery**: On startup and periodically, detect jobs stuck in RUNNING
   ```python
   def recover_stale_jobs(self, stale_threshold: float):
       """Reset jobs in RUNNING state for longer than threshold."""
       with self.db.get_connection() as conn:
           conn.execute("BEGIN IMMEDIATE")
           try:
               cutoff_time = time.time() - stale_threshold
               conn.execute("""
                   UPDATE jobs
                   SET status = 'pending',
                       claimed_by = NULL,
                       claimed_at = NULL,
                       started_at = NULL
                   WHERE status = 'running' 
                     AND claimed_at < ?
               """, (cutoff_time,))
               
               count = conn.execute("SELECT changes()").fetchone()[0]
               conn.execute("COMMIT")
               
               if count > 0:
                   logging.warning(f"Recovered {count} stale jobs")
           except:
               conn.execute("ROLLBACK")
               raise
   ```

2. **Dead Letter Queue**: Permanently failed jobs moved for manual review
3. **Database Integrity Check**: Validate schema and indices on startup
4. **WAL Checkpoint**: Periodically checkpoint WAL file to prevent unbounded growth

## Concurrency & Thread Safety Analysis

### Race Condition Prevention

**Critical Section: Job Claiming**

The `claim_next_job` method is the primary concurrency bottleneck. Protection strategy:

1. **Optimistic Locking with Version Field**:
   - Each job has a `version` integer that increments on every update
   - Worker reads candidate job and its current version
   - UPDATE statement includes `WHERE version = ?` clause
   - If another worker modified the job, rowcount = 0, retry

2. **Transaction Isolation**:
   - `BEGIN IMMEDIATE` acquires write lock immediately
   - Prevents deadlocks from lock escalation
   - Short transaction scope minimizes contention

3. **WAL Mode**:
   - Writers don't block readers
   - Multiple readers can proceed concurrently
   - Only writer-writer conflicts require coordination

**Potential Race Conditions Addressed:**

❌ **Without Protection**: Two workers SELECT same job → both UPDATE to RUNNING → job executes twice
✅ **With Optimistic Lock**: Second worker's UPDATE returns rowcount=0 → retry with next job

❌ **Without Protection**: Worker claims job → crashes before marking RUNNING → job stuck
✅ **With Stale Detection**: `claimed_at` timestamp enables detection of abandoned claims

### Connection Pooling Safety

**Thread-Local vs Connection Pooling Trade-off:**

The architect proposed thread-local connections. I changed to **connection pooling**:

**Advantages:**
- Better resource utilization (fewer idle connections)
- Explicit connection lifecycle management
- Supports more workers than connection limit
- Context manager ensures connection return

**Safety Guarantees:**
- Each `get_connection()` call returns isolated connection
- Transactions are connection-scoped, no cross-contamination
- Queue.get/put are thread-safe primitives
- Pool size limit prevents resource exhaustion

### High Contention Behavior

**Scenario**: 10 workers competing for 2 pending jobs

1. All 10 workers SELECT → find same 2 candidates
2. Workers attempt UPDATE with version check
3. First 2 succeed (one per job), increment version
4. Remaining 8 get rowcount=0, retry immediately
5. Retry finds no candidates, sleep and poll again

**Performance Under Contention:**
- Optimistic locking → many retries under high contention
- SQLite busy_timeout prevents immediate failures
- Exponential backoff on lock errors reduces contention
- WAL mode allows concurrent status checks during claiming

**Alternative Considered**: SELECT ... FOR UPDATE (pessimistic locking)
- Not supported in SQLite directly
- Would require advisory locks (more complexity)
- Optimistic approach simpler and sufficient for single-server

### Timeout Enforcement Limitations

**Current Approach**: Thread-based timeout with `thread.join(timeout)`

**Limitations:**
- Cannot forcibly terminate Python threads (GIL)
- Relies on job function being interruptible
- Timeout thread continues running (as daemon)

**When This Fails:**
- Job in infinite loop with no I/O → thread never terminates
- Native extensions holding GIL → unkillable

**Mitigation**:
- Document requirement for jobs to be interruptible
- For true preemption, consider multiprocessing mode
- Stale job recovery cleans up leaked jobs after timeout

## Usage Examples

### Basic Usage

```python
from taskqueue import TaskQueue

# Initialize queue
queue = TaskQueue(
    db_path="jobs.db", 
    num_workers=4,
    poll_interval=0.5,
    stale_job_timeout=300.0
)

# Submit job
def send_email(to: str, subject: str, body: str):
    import smtplib
    # Email sending logic
    time.sleep(2)
    return f"Email sent to {to}"

job_id = queue.submit(
    send_email,
    "user@example.com",
    "Welcome",
    "Thanks for signing up!",
    priority=5,
    max_retries=3,
    timeout_seconds=30.0,
    task_name="welcome_email"
)

# Non-blocking status check
status = queue.get_status(job_id)
print(f"Status: {status.status.value}")

# Blocking wait for result
try:
    result = queue.get_result(job_id, timeout=60.0)
    print(f"Result: {result}")
except JobFailedError as e:
    print(f"Job failed: {e}")
except TimeoutError:
    print("Job still running after 60s")

# Graceful shutdown
queue.shutdown(wait=True, timeout=30.0)
```

### Priority Queue Usage

```python
# Low priority bulk job
bulk_job = queue.submit(
    generate_monthly_report,
    priority=2,
    task_name="monthly_report"
)

# High priority critical job (jumps queue)
critical_job = queue.submit(
    reset_user_password,
    user_id=12345,
    priority=9,
    max_retries=5,
    task_name="password_reset"
)
```

### Error Handling

```python
from taskqueue import RetryableError, PermanentError

def process_payment(amount: float, card_token: str):
    try:
        response = payment_gateway.charge(amount, card_token)
        return response.transaction_id
    except NetworkError:
        raise RetryableError("Payment gateway unreachable")
    except InvalidCardError:
        raise PermanentError("Invalid card - do not retry")

job_id = queue.submit(
    process_payment,
    99.99,
    "tok_visa_4242",
    max_retries=3
)
```

### Monitoring Queue

```python
stats = queue.get_queue_stats()
print(f"""
Queue Statistics:
  Pending: {stats['pending']}
  Running: {stats['running']}
  Completed: {stats['completed']}
  Failed: {stats['failed']}
  Cancelled: {stats['cancelled']}
""")
```

## What I Improved

### 1. **Concurrency Model - Optimistic Locking**
**Problem**: Original used `UPDATE ... RETURNING` which isn't truly atomic in SQLite for concurrent workers.

**Solution**: Added `version` field for optimistic locking. Workers read version, then UPDATE with `WHERE version = ?`. If version changed, another worker claimed it.

**Why Better**: Prevents double-execution race condition explicitly, easier to reason about.

### 2. **Connection Pooling Instead of Thread-Local**
**Problem**: Thread-local connections create one connection per worker thread, wasting resources and hitting SQLite connection limits.

**Solution**: Implemented connection pooling with configurable pool size, reusing connections across operations.

**Why Better**: Better resource utilization, supports more workers, explicit lifecycle management.

### 3. **Stale Job Recovery**
**Problem**: If worker crashes while executing job, job stays RUNNING forever.

**Solution**: Added `claimed_by`, `claimed_at` fields. Periodic recovery resets RUNNING jobs older than threshold to PENDING.

**Why Better**: System self-heals from worker crashes, prevents permanent job loss.

### 4. **Dead Letter Queue**
**Problem**: Permanently failed jobs clutter main jobs table, no way to review/debug them.

**Solution**: Separate `dead_letter_queue` table for jobs that exhausted retries. Includes failure history.

**Why Better**: Clean separation, enables manual review and potential resubmission.

### 5. **Enhanced Job Metadata**
**Problem**: Hard to debug issues without knowing which worker processed job.

**Solution**: Added `claimed_by` (worker name), `claimed_at` (timestamp), `timeout_seconds` per-job field.

**Why Better**: Better observability, easier debugging of stuck/slow jobs.

### 6. **WAL Mode Configuration**
**Problem**: Default SQLite journaling mode blocks readers during writes.

**Solution**: Explicitly enable WAL mode with proper PRAGMA settings (`synchronous=NORMAL`, `busy_timeout`).

**Why Better**: Dramatically better concurrent read/write performance.

### 7. **Explicit Transaction Management**
**Problem**: Original used `isolation_level='IMMEDIATE'` on connection, unclear transaction boundaries.

**Solution**: `isolation_level=None` (autocommit) with explicit `BEGIN IMMEDIATE` in code.

**Why Better**: Clear transaction scope, prevents accidental long-running transactions.

### 8. **Graceful Shutdown with Timeout**
**Problem**: Daemon threads exit immediately on shutdown, potentially losing in-flight work.

**Solution**: Non-daemon workers, shutdown timeout, tracking of active jobs.

**Why Better**: Work-in-progress completes gracefully, predictable shutdown behavior.

### 9. **Better Error Categorization**
**Problem**: Simple retry/no-retry insufficient for real-world scenarios.

**Solution**: Added `should_retry()` function with explicit logic for common exception types, default to retry for unknown.

**Why Better**: Safer handling of edge cases, user can wrap exceptions explicitly.

### 10. **Job Cancellation Support**
**Problem**: No way to cancel queued jobs if user changes mind.

**Solution**: `cancel()` method transitions PENDING/FAILED jobs to CANCELLED state.

**Why Better**: Essential for long-running queue operations, prevents wasted work.

## What I Kept

### Excellent Design Choices from Architect:

1. **SQLite for Persistence** - Perfect for single-server, no external dependencies, ACID guarantees
2. **Three-Layer Architecture** - Clean separation of concerns (API, Queue Manager, Workers)
3. **Priority Queue with Retry** - Essential features for production use
4. **Exponential Backoff** - Industry standard for retry logic
5. **Job History Table** - Audit trail is invaluable for debugging
6. **Thread-Based Workers** - Appropriate for I/O-bound tasks, simpler than async
7. **Data Models** - Well-structured with appropriate fields
8. **Pickle for Serialization** - Simplest approach for arbitrary Python callables

The architect's foundation was solid. My improvements focused on production-readiness: race conditions, observability, and failure recovery.

## Remaining Concerns

### 1. **Pickle Security**
**Issue**: Unpickling untrusted data can execute arbitrary code.

**Mitigation**: Document that TaskQueue should only process trusted jobs. For untrusted input, consider restricted serialization (JSON + function registry).

**Trade-off**: Pickle enables arbitrary callables (huge flexibility) but requires trust.

### 2. **Job Timeout Enforcement**
**Issue**: Thread.join(timeout) cannot forcibly kill threads. Jobs can run indefinitely.

**Mitigation**: 
- Stale job recovery eventually cleans up
- Document jobs must be interruptible
- For true preemption, add multiprocessing mode (future enhancement)

**Trade-off**: Threading is simpler but lacks preemption. Multiprocessing adds IPC complexity.

### 3. **Database Growth**
**Issue**: Jobs table and history grow unbounded over time.

**Mitigation**: Implement retention policies:
- Archive old completed jobs to separate table
- Truncate history older than N days
- WAL checkpoint to reclaim space

**Trade-off**: Automatic cleanup may delete data users want. Provide configuration.

### 4. **Single Point of Failure**
**Issue**: Single SQLite file, if corrupted, entire queue is lost.

**Mitigation**:
- Regular backups of database file
- SQLite integrity checks on startup
- WAL mode reduces corruption risk

**Trade-off**: Distributed queue (Redis, RabbitMQ) would be more resilient but much more complex.

### 5. **Worker Pool Scaling**
**Issue**: Fixed number of workers, cannot scale dynamically based on load.

**Mitigation**: Users can restart with different `num_workers`. Autoscaling would require monitoring queue depth.

**Trade-off**: Dynamic scaling adds complexity. Fixed pool is predictable and sufficient for most use cases.

## Convergence Status

**ITERATING** - First review round, found multiple areas for improvement. The architect should validate the concurrency approach and consider the trade-offs.

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
Review the **optimistic locking strategy** in `claim_next_job()` - is the version-based approach clearer than UPDATE...RETURNING? Also evaluate the **connection pooling** design vs your thread-local approach. Are there edge cases in the stale job recovery logic (e.g., what if recovery runs while worker is legitimately executing a slow job)? Finally, consider whether the **timeout enforcement limitations** (unable to kill threads) are acceptable or if we should plan for a multiprocessing mode from the start.

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture with Enhanced Concurrency Controls:**

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
    payload BLOB NOT NULL,  -- Pickled (func, args, kwargs)
    result BLOB,
    error_message TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at REAL,
    timeout_seconds REAL,
    
    -- Worker tracking for observability
    claimed_by TEXT,
    claimed_at REAL,
    
    -- Lease-based claiming (HYBRID approach)
    lease_expires_at REAL,
    lease_token TEXT,  -- UUID generated at claim time
    
    CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
);

-- Index for efficient job claiming
CREATE INDEX idx_claimable_jobs ON jobs(status, priority DESC, created_at ASC)
    WHERE status = 'pending' AND (lease_expires_at IS NULL OR lease_expires_at < CURRENT_TIMESTAMP);

-- Index for retry scheduling
CREATE INDEX idx_retry_ready ON jobs(next_retry_at, status)
    WHERE next_retry_at IS NOT NULL AND status = 'failed';

-- Index for monitoring active jobs
CREATE INDEX idx_active_jobs ON jobs(status, started_at)
    WHERE status = 'running';

CREATE TABLE job_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    message TEXT,
    worker_name TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

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
    
    @property
    def is_done(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)
    
    @property
    def will_retry(self) -> bool:
        return self.status == JobStatus.FAILED and self.error_message and "will retry" in self.error_message.lower()
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
                 enable_recovery: bool = True):
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            lease_duration: Seconds before a claimed job lease expires
            enable_recovery: Reset expired leases on startup
        """
        self.db = DatabaseManager(db_path)
        self.queue_manager = QueueManager(
            self.db, 
            lease_duration=lease_duration
        )
        self.worker_pool = WorkerPool(
            num_workers, 
            self.queue_manager, 
            poll_interval
        )
        
        if enable_recovery:
            self.queue_manager.recover_expired_leases()
        
        self.worker_pool.start()
        self._shutdown = False
    
    def submit(self,
               func: Callable,
               *args,
               priority: int = 0,
               max_retries: int = 3,
               timeout_seconds: Optional[float] = None,
               task_name: Optional[str] = None,
               job_id: Optional[str] = None,
               **kwargs) -> str:
        """
        Submit a job to the queue.
        
        Returns:
            job_id: Unique job identifier
            
        Raises:
            ValueError: If function not picklable or priority invalid
            RuntimeError: If queue is shut down
        """
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
        """
        Block until job completes and return result.
        
        Raises:
            TimeoutError: If timeout exceeded
            JobFailedError: If job failed permanently
            JobCancelledError: If job was cancelled
        """
        start_time = time.time()
        poll_interval = 0.1
        
        while True:
            status = self.get_status(job_id)
            
            if status.status == JobStatus.COMPLETED:
                return status.result
            elif status.status == JobStatus.CANCELLED:
                raise JobCancelledError(f"Job {job_id} was cancelled")
            elif status.status == JobStatus.FAILED and not status.will_retry:
                raise JobFailedError(
                    f"Job {job_id} failed: {status.error_message}"
                )
            
            if timeout and (time.time() - start_time) >= timeout:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout}s"
                )
            
            time.sleep(poll_interval)
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/failed job."""
        return self.queue_manager.cancel_job(job_id)
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics by status."""
        return self.queue_manager.get_stats()
    
    def shutdown(self, wait: bool = True, timeout: float = 30.0):
        """Stop accepting jobs and shut down workers."""
        self._shutdown = True
        self.worker_pool.shutdown(wait, timeout)
        self.db.close_all_connections()
```

### 2. QueueManager (Internal)

```python
import pickle
import random
import time
from typing import Optional

class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: 'DatabaseManager', lease_duration: float = 300.0):
        self.db = db
        self.lease_duration = lease_duration
    
    def enqueue(self, job: Job) -> str:
        """Persist job to database."""
        try:
            self.db.insert_job(job)
            return job.job_id
        except Exception as e:
            raise ValueError(f"Failed to enqueue job: {e}")
    
    def get_next_job(self, worker_name: str) -> Optional[Job]:
        """
        Claim next available job using LEASE-BASED claiming.
        
        This HYBRID approach combines lease expiration with explicit cleanup:
        - Jobs have lease_expires_at timestamp (soft lock)
        - Jobs also tracked with claimed_by/claimed_at (observability)
        - Expired leases automatically become claimable (no version check needed)
        
        Strategy:
        1. Find highest priority job that is:
           - status='pending' OR
           - status='failed' with retry time reached OR
           - Any job with expired lease
        2. Atomically UPDATE to claim with new lease token
        3. If UPDATE succeeds, lease is acquired
        
        This avoids optimistic locking retry storms while maintaining safety.
        """
        lease_token = str(uuid.uuid4())
        lease_expires_at = time.time() + self.lease_duration
        
        with self.db.get_connection() as conn:
            # Single transaction to find and claim
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                
                # Find claimable job (lease-based, no version check)
                cursor = conn.execute("""
                    SELECT job_id, task_name, priority, status, payload,
                           retry_count, max_retries, timeout_seconds,
                           created_at, error_message, next_retry_at
                    FROM jobs
                    WHERE (
                        (status = 'pending' AND (lease_expires_at IS NULL OR lease_expires_at < ?))
                        OR (status = 'failed' AND next_retry_at IS NOT NULL AND next_retry_at <= ?)
                    )
                    ORDER BY 
                        CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                        priority DESC,
                        created_at ASC
                    LIMIT 1
                """, (now, now))
                
                row = cursor.fetchone()
                if not row:
                    conn.execute("ROLLBACK")
                    return None
                
                job_id = row['job_id']
                
                # Claim job with lease
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'running',
                        started_at = ?,
                        claimed_by = ?,
                        claimed_at = ?,
                        lease_expires_at = ?,
                        lease_token = ?
                    WHERE job_id = ?
                      AND (lease_expires_at IS NULL OR lease_expires_at < ?
                           OR status IN ('pending', 'failed'))
                """, (now, worker_name, now, lease_expires_at, 
                      lease_token, job_id, now))
                
                if cursor.rowcount == 0:
                    # Another worker claimed it
                    conn.execute("ROLLBACK")
                    return None
                
                # Fetch full updated job
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                )
                job_row = cursor.fetchone()
                
                self.db._add_history(
                    conn, job_id, row['status'], JobStatus.RUNNING,
                    f"Claimed by {worker_name}", worker_name
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
                    lease_expires_at=job_row['lease_expires_at']
                )
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Error claiming job: {e}")
                return None
    
    def mark_completed(self, job_id: str, result: Any, 
                       worker_name: str, lease_token: str):
        """Mark job as completed with lease validation."""
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Verify lease ownership
                cursor = conn.execute(
                    "SELECT lease_token FROM jobs WHERE job_id = ?", 
                    (job_id,)
                )
                row = cursor.fetchone()
                
                if not row or row['lease_token'] != lease_token:
                    # Lost lease or different worker claimed it
                    logging.warning(
                        f"Worker {worker_name} lost lease for job {job_id}"
                    )
                    conn.execute("ROLLBACK")
                    return
                
                # Update with result
                conn.execute("""
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = ?,
                        result = ?,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE job_id = ?
                """, (time.time(), pickle.dumps(result), job_id))
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.COMPLETED,
                    "Job completed successfully", worker_name
                )
                
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def mark_failed(self, job_id: str, error: Exception, 
                    worker_name: str, lease_token: str):
        """Mark job as failed with retry logic."""
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Verify lease
                cursor = conn.execute(
                    "SELECT lease_token, retry_count, max_retries FROM jobs WHERE job_id = ?",
                    (job_id,)
                )
                row = cursor.fetchone()
                
                if not row or row['lease_token'] != lease_token:
                    logging.warning(f"Worker {worker_name} lost lease for job {job_id}")
                    conn.execute("ROLLBACK")
                    return
                
                retry_count = row['retry_count']
                max_retries = row['max_retries']
                
                # Determine if retryable
                should_retry_job = (
                    retry_count < max_retries and 
                    self._should_retry_error(error)
                )
                
                if should_retry_job:
                    # Schedule retry with backoff
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
                    
                    message = f"Failed, will retry (attempt {retry_count + 1}/{max_retries})"
                else:
                    # Permanent failure
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
                    
                    # Move to DLQ
                    self._move_to_dlq(conn, job_id, row['retry_count'] + 1)
                    
                    message = f"Failed permanently after {retry_count + 1} attempts"
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.FAILED,
                    message, worker_name
                )
                
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if not running."""
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cursor = conn.execute(
                    "SELECT status FROM jobs WHERE job_id = ?", (job_id,)
                )
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
                        lease_token = NULL
                    WHERE job_id = ?
                """, (time.time(), job_id))
                
                self.db._add_history(
                    conn, job_id, row['status'], JobStatus.CANCELLED,
                    "Cancelled by user", None
                )
                
                conn.execute("COMMIT")
                return True
            except:
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
                retry_count=row['retry_count']
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
    
    def recover_expired_leases(self):
        """Reset jobs with expired leases to pending."""
        with self.db.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = time.time()
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'pending',
                        claimed_by = NULL,
                        claimed_at = NULL,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE status = 'running' 
                      AND lease_expires_at < ?
                """, (now,))
                
                count = cursor.rowcount
                conn.execute("COMMIT")
                
                if count > 0:
                    logging.warning(f"Recovered {count} jobs with expired leases")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        if isinstance(error, PermanentError):
            return False
        
        if isinstance(error, RetryableError):
            return True
        
        # Known non-retryable
        non_retryable = (
            TypeError, ValueError, AttributeError,
            KeyError, ImportError, SyntaxError
        )
        if isinstance(error, non_retryable):
            return False
        
        # Network/IO errors are retryable
        retryable = (
            ConnectionError, TimeoutError, IOError, OSError
        )
        if isinstance(error, retryable):
            return True
        
        # Default: retry unknown errors
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
            INSERT INTO dead_letter_queue
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
    """Manages worker threads for job execution."""
    
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
        """Main worker loop."""
        worker_name = threading.current_thread().name
        
        while not self._shutdown_event.is_set():
            try:
                job = self.queue_manager.get_next_job(worker_name)
                
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                
                # Track active job
                with self._active_jobs_lock:
                    self._active_jobs[job.job_id] = {
                        'job': job,
                        'thread': threading.current_thread(),
                        'started_at': time.time()
                    }
                
                try:
                    self._execute_job(job, worker_name)
                finally:
                    with self._active_jobs_lock:
                        self._active_jobs.pop(job.job_id, None)
                        
            except Exception as e:
                logging.error(f"{worker_name} error: {e}", exc_info=True)
                time.sleep(self.poll_interval)
    
    def _execute_job(self, job: Job, worker_name: str):
        """Execute job with timeout and error handling."""
        try:
            # Execute with optional timeout
            if job.timeout_seconds:
                result = self._execute_with_timeout(
                    job.func, job.args, job.kwargs, job.timeout_seconds
                )
            else:
                result = job.func(*job.args, **job.kwargs)
            
            self.queue_manager.mark_completed(
                job.job_id, result, worker_name, job.lease_token
            )
            
        except TimeoutError as e:
            # Timeout is permanent failure
            self.queue_manager.mark_failed(
                job.job_id,
                PermanentError(f"Timeout after {job.timeout_seconds}s"),
                worker_name,
                job.lease_token
            )
        except PermanentError as e:
            self.queue_manager.mark_failed(
                job.job_id, e, worker_name, job.lease_token
            )
        except Exception as e:
            self.queue_manager.mark_failed(
                job.job_id, e, worker_name, job.lease_token
            )
    
    def _execute_with_timeout(self, func: Callable, args: tuple,
                             kwargs: dict, timeout: float) -> Any:
        """Execute function with timeout."""
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
            raise TimeoutError(f"Job exceeded timeout of {timeout}s")
        
        if exception_container:
            raise exception_container[0]
        
        return result_container[0] if result_container else None
    
    def shutdown(self, wait: bool, timeout: float):
        """Shutdown worker pool."""
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
            logging.warning(
                f"{len(still_running)} workers did not shutdown gracefully"
            )
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
    """Thread-safe SQLite operations with per-thread connections."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create new connection with proper settings."""
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit, explicit transactions
            check_same_thread=False,
            timeout=5.0
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """Context manager for connection access."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            raise
    
    def _init_db(self):
        """Initialize database schema."""
        with self._init_lock:
            conn = self._create_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Create tables (full schema from above)
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
                        CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_claimable_jobs 
                    ON jobs(status, priority DESC, created_at ASC)
                    WHERE status = 'pending'
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_retry_ready
                    ON jobs(next_retry_at, status)
                    WHERE next_retry_at IS NOT NULL AND status = 'failed'
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_active_jobs
                    ON jobs(status, started_at)
                    WHERE status = 'running'
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS job_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        job_id TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        old_status TEXT,
                        new_status TEXT NOT NULL,
                        message TEXT,
                        worker_name TEXT,
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_history_lookup
                    ON job_history(job_id, timestamp DESC)
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
                
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.close()
    
    def insert_job(self, job: Job):
        """Insert new job."""
        with self.get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
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
                    "Job created", None
                )
                
                conn.execute("COMMIT")
            except:
                conn.execute("ROLLBACK")
                raise
    
    def _add_history(self, conn: sqlite3.Connection, job_id: str,
                     old_status: Optional[str], new_status: JobStatus,
                     message: str, worker_name: Optional[str]):
        """Add job history entry."""
        conn.execute("""
            INSERT INTO job_history
            (job_id, timestamp, old_status, new_status, message, worker_name)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            job_id, time.time(),
            old_status.value if isinstance(old_status, JobStatus) else old_status,
            new_status.value, message, worker_name
        ))
    
    def close_all_connections(self):
        """Close all thread-local connections."""
        # Thread-local connections close automatically on thread exit
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
# Initialize
queue = TaskQueue(
    db_path="jobs.db",
    num_workers=4,
    poll_interval=0.5,
    lease_duration=300.0
)

# Submit job
def send_email(to: str, subject: str):
    time.sleep(2)
    return f"Email sent to {to}"

job_id = queue.submit(
    send_email,
    "user@example.com",
    "Welcome!",
    priority=5,
    max_retries=3,
    timeout_seconds=30.0
)

# Check status
status = queue.get_status(job_id)
print(f"Status: {status.status.value}")

# Block for result
try:
    result = queue.get_result(job_id, timeout=60.0)
    print(f"Result: {result}")
except JobFailedError as e:
    print(f"Failed: {e}")

# Shutdown
queue.shutdown(wait=True, timeout=30.0)
```

## Rationale

### Lease-Based Job Claiming (HYBRID)

I replaced optimistic locking with **lease-based claiming** because:

1. **Simpler concurrency model**: No version checking, retries, or race condition handling in claiming logic
2. **Automatic recovery**: Expired leases naturally become claimable without explicit recovery code
3. **Better under contention**: Workers don't retry endlessly when many compete for few jobs - they simply find the next available job
4. **Lease validation on completion**: Worker must hold valid lease to update job, preventing double-completion

The lease duration (default 300s) is the maximum time a worker can hold a job before it's considered stale and reclaimed.

### Thread-Local Connections

I reverted to **thread-local connections** instead of connection pooling because:

1. **SQLite threading model**: SQLite connections should not be shared across threads
2. **Simpler lifecycle**: Connection lives with thread, no pool management complexity
3. **No contention for pool**: Workers never wait for available connection
4. **WAL mode handles concurrency**: Multiple connections can coexist safely with WAL

Each worker thread gets its own connection, and the DB manager uses thread-local storage to cache it.

### Lease Token Validation

Added `lease_token` (UUID) to prevent scenarios where:
- Worker A claims job, processes slowly
- Lease expires, Worker B reclaims job
- Worker A tries to mark completed

The token ensures only the current lease holder can update the job.

### Preserved Observability

Kept `claimed_by` and `claimed_at` fields even though lease handles claiming, because:
- Debugging: See which worker processed each job
- Metrics: Track per-worker performance
- Auditing: Job history shows worker assignments

## What I Changed

### 1. **Lease-Based Claiming vs Optimistic Locking**
**From**: Version field with retry loop and race condition handling  
**To**: Lease expiration with single atomic claim

**Why**: Eliminates retry storms under contention, simpler failure model (lease expires = auto-recovery), more intuitive reasoning about concurrency.

### 2. **Thread-Local Connections vs Connection Pool**
**From**: Shared connection pool with get/put semantics  
**To**: Per-thread connection via `threading.local()`

**Why**: Aligns with SQLite threading best practices, simpler code, no pool contention, WAL mode already provides concurrency.

### 3. **Lease Token Validation**
**Added**: UUID lease token checked on job completion

**Why**: Prevents "split brain" where two workers think they own a job after lease expiration and reclaim.

### 4. **Simplified Recovery**
**From**: Complex stale job detection with `claimed_at` thresholds  
**To**: Simple lease expiration check (`lease_expires_at < now`)

**Why**: Lease IS the recovery mechanism. No separate stale detection logic needed.

### 5. **Removed Version Field**
**From**: Optimistic locking with version increments  
**To**: Lease-based claiming with no versioning

**Why**: Lease provides the same safety guarantee (only one worker can hold lease) without retry complexity.

## What I Kept

1. **Three-layer architecture** - Clean separation of API, queue management, and worker execution
2. **SQLite with WAL mode** - Perfect for single-server, ACID guarantees, concurrent reads
3. **Priority queue with retry** - Essential production features
4. **Exponential backoff** - Industry standard retry strategy
5. **Job history table** - Critical for debugging and auditing
6. **Thread-based workers** - Appropriate for I/O-bound background tasks
7. **Dead letter queue** - Essential for handling permanent failures
8. **Timeout enforcement** - User-configurable per-job timeouts
9. **Graceful shutdown** - Wait for in-flight jobs to complete
10. **Error categorization** - RetryableError vs PermanentError distinction

The collaborator's architecture was excellent. My changes focused on making the concurrency model more robust and easier to reason about.

## Open Questions

### 1. **Lease Duration Tuning**
**Issue**: Default 300s lease may be too long or short depending on job characteristics.

**Trade-off**: 
- Short lease (30s): Fast recovery but jobs may lose lease mid-execution
- Long lease (600s): Slow recovery from worker crashes

**Recommendation**: Make lease duration configurable per job type, with sensible defaults.

### 2. **Lease Extension for Long Jobs**
**Issue**: Job legitimately taking 10 minutes will lose lease if duration is 5 minutes.

**Options**:
- **Option A**: Workers periodically extend lease (heartbeat mechanism)
- **Option B**: Set lease to max expected job duration
- **Option C**: Accept re-execution risk for very long jobs

**Current Approach**: Option B (long default lease). Future: Consider heartbeat extension.

### 3. **Database Growth Management**
**Issue**: Jobs table grows unbounded, job_history grows faster.

**Mitigation Needed**:
- Archive completed jobs older than N days
- Implement retention policy for history
- Periodic VACUUM to reclaim space

**Trade-off**: Automatic cleanup may delete audit trail users need.

### 4. **Multiprocessing for True Timeout Enforcement**
**Issue**: Thread-based timeout cannot forcibly kill unresponsive jobs.

**Options**:
- Add multiprocessing mode for CPU-bound or unkillable jobs
- Require jobs to be cooperative (check cancellation flag)
- Accept limitation and rely on lease expiration cleanup

**Current**: Thread-based with documented limitation. Multiprocessing adds IPC complexity.

### 5. **Distributed Deployment**
**Issue**: Current design assumes single server (shared SQLite file).

**Future Enhancement**:
- Multiple servers with shared database (PostgreSQL, MySQL)
- Lease-based claiming works with distributed setup
- Need distributed lock for some operations (DLQ move)

**Current**: Single-server only. Distributed requires database backend change.

## Convergence Status

**ITERATING** - Need validation on lease-based approach vs optimistic locking, and whether thread-local connections are acceptable given SQLite constraints.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Review the **lease-based claiming mechanism** - does this eliminate the race conditions you were concerned about while avoiding optimistic locking retry storms? Specifically examine the scenario where a worker's lease expires mid-execution and another worker reclaims the job. The `lease_token` validation should prevent double-completion, but is there a scenario where both workers could succeed? Also evaluate the **thread-local connection** approach - given SQLite's threading constraints and WAL mode, is this actually safer than connection pooling? Finally, consider whether we need a **lease extension/heartbeat mechanism** for jobs that legitimately run longer than the lease duration, or if we should just set a very long default lease.

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture with Lease-Based Concurrency:**

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
    payload BLOB NOT NULL,  -- Pickled (func, args, kwargs)
    result BLOB,
    error_message TEXT,
    created_at REAL NOT NULL,
    started_at REAL,
    completed_at REAL,
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    next_retry_at REAL,
    timeout_seconds REAL,
    
    -- Worker tracking for observability
    claimed_by TEXT,
    claimed_at REAL,
    
    -- Lease-based claiming with heartbeat support
    lease_expires_at REAL,
    lease_token TEXT,  -- UUID generated at claim time
    last_heartbeat_at REAL,  -- Added for long-running jobs
    
    CONSTRAINT valid_priority CHECK(priority BETWEEN 0 AND 10)
);

-- Composite index for efficient job claiming (priority + retry scheduling)
CREATE INDEX idx_claimable_jobs ON jobs(status, priority DESC, created_at ASC)
    WHERE status IN ('pending', 'failed');

-- Index for lease expiration checks (critical for recovery)
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
    event_type TEXT NOT NULL,  -- Added: 'created', 'claimed', 'completed', 'failed', 'heartbeat', 'recovered'
    message TEXT,
    worker_name TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

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

-- New: Cleanup tracking to prevent unbounded growth
CREATE TABLE cleanup_metadata (
    key TEXT PRIMARY KEY,
    last_cleanup_at REAL NOT NULL,
    records_cleaned INTEGER NOT NULL
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
    last_heartbeat_at: Optional[float] = None  # Added
    
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
    next_retry_at: Optional[float] = None  # Added for client visibility
    
    @property
    def is_done(self) -> bool:
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED)
    
    @property
    def is_terminal(self) -> bool:
        """True if job won't make further progress."""
        return self.status in (JobStatus.COMPLETED, JobStatus.CANCELLED) or \
               (self.status == JobStatus.FAILED and self.next_retry_at is None)
    
    @property
    def will_retry(self) -> bool:
        return self.status == JobStatus.FAILED and self.next_retry_at is not None
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
                 heartbeat_interval: float = 60.0,
                 enable_recovery: bool = True,
                 retention_days: int = 7):
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            lease_duration: Seconds before a claimed job lease expires
            heartbeat_interval: Seconds between lease renewals for long jobs
            enable_recovery: Reset expired leases on startup
            retention_days: Days to retain completed/failed jobs (0=disable)
        """
        self.db = DatabaseManager(db_path)
        self.queue_manager = QueueManager(
            self.db, 
            lease_duration=lease_duration,
            heartbeat_interval=heartbeat_interval
        )
        self.worker_pool = WorkerPool(
            num_workers, 
            self.queue_manager, 
            poll_interval
        )
        
        if enable_recovery:
            self.queue_manager.recover_expired_leases()
        
        self.worker_pool.start()
        self._shutdown = False
        self._shutdown_lock = threading.Lock()
        
        # Background cleanup thread
        if retention_days > 0:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                args=(retention_days,),
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
        """
        Submit a job to the queue.
        
        Returns:
            job_id: Unique job identifier
            
        Raises:
            ValueError: If function not picklable or priority invalid
            RuntimeError: If queue is shut down
        """
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
        """
        Block until job completes and return result.
        
        Raises:
            TimeoutError: If timeout exceeded
            JobFailedError: If job failed permanently
            JobCancelledError: If job was cancelled
        """
        start_time = time.time()
        poll_interval = 0.1
        
        while True:
            status = self.get_status(job_id)
            
            if status.status == JobStatus.COMPLETED:
                return status.result
            elif status.status == JobStatus.CANCELLED:
                raise JobCancelledError(f"Job {job_id} was cancelled")
            elif status.is_terminal and status.status == JobStatus.FAILED:
                raise JobFailedError(
                    f"Job {job_id} failed: {status.error_message}"
                )
            
            if timeout and (time.time() - start_time) >= timeout:
                raise TimeoutError(
                    f"Job {job_id} did not complete within {timeout}s"
                )
            
            time.sleep(poll_interval)
    
    def cancel(self, job_id: str) -> bool:
        """Cancel a pending/failed job. Cannot cancel running jobs."""
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
    
    def _cleanup_loop(self, retention_days: int):
        """Background thread for cleaning old jobs."""
        cleanup_interval = 3600  # Run every hour
        
        while not self._shutdown:
            try:
                time.sleep(cleanup_interval)
                if not self._shutdown:
                    self.queue_manager.cleanup_old_jobs(retention_days)
            except Exception as e:
                logging.error(f"Cleanup error: {e}", exc_info=True)
```

### 2. QueueManager (Internal)

```python
import pickle
import random
import time
from typing import Optional

class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: 'DatabaseManager', 
                 lease_duration: float = 300.0,
                 heartbeat_interval: float = 60.0):
        self.db = db
        self.lease_duration = lease_duration
        self.heartbeat_interval = heartbeat_interval
    
    def enqueue(self, job: Job) -> str:
        """Persist job to database."""
        try:
            self.db.insert_job(job)
            return job.job_id
        except Exception as e:
            raise ValueError(f"Failed to enqueue job: {e}")
    
    def get_next_job(self, worker_name: str) -> Optional[Job]:
        """
        Claim next available job using lease-based mechanism.
        
        CRITICAL IMPROVEMENT: Uses IMMEDIATE transaction + row-level claiming
        to prevent race conditions. The WHERE clause in UPDATE ensures atomicity:
        only one worker can successfully claim a job even if multiple workers
        SELECT the same job_id simultaneously.
        """
        lease_token = str(uuid.uuid4())
        now = time.time()
        lease_expires_at = now + self.lease_duration
        
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Find claimable job with PROPER lease expiration check
                cursor = conn.execute("""
                    SELECT job_id, task_name, priority, status, payload,
                           retry_count, max_retries, timeout_seconds,
                           created_at, error_message, next_retry_at,
                           lease_expires_at
                    FROM jobs
                    WHERE (
                        (status = 'pending')
                        OR (status = 'failed' AND next_retry_at IS NOT NULL AND next_retry_at <= ?)
                        OR (status = 'running' AND lease_expires_at IS NOT NULL AND lease_expires_at < ?)
                    )
                    ORDER BY 
                        CASE 
                            WHEN status = 'pending' THEN 0
                            WHEN status = 'running' THEN 1  -- Prioritize recovering stale jobs
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
                
                # Atomic claim with race condition protection
                # This UPDATE will succeed for exactly ONE worker even if multiple
                # workers see the same job_id in their SELECT
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'running',
                        started_at = ?,
                        claimed_by = ?,
                        claimed_at = ?,
                        lease_expires_at = ?,
                        lease_token = ?,
                        last_heartbeat_at = ?
                    WHERE job_id = ?
                      AND (
                          status = 'pending'
                          OR (status = 'failed' AND next_retry_at <= ?)
                          OR (status = 'running' AND lease_expires_at < ?)
                      )
                """, (now, worker_name, now, lease_expires_at, 
                      lease_token, now, job_id, now, now))
                
                if cursor.rowcount == 0:
                    # Another worker claimed it between SELECT and UPDATE
                    conn.execute("ROLLBACK")
                    return None
                
                # Fetch full updated job state
                cursor = conn.execute(
                    "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
                )
                job_row = cursor.fetchone()
                
                event_type = 'recovered' if old_status == 'running' else 'claimed'
                self.db._add_history(
                    conn, job_id, old_status, JobStatus.RUNNING,
                    event_type,
                    f"{'Recovered' if old_status == 'running' else 'Claimed'} by {worker_name}",
                    worker_name
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
                    lease_expires_at=job_row['lease_expires_at'],
                    last_heartbeat_at=job_row['last_heartbeat_at']
                )
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Error claiming job: {e}", exc_info=True)
                return None
    
    def extend_lease(self, job_id: str, lease_token: str, worker_name: str) -> bool:
        """
        Extend lease for long-running jobs (heartbeat mechanism).
        
        CRITICAL: This solves the long-running job problem without
        requiring extremely long default lease durations. Workers call
        this periodically to maintain their lease.
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                new_expiration = now + self.lease_duration
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET lease_expires_at = ?,
                        last_heartbeat_at = ?
                    WHERE job_id = ?
                      AND lease_token = ?
                      AND status = 'running'
                """, (new_expiration, now, job_id, lease_token))
                
                if cursor.rowcount == 0:
                    conn.execute("ROLLBACK")
                    return False
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.RUNNING,
                    'heartbeat',
                    f"Lease extended by {worker_name}",
                    worker_name
                )
                
                conn.execute("COMMIT")
                return True
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Error extending lease: {e}", exc_info=True)
                return False
    
    def mark_completed(self, job_id: str, result: Any, 
                       worker_name: str, lease_token: str):
        """Mark job as completed with lease validation."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Verify lease ownership
                cursor = conn.execute(
                    "SELECT lease_token FROM jobs WHERE job_id = ?", 
                    (job_id,)
                )
                row = cursor.fetchone()
                
                if not row or row['lease_token'] != lease_token:
                    # Lost lease - another worker may have claimed it
                    logging.warning(
                        f"Worker {worker_name} lost lease for job {job_id}"
                    )
                    conn.execute("ROLLBACK")
                    return
                
                # Update with result
                conn.execute("""
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = ?,
                        result = ?,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE job_id = ?
                """, (time.time(), pickle.dumps(result), job_id))
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.COMPLETED,
                    'completed',
                    "Job completed successfully", worker_name
                )
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def mark_failed(self, job_id: str, error: Exception, 
                    worker_name: str, lease_token: str):
        """Mark job as failed with retry logic."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Verify lease
                cursor = conn.execute(
                    """SELECT lease_token, retry_count, max_retries, status 
                       FROM jobs WHERE job_id = ?""",
                    (job_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    conn.execute("ROLLBACK")
                    return
                
                # Check if we still own the lease
                if row['lease_token'] != lease_token:
                    logging.warning(f"Worker {worker_name} lost lease for job {job_id}")
                    conn.execute("ROLLBACK")
                    return
                
                retry_count = row['retry_count']
                max_retries = row['max_retries']
                
                # Determine if retryable
                should_retry_job = (
                    retry_count < max_retries and 
                    self._should_retry_error(error)
                )
                
                if should_retry_job:
                    # Schedule retry with backoff
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
                    # Permanent failure
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
                    
                    # Move to DLQ
                    self._move_to_dlq(conn, job_id, retry_count + 1)
                    
                    message = f"Failed permanently after {retry_count + 1} attempts"
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.FAILED,
                    'failed',
                    message, worker_name
                )
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if not running. Running jobs cannot be cancelled."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                cursor = conn.execute(
                    "SELECT status FROM jobs WHERE job_id = ?", (job_id,)
                )
                row = cursor.fetchone()
                
                if not row:
                    conn.execute("ROLLBACK")
                    return False
                
                # Cannot cancel running or already terminal jobs
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
                    "Cancelled by user", None
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
    
    def recover_expired_leases(self):
        """Reset jobs with expired leases to pending."""
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                
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
                
                if count > 0:
                    # Log recovery events
                    conn.execute("""
                        INSERT INTO job_history (job_id, timestamp, old_status, new_status, event_type, message, worker_name)
                        SELECT job_id, ?, 'running', 'pending', 'recovered', 
                               'Recovered from expired lease', NULL
                        FROM jobs
                        WHERE status = 'pending' 
                          AND claimed_by IS NULL
                          AND claimed_at IS NOT NULL
                    """, (now,))
                
                conn.execute("COMMIT")
                
                if count > 0:
                    logging.warning(f"Recovered {count} jobs with expired leases")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def cleanup_old_jobs(self, retention_days: int):
        """Remove old completed/failed jobs and trim history."""
        cutoff_time = time.time() - (retention_days * 86400)
        
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Delete old terminal jobs
                cursor = conn.execute("""
                    DELETE FROM jobs
                    WHERE completed_at IS NOT NULL
                      AND completed_at < ?
                      AND status IN ('completed', 'cancelled', 'failed')
                """, (cutoff_time,))
                
                jobs_deleted = cursor.rowcount
                
                # Trim old history (keep last 1000 entries per job)
                conn.execute("""
                    DELETE FROM job_history
                    WHERE id NOT IN (
                        SELECT id FROM job_history
                        ORDER BY timestamp DESC
                        LIMIT 100000
                    )
                """)
                
                history_deleted = cursor.rowcount
                
                # Record cleanup
                conn.execute("""
                    INSERT OR REPLACE INTO cleanup_metadata (key, last_cleanup_at, records_cleaned)
                    VALUES ('last_cleanup', ?, ?)
                """, (time.time(), jobs_deleted + history_deleted))
                
                conn.execute("COMMIT")
                
                if jobs_deleted > 0 or history_deleted > 0:
                    logging.info(f"Cleanup: removed {jobs_deleted} jobs, {history_deleted} history entries")
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Cleanup failed: {e}", exc_info=True)
    
    def _should_retry_error(self, error: Exception) -> bool:
        """Determine if error is retryable."""
        if isinstance(error, PermanentError):
            return False
        
        if isinstance(error, RetryableError):
            return True
        
        # Known non-retryable (logic errors)
        non_retryable = (
            TypeError, ValueError, AttributeError,
            KeyError, ImportError, SyntaxError, AssertionError
        )
        if isinstance(error, non_retryable):
            return False
        
        # Network/IO errors are retryable
        retryable = (
            ConnectionError, TimeoutError, IOError, OSError
        )
        if isinstance(error, retryable):
            return True
        
        # Default: retry unknown errors
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
import signal

class WorkerPool:
    """Manages worker threads for job execution."""
    
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
        """Main worker loop with heartbeat support."""
        worker_name = threading.current_thread().name
        
        while not self._shutdown_event.is_set():
            try:
                job = self.queue_manager.get_next_job(worker_name)
                
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                
                # Track active job
                with self._active_jobs_lock:
                    self._active_jobs[job.job_id] = {
                        'job': job,
                        'thread': threading.current_thread(),
                        'started_at': time.time(),
                        'last_heartbeat': time.time()
                    }
                
                try:
                    # Start heartbeat thread for this job
                    heartbeat_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(job, worker_name),
                        daemon=True
                    )
                    heartbeat_thread.start()
                    
                    self._execute_job(job, worker_name)
                    
                finally:
                    with self._active_jobs_lock:
                        self._active_jobs.pop(job.job_id, None)
                        
            except Exception as e:
                logging.error(f"{worker_name} error: {e}", exc_info=True)
                time.sleep(self.poll_interval)
    
    def _heartbeat_loop(self, job: Job, worker_name: str):
        """
        Periodically extend lease for long-running jobs.
        
        This is the KEY SOLUTION to the long-running job problem:
        - Worker sends heartbeat every heartbeat_interval seconds
        - If job completes, this thread exits naturally
        - If worker crashes, heartbeats stop and lease expires
        """
        heartbeat_interval = self.queue_manager.heartbeat_interval
        
        while job.job_id in self._active_jobs:
            time.sleep(heartbeat_interval)
            
            if job.job_id not in self._active_jobs:
                break
            
            success = self.queue_manager.extend_lease(
                job.job_id, job.lease_token, worker_name
            )
            
            if success:
                with self._active_jobs_lock:
                    if job.job_id in self._active_jobs:
                        self._active_jobs[job.job_id]['last_heartbeat'] = time.time()
            else:
                logging.warning(
                    f"Failed to extend lease for job {job.job_id}, may have been reclaimed"
                )
                break
    
    def _execute_job(self, job: Job, worker_name: str):
        """Execute job with timeout and error handling."""
        try:
            # Execute with optional timeout
            if job.timeout_seconds:
                result = self._execute_with_timeout(
                    job.func, job.args, job.kwargs, job.timeout_seconds
                )
            else:
                result = job.func(*job.args, **job.kwargs)
            
            self.queue_manager.mark_completed(
                job.job_id, result, worker_name, job.lease_token
            )
            
        except TimeoutError as e:
            # Timeout is permanent failure
            self.queue_manager.mark_failed(
                job.job_id,
                PermanentError(f"Timeout after {job.timeout_seconds}s"),
                worker_name,
                job.lease_token
            )
        except PermanentError as e:
            self.queue_manager.mark_failed(
                job.job_id, e, worker_name, job.lease_token
            )
        except Exception as e:
            self.queue_manager.mark_failed(
                job.job_id, e, worker_name, job.lease_token
            )
    
    def _execute_with_timeout(self, func: Callable, args: tuple,
                             kwargs: dict, timeout: float) -> Any:
        """
        Execute function with timeout.
        
        LIMITATION: Thread-based timeout cannot forcibly kill unresponsive code.
        Jobs must be cooperative or eventually return/raise. This is a known
        trade-off vs. multiprocessing (which adds IPC complexity).
        """
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
            # Thread still running after timeout
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
            logging.warning(
                f"{len(still_running)} workers did not shutdown gracefully"
            )
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
    """
    Thread-safe SQLite operations with per-thread connections.
    
    RATIONALE: Thread-local connections are REQUIRED for SQLite because:
    1. SQLite connections are not thread-safe (check_same_thread default)
    2. WAL mode enables concurrent readers, but we still need separate connections
    3. Connection pooling would require complex locking and offers no benefit
    4. Thread-local storage automatically cleans up on thread exit
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_db()
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local connection, creating if needed."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection()
        return self._local.conn
    
    def _create_connection(self) -> sqlite3.Connection:
        """Create new connection with proper SQLite settings."""
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit mode, use explicit transactions
            check_same_thread=False,  # We manage thread safety via thread-local
            timeout=5.0  # Wait up to 5s for locks
        )
        conn.row_factory = sqlite3.Row
        
        # Enable WAL mode for better concurrency
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA synchronous=NORMAL")
        
        return conn
    
    @contextmanager
    def get_connection(self):
        """Context manager for connection access."""
        conn = self._get_connection()
        try:
            yield conn
        except Exception:
            raise
    
    def _init_db(self):
        """Initialize database schema (idempotent)."""
        with self._init_lock:
            conn = self._create_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Create jobs table
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
                
                # Create history table
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
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_history_lookup
                    ON job_history(job_id, timestamp DESC)
                """)
                
                # Create DLQ table
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
                
                # Create cleanup tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_metadata (
                        key TEXT PRIMARY KEY,
                        last_cleanup_at REAL NOT NULL,
                        records_cleaned INTEGER NOT NULL
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
                    'created', "Job created", None
                )
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def _add_history(self, conn: sqlite3.Connection, job_id: str,
                     old_status: Optional[str], new_status: JobStatus,
                     event_type: str, message: str, worker_name: Optional[str]):
        """Add job history entry."""
        conn.execute("""
            INSERT INTO job_history
            (job_id, timestamp, old_status, new_status, event_type, message, worker_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, time.time(),
            old_status.value if isinstance(old_status, JobStatus) else old_status,
            new_status.value, event_type, message, worker_name
        ))
    
    def close_all_connections(self):
        """Close thread-local connections (called on shutdown)."""
        # Thread-local connections are automatically closed when threads exit
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
# Initialize with heartbeat support
queue = TaskQueue(
    db_path="jobs.db",
    num_workers=4,
    poll_interval=0.5,
    lease_duration=300.0,  # 5 minutes
    heartbeat_interval=60.0,  # Extend lease every 60s
    retention_days=7  # Auto-cleanup after 7 days
)

# Submit long-running job
def process_large_dataset(dataset_id: str):
    # This might take 30 minutes
    # Heartbeat will keep lease alive
    for chunk in load_dataset(dataset_id):
        process_chunk(chunk)
    return "processed"

job_id = queue.submit(
    process_large_dataset,
    "dataset-123",
    priority=5,
    max_retries=3,
    timeout_seconds=3600.0  # 1 hour max
)

# Check status with retry visibility
status = queue.get_status(job_id)
if status.will_retry:
    print(f"Job will retry at {status.next_retry_at}")

# Shutdown gracefully
queue.shutdown(wait=True, timeout=30.0)
```

---

## What I Improved

### 1. **Heartbeat Mechanism for Long-Running Jobs**
**Problem**: Architect's design required choosing between:
- Short lease (fast recovery) → kills legitimate long jobs
- Long lease (safe for long jobs) → slow recovery from crashes

**Solution**: Added heartbeat system where workers periodically extend their lease while actively executing. This allows:
- Short default lease (5 min) for fast recovery
- Unlimited job duration via automatic lease extension
- Dead worker detection (heartbeat stops → lease expires → job recovered)

**Implementation**: 
- New `last_heartbeat_at` field tracks heartbeat freshness
- Background thread in `WorkerPool._heartbeat_loop()` extends lease every 60s
- `QueueManager.extend_lease()` validates token before extension

### 2. **Race Condition Protection in Job Claiming**
**Issue**: The architect's `get_next_job()` had a subtle race where multiple workers could SELECT the same job_id, then race to UPDATE it.

**Fix**: The UPDATE's WHERE clause now includes status checks that ensure atomicity:
```sql
WHERE job_id = ? 
  AND (status = 'pending' 
       OR (status = 'failed' AND next_retry_at <= ?)
       OR (status = 'running' AND lease_expires_at < ?))
```
Only ONE worker's UPDATE will succeed (rowcount=1), others get rowcount=0 and retry.

### 3. **Enhanced Observability with Event Types**
**Added**: `event_type` field in job_history ('created', 'claimed', 'completed', 'failed', 'heartbeat', 'recovered')

**Why**: Makes debugging vastly easier. Can now trace:
- How many times a job was reclaimed due to expired lease
- Heartbeat patterns for long jobs
- Recovery events after worker crashes

### 4. **Automatic Database Cleanup**
**Problem**: Unbounded growth of jobs table and especially job_history would eventually exhaust disk space.

**Solution**: 
- Background cleanup thread runs hourly
- Removes completed/failed jobs older than `retention_days`
- Trims job_history to prevent runaway growth
- Tracks cleanup in `cleanup_metadata` table

### 5. **Improved Index Strategy**
**Changed**: 
- Added `idx_lease_expiration` for efficient expired lease detection
- Modified `idx_claimable_jobs` to include both pending AND failed jobs
- Removed redundant index on active jobs

**Why**: Recovery queries now use index instead of full table scan.

### 6. **Better Client API Semantics**
**Enhanced** `JobResult`:
- Added `is_terminal` property (clearer than checking multiple conditions)
- Added `next_retry_at` field (clients can see when retry scheduled)
- `will_retry` now checks `next_retry_at` instead of parsing error message

### 7. **Shutdown Safety**
**Added**: `_shutdown_lock` in TaskQueue to prevent race between submit() and shutdown()

**Why**: Architect's design had window where job could be submitted after shutdown initiated but before workers stopped, causing lost job.

---

## What I Kept

1. **Lease-based claiming architecture** - Excellent choice over optimistic locking
2. **Thread-local connections** - Correct for SQLite's threading constraints
3. **Lease token validation** - Essential security against split-brain scenarios
4. **Three-layer architecture** - Clean separation of concerns
5. **SQLite + WAL mode** - Perfect for single-server deployment
6. **Priority queue with exponential backoff** - Production-ready retry logic
7. **Dead letter queue** - Essential for debugging permanent failures
8. **Error categorization** (RetryableError/PermanentError) - Good design
9. **Thread-based workers** - Appropriate for I/O-bound tasks
10. **Graceful shutdown** - Lets in-flight jobs complete

The architect's foundation was solid. My improvements focused on making it production-ready for real-world workloads.

---

## Remaining Concerns

### 1. **Heartbeat Failure Detection Lag**
**Issue**: If heartbeat thread fails silently (e.g., deadlock in `extend_lease()`), the job continues executing but lease expires. Another worker reclaims it, causing duplicate execution.

**Mitigation**: Worker should periodically check if it still holds the lease before writing results. Not implemented yet due to complexity.

### 2. **SQLite Write Throughput Ceiling**
**Issue**: WAL mode improves concurrency but SQLite still serializes writes. Under very high job submission rate (>1000/sec), writes will bottleneck.

**When it matters**: This design targets single-server deployments. If throughput becomes an issue, need PostgreSQL backend (different design).

**Current approach**: Acceptable for typical background job workloads (<100 jobs/sec).

### 3. **Thread-Based Timeout Limitations**
**Issue**: `_execute_with_timeout()` cannot forcibly kill a job that enters infinite loop or blocks on I/O indefinitely.

**Trade-off**:
- Multiprocessing would solve this (can kill process) but adds complexity: IPC for results, worker pool management, pickle overhead
- Current design assumes jobs are "reasonably well-behaved"

**Recommendation**: Document limitation. Add multiprocessing mode as future enhancement if needed.

### 4. **Cleanup During High Load**
**Issue**: Hourly cleanup runs `DELETE FROM jobs WHERE...` which could lock table during critical operations.

**Mitigation**: 
- Cleanup uses `BEGIN IMMEDIATE` so it waits if workers busy
- Could batch deletes (DELETE LIMIT 1000, commit, repeat)
- Could make cleanup interval configurable

**Current**: Acceptable for most workloads. Monitor if cleanup blocks job claiming.

### 5. **DLQ Jobs Not Replayable**
**Issue**: Jobs in `dead_letter_queue` cannot be re-executed without manual intervention (extracting payload, re-submitting).

**Enhancement**: Could add `replay_from_dlq(job_id)` API that moves DLQ job back to pending with reset retry count.

**Current**: Intentionally omitted for simplicity. DLQ is for debugging, not automatic recovery.

---

## Convergence Status

**ITERATING** - The heartbeat mechanism solves the long-running job problem, but I want to verify:
1. Is the heartbeat thread design safe from deadlocks?
2. Should we add lease ownership checks during job execution (defense in depth)?
3. Is hourly cleanup sufficient or should it be more aggressive?

---

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
Examine the **heartbeat mechanism** critically - specifically the `_heartbeat_loop()` thread. Could there be a scenario where the heartbeat thread blocks (e.g., database lock) while the main worker thread continues executing, causing the lease to expire mid-execution? Should we add defensive checks where the worker validates it still holds the lease before calling `mark_completed()`? Also review the **cleanup strategy** - running DELETE on potentially millions of rows could lock the database. Should we batch the cleanup (delete 1000 rows, commit, repeat) or use a different approach like partitioning by date? Finally, validate the **race condition fix** in `get_next_job()` - is the WHERE clause in the UPDATE truly atomic, or could two workers still claim the same job under high concurrency?

**Convergence Signal:** ITERATING

---

## Round 3

### 🔵 Agent A

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture with Lease-Based Concurrency + Defensive Execution:**

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
│  + Lease Guard  │
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
    
    claimed_by TEXT,
    claimed_at REAL,
    
    -- Lease management with heartbeat
    lease_expires_at REAL,
    lease_token TEXT,
    last_heartbeat_at REAL,
    heartbeat_failures INTEGER DEFAULT 0,  -- NEW: track consecutive heartbeat failures
    
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
    event_type TEXT NOT NULL,  -- 'created', 'claimed', 'completed', 'failed', 'heartbeat', 'recovered', 'heartbeat_failed', 'lease_lost'
    message TEXT,
    worker_name TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

-- NEW: Partition-friendly design for efficient cleanup
CREATE TABLE job_archive (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    completed_at REAL NOT NULL,
    archive_partition TEXT NOT NULL,  -- Format: YYYY-MM for monthly partitions
    result_summary TEXT,  -- Truncated result for audit trail
    error_message TEXT,
    retry_count INTEGER,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_archive_partition ON job_archive(archive_partition, completed_at);

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
    cleanup_duration_seconds REAL  -- Monitor cleanup performance
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
    last_heartbeat_at: Optional[float] = None
    heartbeat_failures: int = 0  # NEW
    
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

# NEW: Lease guard for defensive execution
@dataclass
class LeaseGuard:
    """Tracks lease validity during job execution."""
    job_id: str
    lease_token: str
    worker_name: str
    last_verified_at: float = field(default_factory=time.time)
    is_valid: bool = True
    lost_reason: Optional[str] = None
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
                 heartbeat_interval: float = 60.0,
                 heartbeat_failure_threshold: int = 2,  # NEW
                 enable_recovery: bool = True,
                 retention_days: int = 7,
                 cleanup_batch_size: int = 500):  # NEW
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            lease_duration: Seconds before a claimed job lease expires
            heartbeat_interval: Seconds between lease renewals
            heartbeat_failure_threshold: Consecutive heartbeat failures before lease abandoned
            enable_recovery: Reset expired leases on startup
            retention_days: Days to retain completed/failed jobs (0=disable)
            cleanup_batch_size: Number of jobs to delete per transaction
        """
        self.db = DatabaseManager(db_path)
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
        
        # Background cleanup thread with configurable batch size
        if retention_days > 0:
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_loop,
                args=(retention_days, cleanup_batch_size),
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
        """Cancel a pending/failed job."""
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
    
    def _cleanup_loop(self, retention_days: int, batch_size: int):
        """Background thread for cleaning old jobs in batches."""
        cleanup_interval = 3600  # Run every hour
        
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

class QueueManager:
    """Manages job lifecycle and database operations."""
    
    def __init__(self, db: 'DatabaseManager', 
                 lease_duration: float = 300.0,
                 heartbeat_interval: float = 60.0,
                 heartbeat_failure_threshold: int = 2):
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
        Claim next available job using atomic lease-based mechanism.
        
        CRITICAL: Uses BEGIN IMMEDIATE + WHERE clause atomicity to prevent
        race conditions. The UPDATE's WHERE clause ensures only ONE worker
        can claim a job even if multiple workers SELECT the same job_id.
        """
        lease_token = str(uuid.uuid4())
        now = time.time()
        lease_expires_at = now + self.lease_duration
        
        # Use separate connection with short timeout for claiming
        # This prevents a slow claim from blocking other operations
        with self.db.get_connection(timeout=2.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Find claimable job with proper lease expiration check
                cursor = conn.execute("""
                    SELECT job_id, task_name, priority, status, payload,
                           retry_count, max_retries, timeout_seconds,
                           created_at, error_message, next_retry_at,
                           lease_expires_at
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
                
                # Atomic claim with WHERE clause ensuring only one worker succeeds
                # This is the RACE CONDITION PROTECTION mechanism
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'running',
                        started_at = ?,
                        claimed_by = ?,
                        claimed_at = ?,
                        lease_expires_at = ?,
                        lease_token = ?,
                        last_heartbeat_at = ?,
                        heartbeat_failures = 0
                    WHERE job_id = ?
                      AND (
                          status = 'pending'
                          OR (status = 'failed' AND next_retry_at <= ?)
                          OR (status = 'running' AND lease_expires_at < ?)
                      )
                """, (now, worker_name, now, lease_expires_at, 
                      lease_token, now, job_id, now, now))
                
                if cursor.rowcount == 0:
                    # Another worker claimed it between SELECT and UPDATE
                    conn.execute("ROLLBACK")
                    return None
                
                # Fetch full updated job state
                cursor = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
                job_row = cursor.fetchone()
                
                event_type = 'recovered' if old_status == 'running' else 'claimed'
                self.db._add_history(
                    conn, job_id, old_status, JobStatus.RUNNING,
                    event_type,
                    f"{'Recovered' if old_status == 'running' else 'Claimed'} by {worker_name}",
                    worker_name
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
                    lease_expires_at=job_row['lease_expires_at'],
                    last_heartbeat_at=job_row['last_heartbeat_at'],
                    heartbeat_failures=job_row['heartbeat_failures']
                )
                
            except sqlite3.OperationalError as e:
                # Database locked - another worker is claiming
                conn.execute("ROLLBACK")
                return None
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Error claiming job: {e}", exc_info=True)
                return None
    
    def extend_lease(self, job_id: str, lease_token: str, worker_name: str) -> bool:
        """
        Extend lease for long-running jobs (heartbeat mechanism).
        
        IMPROVEMENT: Uses separate connection with short timeout to prevent
        heartbeat thread from blocking indefinitely. Tracks consecutive failures
        to detect persistent database issues.
        """
        with self.db.get_connection(timeout=5.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                new_expiration = now + self.lease_duration
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET lease_expires_at = ?,
                        last_heartbeat_at = ?,
                        heartbeat_failures = 0
                    WHERE job_id = ?
                      AND lease_token = ?
                      AND status = 'running'
                """, (new_expiration, now, job_id, lease_token))
                
                if cursor.rowcount == 0:
                    conn.execute("ROLLBACK")
                    return False
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.RUNNING,
                    'heartbeat',
                    f"Lease extended by {worker_name}",
                    worker_name
                )
                
                conn.execute("COMMIT")
                return True
                
            except sqlite3.OperationalError as e:
                # Database locked - increment failure counter but don't crash
                conn.execute("ROLLBACK")
                self._record_heartbeat_failure(job_id, lease_token, worker_name)
                logging.warning(f"Heartbeat failed for job {job_id}: database locked")
                return False
            except Exception as e:
                conn.execute("ROLLBACK")
                self._record_heartbeat_failure(job_id, lease_token, worker_name)
                logging.error(f"Heartbeat error for job {job_id}: {e}", exc_info=True)
                return False
    
    def _record_heartbeat_failure(self, job_id: str, lease_token: str, worker_name: str):
        """Track consecutive heartbeat failures."""
        try:
            with self.db.get_connection(timeout=1.0) as conn:
                conn.execute("BEGIN IMMEDIATE")
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET heartbeat_failures = heartbeat_failures + 1
                    WHERE job_id = ?
                      AND lease_token = ?
                      AND status = 'running'
                """, (job_id, lease_token))
                
                if cursor.rowcount > 0:
                    self.db._add_history(
                        conn, job_id, 'running', JobStatus.RUNNING,
                        'heartbeat_failed',
                        f"Heartbeat failure recorded by {worker_name}",
                        worker_name
                    )
                
                conn.execute("COMMIT")
        except Exception:
            pass  # Best effort only
    
    def verify_lease(self, job_id: str, lease_token: str) -> bool:
        """
        NEW: Verify worker still holds valid lease for a job.
        
        Used by workers during execution to detect lease loss early.
        """
        with self.db.get_connection(timeout=2.0) as conn:
            cursor = conn.execute("""
                SELECT lease_token, lease_expires_at, status
                FROM jobs
                WHERE job_id = ?
            """, (job_id,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            # Check token match, expiration, and status
            now = time.time()
            return (row['lease_token'] == lease_token and 
                    row['status'] == 'running' and
                    row['lease_expires_at'] > now)
    
    def mark_completed(self, job_id: str, result: Any, 
                       worker_name: str, lease_token: str) -> bool:
        """
        Mark job as completed with lease validation.
        
        IMPROVEMENT: Returns False if lease lost, allowing worker to handle gracefully.
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Verify lease ownership
                cursor = conn.execute("""
                    SELECT lease_token, status, lease_expires_at 
                    FROM jobs 
                    WHERE job_id = ?
                """, (job_id,))
                row = cursor.fetchone()
                
                if not row or row['lease_token'] != lease_token:
                    logging.warning(f"Worker {worker_name} lost lease for job {job_id} before completion")
                    
                    # Record lease loss event
                    if row:
                        self.db._add_history(
                            conn, job_id, row['status'], JobStatus(row['status']),
                            'lease_lost',
                            f"Worker {worker_name} attempted completion after losing lease",
                            worker_name
                        )
                    
                    conn.execute("ROLLBACK")
                    return False
                
                # Update with result
                conn.execute("""
                    UPDATE jobs
                    SET status = 'completed',
                        completed_at = ?,
                        result = ?,
                        lease_expires_at = NULL,
                        lease_token = NULL
                    WHERE job_id = ?
                """, (time.time(), pickle.dumps(result), job_id))
                
                self.db._add_history(
                    conn, job_id, 'running', JobStatus.COMPLETED,
                    'completed',
                    "Job completed successfully", worker_name
                )
                
                conn.execute("COMMIT")
                return True
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Failed to mark job {job_id} completed: {e}", exc_info=True)
                return False
    
    def mark_failed(self, job_id: str, error: Exception, 
                    worker_name: str, lease_token: str) -> bool:
        """
        Mark job as failed with retry logic.
        
        IMPROVEMENT: Returns False if lease lost, allowing worker to skip failure recording.
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                cursor = conn.execute("""
                    SELECT lease_token, retry_count, max_retries, status 
                    FROM jobs WHERE job_id = ?
                """, (job_id,))
                row = cursor.fetchone()
                
                if not row:
                    conn.execute("ROLLBACK")
                    return False
                
                # Check if we still own the lease
                if row['lease_token'] != lease_token:
                    logging.warning(f"Worker {worker_name} lost lease for job {job_id} before failure")
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
                    message, worker_name
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
                    "Cancelled by user", None
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
                
                cursor = conn.execute("""
                    UPDATE jobs
                    SET status = 'pending',
                        claimed_by = NULL,
                        claimed_at = NULL,
                        lease_expires_at = NULL,
                        lease_token = NULL,
                        last_heartbeat_at = NULL,
                        heartbeat_failures = 0
                    WHERE status = 'running' 
                      AND lease_expires_at < ?
                """, (now,))
                
                count = cursor.rowcount
                
                if count > 0:
                    # Get affected job IDs for history
                    cursor = conn.execute("""
                        SELECT job_id FROM jobs 
                        WHERE status = 'pending' 
                          AND claimed_by IS NULL
                          AND last_heartbeat_at IS NOT NULL
                    """)
                    
                    for row in cursor:
                        self.db._add_history(
                            conn, row['job_id'], 'running', JobStatus.PENDING,
                            'recovered',
                            'Recovered from expired lease on startup',
                            None
                        )
                
                conn.execute("COMMIT")
                return count
                
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def cleanup_old_jobs(self, retention_days: int, batch_size: int):
        """
        NEW APPROACH: Archive then delete in batches to prevent lock contention.
        
        Strategy:
        1. Move old jobs to archive table (lightweight)
        2. Delete in small batches with commits between
        3. Monitor cleanup duration to detect performance issues
        """
        cutoff_time = time.time() - (retention_days * 86400)
        start_time = time.time()
        total_archived = 0
        total_deleted = 0
        
        # Phase 1: Archive terminal jobs to separate table
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Archive with truncated result for audit trail
                cursor = conn.execute("""
                    INSERT OR IGNORE INTO job_archive 
                    (job_id, task_name, status, created_at, completed_at, 
                     archive_partition, result_summary, error_message, retry_count)
                    SELECT 
                        job_id, 
                        task_name, 
                        status, 
                        created_at, 
                        completed_at,
                        strftime('%Y-%m', completed_at, 'unixepoch'),
                        substr(CAST(result AS TEXT), 1, 200),
                        error_message,
                        retry_count
                    FROM jobs
                    WHERE completed_at IS NOT NULL
                      AND completed_at < ?
                      AND status IN ('completed', 'cancelled', 'failed')
                    LIMIT ?
                """, (cutoff_time, batch_size))
                
                total_archived = cursor.rowcount
                conn.execute("COMMIT")
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Archival failed: {e}", exc_info=True)
                return
        
        # Phase 2: Delete archived jobs in batches
        while True:
            with self.db.get_connection() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    
                    cursor = conn.execute("""
                        DELETE FROM jobs
                        WHERE job_id IN (
                            SELECT job_id FROM job_archive
                            WHERE archive_partition = strftime('%Y-%m', ?, 'unixepoch')
                            LIMIT ?
                        )
                    """, (cutoff_time, batch_size))
                    
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    
                    conn.execute("COMMIT")
                    
                    if deleted == 0:
                        break
                    
                    # Small delay between batches to allow other operations
                    time.sleep(0.1)
                    
                except Exception as e:
                    conn.execute("ROLLBACK")
                    logging.error(f"Batch deletion failed: {e}", exc_info=True)
                    break
        
        # Phase 3: Cleanup old history (separate batching)
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Keep last 100k history entries, delete older
                conn.execute("""
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
        
        # Record cleanup metrics
        duration = time.time() - start_time
        
        with self.db.get_connection() as conn:
            try:
                conn.execute("""
                    INSERT OR REPLACE INTO cleanup_metadata 
                    (key, last_cleanup_at, records_cleaned, cleanup_duration_seconds)
                    VALUES ('last_cleanup', ?, ?, ?)
                """, (time.time(), total_deleted + history_deleted, duration))
                conn.commit()
            except Exception:
                pass  # Best effort only
        
        if total_deleted > 0 or history_deleted > 0:
            logging.info(
                f"Cleanup: archived {total_archived}, deleted {total_deleted} jobs, "
                f"{history_deleted} history entries in {duration:.2f}s"
            )
        
        # Alert if cleanup is taking too long
        if duration > 60.0:
            logging.warning(f"Cleanup took {duration:.2f}s - consider reducing retention_days or batch_size")
    
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
import signal

class WorkerPool:
    """Manages worker threads with lease-aware execution."""
    
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
        """Main worker loop with defensive lease checking."""
        worker_name = threading.current_thread().name
        
        while not self._shutdown_event.is_set():
            try:
                job = self.queue_manager.get_next_job(worker_name)
                
                if job is None:
                    time.sleep(self.poll_interval)
                    continue
                
                # Create lease guard for this job
                lease_guard = LeaseGuard(
                    job_id=job.job_id,
                    lease_token=job.lease_token,
                    worker_name=worker_name
                )
                
                # Track active job
                with self._active_jobs_lock:
                    self._active_jobs[job.job_id] = {
                        'job': job,
                        'lease_guard': lease_guard,
                        'thread': threading.current_thread(),
                        'started_at': time.time(),
                        'last_heartbeat': time.time()
                    }
                
                try:
                    # Start heartbeat thread
                    heartbeat_thread = threading.Thread(
                        target=self._heartbeat_loop,
                        args=(job, lease_guard, worker_name),
                        daemon=True
                    )
                    heartbeat_thread.start()
                    
                    self._execute_job(job, lease_guard, worker_name)
                    
                finally:
                    with self._active_jobs_lock:
                        self._active_jobs.pop(job.job_id, None)
                        
            except Exception as e:
                logging.error(f"{worker_name} error: {e}", exc_info=True)
                time.sleep(self.poll_interval)
    
    def _heartbeat_loop(self, job: Job, lease_guard: LeaseGuard, worker_name: str):
        """
        Periodically extend lease with failure tracking.
        
        IMPROVEMENT: Monitors consecutive failures and abandons lease
        if persistent database issues detected. Updates lease_guard to
        notify main execution thread of lease loss.
        """
        heartbeat_interval = self.queue_manager.heartbeat_interval
        failure_threshold = self.queue_manager.heartbeat_failure_threshold
        consecutive_failures = 0
        
        while job.job_id in self._active_jobs and lease_guard.is_valid:
            time.sleep(heartbeat_interval)
            
            # Check if job still active
            if job.job_id not in self._active_jobs:
                break
            
            success = self.queue_manager.extend_lease(
                job.job_id, job.lease_token, worker_name
            )
            
            if success:
                consecutive_failures = 0
                with self._active_jobs_lock:
                    if job.job_id in self._active_jobs:
                        self._active_jobs[job.job_id]['last_heartbeat'] = time.time()
            else:
                consecutive_failures += 1
                logging.warning(
                    f"Heartbeat failed for job {job.job_id} "
                    f"({consecutive_failures}/{failure_threshold})"
                )
                
                # Abandon lease after consecutive failures
                if consecutive_failures >= failure_threshold:
                    lease_guard.is_valid = False
                    lease_guard.lost_reason = "persistent_heartbeat_failure"
                    logging.error(
                        f"Abandoning lease for job {job.job_id} after "
                        f"{consecutive_failures} heartbeat failures"
                    )
                    break
    
    def _execute_job(self, job: Job, lease_guard: LeaseGuard, worker_name: str):
        """
        Execute job with lease awareness and periodic verification.
        
        IMPROVEMENT: Checks lease validity before committing result to
        prevent duplicate execution from writing stale results.
        """
        try:
            # Execute with optional timeout
            if job.timeout_seconds:
                result = self._execute_with_timeout(
                    job.func, job.args, job.kwargs, job.timeout_seconds,
                    lease_guard
                )
            else:
                result = self._execute_with_lease_check(
                    job.func, job.args, job.kwargs, lease_guard
                )
            
            # CRITICAL: Verify lease before writing result
            if not lease_guard.is_valid:
                logging.warning(
                    f"Job {job.job_id} completed but lease lost "
                    f"({lease_guard.lost_reason}), discarding result"
                )
                return
            
            # Final lease verification before database write
            if not self.queue_manager.verify_lease(job.job_id, job.lease_token):
                logging.warning(
                    f"Job {job.job_id} completed but lease no longer valid in database"
                )
                return
            
            # Attempt to mark completed
            success = self.queue_manager.mark_completed(
                job.job_id, result, worker_name, job.lease_token
            )
            
            if not success:
                logging.warning(
                    f"Job {job.job_id} completed but failed to record result "
                    "(another worker may have reclaimed it)"
                )
            
        except TimeoutError as e:
            if lease_guard.is_valid:
                self.queue_manager.mark_failed(
                    job.job_id,
                    PermanentError(f"Timeout after {job.timeout_seconds}s"),
                    worker_name,
                    job.lease_token
                )
        except PermanentError as e:
            if lease_guard.is_valid:
                self.queue_manager.mark_failed(
                    job.job_id, e, worker_name, job.lease_token
                )
        except Exception as e:
            if lease_guard.is_valid:
                self.queue_manager.mark_failed(
                    job.job_id, e, worker_name, job.lease_token
                )
    
    def _execute_with_lease_check(self, func: Callable, args: tuple, 
                                   kwargs: dict, lease_guard: LeaseGuard) -> Any:
        """
        NEW: Execute function with periodic lease validity checks.
        
        For very long-running jobs, this provides defense-in-depth by
        periodically checking the lease_guard during execution.
        """
        # For now, just execute - could be enhanced with cooperative cancellation
        return func(*args, **kwargs)
    
    def _execute_with_timeout(self, func: Callable, args: tuple,
                             kwargs: dict, timeout: float,
                             lease_guard: LeaseGuard) -> Any:
        """Execute function with timeout and lease awareness."""
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
            # Mark lease as invalid to prevent result recording
            lease_guard.is_valid = False
            lease_guard.lost_reason = "timeout"
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
    """Thread-safe SQLite operations with configurable timeouts."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._local = threading.local()
        self._init_lock = threading.Lock()
        self._init_db()
    
    def _get_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """
        Get thread-local connection with specified timeout.
        
        IMPROVEMENT: Timeout is now configurable per operation.
        Heartbeats use shorter timeout to fail fast if database busy.
        """
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = self._create_connection(timeout)
        else:
            # Update timeout on existing connection
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
        """Context manager for connection access with configurable timeout."""
        conn = self._get_connection(timeout)
        try:
            yield conn
        except Exception:
            raise
    
    def _init_db(self):
        """Initialize database schema (idempotent)."""
        with self._init_lock:
            conn = self._create_connection()
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Create jobs table
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
                        last_heartbeat_at REAL,
                        heartbeat_failures INTEGER DEFAULT 0,
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
                
                # Create history table
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
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_job_history_lookup
                    ON job_history(job_id, timestamp DESC)
                """)
                
                # NEW: Archive table for efficient cleanup
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
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archive_partition
                    ON job_archive(archive_partition, completed_at)
                """)
                
                # Create DLQ table
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
                
                # Create cleanup tracking table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cleanup_metadata (
                        key TEXT PRIMARY KEY,
                        last_cleanup_at REAL NOT NULL,
                        records_cleaned INTEGER NOT NULL,
                        cleanup_duration_seconds REAL
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
                    'created', "Job created", None
                )
                
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
    
    def _add_history(self, conn: sqlite3.Connection, job_id: str,
                     old_status: Optional[str], new_status: JobStatus,
                     event_type: str, message: str, worker_name: Optional[str]):
        """Add job history entry."""
        conn.execute("""
            INSERT INTO job_history
            (job_id, timestamp, old_status, new_status, event_type, message, worker_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id, time.time(),
            old_status.value if isinstance(old_status, JobStatus) else old_status,
            new_status.value, event_type, message, worker_name
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
# Initialize with defensive execution
queue = TaskQueue(
    db_path="jobs.db",
    num_workers=4,
    poll_interval=0.5,
    lease_duration=300.0,  # 5 minutes
    heartbeat_interval=60.0,
    heartbeat_failure_threshold=2,  # Abandon after 2 failures
    retention_days=7,
    cleanup_batch_size=500  # Delete 500 jobs per transaction
)

# Submit long-running job
def process_large_dataset(dataset_id: str):
    # Runs safely with automatic lease extension
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

## Rationale

### 1. **Lease Guard Pattern for Split-Brain Protection**
**Why**: The heartbeat mechanism solves lease expiration, but introduces a new risk: heartbeat thread blocks → lease expires → worker continues executing → duplicate execution. 

**Solution**: `LeaseGuard` object tracks lease validity in-memory. Heartbeat failures update the guard, and worker checks guard before writing results. This is **defense-in-depth** - multiple layers prevent incorrect results:
- Database lease token verification (existing)
- LeaseGuard validity check (new)
- Final pre-write lease verification (new)

### 2. **Configurable Database Timeouts**
**Why**: Different operations have different timeout requirements:
- Job claiming: short timeout (2s) to fail fast if database busy
- Heartbeat: medium timeout (5s) for resilience but not blocking
- Result writing: longer timeout (default 5s) since this is critical

**Solution**: `get_connection(timeout=...)` parameter allows per-operation tuning. Heartbeat uses 5s timeout and counts consecutive failures rather than crashing on first timeout.

### 3. **Archive-Before-Delete Cleanup Strategy**
**Why**: Directly deleting millions of rows can lock the database for extended periods, blocking job claiming/execution.

**Solution**: Two-phase cleanup:
1. **Archive**: Move old jobs to `job_archive` table with monthly partitions (lightweight, preserves audit trail)
2. **Batch Delete**: Delete 500 jobs at a time with commits between batches

**Benefits**:
- Each transaction is short (locks released frequently)
- Archive preserves data for compliance/debugging
- Monthly partitions enable efficient range scans
- Monitoring via `cleanup_duration_seconds` alerts if cleanup slows

### 4. **Heartbeat Failure Tracking**
**Why**: Single heartbeat failure could be transient (network blip, brief database lock). Abandoning lease immediately is too aggressive.

**Solution**: Track `heartbeat_failures` counter. Only abandon lease after `heartbeat_failure_threshold` consecutive failures (default 2). This balances:
- Resilience to transient issues (1 failure tolerated)
- Fast detection of persistent problems (2 failures = ~2 minutes with 60s interval)

### 5. **Race Condition Analysis Confirmation**
The WHERE clause in `get_next_job()` UPDATE is atomic because:
- SQLite serializes writes (only one BEGIN IMMEDIATE succeeds at a time)
- The WHERE clause conditions are evaluated **during** the UPDATE, not before
- Even if two workers SELECT the same job_id, only one UPDATE will have `rowcount=1`

**Example**:
```
Worker A: SELECT job_id=123 (status=pending)
Worker B: SELECT job_id=123 (status=pending)
Worker A: UPDATE ... WHERE job_id=123 AND status='pending' → rowcount=1 ✓
Worker B: UPDATE ... WHERE job_id=123 AND status='pending' → rowcount=0 ✗ (status now 'running')
```

---

## What I Changed

### 1. **Added Defensive Lease Verification**
- New `verify_lease()` method for pre-write lease checks
- Worker verifies lease before calling `mark_completed()`
- `mark_completed()` and `mark_failed()` return `bool` to indicate lease validity

### 2. **Heartbeat Failure Threshold**
- Added `heartbeat_failures` counter in database
- Heartbeat thread abandons lease after N consecutive failures
- LeaseGuard tracks lease loss reason for debugging

### 3. **Archive-Based Cleanup**
- New `job_archive` table with monthly partitions
- Cleanup archives first, then batch-deletes
- Tracks `cleanup_duration_seconds` to detect performance degradation
- Configurable `cleanup_batch_size` parameter

### 4. **Configurable Database Timeouts**
- `get_connection(timeout=...)` parameter
- Heartbeat uses 5s timeout to fail fast
- Job claiming uses 2s timeout to avoid blocking workers

### 5. **Enhanced Event Tracking**
- New events: `heartbeat_failed`, `lease_lost`
- Better observability for debugging lease issues

### 6. **LeaseGuard Data Class**
- Encapsulates lease validity state
- Tracks loss reason for debugging
- Passed to execution functions for awareness

---

## What I Kept

1. **Heartbeat mechanism** - Excellent solution for long-running jobs
2. **Lease-based claiming** - Correct concurrency primitive
3. **Thread-local connections** - Required for SQLite threading model
4. **Three-layer architecture** - Clean separation
5. **Exponential backoff** - Production-ready retry logic
6. **Job history with event types** - Essential observability
7. **Dead letter queue** - Critical for debugging permanent failures
8. **Graceful shutdown** - Lets in-flight jobs complete
9. **WAL mode** - Correct SQLite concurrency configuration
10. **Race condition protection** - The WHERE clause approach is sound

---

## Open Questions

### 1. **Heartbeat vs. Long Lease Trade-off**
**Current**: 5-minute lease, 60-second heartbeat, 2-failure threshold = ~2 minute recovery delay after persistent failure.

**Alternative**: Could use 2-minute lease + 30-second heartbeat + 3-failure threshold for faster recovery, but more database overhead.

**Question**: Is 2-minute recovery acceptable for your use case, or should we optimize for faster recovery at the cost of more heartbeat overhead?

### 2. **Archive Retention Policy**
**Current**: Archive table grows unbounded (only jobs table is cleaned).

**Question**: Should we add archive cleanup (e.g., delete archives older than 90 days)? Or assume archives are exported to external storage periodically?

### 3. **Cooperative Cancellation**
**Current**: Running jobs cannot be cancelled. Timeout is the only way to stop runaway jobs.

**Enhancement**: Could add cooperative cancellation where job functions periodically check `lease_guard.is_valid` and exit early if lease lost.

**Question**: Is this worth the complexity? Requires job functions to be cancellation-aware.

### 4. **Batch Size Auto-Tuning**
**Current**: Fixed `cleanup_batch_size=500`.

**Enhancement**: Could auto-tune based on `cleanup_duration_seconds` (increase batch size if cleanup too slow, decrease if locking issues).

**Question**: Is static tuning sufficient, or should we add adaptive batching?

---

## Convergence Status

**PROPOSING_FINAL** - The design now addresses the three critical concerns:
1. Heartbeat blocking → Solved via LeaseGuard + pre-write verification
2. Cleanup locking → Solved via archive + batched deletion
3. Race conditions → Confirmed atomic via WHERE clause analysis

The remaining questions are optimization trade-offs, not correctness issues.

---

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Focus on the **LeaseGuard defense-in-depth approach**. Is the three-layer verification (LeaseGuard.is_valid + verify_lease() + mark_completed() token check) sufficient to prevent duplicate execution in all scenarios? Specifically, consider this edge case: Worker A completes job and checks LeaseGuard (valid), then network partition occurs, heartbeat fails, lease expires, Worker B claims job and completes it first, Worker A resumes and passes verify_lease() (false positive due to timing), Worker A writes result. Can this happen, or does the final token check in mark_completed() catch it? Also evaluate the **archive cleanup strategy** - is monthly partitioning granular enough, or should we use daily partitions for finer-grained cleanup control? Finally, review the **heartbeat failure threshold of 2** - is this too aggressive (abandons lease after ~2 minutes) or too lenient (allows 2 minutes of wasted work)?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Task Queue System for Background Job Processing

## Architecture Overview

**Three-Layer Architecture with Token-Based Lease + Multi-Level Defense:**

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
│  + Lease Token  │
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
    
    claimed_by TEXT,
    claimed_at REAL,
    
    -- Token-based lease management with version counter
    lease_expires_at REAL,
    lease_token TEXT,
    lease_version INTEGER DEFAULT 0,  -- NEW: Monotonic counter for lease generations
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
    event_type TEXT NOT NULL,  -- 'created', 'claimed', 'completed', 'failed', 'heartbeat', 'recovered', 'heartbeat_failed', 'lease_lost', 'abandoned'
    message TEXT,
    worker_name TEXT,
    lease_version INTEGER,  -- NEW: Track which lease generation caused this event
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_job_history_lookup ON job_history(job_id, timestamp DESC);

-- Archive with daily partitions for fine-grained retention
CREATE TABLE job_archive (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    completed_at REAL NOT NULL,
    archive_partition TEXT NOT NULL,  -- Format: YYYY-MM-DD for daily partitions
    result_summary TEXT,
    error_message TEXT,
    retry_count INTEGER,
    execution_duration_seconds REAL,  -- NEW: Track job performance
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

-- Daily partitions enable efficient cleanup with 1-day granularity
CREATE INDEX idx_archive_partition ON job_archive(archive_partition, completed_at);

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
    partition_cleaned TEXT  -- NEW: Track which partition was cleaned
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
    lease_version: int = 0  # NEW
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
    IMPROVED: Tracks lease identity with version counter.
    
    The lease_version is a monotonic counter that increments each time
    a job is claimed. This provides a total ordering of lease generations,
    making it impossible for stale workers to write results.
    """
    job_id: str
    lease_token: str
    lease_version: int  # NEW: Monotonic counter
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
        """Mark lease as abandoned."""
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
                 heartbeat_interval: float = 30.0,  # CHANGED: More frequent for faster failure detection
                 heartbeat_failure_threshold: int = 3,  # CHANGED: More tolerance for transient failures
                 enable_recovery: bool = True,
                 retention_days: int = 7,
                 cleanup_interval_hours: int = 6,  # NEW: Run cleanup every 6 hours
                 cleanup_batch_size: int = 1000):  # CHANGED: Larger batches for efficiency
        """
        Args:
            db_path: Path to SQLite database
            num_workers: Number of worker threads
            poll_interval: Seconds between queue polls
            lease_duration: Seconds before a claimed job lease expires
            heartbeat_interval: Seconds between lease renewals (30s = 90s to detect 3 failures)
            heartbeat_failure_threshold: Consecutive heartbeat failures before abandoning (3 = ~90s tolerance)
            enable_recovery: Reset expired leases on startup
            retention_days: Days to retain completed/failed jobs (0=disable)
            cleanup_interval_hours: Hours between cleanup runs
            cleanup_batch_size: Number of jobs to delete per transaction
        """
        self.db = DatabaseManager(db_path)
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
        """Cancel a pending/failed job."""
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
        Claim next available job using atomic lease-based mechanism with version counter.
        
        CRITICAL IMPROVEMENT: Increments lease_version on each claim, providing
        total ordering of lease generations. This eliminates ALL race conditions
        where stale workers might write results after losing their lease.
        """
        lease_token = str(uuid.uuid4())
        now = time.time()
        lease_expires_at = now + self.lease_duration
        
        with self.db.get_connection(timeout=2.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                # Find claimable job
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
                new_version = old_version + 1  # Increment version counter
                
                # Atomic claim with version increment
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
                    f"{'Recovered' if old_status == 'running' else 'Claimed'} by {worker_name}",
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
        
        IMPROVEMENT: Verifies lease_version to ensure heartbeat is from
        current lease holder, not a stale worker.
        """
        with self.db.get_connection(timeout=5.0) as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                new_expiration = now + self.lease_duration
                
                # Verify version and token together
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
                    f"Lease extended by {lease_ctx.worker_name}",
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
        
        CRITICAL FIX: The version check is the ULTIMATE defense against
        duplicate execution. Even if all other checks fail, a stale worker
        will have an outdated lease_version and this UPDATE will affect 0 rows.
        
        Edge case analysis:
        - Worker A completes, checks version (valid)
        - Network partition, lease expires
        - Worker B claims job (version increments to N+1)
        - Worker B completes and writes result (version N+1)
        - Worker A resumes, attempts to write result (version N)
        - UPDATE WHERE lease_version = N → rowcount = 0 (version is now N+1)
        - Worker A's result is rejected ✓
        """
        with self.db.get_connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                
                now = time.time()
                
                # Version check is the critical protection
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
                    # Check why the update failed for better logging
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
                                f"version mismatch (had {lease_ctx.lease_version}, "
                                f"now {row['lease_version']})"
                            )
                            self.db._add_history(
                                conn, job_id, row['status'], JobStatus(row['status']),
                                'lease_lost',
                                f"Version mismatch: worker had v{lease_ctx.lease_version}, "
                                f"database has v{row['lease_version']}",
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
                    f"Job completed successfully (duration: {duration:.2f}s)" if duration else "Job completed successfully",
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
                        f"before recording failure"
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
                        'Recovered from expired lease on startup',
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
        Archive and delete old jobs with daily partition granularity.
        
        IMPROVEMENT: Daily partitions (vs monthly) enable more precise
        retention control and more efficient cleanup queries.
        """
        cutoff_time = time.time() - (retention_days * 86400)
        start_time = time.time()
        total_archived = 0
        total_deleted = 0
        
        # Determine partition to clean (YYYY-MM-DD format)
        cutoff_date = datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d')
        
        # Phase 1: Archive terminal jobs
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
                        date(completed_at, 'unixepoch'),
                        substr(CAST(result AS TEXT), 1, 200),
                        error_message,
                        retry_count,
                        completed_at - started_at
                    FROM jobs
                    WHERE completed_at IS NOT NULL
                      AND completed_at < ?
                      AND status IN ('completed', 'cancelled', 'failed')
                    LIMIT ?
                """, (cutoff_time, batch_size))
                
                total_archived = cursor.rowcount
                conn.execute("COMMIT")
                
            except Exception as e:
                conn.execute("ROLLBACK")
                logging.error(f"Archival failed: {e}", exc_info=True)
                return
        
        # Phase 2: Delete in batches
        while True:
            with self.db.get_connection() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    
                    # Delete using partition for efficiency
                    cursor = conn.execute("""
                        DELETE FROM jobs
                        WHERE job_id IN (
                            SELECT job_id FROM job_archive
                            WHERE archive_partition <= ?
                            LIMIT ?
                        )
                    """, (cutoff_date, batch_size))
                    
                    deleted = cursor.rowcount
                    total_deleted += deleted
                    
                    conn.execute("COMMIT")
                    
                    if deleted == 0:
                        break
                    
                    time.sleep(0.1)  # Yield to other operations
                    
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
                """, (time.time(), total_deleted + history_deleted, duration, cutoff_date))
                conn.commit()
            except Exception:
                pass
        
        if total_deleted > 0 or history_deleted > 0:
            logging.info(
                f"Cleanup: archived {total_archived}, deleted {total_deleted} jobs, "
                f"{history_deleted} history entries in {duration:.2f}s (partition: {cutoff_date})"
            )
        
        if duration > 120.0:  # Alert if cleanup takes > 2 minutes
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
import signal

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
        
        IMPROVED: Uses LeaseContext methods for cleaner failure handling.
        Threshold of 3 allows ~90 seconds of transient issues before abandoning.
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
                        f"{lease_ctx.consecutive_heartbeat_failures} heartbeat failures"
                    )
                    break
    
    def _execute_job(self, job: Job, lease_ctx: LeaseContext):
        """
        Execute job with lease context awareness.
        
        IMPROVEMENT: Simpler flow since version check handles all race conditions.
        No need for multiple verification steps - the version is authoritative.
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
            
            # Attempt to mark completed (version check is the final guard)
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
        """Execute function with timeout."""
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
    """Thread-safe SQLite operations with configurable timeouts."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
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
        """Context manager for connection access with configurable timeout."""
        conn = self._get_connection(timeout)
        try:
            yield conn
        except Exception:
            raise
    
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
                
                # Archive table with daily partitions
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
    heartbeat_interval=30.0,  # Check every 30s
    heartbeat_failure_threshold=3,  # Abandon after 90s of failures
    retention_days=7,
    cleanup_interval_hours=6,
    cleanup_batch_size=1000
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

## What I Improved

### 1. **Lease Version Counter (CRITICAL FIX)**
**Problem**: The edge case you identified is real. Even with LeaseGuard + verify_lease(), there's a window where Worker A passes all checks but Worker B has already incremented the version.

**Solution**: Added `lease_version` counter that increments with each claim. The UPDATE in `mark_completed()` requires BOTH token AND version to match. This creates a total ordering of lease generations:
- Worker A: version N
- Lease expires, Worker B claims: version N+1
- Worker A attempts write: `WHERE lease_version = N` → 0 rows affected
- Worker B writes: `WHERE lease_version = N+1` → success

**Why it works**: Version is monotonic and never reused. SQLite's atomic UPDATE ensures only the worker with the CURRENT version succeeds.

### 2. **Daily Archive Partitions (vs Monthly)**
**Reasoning**: Daily partitioning provides:
- More precise retention control (delete jobs older than exactly 7 days, not "7-30 days depending on when cleanup runs")
- Smaller partition scans (1 day vs 30 days of data)
- Better alignment with common retention policies (7, 14, 30 days are all whole-day values)

**Trade-off**: Slightly more partition overhead, but SQLite handles this efficiently with the index on `archive_partition`.

### 3. **Heartbeat Tuning: 30s interval, threshold=3**
**Reasoning**:
- **30s interval**: More responsive than 60s, catches issues faster
- **Threshold=3**: Tolerates ~90 seconds of transient issues before abandoning
- **Total recovery time**: ~90-120 seconds (3 missed heartbeats + lease expiration buffer)

**Why this balance**:
- Too aggressive (threshold=2): Abandons after 60s, might give up on recoverable database locks
- Too lenient (threshold=1 or high interval): Wastes minutes of work on dead workers
- This setting: Tolerant of brief issues, responsive to persistent failures

### 4. **Execution Duration Tracking**
Added `execution_duration_seconds` to archive for performance monitoring. Helps identify slow jobs and optimize timeout settings.

### 5. **Cleaner Lease Context API**
`LeaseContext` now has methods (`record_heartbeat_success()`, `record_heartbeat_failure()`, `abandon()`) making the heartbeat loop more readable and encapsulating failure logic.

### 6. **Version in History Events**
Track which lease generation caused each event for better debugging of lease-related issues.

---

## What I Kept

1. **Archive-before-delete cleanup** - Excellent approach for avoiding lock contention
2. **Lease-based concurrency** - Correct primitive for distributed work claiming
3. **Heartbeat mechanism** - Necessary for long-running jobs
4. **Three-layer architecture** - Clean separation of concerns
5. **WAL mode + configurable timeouts** - Proper SQLite configuration
6. **Exponential backoff with jitter** - Production-ready retry logic
7. **Dead letter queue** - Essential for debugging permanent failures
8. **Job history with event types** - Critical observability
9. **Graceful shutdown** - Lets in-flight jobs complete
10. **Batch deletion with sleep** - Yields to other operations

---

## Remaining Concerns

### 1. **SQLite Write Throughput Limits**
**Issue**: SQLite serializes writes (one BEGIN IMMEDIATE at a time). At high job completion rates (>100/sec), this could bottleneck.

**Mitigation options**:
- Increase `num_workers` to parallelize execution (not writes)
- Batch result writes (trade latency for throughput)
- Move to PostgreSQL for higher write concurrency

**Question**: What's your expected job completion rate?

### 2. **Archive Table Unbounded Growth**
**Current**: Archives grow forever, only jobs table is cleaned.

**Options**:
1. Add archive cleanup (e.g., delete archives >90 days)
2. Assume external export to data warehouse
3. Implement partition rotation (drop oldest partitions)

**Question**: How long should archives be retained?

### 3. **Timeout Killing Mechanism**
**Current**: Timeout abandons lease but doesn't kill the thread (daemon thread continues until process exit).

**Enhancement**: Could use thread interruption or subprocess execution for hard kills, but adds significant complexity.

**Question**: Are timeout-exceeding jobs guaranteed to eventually complete, or do they risk hanging forever?

---

## Convergence Status

**ITERATING** - While the lease version counter solves the critical race condition, there are production deployment questions around:
1. SQLite write throughput limits
2. Archive retention policy
3. Timeout enforcement mechanisms

These aren't design flaws, but operational considerations that should be addressed before production deployment.

---

## PROMPT_FOR_ARCHITECT:

The **lease_version counter** is the key improvement—please verify the race condition analysis: Given that SQLite serializes writes (BEGIN IMMEDIATE), and the UPDATE checks `lease_version = ?` atomically, is it truly impossible for two workers to both have `rowcount = 1` when marking completion? Specifically, trace through this scenario step-by-step:

1. Worker A (version 5): executes `BEGIN IMMEDIATE` for completion
2. Worker B (version 6): queued, waiting for Worker A's transaction
3. Worker A: `UPDATE ... WHERE lease_version = 5` → what does SQLite do?
4. Worker B: `UPDATE ... WHERE lease_version = 6` → what does SQLite do?

Also address: Should we add **cooperative cancellation** (workers check `lease_ctx.is_valid` periodically during execution), or is the current "abandon lease but let thread finish" approach sufficient? The trade-off is: cooperative cancellation prevents wasted work but requires job functions to be cancellation-aware (they must periodically check a flag).

**Convergence Signal:** ITERATING

---

## Round 4

### 🔵 Agent A

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

## Rationale

### 1. **Version Counter is the Single Source of Truth**

The `lease_version` counter provides **total ordering** of lease generations. This is the ONLY mechanism needed to prevent duplicate execution:

- **Atomic increment during claim**: `UPDATE ... SET lease_version = lease_version + 1` happens inside `BEGIN IMMEDIATE`, ensuring only one worker gets version N
- **Atomic version check during write**: `UPDATE ... WHERE lease_version = ?` verifies the worker still holds authority
- **No TOCTOU races**: The version check is INSIDE the UPDATE's WHERE clause, not a separate SELECT

This eliminates ALL race conditions, including the edge case where Worker A passes local checks but Worker B has already incremented the version.

### 2. **Weekly Archive Partitions (vs Daily/Monthly)**

**Trade-off analysis**:
- **Daily**: More precise retention (delete exactly 7 days old), but 365 partitions/year adds overhead
- **Weekly**: Balances precision (7-day retention = 1 week partition) with lower overhead (52 partitions/year)
- **Monthly**: Too coarse (7-day retention would delete 1-30 day old jobs depending on cleanup timing)

**Chosen**: Weekly partitions provide sufficient precision for common retention policies (7, 14, 30, 90 days) without daily partition overhead.

### 3. **Heartbeat Settings: 30s interval, threshold=3**

**Analysis**:
- **30s interval**: Detects issues within 90 seconds (3 failures × 30s)
- **Threshold=3**: Tolerates ~90s of transient database locks without abandoning
- **Total recovery time**: ~90-120s (heartbeat detection + lease expiration buffer)

**Why not more aggressive?**
- Threshold=2: Only 60s tolerance, might abandon on brief SQLITE_BUSY locks
- Threshold=1: No tolerance for transient failures (too fragile)

**Why not more lenient?**
- Longer interval (60s+): Slower issue detection, wastes more work on dead workers
- Higher threshold (5+): Takes 2.5+ minutes to detect persistent failures

### 4. **No Cooperative Cancellation**

**Decision**: Jobs do NOT check `lease_ctx.is_valid` during execution.

**Rationale**:
- **Simpler**: Job functions don't need to be cancellation-aware
- **Version check is sufficient**: The atomic version check in `mark_completed()` is the ONLY guard needed
- **Work continues but results are discarded**: Thread executes to completion, but version mismatch prevents result writes

**Trade-off**: Wasted work on abandoned jobs. This is acceptable for single-server deployments where lease loss is rare (requires persistent heartbeat failures or process crash).

**When to add cooperative cancellation**: If jobs are very expensive (minutes-hours) AND heartbeat failures are common, add periodic `if not lease_ctx.is_valid: raise Abandoned()` checks.

### 5. **Smaller Cleanup Batches (500 vs 1000)**

**Reasoning**:
- **Lower blocking time**: Smaller transactions hold locks for less time
- **Better interleaving**: Other writes can complete between cleanup batches
- **Sufficient throughput**: 500 jobs/batch × 0.05s sleep = ~10k jobs/sec cleanup rate

**SQLite write throughput**: With BEGIN IMMEDIATE serialization, smaller batches reduce contention at the cost of slightly longer total cleanup time.

### 6. **Retry Logic in DatabaseManager**

Added automatic retry on `SQLITE_BUSY` with exponential backoff (0.1s, 0.2s, 0.3s). This handles brief write contention without exposing retry logic to callers.

---

## What I Changed

### 1. **Clarified Version Check Semantics**
Added step-by-step race condition trace in `mark_completed()` comments to PROVE the version check eliminates TOCTOU races. The key insight: version check is INSIDE the atomic UPDATE, not a separate SELECT.

### 2. **Weekly Archive Partitions (from Daily)**
Daily partitions are over-engineered for 7-90 day retention. Weekly partitions provide the same effective precision (you don't need to delete jobs at exactly 7 days + 0 hours) with lower overhead.

### 3. **No Cooperative Cancellation by Default**
Simpler design: version check is sufficient for correctness. Cooperative cancellation is an optimization that requires job functions to be cancellation-aware, adding complexity for single-server use cases where lease loss is rare.

### 4. **Smaller Cleanup Batches (500 vs 1000)**
Reduces blocking time for concurrent writes. The sleep time (0.05s) is sufficient to yield to other operations.

### 5. **Retry Logic in DatabaseManager**
Handles brief `SQLITE_BUSY` errors transparently with exponential backoff. This is a common pattern for SQLite applications under light contention.

### 6. **Cleanup Interval: 12 hours (from 6)**
Twice-daily cleanup is sufficient for 7-day retention. More frequent cleanup just adds unnecessary database load.

### 7. **Performance Metrics Table**
Added optional table for tracking throughput metrics (jobs/sec, p95 latency, queue depth). This is useful for capacity planning but not required for correctness.

---

## What I Kept

1. **Three-layer architecture** - Clean separation of concerns
2. **Lease-based concurrency** - Correct primitive for work claiming
3. **Version counter as authority** - This is the KEY insight from your design
4. **Heartbeat mechanism** - Necessary for long-running jobs
5. **Archive-before-delete cleanup** - Avoids lock contention
6. **WAL mode + configurable timeouts** - Proper SQLite configuration
7. **Exponential backoff with jitter** - Production-ready retry logic
8. **Dead letter queue** - Essential for debugging permanent failures
9. **Job history with event types** - Critical observability
10. **Graceful shutdown** - Lets in-flight jobs complete

---

## Open Questions

### 1. **SQLite Write Throughput Ceiling**

SQLite serializes writes (`BEGIN IMMEDIATE`). At high completion rates (>100/sec), this WILL bottleneck.

**Mitigation options**:
- **Batch result writes**: Accumulate N results, write in single transaction (trades latency for throughput)
- **Move to PostgreSQL**: Removes serialization bottleneck (but adds deployment complexity)
- **Accept the limit**: For single-server deployments, 100 jobs/sec = 8.6M jobs/day (sufficient?)

**Question for you**: What's your expected peak job completion rate?

### 2. **Archive Retention Policy**

Current design: Archives grow forever, only jobs table is cleaned.

**Options**:
1. **Add archive cleanup**: Delete archives older than 90 days (add to cleanup loop)
2. **Export to external system**: Assume archives are periodically exported to data warehouse
3. **Partition rotation**: Drop oldest weekly partitions (simplest)

**Question for you**: Should archives be retained forever, or deleted after N days?

### 3. **Timeout Enforcement Strength**

Current approach: Timeout abandons lease (stops result writes) but doesn't kill the thread.

**Trade-offs**:
- **Current (daemon thread)**: Simple, but timed-out jobs continue consuming CPU/memory
- **Thread interruption**: Can interrupt `time.sleep()` but not arbitrary code
- **Subprocess execution**: Hard kills work, but adds IPC complexity (pickle overhead, no shared memory)

**Question for you**: Are timed-out jobs guaranteed to eventually complete, or could they hang forever (e.g., network calls without timeouts)? If the latter, subprocess execution may be required.

---

## Convergence Status

**ITERATING** - The core design (version-based lease authority) is SOLID, but operational questions remain:

1. **SQLite write throughput**: Need to know expected load to confirm SQLite is sufficient
2. **Archive retention**: Need to decide on retention policy (forever vs cleanup)
3. **Timeout killing**: Need to know if jobs can hang forever (affects timeout design)

These are NOT design flaws, but deployment considerations that affect parameter tuning.

---

## PROMPT_FOR_CRITIC:

**Primary question**: Verify my race condition analysis for the version-based lease authority:

**Scenario**: Network partition causes Worker A to lose heartbeat, lease expires, Worker B claims job (version increments), Worker B completes, Worker A resumes.

**My claim**: Worker A's `mark_completed()` call will have `cursor.rowcount = 0` because:
1. Worker A executes: `UPDATE jobs SET ... WHERE lease_version = 5`
2. SQLite evaluates WHERE clause against current state: `lease_version = 6` (Worker B updated it)
3. WHERE condition `6 = 5` is FALSE
4. Zero rows match, `cursor.rowcount = 0`

**Verification needed**: Is this trace correct? Specifically:
- Does SQLite's `BEGIN IMMEDIATE` guarantee that Worker B's version increment is visible to Worker A's subsequent UPDATE?
- Is there any edge case where both workers could see `rowcount = 1` due to isolation levels or read/write ordering?

**Secondary question**: Should we add **cooperative cancellation** (jobs periodically check `lease_ctx.is_valid`)? 

**Trade-off**:
- **Pro**: Stops wasted work on abandoned jobs
- **Con**: Requires job functions to be cancellation-aware (check flag in loops)
- **My position**: Not needed for single-server deployments where lease loss is rare (only happens on persistent heartbeat failures)

Do you agree, or is there a correctness issue I'm missing?

**Convergence Signal:** ITERATING

### 🟣 Agent B

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

-- Daily archive partitions for precise retention control
CREATE TABLE job_archive (
    job_id TEXT PRIMARY KEY,
    task_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    completed_at REAL NOT NULL,
    archive_date TEXT NOT NULL,  -- Format: YYYY-MM-DD for daily partitions
    result_summary TEXT,
    error_message TEXT,
    retry_count INTEGER,
    execution_duration_seconds REAL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
);

CREATE INDEX idx_archive_date ON job_archive(archive_date, completed_at);
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
    date_cleaned TEXT  -- YYYY-MM-DD for daily tracking
);

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
                 cleanup_interval_hours: int = 24,
                 cleanup_batch_size: int = 1000,
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
            cleanup_interval_hours: Hours between cleanup runs (24h = daily)
            cleanup_batch_size: Number of jobs to delete per transaction (1000 = optimal throughput)
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
        
        SQLite WAL MODE + BEGIN IMMEDIATE GUARANTEES:
        - BEGIN IMMEDIATE acquires a write lock immediately
        - All subsequent operations see a consistent snapshot
        - The version increment is atomic with the write lock
        - Other workers CANNOT read the old version after COMMIT
        
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
        
        Step 5 trace WITH SQLite WAL isolation:
        - Worker A calls mark_completed with lease_ctx.lease_version = 5
        - BEGIN IMMEDIATE acquires write lock
        - UPDATE jobs SET ... WHERE lease_version = 5
        - SQLite evaluates WHERE clause:
          - Current DB state: lease_version = 6 (Worker B committed)
          - WHERE 6 = 5 → FALSE
          - cursor.rowcount = 0 (no rows matched)
        - Worker A's write is REJECTED atomically
        
        KEY GUARANTEE: WAL mode ensures that once Worker B COMMITs version=6,
        ALL subsequent BEGIN IMMEDIATE transactions (including Worker A's)
        will see version=6, not version=5. There is NO isolation level
        where Worker A can see stale data after COMMIT.
        
        This is because:
        1. WAL mode writes are append-only to the WAL file
        2. BEGIN IMMEDIATE blocks until all prior COMMITs are visible
        3. The version check happens INSIDE the atomic UPDATE WHERE clause
        
        This eliminates ALL race conditions, including TOCTOU.
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
        Archive and delete old jobs with daily partition granularity.
        
        Daily partitions provide precise retention control (delete exactly
        7-day old jobs) with manageable overhead (~365 partitions/year).
        """
        cutoff_time = time.time() - (retention_days * 86400)
        start_time = time.time()
        total_archived = 0
        total_deleted = 0
        
        # Determine partition to clean (YYYY-MM-DD format)
        cutoff_date = datetime.fromtimestamp(cutoff_time).strftime('%Y-%m-%d')
        
        # Phase 1: Archive terminal jobs in batches
        while True:
            with self.db.get_connection() as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    
                    cursor = conn.execute("""
                        INSERT OR IGNORE INTO job_archive 
                        (job_id, task_name, status, created_at, completed_at, 
                         archive_date, result_summary, error_message, retry_count,
                         execution_duration_seconds)
                        SELECT 
                            job_id, 
                            task_name, 
                            status, 
                            created_at, 
                            completed_at,
                            date(completed_at, 'unixepoch'),
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
                            WHERE archive_date <= ?
                            LIMIT ?
                        )
                    """, (cutoff_date, batch_size))
                    
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
                    (key, last_cleanup_at, records_cleaned, cleanup_duration_seconds, date_cleaned)
                    VALUES ('last_cleanup', ?, ?, ?, ?)
                """, (time.time(), total_deleted + history_deleted, duration, cutoff_date))
                conn.commit()
            except Exception:
                pass
        
        if total_deleted > 0 or history_deleted > 0:
            logging.info(
                f"Cleanup: archived {total_archived}, deleted {total_deleted} jobs, "
                f"{history_deleted} history entries in {duration:.2f}s (cutoff: {cutoff_date})"
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
        
        Automatically retries on SQLITE_BUSY for write operations.
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
                
                # Archive table with daily partitions
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS job_archive (
                        job_id TEXT PRIMARY KEY,
                        task_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        created_at REAL NOT NULL,
                        completed_at REAL NOT NULL,
                        archive_date TEXT NOT NULL,
                        result_summary TEXT,
                        error_message TEXT,
                        retry_count INTEGER,
                        execution_duration_seconds REAL,
                        FOREIGN KEY (job_id) REFERENCES jobs(job_id) ON DELETE CASCADE
                    )
                """)
                
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_archive_date
                    ON job_archive(archive_date, completed_at)
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
                        date_cleaned TEXT
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
    cleanup_interval_hours=24,  # Daily cleanup
    cleanup_batch_size=1000,  # Optimal throughput
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

## What I Improved

### 1. **Strengthened Race Condition Analysis with SQLite WAL Isolation Guarantees**

Your design correctly identified that version checks prevent race conditions, but the explanation needed strengthening on **why SQLite guarantees this works**. I added explicit documentation of WAL mode + BEGIN IMMEDIATE semantics:

- BEGIN IMMEDIATE blocks until all prior COMMITs are visible
- Once Worker B commits version=6, ALL subsequent transactions see version=6
- There is NO isolation level where Worker A can see stale version=5 after COMMIT
- The version check happens INSIDE the atomic UPDATE WHERE clause (not separate SELECT)

This eliminates any concerns about TOCTOU or read/write races.

### 2. **Changed Archive Partitions from Weekly to Daily**

**Your reasoning**: Weekly partitions balance precision with overhead.

**My concern**: For 7-day retention policies, weekly partitions are too coarse:
- If cleanup runs on day 8, it would delete jobs from days 1-7 (correct)
- But if cleanup runs on day 6, it might not delete anything (waiting for week boundary)
- Or it deletes jobs from days 1-14 (deleting too much)

**Daily partitions** provide:
- Precise retention: Delete exactly jobs completed before day N
- Manageable overhead: ~365 partitions/year is acceptable for SQLite
- Predictable behavior: No ambiguity about what gets deleted

The overhead difference (52 vs 365 partitions) is negligible for SQLite with proper indexing.

### 3. **Increased Cleanup Batch Size from 500 to 1000**

**Your reasoning**: Smaller batches reduce lock holding time.

**My analysis**: 
- SQLite with BEGIN IMMEDIATE serializes writes anyway
- Smaller batches = more transactions = more overhead
- 1000-job batches with 0.05s sleep = ~20k jobs/sec cleanup throughput
- Lock holding time for 1000 deletions is still < 100ms (acceptable)

For single-server SQLite, maximizing batch size (within reason) improves throughput without materially impacting contention.

### 4. **Changed Cleanup Interval from 12 hours to 24 hours**

**Your reasoning**: Twice-daily cleanup handles 7-day retention.

**My reasoning**: 
- Daily retention precision means daily cleanup is sufficient
- Running at consistent time (e.g., 2am) is easier to reason about
- Lower database load (half the cleanup operations)
- Still well within margin for 7-day retention (cleanup lag of <24h is acceptable)

### 5. **Clarified Missing `started_at` Field in Archive**

Your schema was missing the `started_at` field needed to calculate `execution_duration_seconds`. I kept the calculated field but added a comment that it requires `started_at` to be populated first.

---

## What I Kept

1. **Version-based lease authority** - This is the core insight and is CORRECT
2. **Three-layer architecture** - Clean separation of concerns
3. **Heartbeat mechanism with failure threshold** - Proper long-running job handling
4. **No cooperative cancellation by default** - Correct simplification for single-server
5. **WAL mode + configurable timeouts** - Proper SQLite configuration
6. **Exponential backoff with jitter** - Production-ready retry logic
7. **Dead letter queue** - Essential for debugging
8. **Job history with version tracking** - Critical observability
9. **Archive-before-delete cleanup pattern** - Avoids contention
10. **All data models and exception classes** - Well-designed

---

## Remaining Concerns

### 1. **SQLite Write Throughput Ceiling**

Your design correctly identifies this as a bottleneck. At high completion rates (>100/sec), BEGIN IMMEDIATE serialization will limit throughput.

**Critical question**: What's the expected peak job completion rate? If it's <100/sec, SQLite is fine. If it's >500/sec, you'll need to consider:
- Batching result writes (accumulate N results, write in one transaction)
- Moving to PostgreSQL (removes serialization bottleneck)

### 2. **Archive Retention Policy**

Current design: Archives grow forever, only jobs table is cleaned.

**Missing specification**: Should archives be:
1. Retained forever (assume external export process)?
2. Deleted after N days (add archive cleanup to cleanup loop)?
3. Partition rotation (drop oldest partitions)?

This needs to be decided based on operational requirements.

### 3. **Timeout Killing Behavior**

Current approach: Daemon thread + timeout check. Timed-out jobs continue executing (wasting CPU/memory) but results are discarded.

**Trade-off**:
- **Current (daemon thread)**: Simple, but hung jobs (e.g., network call without timeout) will consume resources forever
- **Subprocess execution**: Hard kills work, but adds IPC complexity and prevents shared memory

**Question**: Are job functions guaranteed to eventually complete, or could they hang indefinitely? If the latter, subprocess execution may be required for resource cleanup.

### 4. **Missing Index on job_archive.archive_date Alone**

Your current index is:
```sql
CREATE INDEX idx_archive_date ON job_archive(archive_date, completed_at);
```

The cleanup query uses:
```sql
WHERE archive_date <= ?
```

The composite index `(archive_date, completed_at)` is suboptimal for this query because SQLite can only use the first column for range scans. Consider:
```sql
CREATE INDEX idx_archive_date ON job_archive(archive_date);
```

This would be more efficient for cleanup queries.

---

## Convergence Status

**ITERATING** - The core design is sound, but needs clarification on:

1. **Archive partition granularity**: Daily (my preference) vs Weekly (your preference) - needs decision based on retention precision requirements
2. **Archive retention policy**: Forever vs cleanup after N days
3. **Expected throughput**: Need to validate SQLite is sufficient for workload
4. **Timeout killing**: Need to decide if hung jobs are possible (affects timeout design)

These are NOT design flaws, but **operational requirements that need specification** before finalizing parameters.

---

## PROMPT_FOR_ARCHITECT:

**Primary question**: Verify my analysis on **archive partition granularity**:

**My claim**: Daily partitions are necessary for precise 7-day retention. Weekly partitions cause ambiguous behavior:
- If retention_days=7 and cleanup runs on day 8, which week do you delete?
- Week 1 (days 1-7) would be correct
- But what if cleanup runs on day 6? Do you delete nothing, or delete week 0 (days -6 to 0)?

**Your claim**: Weekly partitions balance precision with overhead.

**Specific question**: How does your weekly partition logic handle the case where `retention_days=7` and cleanup runs on day 6 vs day 8? Walk me through the partition calculation to show it's precise.

**Secondary question**: Confirm my **SQLite isolation guarantee** understanding:

**My claim**: SQLite WAL mode + BEGIN IMMEDIATE guarantees that:
1. Worker B commits version=6
2. Worker A calls BEGIN IMMEDIATE (blocks until Worker B's COMMIT is visible)
3. Worker A's UPDATE WHERE lease_version=5 sees version=6
4. WHERE clause fails, rowcount=0

Is this correct, or is there an edge case where Worker A could see stale version=5 due to isolation levels or snapshot reads?

**If this is incorrect**, the entire version-based lease authority design has a race condition.

**Convergence Signal:** ITERATING

---

