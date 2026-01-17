# Claude Code Debate Session

**Started:** 2026-01-17T09:20:59.057362
**Ended:** 2026-01-17T09:27:26.840012
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a task queue system with priority support

---

## Round 1

### 🔵 Agent A

## Design

# Task Queue System with Priority Support

## Architecture Overview

The system follows a **producer-consumer pattern** with priority-based scheduling. It consists of three main layers:

1. **API Layer**: REST/gRPC endpoints for task submission and management
2. **Queue Layer**: Priority queue implementation with persistence
3. **Worker Layer**: Consumer pool that processes tasks based on priority

## Core Components

### 1. Task Queue Manager
- **Responsibilities**: 
  - Accept incoming tasks with priority levels
  - Maintain multiple priority queues (high, medium, low)
  - Distribute tasks to available workers
  - Handle task lifecycle (pending → processing → completed/failed)

### 2. Priority Queue Implementation
- **Structure**: Min-heap based priority queue per priority level
- **Storage**: Redis for in-memory performance + PostgreSQL for durability
- **Keys**:
  - `queue:high`, `queue:medium`, `queue:low` (sorted sets in Redis)
  - Task metadata stored in hash structures

### 3. Worker Pool
- **Architecture**: Dynamic worker pool with auto-scaling
- **Worker States**: idle, busy, dead
- **Health Checks**: Heartbeat mechanism every 30 seconds
- **Concurrency**: Configurable max concurrent tasks per worker

### 4. Task Registry
- **Purpose**: Track all tasks across their lifecycle
- **Storage**: PostgreSQL for persistence and queryability
- **Indexing**: By task_id, status, priority, created_at, user_id

## Data Models

### Task Entity
```json
{
  "task_id": "uuid-v4",
  "priority": "high|medium|low",
  "payload": {
    "task_type": "string",
    "parameters": "json-object"
  },
  "status": "pending|processing|completed|failed|retrying",
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "timestamp",
  "started_at": "timestamp|null",
  "completed_at": "timestamp|null",
  "assigned_worker": "worker-id|null",
  "result": "json-object|null",
  "error": "string|null",
  "timeout_seconds": 300,
  "user_id": "string",
  "idempotency_key": "string|null"
}
```

### Worker Entity
```json
{
  "worker_id": "uuid-v4",
  "status": "idle|busy|dead",
  "current_task_id": "uuid-v4|null",
  "last_heartbeat": "timestamp",
  "capacity": 5,
  "current_load": 2,
  "started_at": "timestamp",
  "tags": ["gpu", "cpu-intensive"]
}
```

### Priority Levels
```json
{
  "high": {"score": 1000, "max_retry_delay_seconds": 10},
  "medium": {"score": 500, "max_retry_delay_seconds": 30},
  "low": {"score": 100, "max_retry_delay_seconds": 60}
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
  "timeout_seconds": 600,
  "idempotency_key": "optional-key"
}
Response: {
  "task_id": "uuid",
  "status": "pending",
  "position_in_queue": 5
}
```

#### Task Status
```
GET /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "processing",
  "progress": 45,
  "created_at": "...",
  "started_at": "..."
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
  "high": {"pending": 12, "processing": 3},
  "medium": {"pending": 45, "processing": 10},
  "low": {"pending": 123, "processing": 5},
  "total_workers": 20,
  "idle_workers": 2
}
```

### Worker Interface (Internal)

#### Poll for Tasks
```
POST /internal/workers/{worker_id}/poll
Body: {
  "worker_capabilities": ["gpu", "cpu-intensive"],
  "capacity": 5
}
Response: {
  "task_id": "uuid",
  "task_type": "process_video",
  "parameters": {...},
  "timeout_seconds": 600
}
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
  "status": "busy"
}
```

## Priority Scheduling Algorithm

### Task Selection Strategy
1. **Priority-first**: Always select highest priority queue with pending tasks
2. **FIFO within priority**: Within same priority, oldest task first
3. **Starvation prevention**: If low-priority tasks wait >10 minutes, boost to medium
4. **Worker affinity**: Match task requirements with worker capabilities

### Scoring Formula
```
task_score = priority_base_score - (current_time - created_time) / aging_factor
```
- Higher score = higher urgency
- Aging factor prevents indefinite starvation

## Error Handling

### Retry Strategy
1. **Exponential backoff**: delay = min(2^retry_count * base_delay, max_delay)
2. **Max retries**: Configurable per priority level (default: 3)
3. **Dead Letter Queue**: Failed tasks after max retries go to DLQ for manual inspection

### Failure Scenarios

#### Worker Failure
- **Detection**: Missed heartbeat (>90 seconds)
- **Recovery**: Mark worker as dead, requeue assigned tasks with priority boost

#### Task Timeout
- **Detection**: Execution time exceeds timeout_seconds
- **Action**: Cancel task, increment retry_count, requeue if retries remaining

#### System Crash
- **Recovery**: On startup, scan for tasks in "processing" state with no live worker
- **Action**: Reset to "pending" and requeue with original priority

#### Queue Overflow
- **Detection**: Queue size exceeds threshold (10,000 tasks)
- **Action**: Return 429 Too Many Requests, implement rate limiting per user

### Data Consistency

#### Idempotency
- Use `idempotency_key` to prevent duplicate task submission
- Store key-to-task_id mapping in Redis with TTL of 24 hours

#### Transaction Guarantees
- Task state transitions use optimistic locking (version field)
- Worker assignment uses Redis distributed locks (redlock algorithm)
- PostgreSQL transactions for critical state changes

#### Visibility Timeout
- When worker polls task, task becomes invisible for timeout_seconds
- If worker doesn't complete/fail within timeout, task becomes visible again

## Monitoring & Observability

### Metrics
- Queue depth per priority level
- Task processing latency (p50, p95, p99)
- Worker utilization rate
- Task success/failure rates
- Retry rates per priority

### Logging
- Structured JSON logs with trace_id propagation
- Log all state transitions with timestamps
- Worker assignments and reassignments

### Alerting
- High queue depth (>1000 pending tasks)
- Low worker availability (<20% idle)
- High failure rate (>10% in 5 minutes)
- Stale tasks (pending >1 hour)

## Rationale

**Why multiple priority queues instead of single sorted queue?**
- Simpler implementation and reasoning about priority
- Easier to prevent starvation with clear boundaries
- Better performance for high-priority tasks (no sorting overhead)

**Why Redis + PostgreSQL hybrid?**
- Redis provides low-latency queue operations
- PostgreSQL ensures durability and queryability for task history
- Async replication from Redis to PostgreSQL balances performance and reliability

**Why worker pull model vs push?**
- Workers control their own load
- Natural backpressure mechanism
- Easier to handle heterogeneous worker capabilities

**Why optimistic locking?**
- Better performance than pessimistic locks
- Conflicts are rare in this workload
- Graceful degradation under contention

## What I Changed

This is the initial design proposal, so no changes from previous iterations.

## What I Kept

N/A - initial proposal.

## Open Questions

1. **Distributed deployment**: Should we support multi-datacenter deployment with geo-distributed queues, or assume single-region deployment?

2. **Task dependencies**: Should tasks support dependencies (task B waits for task A), or keep it simple with independent tasks only?

3. **Priority levels**: Three levels (high/medium/low) sufficient, or should we support numeric priorities (1-10)?

4. **Real-time notifications**: Should we add WebSocket support for real-time task status updates, or polling-only?

## Convergence Status
**ITERATING**: This is the initial design and needs critical review before refinement.

## Prompt for Collaborator
PROMPT_FOR_CRITIC:
Focus on the priority scheduling algorithm and starvation prevention mechanism. Are there edge cases where low-priority tasks could still be starved? Also evaluate if the error handling for worker failures is robust enough for production use.

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Task Queue System with Priority Support

## Architecture Overview

The system implements a **priority-based task scheduling system** with strong guarantees against starvation and robust failure recovery. It uses a **hybrid push-pull model** with three main layers:

1. **API Layer**: REST endpoints for task lifecycle management
2. **Scheduling Layer**: Dynamic priority queue with aging-based starvation prevention
3. **Execution Layer**: Worker pool with capability-based routing and failure detection

## Core Components

### 1. Task Queue Manager
- **Responsibilities**: 
  - Accept incoming tasks with priority levels
  - Maintain a unified priority queue with dynamic scoring
  - Route tasks to capable workers based on requirements
  - Orchestrate task lifecycle (submitted → queued → assigned → executing → terminal state)
  - Implement circuit breakers for cascading failure prevention

### 2. Unified Priority Queue Implementation
- **Structure**: Single Redis sorted set with dynamic composite scores
- **Score Calculation**: 
  ```
  score = (priority_weight × 1000) - (age_seconds × aging_factor)
  
  priority_weight: high=1000, medium=100, low=10
  aging_factor: 0.5 (low priority tasks gain 2 points per second)
  
  Example after 600 seconds:
  - High priority task: 1000000 - (600 × 0.5) = 999700
  - Low priority task: 10000 - (600 × 0.5) = 9700
  ```
- **Storage**: 
  - Redis sorted set `queue:active` for fast priority-based polling
  - Redis hash `tasks:{task_id}` for task metadata
  - PostgreSQL for durable task history and analytics
- **Guaranteed Starvation Prevention**: Mathematical guarantee that any task will eventually reach highest effective priority

### 3. Worker Pool with Capability Matching
- **Architecture**: Auto-scaling worker pool with capability tags
- **Worker States**: `initializing`, `idle`, `busy`, `draining`, `dead`
- **Health Checks**: 
  - Heartbeat every 30 seconds with exponential timeout (3 missed = 90s)
  - Active health probes for workers in `busy` state every 60 seconds
- **Concurrency**: Per-worker semaphore with configurable capacity
- **Graceful Shutdown**: `draining` state prevents new assignments while completing current tasks

### 4. Task State Machine
- **States**: `submitted` → `queued` → `assigned` → `executing` → [`completed` | `failed` | `cancelled` | `dead_letter`]
- **Transitions**: 
  - All transitions recorded with timestamp and triggering event
  - State machine enforced in application layer with PostgreSQL constraints
  - Optimistic locking prevents race conditions

### 5. Dead Letter Queue & Observability
- **DLQ**: Separate Redis sorted set `queue:dlq` for tasks exceeding retry limits
- **DLQ Processing**: Manual review interface + automated replay capability
- **Distributed Tracing**: OpenTelemetry instrumentation for full task journey

## Data Models

### Task Entity
```json
{
  "task_id": "uuid-v4",
  "priority": "high|medium|low",
  "payload": {
    "task_type": "string",
    "parameters": "json-object",
    "required_capabilities": ["gpu", "high-memory"]
  },
  "status": "submitted|queued|assigned|executing|completed|failed|cancelled|dead_letter",
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "timestamp",
  "queued_at": "timestamp|null",
  "assigned_at": "timestamp|null",
  "started_at": "timestamp|null",
  "completed_at": "timestamp|null",
  "assigned_worker": "worker-id|null",
  "result": "json-object|null",
  "error": {
    "message": "string",
    "code": "string",
    "retryable": true,
    "details": "json-object"
  },
  "timeout_seconds": 300,
  "user_id": "string",
  "idempotency_key": "string|null",
  "version": 0,
  "trace_id": "string",
  "estimated_duration_seconds": 60,
  "visibility_timeout_until": "timestamp|null"
}
```

### Worker Entity
```json
{
  "worker_id": "uuid-v4",
  "status": "initializing|idle|busy|draining|dead",
  "current_tasks": ["task-id-1", "task-id-2"],
  "last_heartbeat": "timestamp",
  "consecutive_failures": 0,
  "capacity": 5,
  "current_load": 2,
  "started_at": "timestamp",
  "capabilities": ["gpu", "cpu-intensive", "high-memory"],
  "version": 0,
  "drain_initiated_at": "timestamp|null"
}
```

### Priority Configuration
```json
{
  "high": {
    "weight": 1000,
    "max_retry_delay_seconds": 10,
    "max_retries": 5,
    "timeout_multiplier": 1.0
  },
  "medium": {
    "weight": 100,
    "max_retry_delay_seconds": 30,
    "max_retries": 3,
    "timeout_multiplier": 1.5
  },
  "low": {
    "weight": 10,
    "max_retry_delay_seconds": 60,
    "max_retries": 2,
    "timeout_multiplier": 2.0
  },
  "starvation_prevention": {
    "aging_factor": 0.5,
    "max_wait_seconds": 3600
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
  "estimated_duration_seconds": 120,
  "idempotency_key": "optional-key"
}
Response: {
  "task_id": "uuid",
  "status": "queued",
  "estimated_start_time": "timestamp",
  "position_in_queue": 5
}
```

#### Task Status with History
```
GET /api/v1/tasks/{task_id}?include_history=true
Response: {
  "task_id": "uuid",
  "status": "executing",
  "progress": 45,
  "created_at": "...",
  "assigned_worker": "worker-uuid",
  "state_history": [
    {"state": "submitted", "timestamp": "..."},
    {"state": "queued", "timestamp": "..."},
    {"state": "assigned", "timestamp": "...", "worker_id": "..."},
    {"state": "executing", "timestamp": "..."}
  ]
}
```

#### Task Cancellation
```
DELETE /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "cancelled",
  "cancellation_time": "timestamp"
}
```

#### Queue Statistics with Aging Metrics
```
GET /api/v1/queue/stats
Response: {
  "queue_depth": {
    "high": {"pending": 12, "executing": 3},
    "medium": {"pending": 45, "executing": 10},
    "low": {"pending": 123, "executing": 5}
  },
  "aging_stats": {
    "oldest_queued_task_age_seconds": 450,
    "tasks_waiting_over_threshold": 5
  },
  "workers": {
    "total": 20,
    "idle": 2,
    "busy": 17,
    "draining": 1,
    "dead": 0
  },
  "throughput": {
    "completed_last_minute": 120,
    "failed_last_minute": 3
  }
}
```

#### Dead Letter Queue Management
```
GET /api/v1/dlq
Response: {
  "tasks": [...],
  "total_count": 15
}

POST /api/v1/dlq/{task_id}/replay
Body: {
  "reset_retry_count": true,
  "new_priority": "high"
}
```

### Worker Interface (Internal)

#### Worker Registration
```
POST /internal/workers/register
Body: {
  "capabilities": ["gpu", "high-memory"],
  "capacity": 5
}
Response: {
  "worker_id": "uuid",
  "poll_interval_seconds": 5
}
```

#### Poll for Tasks (with Capability Matching)
```
POST /internal/workers/{worker_id}/poll
Body: {
  "capabilities": ["gpu", "cpu-intensive"],
  "available_capacity": 3
}
Response: [
  {
    "task_id": "uuid",
    "task_type": "process_video",
    "parameters": {...},
    "timeout_seconds": 600,
    "trace_id": "..."
  }
]
```

#### Report Task Progress
```
POST /internal/workers/{worker_id}/progress
Body: {
  "task_id": "uuid",
  "progress_percent": 45,
  "status_message": "Processing frame 450/1000"
}
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

#### Worker Heartbeat with Health
```
POST /internal/workers/{worker_id}/heartbeat
Body: {
  "current_load": 3,
  "status": "busy",
  "health": {
    "memory_usage_percent": 65,
    "cpu_usage_percent": 80
  }
}
Response: {
  "acknowledged": true,
  "should_drain": false
}
```

## Enhanced Priority Scheduling Algorithm

### Unified Scoring with Guaranteed Starvation Prevention

**Mathematical Guarantee**:
```
Given:
- High priority weight: 1000
- Low priority weight: 10
- Aging factor: 0.5

A low-priority task will overtake a high-priority task created simultaneously after:
(1000 × 1000 - 10 × 1000) / 0.5 = 1,980,000 seconds

However, high-priority tasks are typically short-lived. More realistically:
- Low priority task created at t=0: score = 10000
- High priority task created at t=1800 (30 min later): score = 1000000 - 900 = 999100
- Low priority task at t=1800: score = 10000 - 900 = 9100

The low task needs to age enough to overcome the gap:
(999100 - 9100) / 0.5 = 1,980,000 additional seconds

This is extreme, so we add an absolute maximum wait threshold.
```

**Starvation Prevention Rules**:
1. **Dynamic Scoring**: Score decreases linearly with age for ALL tasks
2. **Maximum Wait Time**: Any task waiting > 3600 seconds automatically gets boosted:
   ```
   if (current_time - created_at) > max_wait_seconds:
       effective_priority = "high"
       score = 1000000 - (age × aging_factor)
   ```
3. **Priority Inversion Detection**: If a low-priority task has waited longer than the oldest high-priority task has existed, boost to medium
4. **Fair Scheduling within Priority**: FIFO within the same effective priority band (±100 score points)

### Task Assignment Algorithm

```python
def assign_tasks_to_workers():
    idle_workers = get_idle_workers_sorted_by_capacity()
    
    for worker in idle_workers:
        available_slots = worker.capacity - worker.current_load
        
        # Get top N tasks that match worker capabilities
        candidate_tasks = redis.zrevrange(
            'queue:active', 
            0, 
            available_slots * 2  # Fetch extra for capability filtering
        )
        
        matched_tasks = []
        for task_id in candidate_tasks:
            task = get_task_metadata(task_id)
            
            # Skip if task is visibility-locked
            if task.visibility_timeout_until > now():
                continue
            
            # Check capability match
            if not worker.has_capabilities(task.required_capabilities):
                continue
            
            # Check if task is within priority fairness window
            if len(matched_tasks) > 0:
                score_diff = get_score(matched_tasks[0]) - get_score(task)
                if score_diff > fairness_threshold:
                    break  # Don't assign drastically different priorities together
            
            matched_tasks.append(task)
            if len(matched_tasks) >= available_slots:
                break
        
        # Atomic assignment with optimistic locking
        for task in matched_tasks:
            assign_task_to_worker(task, worker)
```

## Comprehensive Error Handling

### Worker Failure Detection & Recovery

#### Three-Tier Health Monitoring
1. **Heartbeat Monitoring** (Primary):
   - Expected interval: 30 seconds
   - Grace period: 3 missed heartbeats (90 seconds)
   - Action: Mark worker as `dead`, trigger task recovery

2. **Active Health Probes** (Secondary):
   - For workers in `busy` state only
   - HTTP health check every 60 seconds
   - Independent of heartbeat
   - Detects worker hangs or network partitions

3. **Task Timeout Monitoring** (Tertiary):
   - Each task has individual timeout
   - Background job checks for tasks in `executing` state past timeout
   - Action: Cancel task, mark for retry, investigate worker health

#### Worker Failure Recovery Protocol
```
When worker fails (missed heartbeat or failed health probe):

1. Immediately mark worker status as 'dead'
2. Acquire distributed lock on worker_id
3. Query all tasks assigned to worker in 'assigned' or 'executing' state
4. For each task:
   a. Check visibility timeout - if not expired, skip (another worker may have it)
   b. Increment 'worker_failure_count' metric
   c. Reset task state:
      - If in 'assigned': return to 'queued'
      - If in 'executing': 
          - If task duration < 10% of timeout: return to 'queued' (likely not started)
          - If task duration >= 10%: mark as 'failed', increment retry_count
   d. Boost priority by one level (low→medium, medium→high)
   e. Add to queue with boosted score
5. Release distributed lock
6. Log worker failure event with task count
7. Alert if worker failure rate > threshold
```

#### Preventing Thundering Herd on Worker Failure
- **Rate Limiting**: Requeued tasks are staggered by 100ms each
- **Backoff**: Tasks that failed on worker death get additional 5-second delay before becoming visible
- **Load Shedding**: If queue depth exceeds 2× normal capacity, new task submissions return 503

### Enhanced Retry Strategy

#### Intelligent Retry Decision
```python
def should_retry(task, error):
    # Check explicit retryability
    if error.retryable == False:
        return False
    
    # Check retry limits
    if task.retry_count >= task.max_retries:
        return False
    
    # Exponential backoff with jitter
    base_delay = 2 ** task.retry_count
    jitter = random.uniform(0, 0.3 * base_delay)
    delay = min(base_delay + jitter, max_retry_delay_for_priority(task.priority))
    
    # Check error patterns
    if error.code in ['RATE_LIMIT', 'TEMPORARY_UNAVAILABLE']:
        delay *= 2  # Double delay for rate limits
    
    if error.code in ['WORKER_OOM', 'TIMEOUT']:
        # Increase task timeout by 50% on retry
        task.timeout_seconds *= 1.5
    
    # Schedule retry
    task.visibility_timeout_until = now() + delay
    task.retry_count += 1
    redis.zadd('queue:active', task_id, calculate_score(task))
    
    return True
```

#### Retry Limits by Error Type
- **Transient errors** (network, rate limit): 5 retries
- **Resource errors** (OOM, timeout): 3 retries with increased resources
- **Logic errors** (invalid input): 0 retries, immediate DLQ
- **Worker failures**: 3 retries with priority boost

### Data Consistency & Race Condition Prevention

#### Optimistic Locking for State Transitions
```python
def transition_task_state(task_id, expected_state, new_state):
    # Atomic compare-and-swap
    result = redis.eval("""
        local task_key = 'tasks:' .. ARGV[1]
        local current_state = redis.call('HGET', task_key, 'status')
        local version = redis.call('HGET', task_key, 'version')
        
        if current_state == ARGV[2] and version == ARGV[4] then
            redis.call('HSET', task_key, 'status', ARGV[3])
            redis.call('HINCRBY', task_key, 'version', 1)
            redis.call('HSET', task_key, 'updated_at', ARGV[5])
            return 1
        else
            return 0
        end
    """, 0, task_id, expected_state, new_state, current_version, timestamp)
    
    if result == 0:
        raise ConcurrentModificationError()
```

#### Distributed Lock for Worker Assignment
- Uses **Redlock algorithm** with 3 Redis instances
- Lock TTL: 10 seconds (exceeding this indicates system issues)
- Retry: 3 attempts with 200ms delay
- Fallback: If redlock fails, use PostgreSQL advisory locks (slower but guaranteed)

#### Idempotency Guarantees
```python
def submit_task(payload, idempotency_key=None):
    if idempotency_key:
        # Check cache first (24-hour TTL)
        existing_task_id = redis.get(f'idempotency:{idempotency_key}')
        if existing_task_id:
            return get_task(existing_task_id)
        
        # Acquire lock on idempotency key
        with redis_lock(f'lock:idempotency:{idempotency_key}', timeout=5):
            # Double-check after acquiring lock
            existing_task_id = redis.get(f'idempotency:{idempotency_key}')
            if existing_task_id:
                return get_task(existing_task_id)
            
            # Create task
            task = create_task_internal(payload)
            
            # Store idempotency mapping
            redis.setex(
                f'idempotency:{idempotency_key}',
                86400,  # 24 hours
                task.task_id
            )
            
            return task
    else:
        return create_task_internal(payload)
```

### Cascading Failure Prevention

#### Circuit Breaker Pattern
```python
class WorkerCircuitBreaker:
    def __init__(self, worker_id):
        self.failure_threshold = 5
        self.timeout = 60  # seconds
        self.half_open_attempts = 3
    
    def record_failure(self):
        failures = redis.incr(f'circuit:{worker_id}:failures')
        redis.expire(f'circuit:{worker_id}:failures', self.timeout)
        
        if failures >= self.failure_threshold:
            self.open_circuit()
    
    def open_circuit(self):
        redis.setex(f'circuit:{worker_id}:state', self.timeout, 'open')
        # Stop assigning tasks to this worker
        
    def attempt_half_open(self):
        # After timeout, try limited assignments
        pass
```

#### Queue Overflow Protection
```
Rate Limiting per User:
- Burst: 100 tasks/minute
- Sustained: 1000 tasks/hour
- Storage: Redis sliding window counter

Global Backpressure:
- If queue depth > 10,000: Return 429 with Retry-After header
- If queue depth > 50,000: Reject all submissions except priority=high
- If queue depth > 100,000: Emergency mode - only accept from allowlist
```

## Monitoring & Observability

### Key Metrics (exported to Prometheus)

**Queue Health**:
- `queue_depth{priority="high|medium|low"}` - Current tasks in queue
- `queue_age_seconds{percentile="p50|p95|p99"}` - Task wait time by percentile
- `starvation_risk_count` - Tasks waiting > 80% of max_wait_seconds

**Task Lifecycle**:
- `task_duration_seconds{status="completed|failed"}` - End-to-end duration
- `task_retry_count{reason="worker_failure|timeout|error"}` - Retry reasons
- `task_state_transitions_total{from="X",to="Y"}` - State machine flow

**Worker Health**:
- `worker_count{status="idle|busy|draining|dead"}` - Worker distribution
- `worker_utilization_percent` - Average utilization across pool
- `worker_failure_rate` - Failures per minute
- `task_assignment_duration_seconds` - Time to assign task to worker

**Error Rates**:
- `task_dlq_total{reason="max_retries|unrecoverable_error"}` - DLQ additions
- `concurrent_modification_errors_total` - Lock contention
- `circuit_breaker_state{worker_id}` - Worker circuit breaker states

### Structured Logging
```json
{
  "timestamp": "2024-01-15T10:30:45.123Z",
  "level": "INFO",
  "trace_id": "abc123",
  "span_id": "def456",
  "event": "task_state_transition",
  "task_id": "uuid",
  "from_state": "queued",
  "to_state": "assigned",
  "worker_id": "worker-uuid",
  "priority": "high",
  "age_seconds": 45,
  "retry_count": 0,
  "user_id": "user-123"
}
```

### Alerting Rules

**Critical**:
- Worker failure rate > 20% over 5 minutes
- Queue depth > 50,000 for any priority
- DLQ growth rate > 10 tasks/minute
- Task completion rate drops by 50% compared to baseline

**Warning**:
- Tasks waiting > max_wait_seconds (starvation)
- Worker availability < 20% idle
- Retry rate > 15% of completions
- Circuit breakers open for > 5 workers

**Info**:
- Queue depth > 5,000
- Worker pool auto-scaled
- Idempotency key collision rate elevated

## Deployment Considerations

### Single-Region Deployment (Recommended)
- Single Redis cluster (3 nodes, sentinel for HA)
- PostgreSQL primary with read replicas
- Worker pool in same VPC/region
- Latency: <5ms for queue operations

### Multi-Region (Advanced)
- Redis cluster per region with async replication
- Global PostgreSQL with region-specific read replicas
- Task affinity to submission region
- Cross-region failover with task reconciliation
- Latency: <20ms for queue operations

## Rationale

### Why Unified Queue with Dynamic Scoring?
**Better than multiple separate queues because**:
- **Mathematical guarantee** against starvation (impossible with separate queues + boost)
- Simpler reasoning about priority - no manual threshold tuning
- No edge cases where boost timing affects fairness
- Single atomic operation to get highest priority task
- Aging is continuous and automatic, not periodic

### Why Hybrid Redis + PostgreSQL?
- **Redis** provides O(log N) priority queue operations with sub-millisecond latency
- **PostgreSQL** provides durable storage, complex queries, and task history
- Async replication keeps databases in sync without blocking queue operations
- Redis failure: Can rebuild queue from PostgreSQL in <10 seconds
- PostgreSQL failure: Queue continues operating, history queued for replay

### Why Capability-Based Routing?
- Prevents task assignment to incompatible workers (GPU task to CPU worker)
- Enables heterogeneous worker pools with specialized hardware
- Allows gradual worker pool composition changes
- Foundation for auto-scaling based on capability demand

### Why Optimistic Locking?
- **10x better throughput** than pessimistic locks under normal load
- Conflicts are rare (<1%) in this workload
- Graceful retry mechanism
- Fallback to PostgreSQL advisory locks for rare high-contention scenarios

### Why Visibility Timeout?
- Prevents duplicate processing if worker polls but crashes before heartbeat
- Allows automatic recovery without explicit failure detection
- Standard pattern from AWS SQS, battle-tested at scale
- Simpler than distributed task ownership tracking

## What I Improved

1. **Starvation Prevention**: Replaced discrete priority queues with unified queue + dynamic scoring, providing **mathematical guarantee** against starvation rather than heuristic boosting.

2. **Worker Failure Detection**: Added **three-tier health monitoring** (heartbeat, active probes, task timeout) to catch all failure modes including network partitions and hung workers.

3. **Race Condition Prevention**: Added comprehensive **optimistic locking** for state transitions, **Redlock** for worker assignment, and **visibility timeouts** to prevent duplicate processing.

4. **Task Recovery Protocol**: Detailed **step-by-step recovery procedure** for worker failures with priority boosting, thundering herd prevention, and intelligent retry decisions.

5. **Capability-Based Routing**: Added worker capabilities and task requirements to prevent mismatched assignments and enable heterogeneous worker pools.

6. **Circuit Breaker Pattern**: Protect against cascading failures by temporarily isolating consistently failing workers.

7. **Enhanced State Machine**: More detailed states (`assigned` vs `executing`) to better track task lifecycle and enable smarter recovery decisions.

8. **DLQ Management**: Added replay capability and manual review interface for dead letter queue, not just storage.

9. **Monitoring**: Added specific metrics for starvation risk, aging statistics, and circuit breaker states beyond basic queue depth.

## What I Kept

1. **Core Architecture**: Three-layer design (API, Queue, Worker) is sound and well-separated.

2. **Data Models**: Task and Worker entities are comprehensive with good metadata.

3. **Idempotency Handling**: Redis-based idempotency key mapping with 24-hour TTL is appropriate.

4. **Retry Strategy**: Exponential backoff with priority-based max delays is industry standard.

5. **REST API Design**: Endpoints are clean and RESTful with appropriate HTTP semantics.

6. **Pull Model for Workers**: Worker-controlled load is correct approach for backpressure.

## Remaining Concerns

1. **Redis Single Point of Failure**: While sentinel provides HA, there's still potential for split-brain scenarios. Consider Redis Cluster for true distributed operation at scale.

2. **Task Payload Size**: No limits specified on `payload.parameters` size. Large payloads could impact Redis memory and network. Recommend 1MB limit with external storage (S3) for larger data.

3. **Long-Running Tasks**: Tasks running for hours may hold worker capacity. Consider splitting into smaller chunks or separate "batch job" system.

4. **Cost at Scale**: Redis memory for large queues can be expensive. May need cold storage tier for tasks in `submitted` state waiting for capacity.

5. **Cross-Datacenter Latency**: Multi-region deployment has unresolved task reconciliation complexity if regions become partitioned.

## Convergence Status
**ITERATING**: Design significantly improved but would benefit from architect's review of dynamic scoring algorithm and feedback on complexity trade-offs.

## Prompt for Collaborator
PROMPT_FOR_ARCHITECT:
Please review the unified priority queue with dynamic scoring versus your separate queue approach. The math provides starvation guarantees, but adds complexity. Also evaluate whether the three-tier health monitoring for workers is over-engineered or necessary for production robustness. Consider if there are simplifications that maintain the guarantees while reducing implementation complexity.

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

### Why Three Separate Queues Instead of Unified Dynamic Scoring?

**Simplicity wins**:
1. **Easier to debug**: "Task X is in the medium queue at position 47" vs. "Task X has score 99,234"
2. **Predictable behavior**: Users understand "promoted after 10 minutes" intuitively
3. **Simpler code**: No complex score calculation, just FIFO within each queue
4. **Cheaper operations**: ZRANGE with time score is faster than computed scores
5. **Observable**: Can monitor each queue independently

**Trade-off accepted**: Promotion happens in 60-second intervals rather than continuously. This is acceptable because:
- 60 seconds is negligible compared to 10-minute promotion threshold
- Reduces Redis load (promotion is a batch operation)
- Makes testing and validation easier

### Why Simplified State Machine?

The original design had 7 states: `submitted → queued → assigned → executing → completed|failed|cancelled|dead_letter`

**Problems with `assigned` state**:
- Adds recovery complexity: what if worker crashes after `assigned` but before `executing`?
- Requires separate timeout monitoring for assignment phase
- Creates ambiguity: who is responsible for the task?

**Solution**: Workers atomically claim tasks during poll (`queued` → `executing`). If worker crashes before processing, task timeout handles recovery. This is simpler and handles all edge cases.

### Why Heartbeat-Only Health Monitoring?

The collaborator's design had three-tier monitoring (heartbeat + active probes + task timeout). 

**Analysis**:
- **Heartbeat**: Necessary and sufficient for worker liveness
- **Active health probes**: Adds complexity, requires health probe infrastructure, creates new failure modes
- **Task timeout**: Necessary and independent - catches hung workers AND legitimately slow tasks

**Conclusion**: Heartbeat + task timeout covers all scenarios:
- Worker crashes: Heartbeat fails
- Worker hangs: Task timeout fires
- Worker slow but progressing: Legitimate, no action needed
- Network partition: Both heartbeat and task timeout will trigger

Adding active probes doesn't add coverage but does add failure modes (probe service down, probe timeouts, etc.).

### Why Fixed Worker Pool?

Simpler than auto-scaling for initial version. Benefits:
- Predictable capacity and cost
- No scaling algorithm to tune
- Easier to reason about system load
- Can add auto-scaling later without changing core design

### Why Redis + PostgreSQL?

**Redis**: 
- Sub-millisecond queue operations
- Atomic claim operations via Lua scripts
- Native sorted set for FIFO ordering

**PostgreSQL**:
- Durable task history for analytics
- Complex queries for monitoring
- Reliable storage for task results

**Separation of concerns**: Redis is ephemeral (can rebuild from PostgreSQL), PostgreSQL is source of truth.

## What I Changed

1. **Simplified Priority System**: Replaced complex dynamic scoring with discrete queues + periodic promotion. Easier to understand, debug, and maintain while still preventing starvation.

2. **Reduced State Machine Complexity**: Eliminated `submitted` and `assigned` states. Workers atomically claim tasks from `queued` → `executing`.

3. **Two-Tier Health Monitoring**: Removed active health probes. Heartbeat + task timeout covers all failure scenarios with less complexity.

4. **Simplified Worker States**: Reduced from 5 states to 3 (`active`, `draining`, `dead`). Removed `initializing` and `busy` as they don't add actionable information.

5. **Removed Optimistic Locking**: Used atomic Lua scripts for critical operations instead. Simpler and avoids retry loops.

6. **Removed Visibility Timeouts**: Not needed with atomic claim operation. Worker either has the task or doesn't.

7. **Fixed Worker Pool**: Removed auto-scaling complexity from initial design. Can add later if needed.

8. **Streamlined Task Entity**: Removed fields that weren't used in core workflows (`estimated_duration_seconds`, `visibility_timeout_until`, user tracking).

## What I Kept

1. **Three-Layer Architecture**: API, Queue, Worker separation is clean and correct.

2. **Worker-Pull Model**: Workers control their own load, providing natural backpressure.

3. **Capability-Based Routing**: Essential for heterogeneous worker pools.

4. **Idempotency Keys**: 24-hour Redis-based deduplication is industry standard.

5. **Dead Letter Queue**: Necessary for handling unrecoverable failures.

6. **Priority Levels**: High/Medium/Low is intuitive and sufficient.

7. **Retry Strategy**: Exponential backoff with priority-based limits is appropriate.

## Open Questions

1. **Promotion Thresholds**: Are 10/20 minutes the right values? Should be configurable per deployment based on SLA requirements.

2. **Task Payload Size**: Need to define max size (suggest 256KB). Larger payloads should use external storage with reference in task.

3. **Long-Running Tasks**: Tasks running for hours may hold worker capacity. Consider separate "batch job" system or streaming progress updates.

4. **Multi-Region**: Current design is single-region. Multi-region adds significant complexity around task ownership and queue consistency.

5. **Worker Authentication**: How do workers authenticate to the system? Need to add auth tokens or mTLS.

## Convergence Status
**ITERATING** - This design is significantly simplified while maintaining core guarantees. However, it represents a major architectural shift (unified queue → separate queues) that warrants detailed review.

## Prompt for Collaborator
PROMPT_FOR_CRITIC:
Please focus your review on:

1. **Starvation Prevention**: Does the discrete promotion approach (low→medium at 10min, medium→high at 20min) provide adequate fairness compared to continuous dynamic scoring? Are there edge cases where tasks could wait longer than 30 minutes?

2. **Atomic Claim Operation**: Does the Lua script approach for claiming tasks (removing from queue + updating task state) adequately prevent race conditions? Are there scenarios where two workers could claim the same task?

3. **Health Monitoring**: Is heartbeat + task timeout truly sufficient? Are there worker failure modes that would be missed without active health probes?

4. **Complexity Reduction**: Does this design sacrifice important capabilities for simplicity? What are the practical operational impacts of the removed features (optimistic locking, visibility timeouts, fine-grained states)?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Task Queue System with Priority Support

## Architecture Overview

The system implements a **priority-based task scheduling system** with guaranteed starvation prevention and comprehensive failure recovery. It uses a **worker-pull model** with four main layers:

1. **API Layer**: REST endpoints for task lifecycle management
2. **Scheduling Layer**: Unified priority queue with continuous fair scheduling
3. **Execution Layer**: Worker pool with dual-mode health monitoring
4. **Persistence Layer**: Redis for hot path, PostgreSQL for durability

## Core Components

### 1. Task Queue Manager
- **Responsibilities**: 
  - Accept incoming tasks with priority levels (high, medium, low)
  - Maintain unified priority queue with age-aware scoring
  - Route tasks to workers based on capability matching
  - Orchestrate task lifecycle (queued → assigned → executing → terminal state)
  - Handle task timeouts, retries, and cancellations

### 2. Unified Priority Queue with Continuous Fair Scheduling

**Structure**: Single Redis sorted set with composite score
```
queue:tasks - All queued tasks (scored by priority + age)
```

**Scoring Function**: Continuous, monotonically increasing
```python
def calculate_task_score(task):
    now = time.time()
    age_seconds = now - task.created_at
    
    # Base priority scores (lower = higher priority)
    priority_base = {
        'high': 0,
        'medium': 100_000,
        'low': 200_000
    }
    
    # Age component: subtract age to move older tasks forward
    # 1 second of age = 1 point reduction in score
    # This ensures older tasks gradually overtake newer ones
    age_score = -min(age_seconds, 100_000)  # Cap at 100k to prevent score inversion
    
    return priority_base[task.priority] + age_score
```

**Starvation Prevention Guarantees**:
- High priority tasks execute immediately unless queue is full
- Medium priority tasks will overtake newer high priority tasks after ~27.8 hours
- Low priority tasks will overtake newer medium priority tasks after ~27.8 hours
- Maximum theoretical wait: ~55.6 hours for a low priority task (in practice much shorter)

**Rationale**: This provides **continuous fairness** without discrete jumps. The scoring is:
- **Predictable**: Score calculation is deterministic and testable
- **Observable**: Can query task score at any time
- **Self-balancing**: No background jobs needed for promotion
- **Fair**: Older tasks naturally move forward without manual intervention
- **Debuggable**: Score explains exact queue position

**Why Unified Queue Is Better**:
1. **No promotion lag**: Tasks move forward continuously, not in 60-second batches
2. **Atomic priority**: Single ZRANGE operation gets next task, no queue-hopping logic
3. **Simpler recovery**: One queue to restore, not three
4. **Better observability**: One metric for queue depth, clearer system state
5. **Flexible tuning**: Can adjust age weight without changing queue structure

### 3. Enhanced Task State Machine

**States**: `queued` → `assigned` → `executing` → [`completed` | `failed` | `cancelled` | `dead_letter`]

**Why Keep `assigned` State**:
The `assigned` state is **critical for accurate failure recovery**:

```python
# Without 'assigned' state (architect's design):
# Worker polls and atomically moves task from queued → executing
# Problem: If worker crashes AFTER poll but BEFORE starting task,
# only the task timeout (5-15 minutes) will detect this failure

# With 'assigned' state:
queued → assigned (worker acknowledged receipt)
       ↓ 
       executing (worker started processing)

# Recovery windows:
# - assigned → executing: 30 seconds (fast recovery)
# - executing → timeout: 5-15 minutes (normal timeout)
```

**Assignment Timeout Detection**: Background job runs every 10 seconds
```python
def detect_stalled_assignments():
    now = time.time()
    assignment_timeout = 30  # seconds
    
    # Find tasks stuck in 'assigned' state
    stalled = query_tasks(
        status='assigned',
        assigned_at__lt=now - assignment_timeout
    )
    
    for task in stalled:
        # Worker crashed after claiming but before executing
        logger.warning(f"Task {task.task_id} stalled in assignment, requeueing")
        requeue_task(task, reason='assignment_timeout')
```

**Real-World Impact**:
- Worker pod killed during rolling deployment: Recovers in 30s instead of 5-15min
- Worker OOM during task initialization: Recovers in 30s instead of 5-15min
- Network partition during claim operation: Recovers in 30s instead of 5-15min

**State Transitions**:
```
queued ──[worker poll]──> assigned ──[worker start]──> executing
   ↑                          ↓                              ↓
   │                     [30s timeout]                  [task timeout]
   └──────────────────────────┴──────────────────────────────┘
                            [requeue with retry++]
```

### 4. Worker Pool with Dual-Mode Health Monitoring

**Architecture**: Dynamic worker pool with capability tags
- **Worker States**: `active`, `draining`, `unhealthy`, `dead`
- **Dual-Mode Health Checks**:
  - **Passive (Heartbeat)**: Every 30 seconds, 3 missed = `dead` (90s)
  - **Active (Health Probe)**: Every 60 seconds, 2 failures = `unhealthy` (120s)
- **Concurrency**: Per-worker capacity (default: 5 concurrent tasks)
- **Graceful Shutdown**: `draining` state prevents new assignments

**Why Dual-Mode Monitoring**:

| Failure Mode | Heartbeat Only | + Health Probe | Benefit |
|--------------|----------------|----------------|---------|
| Worker crash | ✅ Detects (90s) | ✅ Detects (90s) | No change |
| Worker hang (thread deadlock) | ✅ Detects via task timeout (5-15min) | ✅ Detects (120s) | **3-13min faster** |
| Worker resource exhaustion (OOM imminent) | ❌ Misses until OOM crashes | ✅ Detects (120s) | **Proactive** |
| Network partition (worker isolated) | ✅ Detects (90s) | ✅ Detects (120s) | No change |
| Dependency failure (DB connection pool exhausted) | ❌ Misses until task timeout | ✅ Detects (120s) | **3-13min faster** |

**Health Probe Implementation**:
```python
# Worker exposes /health endpoint
@app.get("/health")
def health_check():
    checks = {
        "memory": check_memory_usage(),      # < 90% used
        "connections": check_db_connections(), # pool not exhausted
        "cpu": check_cpu_usage(),            # < 95% over 30s
        "threads": check_thread_status()     # no deadlocks detected
    }
    
    if all(checks.values()):
        return {"status": "healthy", "checks": checks}
    else:
        return {"status": "unhealthy", "checks": checks}, 503

# Queue manager probes workers
def probe_worker_health(worker):
    try:
        response = http_client.get(
            f"http://{worker.host}/health",
            timeout=5
        )
        return response.status_code == 200
    except (Timeout, ConnectionError):
        return False

def monitor_worker_health():
    """Runs every 60 seconds"""
    for worker in get_active_workers():
        if not probe_worker_health(worker):
            worker.health_failures += 1
            
            if worker.health_failures >= 2:
                # Mark unhealthy, stop new assignments
                worker.status = 'unhealthy'
                logger.warning(f"Worker {worker.id} marked unhealthy")
                
                # Tasks already assigned continue (may recover)
                # No immediate requeue - wait for task timeout
        else:
            worker.health_failures = 0  # Reset on success
```

**Rationale for Active Probes**:
- **Catches pre-failure states**: Resource exhaustion before crash
- **Faster failure detection**: 120s vs 5-15min for hung workers
- **Operational visibility**: Health dashboard shows degraded workers
- **Graceful degradation**: Stop new assignments while investigating
- **Cost is minimal**: 60-second interval, simple HTTP check, < 10ms overhead per worker

**Complexity Trade-off**:
- **Added complexity**: ~100 lines of code, one background job, health endpoint
- **Value delivered**: 3-13 minute faster recovery for common failure modes
- **Mitigation**: Health probe failures don't requeue tasks (only stop new assignments), so false positives are non-disruptive

### 5. Atomic Task Claiming with Visibility Timeout

**Why Visibility Timeout Matters**:

The architect's design uses atomic claim (remove from queue + update status). This has a **critical race condition window**:

```python
# Architect's approach:
def try_claim_task(task_id, worker_id):
    # Lua script: ZREM + HSET (atomic)
    redis.eval("""
        redis.call('ZREM', 'queue:tasks', task_id)  -- Remove from queue
        redis.call('HSET', 'tasks:' .. task_id, 'status', 'assigned')
    """)
    
# Problem: What if this worker crashes here, before starting the task?
# The task is NOT in the queue anymore, but also not executing.
# Only the 5-15 minute task timeout will rescue it.
```

**Solution: Visibility Timeout Pattern**
```python
def try_claim_task(task_id, worker_id):
    now = time.time()
    visibility_timeout = 30  # seconds
    
    # Lua script: Update score to future time (becomes invisible)
    result = redis.eval("""
        local task_id = ARGV[1]
        local worker_id = ARGV[2]
        local invisible_until = ARGV[3]
        
        -- Check current score (if missing, already claimed)
        local current_score = redis.call('ZSCORE', 'queue:tasks', task_id)
        if not current_score then
            return 0  -- Already claimed
        end
        
        -- Update score to future time (makes it invisible to ZRANGEBYSCORE)
        redis.call('ZADD', 'queue:tasks', invisible_until, task_id)
        
        -- Update task metadata
        redis.call('HSET', 'tasks:' .. task_id, 'status', 'assigned')
        redis.call('HSET', 'tasks:' .. task_id, 'assigned_worker_id', worker_id)
        redis.call('HSET', 'tasks:' .. task_id, 'assigned_at', ARGV[4])
        redis.call('HSET', 'tasks:' .. task_id, 'visibility_timeout_until', invisible_until)
        
        return 1
    """, 0, task_id, worker_id, now + visibility_timeout, now)
    
    return result == 1

# When worker starts task execution:
def start_task_execution(task_id):
    # Remove from queue permanently
    redis.zrem('queue:tasks', task_id)
    redis.hset(f'tasks:{task_id}', 'status', 'executing')
    redis.hset(f'tasks:{task_id}', 'started_at', time.time())
```

**Recovery with Visibility Timeout**:
```python
def recover_invisible_tasks():
    """Runs every 10 seconds"""
    now = time.time()
    
    # Find tasks with visibility timeout expired but still in queue
    # (Worker crashed after claim but before starting execution)
    expired_tasks = redis.zrangebyscore(
        'queue:tasks',
        0,  # Old score (before claim)
        now,  # Current time
        withscores=True
    )
    
    for task_id, score in expired_tasks:
        task = get_task(task_id)
        
        # Check if task is in 'assigned' state with expired visibility
        if task.status == 'assigned' and task.visibility_timeout_until <= now:
            # Worker crashed, requeue task
            requeue_task(task, reason='visibility_timeout_expired')
```

**Benefits**:
- **Fast recovery**: 30 seconds instead of 5-15 minutes
- **Task never lost**: Stays in queue with modified score until explicitly removed
- **Idempotent**: Multiple recovery attempts are safe
- **Observable**: Can monitor visibility timeout expirations as a health metric

**Comparison**:
| Approach | Worker Crash After Claim | Recovery Time | Queue Consistency |
|----------|--------------------------|---------------|-------------------|
| Atomic Remove | Task missing from queue, stuck in `assigned` | 5-15 minutes (task timeout) | ❌ Queue doesn't reflect reality |
| Visibility Timeout | Task in queue with future score | 30 seconds | ✅ Queue is source of truth |

### 6. Dead Letter Queue & Enhanced Observability

**DLQ Structure**:
```python
# Redis sorted set
queue:dlq - Scored by timestamp when moved to DLQ

# PostgreSQL table for analysis
CREATE TABLE dead_letter_tasks (
    task_id UUID PRIMARY KEY,
    original_task JSONB,
    failure_reason TEXT,
    retry_history JSONB,
    moved_to_dlq_at TIMESTAMP,
    last_error TEXT
);
```

**DLQ Analytics**:
```python
# Automated pattern detection
def analyze_dlq_patterns():
    """Runs hourly"""
    recent_dlq = query_dlq_tasks(last_hours=24)
    
    # Group by failure reason
    failure_counts = Counter(t.failure_reason for t in recent_dlq)
    
    # Alert if new failure pattern emerges
    if failure_counts['dependency_timeout'] > 50:
        alert('High dependency timeout rate in DLQ')
    
    # Identify tasks safe to retry
    retriable = [t for t in recent_dlq if t.error.retriable]
    if len(retriable) > 100:
        alert(f'{len(retriable)} retriable tasks in DLQ, consider bulk replay')
```

**Observability Enhancements**:

**Metrics** (Prometheus):
```python
# Queue health
queue_depth_total
queue_score_p50, queue_score_p95  # Track score distribution
task_age_seconds{priority, percentile}

# Task lifecycle (with assigned state)
task_duration_seconds{priority, status}
task_state_transitions_total{from, to}  # Track state machine flow
task_claim_latency_seconds  # Time to claim after queued

# Worker health (dual-mode)
workers_total{status}  # active, draining, unhealthy, dead
worker_heartbeat_failures_total
worker_health_probe_failures_total  # New
worker_capacity_used_ratio

# Assignment phase (new visibility into fast recovery)
task_assignment_timeouts_total  # Tasks stuck in 'assigned'
task_visibility_timeouts_total  # Visibility timeout recoveries

# Error patterns
tasks_failed_total{reason, priority}
tasks_dlq_total{reason}
task_retries_total{attempt}
```

**Tracing**:
```python
# Distributed tracing with OpenTelemetry
span = tracer.start_span('task.lifecycle', {
    'task.id': task_id,
    'task.priority': priority,
    'task.type': task_type
})

# Child spans for each state transition
with tracer.start_span('task.queued', parent=span):
    add_to_queue(task)

with tracer.start_span('task.assigned', parent=span):
    assign_to_worker(task, worker_id)

with tracer.start_span('task.executing', parent=span):
    execute_task(task)
```

**Dashboard Panels**:
1. **Queue Health**: Depth, age distribution, score histogram
2. **Worker Pool**: Status distribution, capacity utilization, health trends
3. **Task Flow**: State transition rates, assignment→execution latency
4. **Error Analysis**: Failure reasons, retry patterns, DLQ growth
5. **Performance**: Task duration by priority, throughput, p99 latency

## Data Models

### Task Entity
```json
{
  "task_id": "uuid-v4",
  "priority": "high|medium|low",
  "payload": {
    "task_type": "string",
    "parameters": "json-object",
    "required_capabilities": ["gpu"]
  },
  "status": "queued|assigned|executing|completed|failed|cancelled|dead_letter",
  "retry_count": 0,
  "max_retries": 3,
  "created_at": "timestamp",
  "assigned_at": "timestamp|null",
  "started_at": "timestamp|null",
  "completed_at": "timestamp|null",
  "assigned_worker_id": "worker-id|null",
  "visibility_timeout_until": "timestamp|null",
  "queue_score": "float",
  "result": "json-object|null",
  "error": {
    "message": "string",
    "retriable": true,
    "failure_reason": "string"
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
  "status": "active|draining|unhealthy|dead",
  "current_tasks": ["task-id-1", "task-id-2"],
  "last_heartbeat": "timestamp",
  "health_failures": 0,
  "capacity": 5,
  "current_load": 2,
  "capabilities": ["gpu", "cpu-intensive"],
  "version": "string",
  "host": "worker-pod-123.default.svc.cluster.local"
}
```

### Priority Configuration
```json
{
  "high": {
    "max_retries": 5,
    "timeout_seconds": 300,
    "base_score": 0
  },
  "medium": {
    "max_retries": 3,
    "timeout_seconds": 600,
    "base_score": 100000
  },
  "low": {
    "max_retries": 2,
    "timeout_seconds": 900,
    "base_score": 200000
  },
  "starvation_prevention": {
    "age_weight": 1.0,
    "max_age_bonus": 100000
  },
  "recovery": {
    "assignment_timeout_seconds": 30,
    "visibility_timeout_seconds": 30,
    "heartbeat_interval_seconds": 30,
    "heartbeat_timeout_multiplier": 3,
    "health_probe_interval_seconds": 60,
    "health_probe_failures_threshold": 2
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
  "estimated_wait_seconds": 12,
  "queue_score": 145.3
}
```

#### Task Status
```
GET /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "executing",
  "priority": "high",
  "created_at": "...",
  "assigned_at": "...",
  "started_at": "...",
  "assigned_worker_id": "worker-uuid",
  "current_state_duration_seconds": 45,
  "result": null
}
```

#### Task Cancellation
```
DELETE /api/v1/tasks/{task_id}
Response: {
  "task_id": "uuid",
  "status": "cancelled",
  "was_executing": true,
  "worker_notified": true
}
```

#### Queue Statistics
```
GET /api/v1/queue/stats
Response: {
  "queue": {
    "total_depth": 180,
    "by_priority": {
      "high": 12,
      "medium": 45,
      "low": 123
    },
    "oldest_age_seconds": 580,
    "p50_age_seconds": 120,
    "p95_age_seconds": 420
  },
  "workers": {
    "active": 18,
    "draining": 2,
    "unhealthy": 1,
    "dead": 0,
    "total_capacity": 100,
    "used_capacity": 67
  },
  "throughput": {
    "completed_last_minute": 120,
    "failed_last_minute": 3,
    "avg_task_duration_seconds": 8.3
  },
  "recovery_stats": {
    "assignment_timeouts_last_hour": 2,
    "visibility_timeouts_last_hour": 1,
    "health_probe_failures_last_hour": 3
  }
}
```

### Worker Interface (Internal)

#### Worker Registration
```
POST /internal/workers/register
Body: {
  "capabilities": ["gpu"],
  "capacity": 5,
  "host": "worker-pod-123.default.svc.cluster.local"
}
Response: {
  "worker_id": "uuid",
  "poll_interval_ms": 1000,
  "heartbeat_interval_ms": 30000
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
      "trace_id": "...",
      "visibility_timeout_until": "timestamp"
    }
  ]
}
```

**Poll Algorithm with Unified Queue**:
```python
def poll_tasks(worker_id, capabilities, available_capacity):
    now = time.time()
    tasks = []
    
    # Get tasks with lowest scores (highest priority + oldest)
    # Only fetch tasks that are currently visible (score <= now)
    candidate_ids = redis.zrangebyscore(
        'queue:tasks',
        '-inf',
        now,  # Only visible tasks
        start=0,
        num=available_capacity * 3  # Oversubscribe for capability filtering
    )
    
    for task_id in candidate_ids:
        if len(tasks) >= available_capacity:
            break
        
        # Try to claim task with visibility timeout
        success = try_claim_task(task_id, worker_id)
        if not success:
            continue  # Another worker claimed it
        
        task = get_task(task_id)
        
        # Check capabilities
        if task.required_capabilities.issubset(capabilities):
            tasks.append(task)
        else:
            # Return to queue if capabilities don't match
            release_task_claim(task_id)
    
    return tasks
```

#### Start Task Execution
```
POST /internal/workers/{worker_id}/start
Body: {
  "task_id": "uuid"
}
Response: {
  "acknowledged": true
}
```

#### Report Task Result
```
POST /internal/workers/{worker_id}/result
Body: {
  "task_id": "uuid",
  "status": "completed",
  "result": {...},
  "execution_duration_seconds": 45.2
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
  "acknowledged": true,
  "should_drain": false
}
```

## Error Handling & Recovery

### Worker Failure Detection & Recovery

**Heartbeat Monitoring** (runs every 30 seconds):
```python
def detect_dead_workers():
    now = time.time()
    cutoff = now - 90  # 3 missed heartbeats
    
    all_workers = get_active_workers()
    for worker in all_workers:
        if worker.status == 'dead':
            continue
        
        if worker.last_heartbeat < cutoff:
            handle_worker_failure(worker, reason='heartbeat_timeout')

def handle_worker_failure(worker, reason):
    worker.status = 'dead'
    save_worker(worker)
    
    # Find all tasks assigned to this worker
    assigned_tasks = find_tasks_by_worker(worker.worker_id, status='assigned')
    executing_tasks = find_tasks_by_worker(worker.worker_id, status='executing')
    
    # Requeue assigned tasks immediately (fast recovery)
    for task in assigned_tasks:
        requeue_task(task, reason=f'worker_failure_{reason}')
    
    # Requeue executing tasks with retry
    for task in executing_tasks:
        requeue_task(task, reason=f'worker_failure_{reason}')
```

**Health Probe Monitoring** (runs every 60 seconds):
```python
def monitor_worker_health():
    for worker in get_active_workers():
        if not probe_worker_health(worker):
            worker.health_failures += 1
            
            if worker.health_failures >= 2:
                # Mark unhealthy, stop new assignments
                worker.status = 'unhealthy'
                emit_metric('worker_marked_unhealthy', worker_id=worker.id)
                
                # DO NOT requeue tasks yet - wait for task timeout
                # This handles transient health issues gracefully
        else:
            worker.health_failures = 0
```

**Assignment Timeout Detection** (runs every 10 seconds):
```python
def detect_stalled_assignments():
    now = time.time()
    assignment_timeout = 30
    
    stalled = query_tasks(
        status='assigned',
        assigned_at__lt=now - assignment_timeout
    )
    
    for task in stalled:
        logger.warning(f"Task {task.task_id} stalled in assignment")
        requeue_task(task, reason='assignment_timeout')
```

**Visibility Timeout Recovery** (runs every 10 seconds):
```python
def recover_invisible_tasks():
    now = time.time()
    
    # Find tasks with expired visibility timeout still in queue
    expired_tasks = redis.zrangebyscore('queue:tasks', 0, now)
    
    for task_id in expired_tasks:
        task = get_task(task_id)
        
        if task.status == 'assigned' and task.visibility_timeout_until <= now:
            # Worker crashed after claim, before execution
            requeue_task(task, reason='visibility_timeout_expired')
```

**Task Timeout Detection** (runs every 30 seconds):
```python
def detect_timed_out_tasks():
    now = time.time()
    
    # Find executing tasks past their timeout
    timed_out = query_tasks(status='executing')
    
    for task in timed_out:
        elapsed = now - task.started_at
        if elapsed > task.timeout_seconds:
            handle_task_timeout(task)
```

### Retry Strategy

```python
def requeue_task(task, reason):
    task.retry_count += 1
    
    if task.retry_count > task.max_retries:
        move_to_dlq(task, reason=f'max_retries_exceeded_{reason}')
        return
    
    # Reset task state
    task.status = 'queued'
    task.assigned_worker_id = None
    task.assigned_at = None
    task.started_at = None
    task.visibility_timeout_until = None
    
    # Exponential timeout increase
    task.timeout_seconds = min(
        task.timeout_seconds * 1.5,
        3600  # Max 1 hour
    )
    
    # Recalculate score and add back to queue
    score = calculate_task_score(task)
    task.queue_score = score
    redis.zadd('queue:tasks', {task.task_id: score})
    
    save_task(task)
    emit_metric('task_requeued', reason=reason, retry_count=task.retry_count)
```

### Idempotency

```python
def submit_task(payload, idempotency_key=None):
    if idempotency_key:
        cache_key = f'idempotent:{idempotency_key}'
        existing_id = redis.get(cache_key)
        
        if existing_id:
            task = get_task(existing_id)
            # Return existing task if still active
            if task.status not in ['completed', 'failed', 'cancelled']:
                return task
            # Allow resubmission if terminal state
    
    # Create new task
    task = create_task(payload)
    score = calculate_task_score(task)
    task.queue_score = score
    
    # Add to queue
    redis.zadd('queue:tasks', {task.task_id: score})
    
    if idempotency_key:
        redis.setex(cache_key, 86400, task.task_id)
    
    save_task(task)
    return task
```

## Monitoring & Observability

### Key Metrics (Prometheus)

**Queue Health**:
- `queue_depth_total{priority}` - Tasks by priority
- `queue_age_seconds{priority, percentile}` - Wait time distribution
- `queue_score_distribution` - Histogram of task scores

**Task Lifecycle with Assignment Phase**:
- `task_duration_seconds{priority, status}` - Full lifecycle time
- `task_assignment_duration_seconds` - Time in `assigned` state
- `task_execution_duration_seconds` - Time in `executing` state
- `task_state_transitions_total{from, to}` - State flow

**Worker Health (Dual-Mode)**:
- `workers_total{status}` - active/draining/unhealthy/dead
- `worker_heartbeat_failures_total{worker_id}` - Passive monitoring
- `worker_health_probe_failures_total{worker_id}` - Active monitoring
- `worker_capacity_used_ratio` - Utilization

**Recovery Metrics (Enhanced)**:
- `task_assignment_timeouts_total` - Stuck in assigned (30s recovery)
- `task_visibility_timeouts_total` - Visibility timeout recovery
- `task_execution_timeouts_total` - Task timeout (5-15min recovery)
- `worker_failures_total{reason}` - heartbeat vs health probe

**Error Patterns**:
- `tasks_failed_total{reason, priority}` - Classified failures
- `tasks_dlq_total{reason}` - DLQ additions
- `task_retries_total{attempt, priority}` - Retry distribution

### Alerting Rules

**Critical**:
- No active workers for >2 minutes
- Queue depth >1000 AND growing for >5 minutes
- Task failure rate >25% for >5 minutes
- DLQ growth >10 tasks/minute

**Warning**:
- Worker utilization >90% for >10 minutes
- High priority tasks waiting >60 seconds
- Assignment timeout rate >5/minute (workers crashing during claim)
- Health probe failure rate >10/minute (workers degraded)
- Any queue age p95 >10 minutes

**Info**:
- Visibility timeout recovery >1/minute (investigate worker stability)
- Unhealthy workers >10% of pool

## Deployment Architecture

**Single-Region**:
- Redis Sentinel (3 nodes) for HA
- PostgreSQL (primary + replica) for durability
- Worker pool: Auto-scaling 10-100 instances
- Queue manager: 2-3 instances behind load balancer

**Scaling Characteristics**:
- Queue operations: O(log N) for single queue
- Worker polling: O(K log N) where K = available_capacity
- Score calculation: O(1)
- Expected throughput: 1000+ tasks/second

## What I Improved

1. **Unified Priority Queue with Continuous Fairness**: Replaced separate queues with single queue + dynamic scoring. Provides continuous (not discrete) starvation prevention without background promotion jobs. Simpler recovery and better observability.

2. **Restored `assigned` State**: Critical for fast failure recovery. Enables 30-second detection of worker crashes during task initialization (vs 5-15 minute task timeout). Real-world benefit for rolling deployments and OOM scenarios.

3. **Added Visibility Timeout Pattern**: Prevents task loss during worker crashes. Task stays in queue with future score until explicitly removed. Enables fast, safe recovery with queue as source of truth.

4. **Dual-Mode Health Monitoring**: Added active health probes alongside heartbeat. Detects hung workers (3-13min faster), resource exhaustion (proactive), and dependency failures. Minimal cost (~100 LOC, 60s interval) for significant operational value.

5. **Enhanced Observability**: Added metrics for assignment phase, visibility timeout recovery, health probe failures, and state transitions. Enables root cause analysis and proactive intervention.

6. **DLQ Analytics**: Automated pattern detection and retriable task identification. Turns DLQ from "where tasks go to die" into operational intelligence.

## What I Kept

1. **Worker-Pull Model**: Core architecture is sound.

2. **Capability-Based Routing**: Essential for heterogeneous workers.

3. **Three Priority Levels**: High/medium/low is intuitive.

4. **Idempotency Keys**: 24-hour deduplication pattern works well.

5. **Dead Letter Queue**: Necessary for unrecoverable failures.

6. **Retry Strategy**: Exponential backoff with configurable limits.

7. **Redis + PostgreSQL Split**: Hot path vs durability separation is correct.

## Remaining Concerns

1. **Score Calculation Cost**: The unified queue requires score recalculation on requeue. With high retry rates, this could become a bottleneck. Mitigation: score calculation is O(1) and Redis sorted set updates are O(log N).

2. **Capability Filtering After Claim**: Workers claim tasks then check capabilities. If mismatch, task is released. This wastes claim operations when workers are highly specialized. Mitigation: capability tags could be added to queue keys (e.g., `queue:tasks:gpu`).

3. **Health Probe Thundering Herd**: If 100 workers all expose health endpoints, probing creates 100 HTTP requests every 60 seconds from queue manager. Mitigation: acceptable at 100 workers (1.67 req/s), but consider batching or sampling at scale.

4. **Visibility Timeout vs Queue Depth Metrics**: Tasks with future scores appear in queue but aren't "really" queued. Queue depth metrics need to filter `score <= now`. Mitigation: added in queue stats endpoint.

5. **Long-Running Task Fairness**: Tasks running for hours hold worker capacity while queue grows. Consider separating short-task and long-task queues, or streaming progress updates.

## Convergence Status
**ITERATING** - I've made significant improvements around recovery speed and observability, but the unified queue vs. separate queues is an architectural choice that warrants discussion. The continuous scoring adds elegance but may add operational complexity.

## Prompt for Collaborator
PROMPT_FOR_ARCHITECT:

Please focus your response on:

1. **Unified Queue Trade-offs**: Does the continuous scoring approach provide enough practical benefit over separate queues to justify the added complexity? Consider:
   - Score calculation on every requeue
   - Observability (single depth metric vs three separate metrics)
   - Debugging (task score vs queue name + position)
   - Performance at scale (single sorted set vs three)

2. **Assignment State Value**: I've argued the `assigned` state enables 30-second recovery vs 5-15 minute task timeout. Do you see scenarios where this is critical, or is the added state complexity not worth the faster recovery? Consider:
   - Kubernetes pod evictions during deployment
   - Worker OOM during task initialization
   - Operator "kill random worker pod" chaos testing

3. **Visibility Timeout Necessity**: Is the visibility timeout pattern essential, or does your atomic ZREM + HSET approach adequately handle worker crashes? Compare:
   - Task lost from queue: How do we recover if worker crashes after ZREM?
   - Complexity cost: Visibility timeout adds ~50 LOC, is it worth it?

4. **Health Probe Benefit**: Does active health monitoring provide enough value (3-13min faster hung worker detection) to justify the added complexity (health endpoint, probe job, false positive handling)?

**Convergence Signal:** ITERATING

---

