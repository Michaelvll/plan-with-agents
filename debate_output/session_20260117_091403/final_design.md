# Final Agreed Design

**Task:** Design a simple task queue system with priority support

**Status:** debating

---

## Design

# Priority Task Queue System with Bounded Memory & Smart Cleanup

## Architecture Overview

A production-ready priority task queue system with in-memory storage, automatic memory management, and flexible retry policies. Key improvements: bounded memory through automatic cleanup, heap health monitoring, and simplified worker API.

## Core Components

### 1. Task Model
```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any, Dict
from datetime import datetime, timedelta
import uuid

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class Task:
    id: str
    payload: Any
    priority: TaskPriority
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    sequence: int = 0
    worker_id: Optional[str] = None
    # Retry policy metadata
    retry_policy: Optional[Dict[str, Any]] = None
    
    def is_terminal(self) -> bool:
        """Check if task is in a terminal state"""
        return self.status in {TaskStatus.COMPLETED, TaskStatus.FAILED, 
                               TaskStatus.CANCELLED}
    
    def age_seconds(self) -> float:
        """Get task age in seconds"""
        return (datetime.utcnow() - self.created_at).total_seconds()
    
    def time_in_progress_seconds(self) -> Optional[float]:
        """Get time spent in progress (None if not started)"""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()
```

### 2. Heap Health Monitor
```python
@dataclass
class HeapHealth:
    """Track heap efficiency for automatic maintenance"""
    total_entries: int = 0
    valid_entries: int = 0
    invalid_entries: int = 0
    last_rebuild: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def efficiency(self) -> float:
        """Percentage of valid entries in heap"""
        if self.total_entries == 0:
            return 1.0
        return self.valid_entries / self.total_entries
    
    @property
    def should_rebuild(self) -> bool:
        """Rebuild if efficiency drops below 50% and heap has 100+ entries"""
        return (self.efficiency < 0.5 and self.total_entries >= 100)
```

### 3. Priority Queue Storage with Auto-Cleanup
```python
import heapq
import threading
from collections import defaultdict
from typing import Set, Optional, Tuple

class PriorityTaskQueue:
    def __init__(self, 
                 max_queue_size: Optional[int] = None,
                 task_retention_seconds: int = 3600,
                 cleanup_interval_seconds: int = 300):
        """
        Args:
            max_queue_size: Max pending tasks (None = unlimited)
            task_retention_seconds: How long to keep completed/failed tasks (default 1hr)
            cleanup_interval_seconds: How often to run cleanup (default 5min)
        """
        self._lock = threading.RLock()
        self._heap = []
        self._tasks: Dict[str, Task] = {}
        self._heap_task_ids: Set[str] = set()
        self._counter = 0
        self._max_queue_size = max_queue_size
        self._task_retention = timedelta(seconds=task_retention_seconds)
        self._cleanup_interval = timedelta(seconds=cleanup_interval_seconds)
        self._last_cleanup = datetime.utcnow()
        self._heap_health = HeapHealth()
        
    def enqueue(self, payload: Any, priority: TaskPriority = TaskPriority.MEDIUM,
                max_retries: int = 3, retry_policy: Optional[Dict] = None) -> str:
        """Add task to queue, return task ID"""
        with self._lock:
            # Run cleanup opportunistically
            self._maybe_cleanup()
            
            # Check queue size limit (only count PENDING)
            pending_count = sum(1 for t in self._tasks.values() 
                              if t.status == TaskStatus.PENDING)
            if self._max_queue_size and pending_count >= self._max_queue_size:
                raise QueueFullError(f"Queue at capacity: {self._max_queue_size}")
            
            task = Task(
                id=str(uuid.uuid4()),
                payload=payload,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                max_retries=max_retries,
                sequence=self._counter,
                retry_policy=retry_policy
            )
            self._tasks[task.id] = task
            self._add_to_heap(task)
            return task.id
    
    def _add_to_heap(self, task: Task):
        """Add task to heap with health tracking"""
        heapq.heappush(self._heap, (-task.priority.value, task.sequence, task.id))
        self._heap_task_ids.add(task.id)
        self._counter += 1
        self._heap_health.total_entries += 1
        self._heap_health.valid_entries += 1
    
    def dequeue(self, worker_id: Optional[str] = None) -> Optional[Task]:
        """Get highest priority pending task"""
        with self._lock:
            self._maybe_cleanup()
            
            found_valid = False
            while self._heap:
                _, _, task_id = heapq.heappop(self._heap)
                self._heap_task_ids.discard(task_id)
                self._heap_health.total_entries -= 1
                
                task = self._tasks.get(task_id)
                
                if not task or task.status != TaskStatus.PENDING:
                    # Invalid entry, continue searching
                    continue
                
                # Found valid task
                found_valid = True
                self._heap_health.valid_entries -= 1
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.utcnow()
                task.updated_at = datetime.utcnow()
                task.worker_id = worker_id
                
                # Check if heap needs rebuilding
                if self._heap_health.should_rebuild:
                    self._rebuild_heap()
                
                return task
            
            # Heap exhausted
            if not found_valid and self._heap_health.total_entries > 0:
                # All remaining entries are invalid, rebuild
                self._rebuild_heap()
            
            return None
    
    def _rebuild_heap(self):
        """Rebuild heap with only valid pending tasks"""
        with self._lock:
            valid_tasks = [t for t in self._tasks.values() 
                          if t.status == TaskStatus.PENDING]
            
            self._heap.clear()
            self._heap_task_ids.clear()
            
            for task in valid_tasks:
                heapq.heappush(self._heap, 
                             (-task.priority.value, task.sequence, task.id))
                self._heap_task_ids.add(task.id)
            
            self._heap_health = HeapHealth(
                total_entries=len(self._heap),
                valid_entries=len(self._heap),
                invalid_entries=0,
                last_rebuild=datetime.utcnow()
            )
    
    def _maybe_cleanup(self):
        """Run cleanup if enough time has passed"""
        now = datetime.utcnow()
        if now - self._last_cleanup > self._cleanup_interval:
            self._cleanup_old_tasks()
            self._last_cleanup = now
    
    def _cleanup_old_tasks(self):
        """Remove old terminal tasks to prevent unbounded memory growth"""
        with self._lock:
            now = datetime.utcnow()
            cutoff = now - self._task_retention
            
            to_delete = []
            for task_id, task in self._tasks.items():
                if task.is_terminal() and task.updated_at < cutoff:
                    to_delete.append(task_id)
            
            for task_id in to_delete:
                del self._tasks[task_id]
                # Note: task might still be in heap, but will be skipped during dequeue
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID (returns reference for internal use)"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def update_status(self, task_id: str, status: TaskStatus, 
                     error_message: Optional[str] = None) -> Tuple[bool, bool]:
        """
        Update task status with state validation.
        Returns: (success, was_retried)
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")
            
            if not self._is_valid_transition(task.status, status):
                raise InvalidStateTransitionError(
                    f"Cannot transition from {task.status.value} to {status.value}"
                )
            
            task.status = status
            task.updated_at = datetime.utcnow()
            
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
                return (True, False)
            
            elif status == TaskStatus.FAILED:
                task.error_message = error_message
                task.completed_at = datetime.utcnow()
                task.retry_count += 1
                
                # Check if should retry (automatic based on max_retries)
                if task.retry_count < task.max_retries:
                    # Reset for retry
                    task.status = TaskStatus.PENDING
                    task.started_at = None
                    task.completed_at = None
                    task.worker_id = None
                    
                    # Add back to heap if not already present
                    if task_id not in self._heap_task_ids:
                        self._add_to_heap(task)
                    
                    return (True, True)
                return (True, False)
            
            elif status == TaskStatus.CANCELLED:
                task.completed_at = datetime.utcnow()
                return (True, False)
            
            return (True, False)
    
    def _is_valid_transition(self, from_status: TaskStatus, 
                            to_status: TaskStatus) -> bool:
        """Validate state machine transitions"""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, 
                                    TaskStatus.CANCELLED},
            TaskStatus.FAILED: set(),
            TaskStatus.COMPLETED: set(),
            TaskStatus.CANCELLED: set(),
        }
        return to_status in valid_transitions.get(from_status, set())
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status == TaskStatus.PENDING:
                try:
                    self.update_status(task_id, TaskStatus.CANCELLED)
                    return True
                except (TaskNotFoundError, InvalidStateTransitionError):
                    return False
            return False
    
    def requeue_task(self, task_id: str, reset_retries: bool = False) -> bool:
        """
        Manually requeue a task (for worker failures or manual retry).
        Only works for IN_PROGRESS tasks.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != TaskStatus.IN_PROGRESS:
                return False
            
            task.status = TaskStatus.PENDING
            task.started_at = None
            task.worker_id = None
            task.updated_at = datetime.utcnow()
            
            if reset_retries:
                task.retry_count = 0
                task.error_message = None
            
            if task_id not in self._heap_task_ids:
                self._add_to_heap(task)
            
            return True
    
    def get_queue_stats(self) -> dict:
        """Get comprehensive queue statistics"""
        with self._lock:
            status_counts = defaultdict(int)
            priority_counts = defaultdict(int)
            
            for task in self._tasks.values():
                status_counts[task.status.value] += 1
                if task.status == TaskStatus.PENDING:
                    priority_counts[task.priority.name] += 1
            
            return {
                "total_tasks": len(self._tasks),
                "pending": status_counts[TaskStatus.PENDING.value],
                "in_progress": status_counts[TaskStatus.IN_PROGRESS.value],
                "completed": status_counts[TaskStatus.COMPLETED.value],
                "failed": status_counts[TaskStatus.FAILED.value],
                "cancelled": status_counts[TaskStatus.CANCELLED.value],
                "pending_by_priority": dict(priority_counts),
                "heap_size": len(self._heap),
                "heap_efficiency": self._heap_health.efficiency,
                "last_cleanup": self._last_cleanup.isoformat(),
                "last_heap_rebuild": self._heap_health.last_rebuild.isoformat()
            }
    
    def force_cleanup(self) -> dict:
        """Manually trigger cleanup and return results"""
        with self._lock:
            before_count = len(self._tasks)
            self._cleanup_old_tasks()
            after_count = len(self._tasks)
            
            before_heap = len(self._heap)
            self._rebuild_heap()
            after_heap = len(self._heap)
            
            return {
                "tasks_removed": before_count - after_count,
                "heap_entries_removed": before_heap - after_heap,
                "tasks_remaining": after_count,
                "heap_size": after_heap
            }

# Custom exceptions
class QueueFullError(Exception):
    pass

class TaskNotFoundError(Exception):
    pass

class InvalidStateTransitionError(Exception):
    pass
```

### 4. Task Queue Manager Interface
```python
class TaskQueueManager:
    """High-level interface for task queue operations"""
    
    def __init__(self, 
                 max_queue_size: Optional[int] = None,
                 task_retention_seconds: int = 3600,
                 cleanup_interval_seconds: int = 300):
        """
        Args:
            max_queue_size: Max pending tasks (None = unlimited)
            task_retention_seconds: Keep terminal tasks for this long (default 1hr)
            cleanup_interval_seconds: Run cleanup every N seconds (default 5min)
        """
        self.queue = PriorityTaskQueue(
            max_queue_size=max_queue_size,
            task_retention_seconds=task_retention_seconds,
            cleanup_interval_seconds=cleanup_interval_seconds
        )
    
    def submit_task(self, 
                   payload: Any, 
                   priority: str = "medium",
                   max_retries: int = 3,
                   retry_policy: Optional[Dict] = None) -> dict:
        """
        Submit a new task.
        
        Args:
            payload: Task data
            priority: "low", "medium", "high", or "critical"
            max_retries: Max automatic retries (0 = no retry)
            retry_policy: Optional metadata for worker-side retry logic
                         e.g., {"backoff": "exponential", "max_delay": 300}
        """
        try:
            priority_enum = TaskPriority[priority.upper()]
        except KeyError:
            raise ValueError(f"Invalid priority: {priority}. "
                           f"Valid: {[p.name.lower() for p in TaskPriority]}")
        
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        
        try:
            task_id = self.queue.enqueue(payload, priority_enum, max_retries, 
                                        retry_policy)
            return {
                "task_id": task_id, 
                "status": "pending",
                "priority": priority
            }
        except QueueFullError as e:
            return {"error": str(e), "status": "rejected"}
    
    def get_next_task(self, worker_id: Optional[str] = None) -> Optional[dict]:
        """
        Worker polls for next task.
        Returns None if queue is empty.
        """
        task = self.queue.dequeue(worker_id=worker_id)
        if task:
            return {
                "task_id": task.id,
                "payload": task.payload,
                "priority": task.priority.name,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries,
                "retry_policy": task.retry_policy
            }
        return None
    
    def complete_task(self, task_id: str, success: bool = True, 
                     error: Optional[str] = None) -> dict:
        """
        Mark task as completed or failed.
        Automatic retry happens based on max_retries.
        """
        try:
            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            success_flag, was_retried = self.queue.update_status(
                task_id, status, error
            )
            
            return {
                "task_id": task_id,
                "status": status.value,
                "retried": was_retried
            }
        except (TaskNotFoundError, InvalidStateTransitionError) as e:
            return {"error": str(e)}
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get detailed task status"""
        task = self.queue.get_task(task_id)
        if not task:
            return None
        
        return {
            "task_id": task.id,
            "status": task.status.value,
            "priority": task.priority.name,
            "created_at": task.created_at.isoformat(),
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
            "error_message": task.error_message,
            "retry_count": task.retry_count,
            "max_retries": task.max_retries,
            "worker_id": task.worker_id,
            "age_seconds": task.age_seconds(),
            "time_in_progress": task.time_in_progress_seconds()
        }
    
    def cancel_task(self, task_id: str) -> dict:
        """Cancel a pending task"""
        success = self.queue.cancel_task(task_id)
        return {
            "task_id": task_id,
            "cancelled": success,
            "message": "Task cancelled" if success 
                      else "Task not pending or not found"
        }
    
    def requeue_task(self, task_id: str, reset_retries: bool = False) -> dict:
        """
        Manually requeue an in-progress task.
        Useful for worker failure recovery.
        """
        success = self.queue.requeue_task(task_id, reset_retries)
        return {
            "task_id": task_id,
            "requeued": success,
            "reset_retries": reset_retries,
            "message": "Task requeued" if success 
                      else "Task not in-progress or not found"
        }
    
    def get_statistics(self) -> dict:
        """Get comprehensive queue statistics"""
        return self.queue.get_queue_stats()
    
    def force_maintenance(self) -> dict:
        """
        Manually trigger cleanup and heap rebuild.
        Useful for testing or emergency maintenance.
        """
        return self.queue.force_cleanup()
```

### 5. Health Monitor & Supervisor Utilities
```python
class TaskSupervisor:
    """Monitor and recover stuck tasks"""
    
    def __init__(self, manager: TaskQueueManager, 
                 stuck_threshold_seconds: int = 300):
        self.manager = manager
        self.stuck_threshold = stuck_threshold_seconds
    
    def check_stuck_tasks(self) -> list[dict]:
        """Find tasks stuck in IN_PROGRESS state"""
        stats = self.manager.get_statistics()
        stuck_tasks = []
        
        # Would need to iterate tasks - simplified here
        # In production, maintain a separate index of in-progress tasks
        
        return stuck_tasks
    
    def requeue_stuck_tasks(self) -> dict:
        """Automatically requeue stuck tasks"""
        stuck = self.check_stuck_tasks()
        requeued = []
        
        for task_info in stuck:
            result = self.manager.requeue_task(task_info['task_id'])
            if result['requeued']:
                requeued.append(task_info['task_id'])
        
        return {
            "stuck_tasks_found": len(stuck),
            "tasks_requeued": len(requeued),
            "task_ids": requeued
        }
```

## Usage Examples

### Basic Worker (Automatic Retry)
```python
# Initialize with bounded memory
manager = TaskQueueManager(
    max_queue_size=10000,
    task_retention_seconds=3600,  # Keep completed tasks for 1 hour
    cleanup_interval_seconds=300   # Cleanup every 5 minutes
)

# Submit tasks with automatic retry
task1 = manager.submit_task(
    {"action": "send_email", "to": "user@example.com"}, 
    priority="high",
    max_retries=3  # Will retry up to 3 times automatically
)

# Simple worker loop - retry is automatic
worker_id = "worker-1"
while True:
    task = manager.get_next_task(worker_id=worker_id)
    if task:
        try:
            result = process(task['payload'])
            manager.complete_task(task['task_id'], success=True)
        except Exception as e:
            # Automatic retry based on max_retries
            manager.complete_task(task['task_id'], success=False, error=str(e))
    else:
        time.sleep(1)
```

### Advanced Worker with Retry Policy Metadata
```python
# Submit task with retry policy hints for worker
task = manager.submit_task(
    {"action": "api_call", "url": "https://api.example.com"},
    priority="medium",
    max_retries=5,
    retry_policy={
        "backoff": "exponential",
        "base_delay": 2,
        "max_delay": 60,
        "retryable_errors": ["timeout", "rate_limit"]
    }
)

# Worker interprets retry_policy for smart delays
def smart_worker():
    while True:
        task = manager.get_next_task(worker_id="smart-worker")
        if not task:
            time.sleep(1)
            continue
        
        try:
            result = process(task['payload'])
            manager.complete_task(task['task_id'], success=True)
        except Exception as e:
            # Mark as failed (automatic retry happens in queue)
            manager.complete_task(task['task_id'], success=False, error=str(e))
            
            # Worker can implement smart delay before next poll
            if task.get('retry_policy'):
                policy = task['retry_policy']
                if policy.get('backoff') == 'exponential':
                    delay = min(
                        policy['base_delay'] ** task['retry_count'],
                        policy['max_delay']
                    )
                    time.sleep(delay)
```

### Monitoring & Maintenance
```python
# Check queue health
stats = manager.get_statistics()
print(f"Heap efficiency: {stats['heap_efficiency']:.2%}")
print(f"Pending tasks: {stats['pending']}")
print(f"Tasks in progress: {stats['in_progress']}")

# Force maintenance if needed
if stats['heap_efficiency'] < 0.3:
    result = manager.force_maintenance()
    print(f"Cleaned up {result['tasks_removed']} old tasks")
    print(f"Removed {result['heap_entries_removed']} stale heap entries")

# Supervisor for stuck task recovery
supervisor = TaskSupervisor(manager, stuck_threshold_seconds=300)
recovery = supervisor.requeue_stuck_tasks()
print(f"Requeued {recovery['tasks_requeued']} stuck tasks")
```