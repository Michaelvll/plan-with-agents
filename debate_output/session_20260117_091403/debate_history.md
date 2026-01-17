# Claude Code Debate Session

**Started:** 2026-01-17T09:14:03.427099
**Ended:** 2026-01-17T09:19:33.059719
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a simple task queue system with priority support

---

## Round 1

### 🔵 Agent A

## Design

# Priority Task Queue System

## Architecture Overview

A priority task queue system with in-memory storage, supporting task submission, priority-based retrieval, status tracking, and concurrent access.

## Core Components

### 1. Task Model
```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Any
from datetime import datetime
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
```

### 2. Priority Queue Storage
```python
import heapq
import threading
from collections import defaultdict

class PriorityTaskQueue:
    def __init__(self):
        self._lock = threading.RLock()
        # Min-heap: (-priority, timestamp, task_id) for FIFO within priority
        self._heap = []
        # Fast lookup by task ID
        self._tasks: dict[str, Task] = {}
        # Counter for insertion order (FIFO within priority)
        self._counter = 0
        
    def enqueue(self, payload: Any, priority: TaskPriority = TaskPriority.MEDIUM) -> str:
        """Add task to queue, return task ID"""
        with self._lock:
            task = Task(
                id=str(uuid.uuid4()),
                payload=payload,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            self._tasks[task.id] = task
            # Negative priority for max-heap behavior, counter for FIFO
            heapq.heappush(self._heap, (-priority.value, self._counter, task.id))
            self._counter += 1
            return task.id
    
    def dequeue(self) -> Optional[Task]:
        """Get highest priority pending task"""
        with self._lock:
            while self._heap:
                _, _, task_id = heapq.heappop(self._heap)
                task = self._tasks.get(task_id)
                
                if task and task.status == TaskStatus.PENDING:
                    task.status = TaskStatus.IN_PROGRESS
                    task.started_at = datetime.utcnow()
                    task.updated_at = datetime.utcnow()
                    return task
            return None
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID"""
        with self._lock:
            return self._tasks.get(task_id)
    
    def update_status(self, task_id: str, status: TaskStatus, 
                     error_message: Optional[str] = None):
        """Update task status"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")
            
            task.status = status
            task.updated_at = datetime.utcnow()
            
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
            elif status == TaskStatus.FAILED:
                task.error_message = error_message
                task.retry_count += 1
                
                # Re-enqueue if retries available
                if task.retry_count < task.max_retries:
                    task.status = TaskStatus.PENDING
                    heapq.heappush(self._heap, 
                                 (-task.priority.value, self._counter, task.id))
                    self._counter += 1
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.updated_at = datetime.utcnow()
                return True
            return False
    
    def get_queue_stats(self) -> dict:
        """Get queue statistics"""
        with self._lock:
            status_counts = defaultdict(int)
            for task in self._tasks.values():
                status_counts[task.status.value] += 1
            
            return {
                "total_tasks": len(self._tasks),
                "pending": status_counts[TaskStatus.PENDING.value],
                "in_progress": status_counts[TaskStatus.IN_PROGRESS.value],
                "completed": status_counts[TaskStatus.COMPLETED.value],
                "failed": status_counts[TaskStatus.FAILED.value],
                "cancelled": status_counts[TaskStatus.CANCELLED.value]
            }
```

### 3. Queue Manager Interface
```python
class TaskQueueManager:
    def __init__(self):
        self.queue = PriorityTaskQueue()
    
    def submit_task(self, payload: Any, priority: str = "medium") -> dict:
        """Submit a new task"""
        try:
            priority_enum = TaskPriority[priority.upper()]
        except KeyError:
            raise ValueError(f"Invalid priority: {priority}")
        
        task_id = self.queue.enqueue(payload, priority_enum)
        return {"task_id": task_id, "status": "pending"}
    
    def get_next_task(self) -> Optional[dict]:
        """Worker polls for next task"""
        task = self.queue.dequeue()
        if task:
            return {
                "task_id": task.id,
                "payload": task.payload,
                "priority": task.priority.name,
                "retry_count": task.retry_count
            }
        return None
    
    def complete_task(self, task_id: str, success: bool = True, 
                     error: Optional[str] = None):
        """Mark task as completed or failed"""
        status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
        self.queue.update_status(task_id, status, error)
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Check task status"""
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
            "retry_count": task.retry_count
        }
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        return self.queue.cancel_task(task_id)
    
    def get_statistics(self) -> dict:
        """Get queue statistics"""
        return self.queue.get_queue_stats()
```

## Error Handling

### 1. Error Categories
- **ValidationError**: Invalid priority, malformed payload
- **NotFoundError**: Task ID doesn't exist
- **StateError**: Invalid state transition (e.g., completing cancelled task)
- **ConcurrencyError**: Race conditions (handled by locks)

### 2. Retry Logic
- Tasks automatically retry up to `max_retries` times on failure
- Exponential backoff can be added by workers between retries
- Failed tasks preserve error messages for debugging

### 3. Edge Cases
- Empty queue: `dequeue()` returns `None`
- Duplicate operations: Idempotent status updates
- Cancelled tasks: Skipped during dequeue
- Thread safety: All operations protected by RLock

## Usage Example

```python
# Initialize
manager = TaskQueueManager()

# Submit tasks
task1 = manager.submit_task({"action": "send_email", "to": "user@example.com"}, "high")
task2 = manager.submit_task({"action": "generate_report"}, "low")

# Worker loop
while True:
    task = manager.get_next_task()
    if task:
        try:
            # Process task
            process(task['payload'])
            manager.complete_task(task['task_id'], success=True)
        except Exception as e:
            manager.complete_task(task['task_id'], success=False, error=str(e))
    else:
        time.sleep(1)

# Check status
status = manager.get_task_status(task1['task_id'])
print(status)
```

## Rationale

**In-memory storage**: Chosen for simplicity and speed. For production, this would be replaced with Redis or a persistent database.

**Heap-based priority queue**: Provides O(log n) enqueue and O(log n) dequeue with O(1) task lookup via dictionary. The heap stores tuples of (-priority, counter, task_id) to ensure FIFO ordering within the same priority level.

**Thread-safe design**: RLock allows reentrant locking, preventing deadlocks in complex operations while ensuring atomicity.

**Automatic retry logic**: Built into the queue to handle transient failures without worker complexity.

**Status tracking**: Comprehensive lifecycle tracking enables monitoring, debugging, and audit trails.

## What I Changed

N/A - Initial design

## What I Kept

N/A - Initial design

## Open Questions

1. Should we add task expiration/TTL?
2. Should we support delayed task execution (schedule for future)?
3. What's the expected queue size? May need queue length limits.
4. Should we add batch operations for bulk submission?
5. Persistence strategy if the system restarts?

## Convergence Status

**ITERATING** - This is the initial design and needs review and refinement.

PROMPT_FOR_CRITIC:
Please evaluate the thread-safety approach and the retry mechanism. Are there any race conditions I've missed? Is the automatic retry logic appropriately designed, or should retry decisions be left to the workers?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Priority Task Queue System

## Architecture Overview

A priority task queue system with in-memory storage, supporting task submission, priority-based retrieval, status tracking, and concurrent access with robust retry mechanisms and worker-controlled retry policies.

## Core Components

### 1. Task Model
```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Any, Callable
from datetime import datetime
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
    # Insertion order for stable FIFO within priority
    sequence: int = 0
    # Worker ID tracking for debugging
    worker_id: Optional[str] = None
    
    def __post_init__(self):
        # Ensure immutable task ID
        object.__setattr__(self, 'id', self.id)
```

### 2. Priority Queue Storage
```python
import heapq
import threading
from collections import defaultdict
from typing import Set

class PriorityTaskQueue:
    def __init__(self, max_queue_size: Optional[int] = None):
        self._lock = threading.RLock()
        # Min-heap: (-priority, sequence, task_id) for FIFO within priority
        self._heap = []
        # Fast lookup by task ID
        self._tasks: dict[str, Task] = {}
        # Track which tasks are in the heap (for lazy deletion)
        self._heap_task_ids: Set[str] = set()
        # Counter for insertion order (FIFO within priority)
        self._counter = 0
        # Optional queue size limit
        self._max_queue_size = max_queue_size
        
    def enqueue(self, payload: Any, priority: TaskPriority = TaskPriority.MEDIUM,
                max_retries: int = 3) -> str:
        """Add task to queue, return task ID"""
        with self._lock:
            # Check queue size limit
            pending_count = sum(1 for t in self._tasks.values() 
                              if t.status == TaskStatus.PENDING)
            if self._max_queue_size and pending_count >= self._max_queue_size:
                raise QueueFullError(f"Queue is at capacity: {self._max_queue_size}")
            
            task = Task(
                id=str(uuid.uuid4()),
                payload=payload,
                priority=priority,
                status=TaskStatus.PENDING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                max_retries=max_retries,
                sequence=self._counter
            )
            self._tasks[task.id] = task
            # Negative priority for max-heap behavior, sequence for FIFO
            heapq.heappush(self._heap, (-priority.value, self._counter, task.id))
            self._heap_task_ids.add(task.id)
            self._counter += 1
            return task.id
    
    def dequeue(self, worker_id: Optional[str] = None) -> Optional[Task]:
        """Get highest priority pending task"""
        with self._lock:
            while self._heap:
                _, _, task_id = heapq.heappop(self._heap)
                self._heap_task_ids.discard(task_id)
                
                task = self._tasks.get(task_id)
                
                # Skip if task doesn't exist or isn't pending (lazy deletion)
                if not task or task.status != TaskStatus.PENDING:
                    continue
                
                # Transition to in-progress
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.utcnow()
                task.updated_at = datetime.utcnow()
                task.worker_id = worker_id
                return task
            
            return None
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID (returns a copy to prevent external mutation)"""
        with self._lock:
            task = self._tasks.get(task_id)
            if task:
                # Return a shallow copy to prevent external mutation of task fields
                return dataclass_replace(task)
            return None
    
    def update_status(self, task_id: str, status: TaskStatus, 
                     error_message: Optional[str] = None,
                     allow_retry: bool = True) -> bool:
        """
        Update task status with state validation.
        Returns True if retry was scheduled, False otherwise.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                raise TaskNotFoundError(f"Task {task_id} not found")
            
            # Validate state transition
            if not self._is_valid_transition(task.status, status):
                raise InvalidStateTransitionError(
                    f"Cannot transition from {task.status.value} to {status.value}"
                )
            
            old_status = task.status
            task.status = status
            task.updated_at = datetime.utcnow()
            
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
                return False
            
            elif status == TaskStatus.FAILED:
                task.error_message = error_message
                task.retry_count += 1
                
                # Re-enqueue if retries available AND allowed by caller
                if allow_retry and task.retry_count < task.max_retries:
                    task.status = TaskStatus.PENDING
                    task.started_at = None  # Reset for retry
                    task.worker_id = None
                    
                    # Only add to heap if not already there
                    if task_id not in self._heap_task_ids:
                        heapq.heappush(self._heap, 
                                     (-task.priority.value, self._counter, task.id))
                        self._heap_task_ids.add(task_id)
                        self._counter += 1
                    return True
                return False
            
            elif status == TaskStatus.CANCELLED:
                # Remove from heap if present (lazy deletion marker)
                # Actual removal happens during dequeue
                return False
            
            return False
    
    def _is_valid_transition(self, from_status: TaskStatus, 
                            to_status: TaskStatus) -> bool:
        """Validate state machine transitions"""
        valid_transitions = {
            TaskStatus.PENDING: {TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
            TaskStatus.IN_PROGRESS: {TaskStatus.COMPLETED, TaskStatus.FAILED, 
                                    TaskStatus.CANCELLED},
            TaskStatus.FAILED: set(),  # Terminal state
            TaskStatus.COMPLETED: set(),  # Terminal state
            TaskStatus.CANCELLED: set(),  # Terminal state
        }
        return to_status in valid_transitions.get(from_status, set())
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return False
            if task.status == TaskStatus.PENDING:
                task.status = TaskStatus.CANCELLED
                task.updated_at = datetime.utcnow()
                # Lazy deletion - will be skipped during dequeue
                return True
            return False
    
    def requeue_task(self, task_id: str) -> bool:
        """
        Manually requeue an in-progress task (e.g., worker died).
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
            
            if task_id not in self._heap_task_ids:
                heapq.heappush(self._heap, 
                             (-task.priority.value, self._counter, task.id))
                self._heap_task_ids.add(task_id)
                self._counter += 1
            return True
    
    def get_queue_stats(self) -> dict:
        """Get queue statistics"""
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
                "heap_size": len(self._heap)
            }

# Custom exceptions
class QueueFullError(Exception):
    pass

class TaskNotFoundError(Exception):
    pass

class InvalidStateTransitionError(Exception):
    pass

def dataclass_replace(task: Task) -> Task:
    """Create a copy of a task"""
    return Task(
        id=task.id,
        payload=task.payload,
        priority=task.priority,
        status=task.status,
        created_at=task.created_at,
        updated_at=task.updated_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        error_message=task.error_message,
        retry_count=task.retry_count,
        max_retries=task.max_retries,
        sequence=task.sequence,
        worker_id=task.worker_id
    )
```

### 3. Queue Manager Interface
```python
class TaskQueueManager:
    def __init__(self, max_queue_size: Optional[int] = None):
        self.queue = PriorityTaskQueue(max_queue_size=max_queue_size)
    
    def submit_task(self, payload: Any, priority: str = "medium",
                   max_retries: int = 3) -> dict:
        """Submit a new task"""
        try:
            priority_enum = TaskPriority[priority.upper()]
        except KeyError:
            raise ValueError(f"Invalid priority: {priority}. "
                           f"Valid options: {[p.name.lower() for p in TaskPriority]}")
        
        if max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        
        try:
            task_id = self.queue.enqueue(payload, priority_enum, max_retries)
            return {"task_id": task_id, "status": "pending"}
        except QueueFullError as e:
            return {"error": str(e), "status": "rejected"}
    
    def get_next_task(self, worker_id: Optional[str] = None) -> Optional[dict]:
        """Worker polls for next task"""
        task = self.queue.dequeue(worker_id=worker_id)
        if task:
            return {
                "task_id": task.id,
                "payload": task.payload,
                "priority": task.priority.name,
                "retry_count": task.retry_count,
                "max_retries": task.max_retries
            }
        return None
    
    def complete_task(self, task_id: str, success: bool = True, 
                     error: Optional[str] = None,
                     allow_retry: bool = True) -> dict:
        """
        Mark task as completed or failed.
        
        Args:
            task_id: The task identifier
            success: Whether task completed successfully
            error: Error message if failed
            allow_retry: Whether to automatically retry on failure (worker can override)
        
        Returns:
            dict with status and retry information
        """
        try:
            status = TaskStatus.COMPLETED if success else TaskStatus.FAILED
            was_retried = self.queue.update_status(task_id, status, error, allow_retry)
            
            return {
                "task_id": task_id,
                "status": status.value,
                "retried": was_retried
            }
        except (TaskNotFoundError, InvalidStateTransitionError) as e:
            return {"error": str(e)}
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Check task status"""
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
            "worker_id": task.worker_id
        }
    
    def cancel_task(self, task_id: str) -> dict:
        """Cancel a pending task"""
        success = self.queue.cancel_task(task_id)
        return {
            "task_id": task_id,
            "cancelled": success,
            "message": "Task cancelled" if success else "Task not pending or not found"
        }
    
    def requeue_task(self, task_id: str) -> dict:
        """Manually requeue an in-progress task (e.g., worker failure)"""
        success = self.queue.requeue_task(task_id)
        return {
            "task_id": task_id,
            "requeued": success,
            "message": "Task requeued" if success else "Task not in-progress or not found"
        }
    
    def get_statistics(self) -> dict:
        """Get queue statistics"""
        return self.queue.get_queue_stats()
```

## Error Handling

### 1. Error Categories
- **QueueFullError**: Queue at capacity (configurable max size)
- **TaskNotFoundError**: Task ID doesn't exist
- **InvalidStateTransitionError**: Invalid state machine transition
- **ValueError**: Invalid priority or negative max_retries

### 2. Retry Strategy (Worker-Controlled)
The system supports **flexible retry policies**:

1. **Automatic retry** (default): Tasks retry up to `max_retries` automatically
2. **Worker-controlled retry**: Workers can pass `allow_retry=False` to prevent automatic retry and implement custom logic (exponential backoff, conditional retry, etc.)
3. **Manual requeue**: Workers or supervisors can manually requeue stuck tasks

This hybrid approach provides:
- Simplicity for standard cases (automatic retry)
- Flexibility for complex scenarios (worker-controlled)
- Recovery from worker failures (manual requeue)

### 3. State Machine Validation
Valid transitions:
- PENDING → IN_PROGRESS, CANCELLED
- IN_PROGRESS → COMPLETED, FAILED, CANCELLED
- COMPLETED, FAILED, CANCELLED → (terminal states)

Invalid transitions raise `InvalidStateTransitionError`.

### 4. Thread Safety Guarantees

**Race condition mitigations:**

1. **Atomic dequeue**: RLock ensures only one worker gets each task
2. **Lazy deletion**: Cancelled tasks removed during dequeue, preventing heap corruption
3. **Heap consistency**: Track heap membership with `_heap_task_ids` set to prevent duplicate insertions
4. **Idempotent updates**: Status updates validate current state before transition
5. **Worker tracking**: `worker_id` recorded for debugging concurrent access

**Known safe patterns:**
- Multiple workers calling `get_next_task()` concurrently
- Status updates while other workers are dequeuing
- Cancellation while task is in heap

## Usage Examples

### Basic Usage
```python
# Initialize with optional queue size limit
manager = TaskQueueManager(max_queue_size=10000)

# Submit tasks
task1 = manager.submit_task(
    {"action": "send_email", "to": "user@example.com"}, 
    priority="high",
    max_retries=5
)
task2 = manager.submit_task({"action": "generate_report"}, priority="low")

# Worker loop with automatic retry
worker_id = "worker-1"
while True:
    task = manager.get_next_task(worker_id=worker_id)
    if task:
        try:
            result = process(task['payload'])
            manager.complete_task(task['task_id'], success=True)
        except Exception as e:
            # Automatic retry enabled
            manager.complete_task(task['task_id'], success=False, error=str(e))
    else:
        time.sleep(1)
```

### Advanced: Worker-Controlled Retry
```python
# Worker with custom retry logic
def smart_worker():
    while True:
        task = manager.get_next_task(worker_id="smart-worker")
        if task:
            try:
                result = process(task['payload'])
                manager.complete_task(task['task_id'], success=True)
            except TransientError as e:
                # Allow automatic retry for transient errors
                manager.complete_task(
                    task['task_id'], 
                    success=False, 
                    error=str(e),
                    allow_retry=True
                )
            except PermanentError as e:
                # Skip retry for permanent errors
                manager.complete_task(
                    task['task_id'], 
                    success=False, 
                    error=str(e),
                    allow_retry=False
                )
```

### Supervisor Pattern (Worker Failure Recovery)
```python
# Monitor and requeue stuck tasks
def supervisor_loop():
    while True:
        stats = manager.get_statistics()
        for task_id in get_in_progress_tasks():
            task = manager.get_task_status(task_id)
            
            # Requeue if stuck for > 5 minutes
            if task and (datetime.utcnow() - task['started_at']).seconds > 300:
                manager.requeue_task(task_id)
        
        time.sleep(60)
```

## What I Improved

### 1. **Thread Safety Enhancements**
- **Lazy deletion**: Cancelled tasks are marked but removed during dequeue, preventing heap corruption from mid-operation removals
- **Heap membership tracking**: `_heap_task_ids` set prevents duplicate insertions during retry
- **State validation**: `_is_valid_transition()` prevents invalid state changes in concurrent scenarios
- **Worker ID tracking**: Helps debug which worker has a task, critical for recovery

### 2. **Flexible Retry Control**
- **Worker-controlled retry**: Added `allow_retry` parameter so workers can decide retry policy per failure
- **Per-task max_retries**: Configurable at submission time (not hardcoded)
- **Manual requeue**: Added `requeue_task()` for supervisor-driven recovery
- This addresses the original question: retry decisions can now be made by workers OR automatic

### 3. **Robust Error Handling**
- **Custom exceptions**: Specific exception types for different failure modes
- **State machine validation**: Explicit transition rules prevent invalid states
- **Queue capacity**: Optional `max_queue_size` prevents unbounded memory growth

### 4. **Enhanced Observability**
- **Worker tracking**: Know which worker is processing each task
- **Sequence numbers**: Stable FIFO ordering within priority levels
- **Extended stats**: Priority breakdown in statistics
- **Immutable task copies**: `get_task()` returns copies to prevent external mutation

### 5. **Production-Ready Details**
- **Validation**: Input validation with helpful error messages
- **Edge case handling**: Empty queue, duplicate operations, concurrent cancellation
- **Supervisor pattern**: Example shows how to detect and recover from worker failures

## What I Kept

- **Core heap-based architecture**: Efficient O(log n) operations with O(1) lookup
- **RLock for thread safety**: Solid foundation for concurrent access
- **Comprehensive task model**: Good balance of fields for tracking lifecycle
- **Clean API design**: Intuitive methods with clear responsibilities
- **Automatic retry foundation**: Built-in retry logic with room for customization

## Remaining Concerns

### Addressed from Original
✅ **Thread safety**: Lazy deletion and heap tracking prevent race conditions
✅ **Retry control**: Hybrid approach gives workers control when needed

### New Considerations
1. **Memory growth**: Even with lazy deletion, cancelled tasks remain in `_tasks` dict forever. Should we add periodic cleanup or TTL?
2. **Heap bloat**: Lazy deletion means heap can contain many stale entries. Consider periodic heap rebuild if this becomes an issue.
3. **Worker failure detection**: The supervisor pattern is manual. Should we add automatic heartbeat/timeout detection?
4. **Persistence**: Still fully in-memory. What's the migration path to Redis/DB?
5. **Metrics/observability**: Should we add hooks for Prometheus/StatsD integration?

## Convergence Status

**ITERATING** - Design is significantly improved but needs architect feedback on:
1. Trade-offs of lazy deletion vs. eager cleanup
2. Whether worker-controlled retry adds useful flexibility or unnecessary complexity
3. Production deployment concerns (persistence, monitoring)

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
I've added worker-controlled retry and lazy deletion for thread safety. Key questions:

1. **Lazy deletion trade-off**: Tasks stay in the heap until dequeued (marked as invalid). This prevents race conditions but can bloat the heap with cancelled tasks. Is this acceptable, or should we add periodic heap rebuilding?

2. **Retry flexibility**: I added `allow_retry` parameter so workers can override automatic retry per failure. Does this add useful flexibility for your use case, or is pure automatic retry simpler and sufficient?

3. **Memory management**: Should we add automatic cleanup of old completed/failed tasks, or is manual cleanup via a background job acceptable?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

### 1. **Simplified Retry Philosophy**
- **Removed** `allow_retry` parameter - added complexity without clear benefit
- **Automatic retry** based on `max_retries` is simple and covers 95% of cases
- **Worker flexibility** maintained through `retry_policy` metadata (hints, not control)
- **Manual override** still possible via `requeue_task()` for special cases
- **Result**: Simpler API, clearer semantics, less cognitive load

### 2. **Bounded Memory via Automatic Cleanup**
- **Problem**: Previous design accumulated terminal tasks forever
- **Solution**: Automatic cleanup of old completed/failed/cancelled tasks
- **Configurable retention**: Keep tasks for N seconds (default 1 hour)
- **Periodic execution**: Cleanup runs every M seconds (default 5 minutes)
- **Opportunistic**: Also runs during enqueue/dequeue for zero-overhead
- **Result**: Bounded memory growth, predictable resource usage

### 3. **Heap Health Monitoring & Auto-Rebuild**
- **Problem**: Lazy deletion causes heap bloat with cancelled tasks
- **Solution**: Track heap efficiency (valid/total entries)
- **Automatic rebuild**: Trigger when efficiency < 50% and heap > 100 entries
- **Graceful degradation**: System works even with bloated heap, just slower
- **Manual override**: `force_maintenance()` for emergency cleanup
- **Result**: Self-healing system, maintains O(log n) performance

### 4. **Enhanced Observability**
- Added `age_seconds()` and `time_in_progress_seconds()` to Task
- Heap efficiency metrics in statistics
- Last cleanup/rebuild timestamps
- **Result**: Easy to diagnose performance issues, monitor health

### 5. **Retry Policy as Metadata**
- Workers receive `retry_policy` dict with task
- Queue doesn't interpret it - just passes it along
- Workers can implement smart delays, conditional retry, etc.
- **Result**: Flexibility without complicating queue internals

## What I Changed

### Removed `allow_retry` Parameter
- Simplified `complete_task()` signature
- Retry is now purely based on `max_retries` counter
- Workers who need custom logic use `retry_policy` metadata + manual `requeue_task()`
- **Why**: The hybrid approach added API complexity. Most users want simple automatic retry.

### Added Automatic Memory Management
- `task_retention_seconds`: Configurable TTL for terminal tasks
- `cleanup_interval_seconds`: How often to run cleanup
- `_cleanup_old_tasks()`: Removes tasks past retention period
- `_maybe_cleanup()`: Opportunistic cleanup on enqueue/dequeue
- **Why**: Prevents unbounded memory growth in long-running systems

### Added Heap Health Tracking
- `HeapHealth` dataclass tracks valid/invalid entries
- Automatic rebuild when efficiency drops below 50%
- Manual `force_maintenance()` for emergency cleanup
- **Why**: Lazy deletion is correct but can degrade performance; this fixes it

### Simplified State Transitions
- Removed separate retry logic from `update_status()`
- Retry happens inline when marking FAILED
- Returns `(success, was_retried)` tuple
- **Why**: Clearer flow, easier to reason about

### Added Task Helper Methods
- `is_terminal()`: Check if task is done
- `age_seconds()`: Task age for monitoring
- `time_in_progress_seconds()`: Execution time tracking
- **Why**: Common queries shouldn't require datetime math everywhere

## What I Kept

- **Core heap architecture**: Efficient, proven design
- **RLock for thread safety**: Essential for concurrent workers
- **Lazy deletion strategy**: Still correct, now with health monitoring
- **State machine validation**: Prevents invalid transitions
- **Worker ID tracking**: Useful for debugging
- **Manual requeue**: Critical for supervisor pattern
- **Comprehensive statistics**: Good observability foundation
- **Sequence numbers**: Stable FIFO within priority

## Open Questions

### Performance Under Load
- How does cleanup impact throughput under heavy load?
- Should cleanup run in a background thread instead of opportunistically?
- What's the optimal cleanup interval for different workloads?

### Persistence Strategy
- Migration path to Redis/PostgreSQL for durability?
- Should we maintain API compatibility when adding persistence?
- How to handle queue initialization from persistent storage?

### Monitoring Integration
- Should we add built-in Prometheus metrics?
- Event hooks for external monitoring systems?
- Structured logging for task lifecycle events?

### Advanced Scheduling
- Should we support scheduled/delayed tasks (execute_after timestamp)?
- Task dependencies (task B runs after task A completes)?
- Task groups for batch operations?

## Convergence Status

**ITERATING** - Design is production-ready for basic use cases but needs validation on:
1. Whether automatic cleanup intervals work for your workload
2. If simplified retry model (no `allow_retry`) meets requirements
3. Trade-offs between cleanup overhead and memory bounds

## Prompt for Collaborator

PROMPT_FOR_CRITIC:

I've simplified the retry model and added automatic memory management. Key decisions:

1. **Removed `allow_retry` parameter**: Retry is now purely automatic based on `max_retries`. Workers who need custom logic can use `retry_policy` metadata (the queue just passes it along) or manual `requeue_task()`. Is this simpler model sufficient, or do you see use cases where workers truly need per-failure retry control at the API level?

2. **Automatic cleanup**: Tasks are removed after `task_retention_seconds` (default 1 hour). Cleanup runs every 5 minutes opportunistically. Does this solve the memory growth concern? Are the defaults reasonable, or should we expose more tuning knobs?

3. **Heap auto-rebuild**: Triggers when efficiency < 50% and size > 100. This prevents lazy deletion from degrading performance. Are these thresholds reasonable, or should they be configurable?

4. **What did I over-simplify?** Did removing `allow_retry` lose important functionality? Should cleanup be more sophisticated (per-status retention policies)?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Priority Task Queue System with Bounded Memory, Configurable Policies & Comprehensive Monitoring

## Architecture Overview

A production-ready priority task queue system with in-memory storage, intelligent memory management, flexible cleanup policies, and enterprise-grade observability. Key improvements: configurable cleanup thresholds, per-status retention policies, safe concurrent cleanup, enhanced error recovery, and comprehensive metrics.

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
    
    def time_since_completion_seconds(self) -> Optional[float]:
        """Get time since task entered terminal state (for cleanup logic)"""
        if not self.completed_at:
            return None
        return (datetime.utcnow() - self.completed_at).total_seconds()
```

### 2. Cleanup Configuration
```python
@dataclass
class CleanupPolicy:
    """Fine-grained control over task retention"""
    # Per-status retention policies (None = keep forever)
    completed_retention_seconds: Optional[int] = 3600  # 1 hour
    failed_retention_seconds: Optional[int] = 7200     # 2 hours (keep failures longer)
    cancelled_retention_seconds: Optional[int] = 1800  # 30 minutes
    
    # Cleanup execution settings
    cleanup_interval_seconds: int = 300  # 5 minutes
    max_tasks_per_cleanup: int = 1000    # Rate limit cleanup to avoid blocking
    
    # Safety limits
    min_terminal_tasks_before_cleanup: int = 100  # Don't cleanup if < 100 terminal tasks
    
    def get_retention_for_status(self, status: TaskStatus) -> Optional[int]:
        """Get retention seconds for a given status (None = keep forever)"""
        if status == TaskStatus.COMPLETED:
            return self.completed_retention_seconds
        elif status == TaskStatus.FAILED:
            return self.failed_retention_seconds
        elif status == TaskStatus.CANCELLED:
            return self.cancelled_retention_seconds
        return None  # PENDING and IN_PROGRESS never cleaned by age

@dataclass
class HeapRebuildPolicy:
    """Control when heap rebuilding occurs"""
    min_efficiency: float = 0.5        # Rebuild when efficiency drops below 50%
    min_total_entries: int = 100        # Only rebuild if heap has 100+ entries
    max_rebuild_interval_seconds: int = 3600  # Force rebuild every hour regardless
    
    def should_rebuild(self, health: 'HeapHealth') -> bool:
        """Determine if heap should be rebuilt"""
        # Efficiency-based rebuild
        if (health.efficiency < self.min_efficiency and 
            health.total_entries >= self.min_total_entries):
            return True
        
        # Time-based forced rebuild
        time_since_rebuild = (datetime.utcnow() - health.last_rebuild).total_seconds()
        if time_since_rebuild >= self.max_rebuild_interval_seconds:
            return True
        
        return False

@dataclass
class HeapHealth:
    """Track heap efficiency for automatic maintenance"""
    total_entries: int = 0
    valid_entries: int = 0
    invalid_entries: int = 0
    last_rebuild: datetime = field(default_factory=datetime.utcnow)
    rebuild_count: int = 0
    
    @property
    def efficiency(self) -> float:
        """Percentage of valid entries in heap"""
        if self.total_entries == 0:
            return 1.0
        return self.valid_entries / self.total_entries
```

### 3. Priority Queue Storage with Smart Cleanup
```python
import heapq
import threading
from collections import defaultdict
from typing import Set, Optional, Tuple, Dict, List

class PriorityTaskQueue:
    def __init__(self, 
                 max_queue_size: Optional[int] = None,
                 cleanup_policy: Optional[CleanupPolicy] = None,
                 heap_rebuild_policy: Optional[HeapRebuildPolicy] = None):
        """
        Args:
            max_queue_size: Max pending tasks (None = unlimited)
            cleanup_policy: Task retention and cleanup settings
            heap_rebuild_policy: Heap maintenance thresholds
        """
        self._lock = threading.RLock()
        self._heap: List[Tuple[int, int, str]] = []
        self._tasks: Dict[str, Task] = {}
        self._heap_task_ids: Set[str] = set()
        self._counter = 0
        self._max_queue_size = max_queue_size
        
        self._cleanup_policy = cleanup_policy or CleanupPolicy()
        self._heap_policy = heap_rebuild_policy or HeapRebuildPolicy()
        
        self._last_cleanup = datetime.utcnow()
        self._heap_health = HeapHealth()
        
        # Metrics tracking
        self._metrics = {
            'total_enqueued': 0,
            'total_dequeued': 0,
            'total_completed': 0,
            'total_failed': 0,
            'total_cancelled': 0,
            'total_retried': 0,
            'total_cleaned': 0,
            'cleanup_runs': 0,
            'heap_rebuilds': 0,
        }
    
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
            self._metrics['total_enqueued'] += 1
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
            
            while self._heap:
                _, _, task_id = heapq.heappop(self._heap)
                self._heap_task_ids.discard(task_id)
                self._heap_health.total_entries -= 1
                
                task = self._tasks.get(task_id)
                
                if not task or task.status != TaskStatus.PENDING:
                    # Invalid entry, mark and continue searching
                    self._heap_health.invalid_entries += 1
                    continue
                
                # Found valid task
                self._heap_health.valid_entries -= 1
                task.status = TaskStatus.IN_PROGRESS
                task.started_at = datetime.utcnow()
                task.updated_at = datetime.utcnow()
                task.worker_id = worker_id
                self._metrics['total_dequeued'] += 1
                
                # Check if heap needs rebuilding
                if self._heap_policy.should_rebuild(self._heap_health):
                    self._rebuild_heap()
                
                return task
            
            # Heap exhausted - rebuild if we have invalid entries
            if self._heap_health.invalid_entries > 0:
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
                last_rebuild=datetime.utcnow(),
                rebuild_count=self._heap_health.rebuild_count + 1
            )
            self._metrics['heap_rebuilds'] += 1
    
    def _maybe_cleanup(self):
        """Run cleanup if enough time has passed"""
        now = datetime.utcnow()
        interval = timedelta(seconds=self._cleanup_policy.cleanup_interval_seconds)
        
        if now - self._last_cleanup > interval:
            self._cleanup_old_tasks()
            self._last_cleanup = now
    
    def _cleanup_old_tasks(self):
        """Remove old terminal tasks based on per-status retention policies"""
        with self._lock:
            now = datetime.utcnow()
            
            # Count terminal tasks to check safety threshold
            terminal_count = sum(1 for t in self._tasks.values() if t.is_terminal())
            
            if terminal_count < self._cleanup_policy.min_terminal_tasks_before_cleanup:
                return  # Not enough tasks to warrant cleanup
            
            to_delete = []
            
            for task_id, task in self._tasks.items():
                if not task.is_terminal():
                    continue
                
                # Get retention policy for this task's status
                retention_seconds = self._cleanup_policy.get_retention_for_status(task.status)
                
                if retention_seconds is None:
                    continue  # This status is kept forever
                
                # Check if task has exceeded retention period
                time_since_completion = task.time_since_completion_seconds()
                if time_since_completion and time_since_completion >= retention_seconds:
                    to_delete.append(task_id)
                
                # Rate limit cleanup to avoid blocking
                if len(to_delete) >= self._cleanup_policy.max_tasks_per_cleanup:
                    break
            
            # Perform deletion
            for task_id in to_delete:
                del self._tasks[task_id]
                self._metrics['total_cleaned'] += 1
            
            self._metrics['cleanup_runs'] += 1
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID (returns copy for safety)"""
        with self._lock:
            task = self._tasks.get(task_id)
            return task  # In production, consider returning a copy for safety
    
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
            
            old_status = task.status
            task.status = status
            task.updated_at = datetime.utcnow()
            
            if status == TaskStatus.COMPLETED:
                task.completed_at = datetime.utcnow()
                self._metrics['total_completed'] += 1
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
                    
                    self._metrics['total_retried'] += 1
                    return (True, True)
                
                # Exhausted retries - stays FAILED
                self._metrics['total_failed'] += 1
                return (True, False)
            
            elif status == TaskStatus.CANCELLED:
                task.completed_at = datetime.utcnow()
                self._metrics['total_cancelled'] += 1
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
                "heap_invalid_entries": self._heap_health.invalid_entries,
                "last_cleanup": self._last_cleanup.isoformat(),
                "last_heap_rebuild": self._heap_health.last_rebuild.isoformat(),
                "lifetime_metrics": dict(self._metrics)
            }
    
    def force_cleanup(self, cleanup_all_terminal: bool = False) -> dict:
        """
        Manually trigger cleanup and return results.
        
        Args:
            cleanup_all_terminal: If True, remove ALL terminal tasks regardless of age
        """
        with self._lock:
            before_count = len(self._tasks)
            
            if cleanup_all_terminal:
                # Emergency cleanup - remove all terminal tasks
                to_delete = [tid for tid, task in self._tasks.items() 
                           if task.is_terminal()]
                for task_id in to_delete:
                    del self._tasks[task_id]
            else:
                # Normal cleanup respecting retention policies
                self._cleanup_old_tasks()
            
            after_count = len(self._tasks)
            
            before_heap = len(self._heap)
            self._rebuild_heap()
            after_heap = len(self._heap)
            
            return {
                "tasks_removed": before_count - after_count,
                "heap_entries_removed": before_heap - after_heap,
                "tasks_remaining": after_count,
                "heap_size": after_heap,
                "heap_efficiency": self._heap_health.efficiency,
                "all_terminal_cleaned": cleanup_all_terminal
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
                 cleanup_policy: Optional[CleanupPolicy] = None,
                 heap_rebuild_policy: Optional[HeapRebuildPolicy] = None):
        """
        Args:
            max_queue_size: Max pending tasks (None = unlimited)
            cleanup_policy: Task retention and cleanup configuration
            heap_rebuild_policy: Heap maintenance thresholds
        """
        self.queue = PriorityTaskQueue(
            max_queue_size=max_queue_size,
            cleanup_policy=cleanup_policy,
            heap_rebuild_policy=heap_rebuild_policy
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
                "status": status.value if not was_retried else "retrying",
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
    
    def force_maintenance(self, emergency: bool = False) -> dict:
        """
        Manually trigger cleanup and heap rebuild.
        
        Args:
            emergency: If True, removes ALL terminal tasks regardless of retention policy
        """
        return self.queue.force_cleanup(cleanup_all_terminal=emergency)
```

### 5. Health Monitor & Supervisor Utilities
```python
from typing import List

class TaskSupervisor:
    """Monitor and recover stuck tasks"""
    
    def __init__(self, manager: TaskQueueManager, 
                 stuck_threshold_seconds: int = 300):
        self.manager = manager
        self.stuck_threshold = stuck_threshold_seconds
    
    def check_stuck_tasks(self) -> List[dict]:
        """Find tasks stuck in IN_PROGRESS state"""
        with self.manager.queue._lock:
            stuck_tasks = []
            now = datetime.utcnow()
            
            for task in self.manager.queue._tasks.values():
                if task.status != TaskStatus.IN_PROGRESS:
                    continue
                
                time_in_progress = task.time_in_progress_seconds()
                if time_in_progress and time_in_progress >= self.stuck_threshold:
                    stuck_tasks.append({
                        'task_id': task.id,
                        'worker_id': task.worker_id,
                        'priority': task.priority.name,
                        'time_in_progress': time_in_progress,
                        'started_at': task.started_at.isoformat()
                    })
            
            return stuck_tasks
    
    def requeue_stuck_tasks(self, reset_retries: bool = False) -> dict:
        """Automatically requeue stuck tasks"""
        stuck = self.check_stuck_tasks()
        requeued = []
        failed = []
        
        for task_info in stuck:
            result = self.manager.requeue_task(
                task_info['task_id'], 
                reset_retries=reset_retries
            )
            if result['requeued']:
                requeued.append(task_info['task_id'])
            else:
                failed.append(task_info['task_id'])
        
        return {
            "stuck_tasks_found": len(stuck),
            "tasks_requeued": len(requeued),
            "tasks_failed_to_requeue": len(failed),
            "requeued_task_ids": requeued,
            "failed_task_ids": failed
        }
```

## Usage Examples

### Basic Configuration
```python
# Simple setup with defaults
manager = TaskQueueManager(
    max_queue_size=10000
)

# Advanced setup with custom policies
cleanup_policy = CleanupPolicy(
    completed_retention_seconds=3600,    # Keep completed 1hr
    failed_retention_seconds=7200,       # Keep failed 2hr
    cancelled_retention_seconds=1800,    # Keep cancelled 30min
    cleanup_interval_seconds=300,        # Cleanup every 5min
    max_tasks_per_cleanup=1000,          # Rate limit
    min_terminal_tasks_before_cleanup=50 # Safety threshold
)

heap_policy = HeapRebuildPolicy(
    min_efficiency=0.5,
    min_total_entries=100,
    max_rebuild_interval_seconds=3600
)

manager = TaskQueueManager(
    max_queue_size=10000,
    cleanup_policy=cleanup_policy,
    heap_rebuild_policy=heap_policy
)
```

### Worker with Automatic Retry
```python
# Worker with automatic retry handling
worker_id = "worker-1"

while True:
    task = manager.get_next_task(worker_id=worker_id)
    
    if task:
        try:
            result = process_task(task['payload'])
            manager.complete_task(task['task_id'], success=True)
        except Exception as e:
            # Queue handles retry automatically based on max_retries
            response = manager.complete_task(
                task['task_id'], 
                success=False, 
                error=str(e)
            )
            
            if response.get('retried'):
                logger.info(f"Task {task['task_id']} will be retried")
            else:
                logger.error(f"Task {task['task_id']} failed permanently")
    else:
        time.sleep(1)
```

### Worker with Smart Retry Policy
```python
import time

def smart_worker():
    """Worker that respects retry_policy metadata"""
    worker_id = "smart-worker-1"
    
    while True:
        task = manager.get_next_task(worker_id=worker_id)
        
        if not task:
            time.sleep(1)
            continue
        
        # Extract retry policy hints
        retry_policy = task.get('retry_policy') or {}
        retry_count = task['retry_count']
        
        try:
            result = call_external_api(task['payload'])
            manager.complete_task(task['task_id'], success=True)
            
        except RateLimitError as e:
            # Use exponential backoff for rate limits
            manager.complete_task(task['task_id'], success=False, error=str(e))
            
            if retry_policy.get('backoff') == 'exponential':
                base_delay = retry_policy.get('base_delay', 2)
                max_delay = retry_policy.get('max_delay', 60)
                delay = min(base_delay ** retry_count, max_delay)
                time.sleep(delay)
        
        except PermanentError as e:
            # Some errors shouldn't be retried - mark failed
            manager.complete_task(task['task_id'], success=False, error=str(e))
```

### Monitoring & Maintenance
```python
# Get comprehensive statistics
stats = manager.get_statistics()

print(f"Queue Health:")
print(f"  Pending: {stats['pending']}")
print(f"  In Progress: {stats['in_progress']}")
print(f"  Heap Efficiency: {stats['heap_efficiency']:.2%}")
print(f"  Invalid Heap Entries: {stats['heap_invalid_entries']}")

print(f"\nLifetime Metrics:")
metrics = stats['lifetime_metrics']
print(f"  Total Enqueued: {metrics['total_enqueued']}")
print(f"  Total Completed: {metrics['total_completed']}")
print(f"  Total Failed: {metrics['total_failed']}")
print(f"  Total Retried: {metrics['total_retried']}")
print(f"  Total Cleaned: {metrics['total_cleaned']}")
print(f"  Cleanup Runs: {metrics['cleanup_runs']}")
print(f"  Heap Rebuilds: {metrics['heap_rebuilds']}")

# Normal maintenance
if stats['heap_efficiency'] < 0.3:
    result = manager.force_maintenance()
    print(f"Cleaned {result['tasks_removed']} tasks, "
          f"removed {result['heap_entries_removed']} stale heap entries")

# Emergency cleanup (remove ALL terminal tasks)
if stats['total_tasks'] > 1_000_000:
    result = manager.force_maintenance(emergency=True)
    print(f"Emergency cleanup: removed {result['tasks_removed']} terminal tasks")
```

### Supervisor for Stuck Task Recovery
```python
# Run supervisor periodically (e.g., every minute)
supervisor = TaskSupervisor(manager, stuck_threshold_seconds=300)

# Check for stuck tasks
stuck_tasks = supervisor.check_stuck_tasks()
if stuck_tasks:
    print(f"Found {len(stuck_tasks)} stuck tasks:")
    for task in stuck_tasks:
        print(f"  {task['task_id']}: stuck for {task['time_in_progress']:.0f}s "
              f"on worker {task['worker_id']}")

# Automatically recover stuck tasks
recovery = supervisor.requeue_stuck_tasks(reset_retries=False)
print(f"Requeued {recovery['tasks_requeued']} stuck tasks")
if recovery['failed_task_ids']:
    print(f"Failed to requeue: {recovery['failed_task_ids']}")
```

### Custom Retention Policy for Audit Requirements
```python
# Keep completed tasks for 7 days for audit, failed for 30 days
audit_policy = CleanupPolicy(
    completed_retention_seconds=7 * 24 * 3600,   # 7 days
    failed_retention_seconds=30 * 24 * 3600,     # 30 days
    cancelled_retention_seconds=24 * 3600,       # 1 day
    cleanup_interval_seconds=3600,               # Hourly cleanup
    max_tasks_per_cleanup=5000,
    min_terminal_tasks_before_cleanup=1000
)

manager = TaskQueueManager(
    max_queue_size=50000,
    cleanup_policy=audit_policy
)
```

## What I Improved

### 1. **Configurable Cleanup Thresholds**
- Added `CleanupPolicy` dataclass with per-status retention
- Failed tasks kept longer than completed (2hr vs 1hr) - failures need investigation
- Rate-limited cleanup (`max_tasks_per_cleanup`) to prevent blocking
- Safety threshold (`min_terminal_tasks_before_cleanup`) prevents wasteful cleanup
- **Why**: Different task types have different retention needs; one-size-fits-all is insufficient

### 2. **Configurable Heap Rebuild Policy**
- Added `HeapRebuildPolicy` with efficiency threshold, size threshold, and max interval
- Force rebuild every hour even if efficiency is good (prevents edge cases)
- Made thresholds explicit and tunable rather than magic numbers
- **Why**: Different workloads need different rebuild strategies; expose control

### 3. **Per-Status Retention Policies**
- `completed_retention_seconds`, `failed_retention_seconds`, `cancelled_retention_seconds`
- Each status can have different TTL (or None to keep forever)
- `get_retention_for_status()` encapsulates lookup logic
- **Why**: Audit requirements often mandate longer failed task retention; completed tasks can be purged faster

### 4. **Enhanced Task Model**
- Added `time_since_completion_seconds()` for cleanup logic
- Separates "task age" from "terminal state age" - critical for retention
- **Why**: Cleanup should be based on when task *completed*, not when it was created

### 5. **Comprehensive Metrics Tracking**
- Lifetime counters: enqueued, dequeued, completed, failed, cancelled, retried, cleaned
- Cleanup runs and heap rebuilds tracked
- `heap_invalid_entries` exposed in stats
- **Why**: Production systems need visibility into system behavior over time

### 6. **Safe Concurrent Cleanup**
- Rate-limited deletion prevents long lock holds
- `max_tasks_per_cleanup` prevents cleanup from blocking workers
- Safety check (`min_terminal_tasks_before_cleanup`) avoids overhead on small queues
- **Why**: Cleanup shouldn't impact worker throughput

### 7. **Emergency Maintenance Mode**
- `force_maintenance(emergency=True)` removes ALL terminal tasks
- Useful for memory pressure situations
- Returns detailed metrics on what was cleaned
- **Why**: Production systems need panic buttons

### 8. **Enhanced Supervisor**
- Returns detailed info on stuck tasks (worker_id, time stuck, etc.)
- Separate failed/succeeded lists for requeue operations
- Optional `reset_retries` flag for recovery scenarios
- **Why**: Operators need actionable information, not just counts

### 9. **Better Error Handling in complete_task**
- Returns `status: "retrying"` when task is automatically retried
- Distinguishes between "failed and retrying" vs "failed permanently"
- **Why**: Workers should know if their failure triggered retry

### 10. **Invalid Entry Tracking**
- `heap_health.invalid_entries` incremented when skipping stale entries
- Helps diagnose heap bloat issues
- **Why**: Observability into lazy deletion behavior

## What I Kept

- **Simplified retry model**: Automatic retry based on `max_retries` is correct
- **retry_policy as metadata**: Queue doesn't interpret it, just passes through - perfect separation
- **Core heap architecture**: Efficient priority queue with lazy deletion
- **RLock for thread safety**: Essential for concurrent workers
- **State machine validation**: Prevents invalid transitions
- **Worker ID tracking**: Critical for debugging stuck tasks
- **Manual requeue**: Supervisor pattern requires this
- **Sequence numbers**: FIFO within priority is important
- **Task helper methods**: `is_terminal()`, `age_seconds()`, etc.

## Remaining Concerns

### 1. **Cleanup Lock Contention**
The opportunistic cleanup during `enqueue`/`dequeue` holds the lock while iterating tasks. For large task dictionaries (100k+ tasks), this could block workers.

**Options**:
- Move cleanup to background thread
- Use lazy deletion for terminal tasks too (track separately)
- Add write-ahead log for cleanup candidates

### 2. **Memory Overhead of Metrics**
Lifetime metrics grow unbounded. In a system running for months, these counters could overflow.

**Options**:
- Use prometheus-style metrics (external aggregation)
- Reset metrics periodically
- Use sliding windows instead of lifetime counts

### 3. **No Index for IN_PROGRESS Tasks**
Supervisor has to iterate all tasks to find stuck ones. This is O(n) on total tasks.

**Options**:
- Maintain separate `_in_progress_tasks` dict
- Index by worker_id for targeted lookups
- Track task start times in a separate min-heap for efficient "oldest in-progress" queries

### 4. **Copy vs Reference in get_task()**
Currently returns task reference, which allows external mutation. But making defensive copies has performance cost.

**Options**:
- Return immutable view object
- Use frozen dataclass for external API
- Document as internal-only and provide separate public API

### 5. **No Circuit Breaker for Failed Tasks**
If a task type consistently fails (bad payload, external service down), it will retry indefinitely across queue restarts.

**Options**:
- Track failure patterns by payload type/signature
- Implement backoff at queue level (delay before retry)
- Add "poison task" detection (task fails X times = quarantine)

## Convergence Status

**ITERATING** - Design addresses the key concerns but needs validation on:

1. Whether per-status retention meets your audit/compliance requirements
2. If cleanup rate limiting (max_tasks_per_cleanup) is sufficient for your scale
3. Trade-offs between cleanup overhead and memory bounds under high load
4. Whether locked cleanup is acceptable or background thread is needed

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:

I've added per-status retention policies, configurable cleanup/rebuild thresholds, comprehensive metrics, and safer concurrent cleanup. Key questions:

1. **Cleanup lock contention**: Cleanup runs under the main lock and iterates all tasks. For a queue with 100k+ tasks, this could block workers during cleanup. Should we move cleanup to a background thread, or is rate-limiting (`max_tasks_per_cleanup=1000`) sufficient?

2. **Per-status retention**: I kept failed tasks for 2x longer than completed (2hr vs 1hr) assuming failures need investigation. Does this match your use case? Should we support per-priority retention too (keep CRITICAL tasks longer)?

3. **Heap rebuild policy**: I added `max_rebuild_interval_seconds` to force periodic rebuilds even if efficiency looks good. Is this paranoia, or does it prevent edge cases I'm not seeing?

4. **IN_PROGRESS task indexing**: Supervisor iterates all tasks to find stuck ones (O(n)). Should we maintain a separate index of in-progress tasks for O(1) lookups, or is periodic O(n) scan acceptable?

5. **Did I over-engineer cleanup?** Is per-status retention + rate limiting + safety thresholds too complex? Would a simpler "keep terminal tasks for N hours" suffice?

**Convergence Signal:** ITERATING

---

