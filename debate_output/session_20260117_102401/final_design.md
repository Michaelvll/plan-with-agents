# Final Agreed Design

**Task:** Design a webhook delivery system with retries

**Status:** consensus

---

## Design

# Webhook Delivery System with Retries

## System Architecture

### Components

1. **Webhook API Service**
   - Accepts webhook registration requests with URL validation
   - Validates webhook configurations
   - Stores webhook subscriptions in database
   - Provides CRUD operations for webhooks
   - Enforces per-tenant quotas and rate limits

2. **Event Publisher**
   - Receives events from application components
   - Validates event payloads against schema
   - Performs duplicate detection using idempotency keys
   - Publishes events to message queue for async processing
   - Returns immediately to avoid blocking event sources

3. **Delivery Worker Pool**
   - Consumes events from message queue with priority handling
   - Checks circuit breaker and rate limiter before delivery
   - Executes HTTP POST requests to registered webhook URLs
   - Implements retry logic with exponential backoff
   - Records delivery attempts and outcomes with detailed error classification
   - Updates circuit breaker metrics based on error patterns
   - Handles graceful degradation for partial failures

4. **Dead Letter Queue (DLQ) Handler**
   - Processes events that exhausted all retry attempts
   - Classifies failures by type (permanent vs potentially recoverable)
   - Logs failed deliveries for manual inspection
   - Provides API for retry of failed deliveries with bulk operations
   - Alerts webhook owners of permanent failures via email/notification
   - Supports scheduled batch retry for DLQ items with rate limiting

5. **Circuit Breaker Manager**
   - Maintains per-webhook circuit state with error pattern analysis
   - Uses time-window based thresholds (failure rate over period)
   - Gradual recovery mechanism with probe requests
   - Prevents cascade failures across tenant boundaries

6. **Monitoring & Observability**
   - Tracks delivery success/failure rates by error type
   - Monitors queue depths and worker health
   - Exposes metrics for latency and throughput by percentile
   - Provides webhook delivery history API with filtering
   - Tracks circuit breaker state transitions
   - Alert on anomalous failure patterns

### Technology Stack

- **Message Queue**: RabbitMQ with priority queues and DLQ support
- **Database**: PostgreSQL (for webhook configs and delivery logs)
- **Cache Layer**: Redis (for circuit breaker state, rate limiting, deduplication)
- **Worker Framework**: Custom Go workers with concurrency control
- **API Framework**: FastAPI (Python) with async support

## Data Models

### Webhook Subscription
```json
{
  "id": "uuid",
  "owner_id": "string",
  "tenant_id": "string",
  "url": "https://customer.example.com/webhook",
  "events": ["user.created", "order.completed"],
  "secret": "signing_secret_for_hmac",
  "active": true,
  "retry_config": {
    "max_attempts": 5,
    "base_delay_ms": 1000,
    "max_delay_ms": 300000,
    "backoff_multiplier": 2.0,
    "timeout_ms": 30000,
    "timeout_growth_factor": 1.0
  },
  "circuit_breaker_config": {
    "enabled": true,
    "error_threshold_percentage": 50,
    "minimum_throughput": 10,
    "window_size_ms": 60000,
    "sleep_window_ms": 30000,
    "half_open_max_calls": 3,
    "force_open_until": null
  },
  "rate_limit": {
    "requests_per_minute": 100,
    "burst": 20
  },
  "ordering_guarantee": "none",
  "headers": {
    "X-Custom-Header": "value"
  },
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "last_success_at": "timestamp",
  "metadata": {}
}
```

### Delivery Attempt
```json
{
  "id": "uuid",
  "webhook_id": "uuid",
  "event_id": "uuid",
  "attempt_number": 1,
  "status": "pending|success|failed|exhausted|circuit_blocked",
  "failure_category": "timeout|server_error|client_error|network|dns|ssl|rate_limit|payload_too_large",
  "http_status_code": 200,
  "response_body_sample": "limited to 1KB",
  "error_message": "string",
  "duration_ms": 245,
  "scheduled_at": "timestamp",
  "executed_at": "timestamp",
  "next_retry_at": "timestamp",
  "circuit_breaker_prevented": false
}
```

### Event Payload
```json
{
  "id": "uuid",
  "event_type": "user.created",
  "data": {
    "user_id": 12345,
    "email": "user@example.com"
  },
  "timestamp": "ISO8601",
  "idempotency_key": "unique_per_event",
  "source": "api-service",
  "priority": "high|normal|low",
  "sequence_number": 12345
}
```

### Circuit Breaker State
```json
{
  "webhook_id": "uuid",
  "state": "closed|open|half_open",
  "failure_count_in_window": 8,
  "success_count_in_window": 2,
  "total_calls_in_window": 10,
  "error_percentage": 80.0,
  "window_start": "timestamp",
  "state_transition_at": "timestamp",
  "next_half_open_at": "timestamp",
  "half_open_attempts": 0,
  "half_open_successes": 0
}
```

## Interfaces

### Webhook Registration API

```
POST /v1/webhooks
{
  "url": "https://...",
  "events": ["event.type"],
  "secret": "optional",
  "retry_config": {},
  "circuit_breaker_config": {},
  "ordering_guarantee": "none|per_event_type|strict",
  "verify_url": true
}
Response: 201 Created + webhook object

GET /v1/webhooks
Query params: ?active=true&event_type=user.created&tenant_id=xyz
Response: 200 OK + list of webhooks

GET /v1/webhooks/{id}
Response: 200 OK + webhook object

GET /v1/webhooks/{id}/health
Response: 200 OK + circuit breaker state, recent delivery stats, error distribution

PUT /v1/webhooks/{id}
Body: partial webhook update
Response: 200 OK + updated webhook

PATCH /v1/webhooks/{id}/circuit-breaker
Body: {"action": "reset|force_open|force_close", "duration_seconds": 3600}
Response: 200 OK + updated circuit state

DELETE /v1/webhooks/{id}
Response: 204 No Content
```

### Delivery History API

```
GET /v1/webhooks/{id}/deliveries?limit=50&offset=0&status=failed&from=2024-01-01
Response: paginated delivery attempts with filtering

GET /v1/deliveries/{delivery_id}
Response: 200 OK + full delivery attempt details

POST /v1/webhooks/{id}/deliveries/{delivery_id}/retry
Body: {"priority": "high"}
Response: 202 Accepted + new delivery_id

POST /v1/dlq/retry-batch
Body: {
  "filter": {
    "webhook_ids": ["id1", "id2"],
    "event_types": ["user.created"],
    "failure_categories": ["timeout"]
  },
  "rate_limit": {"requests_per_second": 10},
  "priority": "normal"
}
Response: 202 Accepted + batch_operation_id

GET /v1/dlq/batch-operations/{id}
Response: 200 OK + batch operation status and progress
```

### Event Publishing (Internal)

```python
def publish_event(
    event_type: str, 
    data: dict, 
    source: str,
    idempotency_key: Optional[str] = None,
    priority: str = "normal",
    tenant_id: str = None
) -> str:
    """
    Publishes event to message queue for webhook delivery
    Deduplicates based on idempotency_key if provided
    Returns: event_id
    Raises: 
      - DuplicateEventError if idempotency key seen within 24h
      - PayloadTooLargeError if payload exceeds 256KB
    """
```

## Retry Logic

### Simplified Exponential Backoff

```python
def calculate_next_retry(
    attempt: int, 
    config: RetryConfig,
    failure_category: str
) -> tuple[datetime, int]:
    """
    Returns: (next_retry_timestamp, timeout_ms)
    
    Simpler approach: use consistent backoff with category-based minimum delays
    Let circuit breaker handle broader failure patterns
    """
    # Base exponential backoff
    delay_ms = min(
        config.base_delay_ms * (config.backoff_multiplier ** attempt),
        config.max_delay_ms
    )
    
    # Category-specific minimum delays only
    category_minimums = {
        "rate_limit": 60000,  # 1 minute minimum
        "dns": 5000,          # 5 seconds (DNS might be propagating)
        "timeout": 2000,      # 2 seconds (give server breathing room)
    }
    
    if failure_category in category_minimums:
        delay_ms = max(delay_ms, category_minimums[failure_category])
    
    # Simple uniform jitter (±25%)
    jitter = random.uniform(-0.25, 0.25) * delay_ms
    final_delay_ms = max(0, delay_ms + jitter)
    
    # Timeout growth for subsequent attempts
    timeout_ms = config.timeout_ms * (config.timeout_growth_factor ** attempt)
    timeout_ms = min(timeout_ms, config.timeout_ms * 3)  # Cap at 3x
    
    return (now() + timedelta(milliseconds=final_delay_ms), int(timeout_ms))
```

### Retry Eligibility

```python
class RetryDecision:
    # Non-retryable HTTP status codes
    PERMANENT_FAILURES = {400, 401, 403, 404, 410, 413, 414, 415, 451}
    
    def should_retry(
        self, 
        attempt: int, 
        error_type: str,
        http_status: Optional[int],
        max_attempts: int
    ) -> tuple[bool, str]:
        """
        Returns: (should_retry, reason)
        """
        if attempt >= max_attempts:
            return (False, "max_attempts_exceeded")
        
        # Network/DNS errors - always retry
        if error_type in ["dns_failure", "connection_refused", "connection_timeout", "network_unreachable"]:
            return (True, f"retryable_network_{error_type}")
        
        # SSL errors - retry with limit
        if error_type == "ssl_error":
            return (attempt < 3, "ssl_error_retry_limit" if attempt >= 3 else "ssl_error")
        
        # HTTP status code based decisions
        if http_status:
            if http_status in self.PERMANENT_FAILURES:
                return (False, f"permanent_client_error_{http_status}")
            
            if http_status == 429:
                return (True, "rate_limited")
            
            if http_status >= 500:
                return (True, f"server_error_{http_status}")
            
            if 200 <= http_status < 300:
                return (False, "success")
        
        # Timeout errors
        if error_type in ["read_timeout", "request_timeout"]:
            return (True, "timeout")
        
        # Unknown - retry cautiously
        return (True, "unknown_error")
```

## Circuit Breaker Design

### Time-Window Based Circuit Breaker

```python
class TimeWindowCircuitBreaker:
    """
    Simpler, more predictable circuit breaker using rolling time windows
    Avoids complexity of separate counters for different error types
    """
    
    def __init__(self, webhook_id: str, config: CircuitBreakerConfig):
        self.webhook_id = webhook_id
        self.config = config
        self.state = "closed"
        
        # Rolling window data stored in Redis sorted set
        # Key: webhook_id, Score: timestamp, Value: success|failure
        self.window_key = f"cb:{webhook_id}:window"
        
    def record_attempt(self, success: bool, failure_category: Optional[str] = None):
        """
        Records attempt in time window and evaluates state transition
        """
        timestamp = now_ms()
        result = "success" if success else f"failure:{failure_category}"
        
        # Add to sorted set with timestamp as score
        redis.zadd(self.window_key, {result: timestamp})
        
        # Remove entries outside window
        window_start = timestamp - self.config.window_size_ms
        redis.zremrangebyscore(self.window_key, 0, window_start)
        
        # Update state based on current window
        self._evaluate_state()
    
    def _evaluate_state(self):
        """
        Evaluate state transition based on time window metrics
        """
        timestamp = now_ms()
        window_start = timestamp - self.config.window_size_ms
        
        # Get all attempts in window
        attempts = redis.zrangebyscore(self.window_key, window_start, timestamp)
        total = len(attempts)
        failures = sum(1 for a in attempts if a.startswith("failure:"))
        
        if self.state == "closed":
            # Check if we should open
            if total >= self.config.minimum_throughput:
                error_rate = (failures / total) * 100
                if error_rate >= self.config.error_threshold_percentage:
                    self._transition_to_open()
        
        elif self.state == "open":
            # Check if sleep window expired
            state_age_ms = timestamp - self.state_transition_at
            if state_age_ms >= self.config.sleep_window_ms:
                self._transition_to_half_open()
        
        elif self.state == "half_open":
            # Evaluate based on probe attempts
            if self.half_open_attempts >= self.config.half_open_max_calls:
                # Decision time
                success_rate = self.half_open_successes / self.half_open_attempts
                if success_rate >= 0.5:  # 50% threshold
                    self._transition_to_closed()
                else:
                    self._transition_to_open()
    
    def should_allow_request(self) -> tuple[bool, str]:
        """
        Returns: (allow, reason)
        """
        # Check force_open override
        if self.config.force_open_until and now() < self.config.force_open_until:
            return (False, "manually_forced_open")
        
        if self.state == "closed":
            return (True, "circuit_closed")
        
        if self.state == "open":
            # Re-evaluate in case sleep window expired
            self._evaluate_state()
            if self.state == "half_open":
                return self._allow_half_open_request()
            return (False, "circuit_open")
        
        if self.state == "half_open":
            return self._allow_half_open_request()
    
    def _allow_half_open_request(self) -> tuple[bool, str]:
        """
        Rate-limit probe requests in half-open state
        """
        if self.half_open_attempts < self.config.half_open_max_calls:
            self.half_open_attempts += 1
            return (True, "circuit_half_open_probe")
        return (False, "half_open_probe_limit_reached")
    
    def _transition_to_open(self):
        self.state = "open"
        self.state_transition_at = now_ms()
        self.half_open_attempts = 0
        self.half_open_successes = 0
        emit_metric("circuit_breaker_opened", {"webhook_id": self.webhook_id})
        notify_webhook_owner(self.webhook_id, "circuit_opened")
    
    def _transition_to_half_open(self):
        self.state = "half_open"
        self.state_transition_at = now_ms()
        self.half_open_attempts = 0
        self.half_open_successes = 0
        emit_metric("circuit_breaker_half_opened", {"webhook_id": self.webhook_id})
    
    def _transition_to_closed(self):
        self.state = "closed"
        self.state_transition_at = now_ms()
        # Clear window on successful recovery
        redis.delete(self.window_key)
        emit_metric("circuit_breaker_closed", {"webhook_id": self.webhook_id})
        notify_webhook_owner(self.webhook_id, "circuit_recovered")
```

### Circuit Breaker and Retry Interaction

```
Event Lifecycle with Circuit Breaker:

1. Event arrives for webhook
2. Check circuit breaker state:
   
   CLOSED:
   - Attempt delivery normally
   - If fails: record in circuit breaker, schedule retry
   - Retry attempts proceed independently
   
   OPEN:
   - Do NOT attempt delivery
   - Record attempt as "circuit_blocked" (doesn't count toward retry limit)
   - Requeue message with delay = min(circuit sleep window, max backoff delay)
   - When circuit transitions to half-open, message will be reprocessed
   
   HALF_OPEN:
   - Allow up to N probe requests
   - If selected as probe: attempt delivery normally
   - If not selected: treat as OPEN (requeue)

3. Retry sequence behavior:
   - Retry counter persists across circuit breaker cycles
   - Example: Attempt 1 fails → circuit opens → retry 2 scheduled
   - When circuit reopens: retry 2 proceeds (still counts as attempt 2)
   - This prevents infinite retries due to circuit breaker delays
```

## Security

1. **HMAC Signing**
   - Sign payload with webhook secret using HMAC-SHA256
   - Include timestamp in signature to prevent replay attacks (valid 5 minutes)
   - Signature format: `t={timestamp},v1={signature}`
   - Header: `X-Webhook-Signature: t=1234567890,v1={hmac_sha256}`

2. **Request Headers**
```
POST /webhook HTTP/1.1
Content-Type: application/json
X-Webhook-ID: {webhook_id}
X-Webhook-Signature: t=1234567890,v1={hmac_sha256}
X-Webhook-Event: user.created
X-Webhook-Delivery: {delivery_id}
X-Webhook-Attempt: 2
X-Webhook-Timestamp: 2024-01-15T10:30:00Z
X-Idempotency-Key: {event_idempotency_key}
User-Agent: WebhookService/1.0
```

3. **Timeout & Rate Limiting**
   - HTTP request timeout: 30s default, grows by `timeout_growth_factor` per retry
   - Per-webhook rate limit: configurable requests/minute with token bucket
   - Per-tenant global rate limits (default: 1000 req/min)
   - Connection pooling with max 5 concurrent connections per webhook

4. **URL Validation**
   - Block private IP ranges (RFC1918, loopback, link-local)
   - Require HTTPS in production
   - Optional verification request during registration (webhook must echo challenge)
   - Max URL length: 2048 characters

### Idempotency

- Each event has unique `idempotency_key` (UUID v4 if not provided)
- Included in delivery headers for consumer deduplication
- Publisher deduplicates events within 24h window (Redis cache)
- Retry attempts preserve same idempotency key
- Consumers responsible for deduplication handling

## Worker Processing Flow

```
1. Worker polls message queue with priority
2. Extract webhook_id, event_id, attempt_number from message
3. Load webhook config (cached in Redis, TTL 5min)
4. Verify webhook is active:
   - If inactive: ACK message, log skip, exit
5. Check circuit breaker:
   a. Load circuit state from Redis
   b. Call should_allow_request()
   c. If blocked:
      - Record delivery attempt as "circuit_blocked"
      - Calculate requeue delay = min(circuit sleep window remaining, max retry delay)
      - NACK message with delay
      - Exit
   d. If allowed: proceed
6. Check rate limiter (token bucket in Redis):
   - If rate limited: NACK with 1s delay, exit
7. Evaluate retry eligibility:
   - If attempt >= max_attempts: move to DLQ, ACK, exit
8. Build HTTP request:
   a. Generate HMAC signature with timestamp
   b. Add all standard headers
   c. Calculate timeout based on attempt number
9. Execute HTTP request with error capture:
   a. Record start time
   b. Execute POST with timeout
   c. Record duration, status, response sample
   d. Classify outcome and failure category
10. Process outcome:
    a. Success (2xx):
       - Record in circuit breaker as success
       - Store delivery attempt as "success"
       - ACK message
       - Exit
    b. Retryable failure:
       - Record in circuit breaker as failure
       - Determine failure category
       - Calculate next retry time and timeout
       - Store delivery attempt as "failed"
       - NACK message with retry delay
       - Exit
    c. Non-retryable failure:
       - Record in circuit breaker as failure
       - Store delivery attempt as "exhausted"
       - Move to DLQ with classification
       - ACK message
       - Exit
11. Handle worker errors:
    - Redis/DB unavailable: NACK immediately (no delay)
    - Unexpected exception: log, NACK, alert
    - Graceful shutdown: NACK all in-flight
```

## Event Ordering

Three ordering modes (webhook configuration):

1. **none** (default): Maximum throughput, no ordering guarantees
   - Events processed by any available worker
   - Fastest option for most use cases

2. **per_event_type**: Events of same type processed in order
   - Use message queue partition key = `{webhook_id}:{event_type}`
   - Events with different types can process in parallel
   - Good balance for most ordering needs

3. **strict**: All events for webhook processed sequentially
   - Use message queue partition key = `{webhook_id}`
   - Significant throughput impact
   - Only use when strictly necessary

## Payload Size Limits

- Maximum event payload: 256KB (configurable)
- Oversized payloads: rejected at publish time with clear error
- Response body sample stored: max 1KB
- Future enhancement: external blob storage for large payloads with reference URL

## Failure Mode Handling

**Database Unavailable:**
- Cannot load webhook config → NACK immediately
- Message returns to queue for retry
- Alert after 5 consecutive DB failures

**Redis Unavailable:**
- Circuit breaker falls back to "closed" (fail-safe)
- Rate limiting disabled temporarily
- Worker logs warning and continues
- Alert on Redis connection issues

**Message Queue Connection Lost:**
- Worker enters reconnection loop (exp backoff, max 5min)
- In-flight messages auto-NACK on connection loss
- Alert after 3 failed reconnection attempts

**DNS Resolution Failure:**
- Treat as retryable network error
- Cache successful DNS lookups (TTL 5min)
- If DNS fails consistently (>80% over 10min) → notify webhook owner

**Worker Crash During Delivery:**
- Message not ACKed → returns to queue
- Other worker will retry
- Duplicate delivery attempt records prevented by unique constraint on (event_id, webhook_id, attempt_number)

**Webhook Returns 2xx After Long Processing:**
- System treats as success
- Consumer responsible for async processing patterns
- Document best practices: return 2xx quickly, process async

## Scalability Considerations

- **Horizontal scaling**: Stateless workers, scale based on queue depth
- **Tenant isolation**: Route high-volume tenants to dedicated worker pools via queue routing
- **Priority queues**: Separate queues for high/normal/low priority
- **Database partitioning**: 
  - Partition `delivery_attempts` by month
  - Index on (webhook_id, executed_at) for history queries
  - Archive to cold storage after 90 days
- **Connection pooling**: Per-worker HTTP client with max 100 connections, max 5 per host
- **Batch DLQ retry**: Rate-limited bulk retry (configurable req/sec)

## Monitoring Metrics

- `webhook_deliveries_total{status, event_type, failure_category, tenant_id}`
- `webhook_delivery_duration_seconds{percentile}` (p50, p95, p99)
- `webhook_retry_attempt_number{outcome}` (histogram)
- `webhook_queue_depth{priority}`
- `webhook_circuit_breaker_state{webhook_id, state}` (gauge)
- `webhook_circuit_breaker_transitions_total{from_state, to_state}`
- `webhook_dlq_size{tenant_id}`
- `webhook_rate_limit_hits_total{webhook_id}`
- `webhook_worker_pool_utilization{pool_id}`

## Alerting Rules

- Circuit breaker opened (severity: warning)
- Circuit breaker open >1 hour (severity: critical)
- DLQ size >1000 per tenant (severity: warning)
- Webhook success rate <90% over 5min (severity: warning)
- Worker pool >80% utilization (severity: warning)
- Queue depth >10000 (severity: critical)