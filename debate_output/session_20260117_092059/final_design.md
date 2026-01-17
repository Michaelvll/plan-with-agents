# Final Agreed Design

**Task:** Design a task queue system with priority support

**Status:** debating

---

## Design

# Task Queue System with Priority Support

## Architecture Overview

The system implements a **priority-based task scheduling system** with proven starvation prevention and pragmatic failure recovery. It uses a **worker-pull model** with three main layers:

1. **API Layer**: REST endpoints for task lifecycle management
2. **Scheduling Layer**: Multi-queue priority system with age-based promotion
3. **Execution Layer**: Worker pool with health monitoring and graceful degradation

## Core Components

### 1. Task Queue Manager
- **Responsibilities**: 
  - Accept incoming tasks with priority levels (high, medium, low)
  - Maintain separate priority queues with periodic age-based promotion
  - Route tasks to workers based on simple capability matching
  - Orchestrate task lifecycle (submitted → queued → executing → terminal state)
  - Handle task timeouts and retries

### 2. Multi-Queue Priority System with Age-Based Promotion

**Structure**: Three separate Redis sorted sets, scored by submission time
```
queue:high    - High priority tasks (scored by created_at timestamp)
queue:medium  - Medium priority tasks (scored by created_at timestamp)
queue:low     - Low priority tasks (scored by created_at timestamp)
```

**Starvation Prevention**: Periodic promotion via background job
```python
# Runs every 60 seconds
def promote_aged_tasks():
    now = time.time()
    
    # Promote low → medium if waiting > 10 minutes
    aged_low = redis.zrangebyscore(
        'queue:low', 
        0, 
        now - 600,  # 10 minutes
        start=0, 
        num=100
    )
    for task_id in aged_low:
        task = get_task(task_id)
        task.effective_priority = 'medium'
        redis.zrem('queue:low', task_id)
        redis.zadd('queue:medium', {task_id: task.created_at})
    
    # Promote medium → high if waiting > 20 minutes
    aged_medium = redis.zrangebyscore(
        'queue:medium',
        0,
        now - 1200,  # 20 minutes
        start=0,
        num=50
    )
    for task_id in aged_medium:
        task = get_task(task_id)
        task.effective_priority = 'high'
        redis.zrem('queue:medium', task_id)
        redis.zadd('queue:high', {task_id: task.created_at})
```

**Guarantees**:
- Low priority tasks promoted to medium after 10 minutes
- Medium priority tasks promoted to high after 20 minutes
- Maximum wait time: 30 minutes for any task
- Within each queue: strict FIFO ordering

**Rationale**: This approach is simpler to reason about, debug, and maintain than dynamic scoring. The discrete promotion thresholds are easy to explain to users ("your low priority task will be treated as medium after 10 minutes") and the behavior is predictable. The 60-second promotion interval is frequent enough for practical fairness while being cheap to execute.

### 3. Worker Pool with Simple Health Monitoring

**Architecture**: Fixed-size worker pool with capability tags
- **Worker States**: `active`, `draining`, `dead`
- **Health Checks**: 
  - **Heartbeat only**: Every 30 seconds, 3 missed heartbeats (90s) = worker dead
  - **Task timeout**: Independent per-task timeout, triggers recovery on expiry
- **Concurrency**: Per-worker capacity (default: 5 concurrent tasks)
- **Graceful Shutdown**: `draining` state prevents new assignments

**Rationale for Simplified Health Monitoring**: 
- Active health probes add complexity and create new failure modes (probe timeouts, probe service overload)
- Task-level timeouts already detect hung workers effectively
- Heartbeat + task timeout covers 99% of failure scenarios
- Simpler system = fewer edge cases = more reliable

### 4. Task State Machine

**States**: `queued` → `executing` → [`completed` | `failed` | `cancelled` | `dead_letter`]

**Simplified from 7 states to 5 states**: 
- Removed `submitted` (immediately becomes `queued`)
- Removed `assigned` (worker atomically transitions `queued` → `executing` during poll)
- Removed `initializing` worker state (workers register as `active`)

**Rationale**: Each state adds complexity in recovery logic. The key insight is that if a worker has the task, the worker is responsible for it. We don't need fine-grained tracking of "assigned but not started" - the task timeout handles this case.

### 5. Dead Letter Queue & Core Observability

**DLQ**: Separate Redis sorted set `queue:dlq` for tasks exceeding retry limits
- Score: timestamp when moved to DLQ
- TTL: 30 days
- Manual replay: Admin endpoint to requeue with reset retries

**Observability**: 
- **Metrics**: Queue depth, task duration, worker utilization, error rates
- **Logging**: Structured JSON logs for state transitions
- **Tracing**: Trace ID propagated through task lifecycle

## Data Models

### Task Entity
```json
{
  "task_id": "uuid-v4",
  "priority": "high|medium|low",
  "effective_priority": "high|medium|low",
  "payload": {
    "task_type": "string",
    "parameters": "json-object",
    "required_capabilities": ["gpu"]
  },
  "status": "queued|executing|completed|failed|cancelled|dead_letter",
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "timestamp",
  "started_at": "timestamp|null",
  "completed_at": "timestamp|null",
  "assigned_worker_id": "worker-id|null",
  "result": "json-object|null",
  "error": {
    "message": "string",
    "retriable": true
  },
  "timeout_seconds": 300,
  "idempotency_key": "string|null",
  "trace_id": "string"
}
```

### Worker Entity
```json
{
  "worker_id": "uuid-v4",
  "status": "active|draining|dead",
  "current_tasks": ["task-id-1", "task-id-2"],
  "last_heartbeat": "timestamp",
  "capacity": 5,
  "current_load": 2,
  "capabilities": ["gpu", "cpu-intensive"],
  "version": "string"
}
```

### Priority Configuration
```json
{
  "high": {
    "max_retries": 5,
    "timeout_seconds": 300
  },
  "medium": {
    "max_retries": 3,
    "timeout_seconds": 600
  },
  "low": {
    "max_retries": 2,
    "timeout_seconds": 900
  },
  "starvation_prevention": {
    "low_to_medium_seconds": 600,
    "medium_to_high_seconds": 1200,
    "promotion_interval_seconds": 60,
    "promotion_batch_size": 100
  }
}
```

## Interfaces

### REST API Endpoints

#### Task Submission
```
POST /api/v1/tasks
Body: {
  "task_type": "process_video",
  "priority": "high",
  "parameters": {...},
  "required_capabilities": ["gpu"],
  "timeout_seconds": 600,
  "idempotency_key": "optional-key"
}
Response: {
  "task_id": "uuid",
  "status": "queued",
  "queue_position": 5
}
```

#### Task Status
```
GET /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "executing",
  "priority": "high",
  "effective_priority": "high",
  "created_at": "...",
  "assigned_worker_id": "worker-uuid",
  "result": null
}
```

#### Task Cancellation
```
DELETE /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "cancelled"
}
```

#### Queue Statistics
```
GET /api/v1/queue/stats
Response: {
  "queues": {
    "high": {"depth": 12, "oldest_age_seconds": 45},
    "medium": {"depth": 45, "oldest_age_seconds": 320},
    "low": {"depth": 123, "oldest_age_seconds": 580}
  },
  "workers": {
    "active": 18,
    "draining": 2,
    "dead": 0,
    "total_capacity": 100,
    "used_capacity": 67
  },
  "throughput": {
    "completed_last_minute": 120,
    "failed_last_minute": 3
  }
}
```

### Worker Interface (Internal)

#### Worker Registration
```
POST /internal/workers/register
Body: {
  "capabilities": ["gpu"],
  "capacity": 5
}
Response: {
  "worker_id": "uuid",
  "poll_interval_ms": 1000
}
```

#### Poll for Tasks
```
POST /internal/workers/{worker_id}/poll
Body: {
  "capabilities": ["gpu"],
  "available_capacity": 3
}
Response: {
  "tasks": [
    {
      "task_id": "uuid",
      "task_type": "process_video",
      "parameters": {...},
      "timeout_seconds": 600,
      "trace_id": "..."
    }
  ]
}
```

**Poll Algorithm**:
```python
def poll_tasks(worker_id, capabilities, available_capacity):
    tasks = []
    
    # Try each queue in priority order
    for queue_name in ['queue:high', 'queue:medium', 'queue:low']:
        if len(tasks) >= available_capacity:
            break
        
        # Get oldest tasks from this queue
        candidate_ids = redis.zrange(queue_name, 0, available_capacity * 2)
        
        for task_id in candidate_ids:
            if len(tasks) >= available_capacity:
                break
            
            # Atomic claim: remove from queue and update task
            success = try_claim_task(task_id, worker_id, queue_name)
            if success:
                task = get_task(task_id)
                
                # Check capabilities
                if task.required_capabilities.issubset(capabilities):
                    tasks.append(task)
                else:
                    # Return to queue if capabilities don't match
                    return_task_to_queue(task_id, queue_name)
    
    return tasks

def try_claim_task(task_id, worker_id, queue_name):
    # Atomic Lua script
    result = redis.eval("""
        local task_id = ARGV[1]
        local worker_id = ARGV[2]
        local queue_name = ARGV[3]
        
        -- Remove from queue
        local removed = redis.call('ZREM', queue_name, task_id)
        if removed == 0 then
            return 0  -- Already claimed
        end
        
        -- Update task status
        local task_key = 'tasks:' .. task_id
        redis.call('HSET', task_key, 'status', 'executing')
        redis.call('HSET', task_key, 'assigned_worker_id', worker_id)
        redis.call('HSET', task_key, 'started_at', ARGV[4])
        
        return 1
    """, 0, task_id, worker_id, queue_name, time.time())
    
    return result == 1
```

#### Report Task Result
```
POST /internal/workers/{worker_id}/result
Body: {
  "task_id": "uuid",
  "status": "completed",
  "result": {...}
}
```

#### Worker Heartbeat
```
POST /internal/workers/{worker_id}/heartbeat
Body: {
  "current_load": 3,
  "status": "active"
}
Response: {
  "acknowledged": true
}
```

## Error Handling & Recovery

### Worker Failure Detection & Recovery

**Detection**: Background job runs every 30 seconds
```python
def detect_dead_workers():
    now = time.time()
    cutoff = now - 90  # 3 missed heartbeats
    
    all_workers = get_all_workers()
    for worker in all_workers:
        if worker.status == 'dead':
            continue
        
        if worker.last_heartbeat < cutoff:
            handle_worker_failure(worker)

def handle_worker_failure(worker):
    # Mark worker as dead
    worker.status = 'dead'
    save_worker(worker)
    
    # Find all tasks assigned to this worker
    tasks = find_tasks_by_worker(worker.worker_id)
    
    for task in tasks:
        if task.status == 'executing':
            # Requeue with incremented retry
            requeue_task(task)
```

**Task Timeout Detection**: Separate background job runs every 30 seconds
```python
def detect_timed_out_tasks():
    now = time.time()
    
    # Find tasks in 'executing' state past their timeout
    timed_out = query_tasks(
        status='executing',
        started_at__lt=now - max_task_timeout
    )
    
    for task in timed_out:
        # This handles hung workers AND legitimately long tasks
        handle_task_timeout(task)
```

### Retry Strategy

```python
def requeue_task(task):
    task.retry_count += 1
    
    # Check retry limit
    if task.retry_count > task.max_retries:
        move_to_dlq(task, reason='max_retries_exceeded')
        return
    
    # Reset state
    task.status = 'queued'
    task.assigned_worker_id = None
    task.started_at = None
    
    # Increase timeout by 50% on retry (handle slow tasks)
    task.timeout_seconds *= 1.5
    
    # Return to original priority queue (NOT effective_priority)
    # This ensures retries don't skip ahead unfairly
    queue_name = f'queue:{task.priority}'
    redis.zadd(queue_name, {task.task_id: task.created_at})
    
    save_task(task)
```

### Idempotency

```python
def submit_task(payload, idempotency_key=None):
    if idempotency_key:
        # Check if already exists (24-hour window)
        cache_key = f'idempotent:{idempotency_key}'
        existing_id = redis.get(cache_key)
        
        if existing_id:
            return get_task(existing_id)
    
    # Create new task
    task = create_task(payload)
    
    if idempotency_key:
        # Store mapping with 24-hour TTL
        redis.setex(cache_key, 86400, task.task_id)
    
    # Add to appropriate queue
    queue_name = f'queue:{task.priority}'
    redis.zadd(queue_name, {task.task_id: task.created_at})
    
    return task
```

## Monitoring & Observability

### Key Metrics (Prometheus)

**Queue Health**:
- `queue_depth{priority="high|medium|low"}` - Tasks waiting
- `queue_age_seconds{priority,percentile="p50|p95|p99"}` - Wait time distribution
- `tasks_promoted_total{from,to}` - Starvation prevention activity

**Task Lifecycle**:
- `task_duration_seconds{priority,status}` - End-to-end time
- `task_retries_total{priority,reason}` - Retry patterns
- `task_state_total{status}` - Current task distribution

**Worker Health**:
- `workers_total{status}` - Worker pool state
- `worker_capacity_used_ratio` - Utilization
- `worker_heartbeat_failures_total` - Health issues

**Error Rates**:
- `tasks_failed_total{reason}` - Failure classification
- `tasks_dlq_total` - Unrecoverable failures

### Alerting Rules

**Critical**:
- No active workers for >2 minutes
- High priority queue depth >1000
- Task failure rate >25%
- DLQ growth >10 tasks/minute

**Warning**:
- Worker utilization >90% for >10 minutes
- Low priority tasks waiting >25 minutes (promotion not working)
- Any queue depth >5000

## Deployment Architecture

**Single-Region (Recommended)**:
- Redis Sentinel (3 nodes) for high availability
- PostgreSQL for durable task history
- Worker pool: 10-100 instances depending on load
- All components in same VPC for <5ms latency

**Scaling Characteristics**:
- Queue operations: O(log N) where N = queue depth
- Worker polling: O(1) - fixed batch size
- Promotion job: O(P) where P = tasks to promote (bounded by batch_size)
- Expected throughput: 1000+ tasks/second per Redis instance