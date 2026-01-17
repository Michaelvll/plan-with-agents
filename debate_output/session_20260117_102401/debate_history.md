# Claude Code Debate Session

**Started:** 2026-01-17T10:24:01.222215
**Ended:** 2026-01-17T10:31:21.450356
**Status:** consensus
**Rounds:** 2

## Initial Prompt

Design a webhook delivery system with retries

---

## Round 1

### 🔵 Agent A

## Design

# Webhook Delivery System with Retries

## System Architecture

### Components

1. **Webhook API Service**
   - Accepts webhook registration requests
   - Validates webhook configurations
   - Stores webhook subscriptions in database
   - Provides CRUD operations for webhooks

2. **Event Publisher**
   - Receives events from application components
   - Validates event payloads
   - Publishes events to message queue for async processing
   - Returns immediately to avoid blocking event sources

3. **Delivery Worker Pool**
   - Consumes events from message queue
   - Executes HTTP POST requests to registered webhook URLs
   - Implements retry logic with exponential backoff
   - Records delivery attempts and outcomes
   - Handles circuit breaking for persistently failing endpoints

4. **Dead Letter Queue (DLQ) Handler**
   - Processes events that exhausted all retry attempts
   - Logs failed deliveries for manual inspection
   - Provides webhook for retry of failed deliveries
   - Alerts webhook owners of permanent failures

5. **Monitoring & Observability**
   - Tracks delivery success/failure rates
   - Monitors queue depths and worker health
   - Exposes metrics for latency and throughput
   - Provides webhook delivery history API

### Technology Stack

- **Message Queue**: Redis Streams or RabbitMQ (for durability and ordering)
- **Database**: PostgreSQL (for webhook configs and delivery logs)
- **Worker Framework**: Celery or custom Go workers
- **API Framework**: FastAPI (Python) or Gin (Go)

## Data Models

### Webhook Subscription
```json
{
  "id": "uuid",
  "owner_id": "string",
  "url": "https://customer.example.com/webhook",
  "events": ["user.created", "order.completed"],
  "secret": "signing_secret_for_hmac",
  "active": true,
  "retry_config": {
    "max_attempts": 5,
    "initial_delay_seconds": 2,
    "max_delay_seconds": 3600,
    "backoff_multiplier": 2.0
  },
  "headers": {
    "X-Custom-Header": "value"
  },
  "created_at": "timestamp",
  "updated_at": "timestamp",
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
  "status": "pending|success|failed|exhausted",
  "http_status_code": 200,
  "response_body": "limited to 1KB",
  "error_message": "string",
  "duration_ms": 245,
  "scheduled_at": "timestamp",
  "executed_at": "timestamp",
  "next_retry_at": "timestamp"
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
  "source": "api-service"
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
  "retry_config": {}
}
Response: 201 Created + webhook object

GET /v1/webhooks
Response: 200 OK + list of webhooks

GET /v1/webhooks/{id}
Response: 200 OK + webhook object

PUT /v1/webhooks/{id}
Body: partial webhook update
Response: 200 OK + updated webhook

DELETE /v1/webhooks/{id}
Response: 204 No Content
```

### Delivery History API

```
GET /v1/webhooks/{id}/deliveries?limit=50&offset=0
Response: paginated delivery attempts

POST /v1/webhooks/{id}/deliveries/{delivery_id}/retry
Response: 202 Accepted (re-queues for delivery)
```

### Event Publishing (Internal)

```python
def publish_event(event_type: str, data: dict, source: str):
    """
    Publishes event to message queue for webhook delivery
    Returns: event_id
    """
```

## Retry Logic

### Exponential Backoff Algorithm

```python
def calculate_next_retry(attempt: int, config: RetryConfig) -> datetime:
    """
    attempt: 0-indexed attempt number
    Returns: timestamp for next retry
    """
    delay = min(
        config.initial_delay_seconds * (config.backoff_multiplier ** attempt),
        config.max_delay_seconds
    )
    # Add jitter to prevent thundering herd
    jitter = random.uniform(0, delay * 0.1)
    return now() + timedelta(seconds=delay + jitter)
```

### Retry Schedule Example
- Attempt 1: Immediate
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds  
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds
- Attempt 6+: Exhausted → DLQ

### Retry Eligibility

Retry on:
- Network timeouts
- Connection errors
- HTTP 408, 429, 500, 502, 503, 504
- DNS failures

Do NOT retry on:
- HTTP 400, 401, 403, 404, 410 (client errors)
- Invalid webhook URL
- SSL/TLS certificate errors (after 3 attempts)

## Error Handling

### Circuit Breaker Pattern

```python
class WebhookCircuitBreaker:
    """
    Opens circuit after 10 consecutive failures
    Half-open after 5 minutes to test recovery
    Closes after 3 consecutive successes
    """
    states = ["closed", "open", "half_open"]
```

When circuit is OPEN:
- Skip delivery attempts
- Log circuit open event
- Notify webhook owner
- Attempt to close circuit periodically

### Security

1. **HMAC Signing**
   - Sign payload with webhook secret
   - Include signature in `X-Webhook-Signature` header
   - Algorithm: HMAC-SHA256

2. **Request Headers**
```
POST /webhook HTTP/1.1
Content-Type: application/json
X-Webhook-ID: {webhook_id}
X-Webhook-Signature: sha256={signature}
X-Webhook-Event: user.created
X-Webhook-Delivery: {delivery_id}
X-Webhook-Attempt: 2
User-Agent: WebhookService/1.0
```

3. **Timeout & Rate Limiting**
   - HTTP request timeout: 30 seconds
   - Per-webhook rate limit: 100 requests/minute
   - Connection pooling with max 10 connections per host

### Idempotency

- Each event has unique `idempotency_key`
- Include in delivery headers
- Consumers should deduplicate using this key
- System guarantees at-least-once delivery

## Worker Processing Flow

```
1. Worker polls message queue
2. Load webhook subscription from database
3. Check circuit breaker status
4. If closed/half-open:
   a. Build HTTP request with signed payload
   b. Execute request with timeout
   c. Record delivery attempt
   d. On success: ACK message, update metrics
   e. On retryable failure: 
      - Schedule retry (NACK with delay)
      - Update circuit breaker
   f. On non-retryable failure: 
      - Mark exhausted, move to DLQ
5. If open: Skip delivery, reschedule check
```

## Scalability Considerations

- **Horizontal scaling**: Add more worker instances
- **Partitioning**: Shard webhooks by ID across worker pools
- **Priority queues**: Separate queues for different event types
- **Batch processing**: Group deliveries to same endpoint (future)
- **Database indexing**: Index on (webhook_id, created_at) for queries

## Monitoring Metrics

- `webhook_deliveries_total{status, event_type}`
- `webhook_delivery_duration_seconds{status}`
- `webhook_retry_attempts_total{attempt_number}`
- `webhook_queue_depth`
- `webhook_circuit_breaker_state{webhook_id}`
- `webhook_dlq_size`

## Rationale

1. **Message Queue Architecture**: Decouples event generation from delivery, enabling async processing and natural retry handling without blocking application flow.

2. **Exponential Backoff with Jitter**: Balances aggressive retries with respecting downstream rate limits. Jitter prevents synchronized retry storms.

3. **Circuit Breaker**: Protects system from wasting resources on persistently failing endpoints while allowing automatic recovery.

4. **PostgreSQL for State**: Webhooks and delivery history need strong consistency and queryability. Redis/Queue only for transient work items.

5. **HMAC Signing**: Standard webhook security pattern that allows consumers to verify authenticity without complex auth flows.

6. **Separate DLQ Handler**: Isolates failure analysis from hot path, enables manual intervention and batch reprocessing.

## What I Changed

N/A - This is the initial design proposal.

## What I Kept

N/A - This is the initial design proposal.

## Open Questions

1. **Ordering Guarantees**: Should we guarantee event ordering per webhook? This adds complexity (serialization) but may be required for certain event types.

2. **Webhook URL Validation**: Should we verify webhook URLs are reachable during registration (test delivery)? Could prevent misconfigurations but adds latency.

3. **Payload Size Limits**: What's the maximum event payload size? Larger payloads impact memory, network, and storage.

4. **Multi-tenancy**: How do we isolate webhook traffic between customers? Separate worker pools? Rate limiting?

5. **Delivery Acknowledgment**: Should we support synchronous acknowledgment from webhook consumers (they return 200 only after processing)?

## Convergence Status

**ITERATING** - This is the first round. The design needs critical review to identify gaps, edge cases, and potential improvements.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Please focus on the retry logic and error handling strategy. Specifically:
1. Are there edge cases in the retry eligibility rules that could cause problems?
2. Does the circuit breaker pattern integration make sense, or does it conflict with the retry mechanism?
3. Are there failure modes in the worker processing flow that aren't adequately handled?
4. Should we handle webhook endpoint failures differently based on error patterns (e.g., timeouts vs 5xx errors)?

**Convergence Signal:** ITERATING

### 🟣 Agent B

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
   - Implements retry logic with exponential backoff and adaptive jitter
   - Records delivery attempts and outcomes with detailed error classification
   - Updates circuit breaker metrics based on error patterns
   - Handles graceful degradation for partial failures

4. **Dead Letter Queue (DLQ) Handler**
   - Processes events that exhausted all retry attempts
   - Classifies failures by type (permanent vs potentially recoverable)
   - Logs failed deliveries for manual inspection
   - Provides API for retry of failed deliveries with bulk operations
   - Alerts webhook owners of permanent failures via email/notification
   - Supports scheduled batch retry for DLQ items

5. **Circuit Breaker Manager**
   - Maintains per-webhook circuit state with error pattern analysis
   - Separate thresholds for different failure types (timeout vs 5xx)
   - Gradual recovery mechanism with health probes
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
    "initial_delay_seconds": 2,
    "max_delay_seconds": 3600,
    "backoff_multiplier": 2.0,
    "timeout_seconds": 30,
    "separate_timeout_retries": true
  },
  "circuit_breaker_config": {
    "failure_threshold": 10,
    "timeout_threshold": 5,
    "success_threshold": 3,
    "half_open_timeout_seconds": 300,
    "health_check_interval_seconds": 60
  },
  "rate_limit": {
    "requests_per_minute": 100,
    "burst": 20
  },
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
  "status": "pending|success|failed|exhausted|skipped",
  "failure_category": "timeout|server_error|client_error|network|ssl|rate_limit",
  "http_status_code": 200,
  "response_body": "limited to 1KB",
  "response_headers": {"X-Request-ID": "..."},
  "error_message": "string",
  "error_details": "detailed stack trace or diagnostic info",
  "duration_ms": 245,
  "dns_resolution_ms": 12,
  "connection_time_ms": 45,
  "scheduled_at": "timestamp",
  "executed_at": "timestamp",
  "next_retry_at": "timestamp",
  "retry_reason": "string"
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
  "max_payload_size_bytes": 262144
}
```

### Circuit Breaker State
```json
{
  "webhook_id": "uuid",
  "state": "closed|open|half_open",
  "consecutive_failures": 5,
  "consecutive_timeouts": 2,
  "consecutive_successes": 0,
  "last_failure_at": "timestamp",
  "opened_at": "timestamp",
  "next_attempt_at": "timestamp",
  "failure_rate_1m": 0.85,
  "error_distribution": {
    "timeout": 3,
    "5xx": 2,
    "network": 1
  }
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
  "verify_url": true  // optional, defaults to false
}
Response: 201 Created + webhook object

GET /v1/webhooks
Query params: ?active=true&event_type=user.created
Response: 200 OK + list of webhooks

GET /v1/webhooks/{id}
Response: 200 OK + webhook object

GET /v1/webhooks/{id}/health
Response: 200 OK + circuit breaker state, recent delivery stats

PUT /v1/webhooks/{id}
Body: partial webhook update
Response: 200 OK + updated webhook

PATCH /v1/webhooks/{id}/circuit-breaker
Body: {"action": "reset|force_open|force_close"}
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
Response: 202 Accepted (re-queues for delivery)

POST /v1/webhooks/{id}/deliveries/retry-batch
Body: {"delivery_ids": ["id1", "id2"], "priority": "high"}
Response: 202 Accepted + batch operation ID

GET /v1/dlq?tenant_id=xyz&limit=100
Response: 200 OK + list of exhausted deliveries

POST /v1/dlq/retry-batch
Body: {"filter": {"event_type": "user.created", "failure_category": "timeout"}}
Response: 202 Accepted + batch operation ID
```

### Event Publishing (Internal)

```python
def publish_event(
    event_type: str, 
    data: dict, 
    source: str,
    idempotency_key: Optional[str] = None,
    priority: str = "normal"
) -> str:
    """
    Publishes event to message queue for webhook delivery
    Deduplicates based on idempotency_key if provided
    Returns: event_id
    Raises: DuplicateEventError if idempotency key seen within 24h
    """
```

## Retry Logic

### Enhanced Exponential Backoff Algorithm

```python
def calculate_next_retry(
    attempt: int, 
    config: RetryConfig,
    failure_category: str,
    recent_success_rate: float
) -> datetime:
    """
    attempt: 0-indexed attempt number
    failure_category: timeout, server_error, network, etc.
    recent_success_rate: success rate over last 1 minute
    Returns: timestamp for next retry
    """
    # Base delay calculation
    delay = min(
        config.initial_delay_seconds * (config.backoff_multiplier ** attempt),
        config.max_delay_seconds
    )
    
    # Adaptive adjustments based on failure type
    if failure_category == "timeout":
        # Timeouts might need more breathing room
        delay *= 1.5
    elif failure_category == "rate_limit":
        # Respect rate limiting with longer delays
        delay = max(delay, 60)  # minimum 1 minute
    elif failure_category == "server_error" and recent_success_rate > 0.5:
        # If mostly successful, retry more aggressively for transient 5xx
        delay *= 0.7
    
    # Add adaptive jitter based on success rate
    # Lower success rate = more jitter to spread load
    jitter_factor = 0.1 + (0.2 * (1 - recent_success_rate))
    jitter = random.uniform(0, delay * jitter_factor)
    
    return now() + timedelta(seconds=delay + jitter)
```

### Retry Schedule Examples

**Standard failure (5xx):**
- Attempt 1: Immediate
- Attempt 2: 2s + jitter
- Attempt 3: 4s + jitter
- Attempt 4: 8s + jitter
- Attempt 5: 16s + jitter
- Attempt 6+: Exhausted → DLQ

**Timeout failure (separate budget):**
- Attempt 1: Immediate (30s timeout)
- Attempt 2: 3s + jitter (30s timeout)
- Attempt 3: 6s + jitter (45s timeout, increased)
- Attempt 4: 12s + jitter (60s timeout)
- Attempt 5+: Exhausted → DLQ (marked as "timeout_exhausted")

**Rate limit (429):**
- Attempt 1: Immediate
- Attempt 2: 60s minimum + jitter
- Attempt 3: 120s + jitter
- Subsequent: Respect Retry-After header if present

### Retry Eligibility Decision Tree

```python
class RetryDecision:
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
        
        # Network-level errors - always retry
        if error_type in ["dns_failure", "connection_refused", "connection_timeout"]:
            return (True, f"retryable_network_error_{error_type}")
        
        # SSL errors - retry only first 2 attempts (might be transient)
        if error_type == "ssl_error":
            if attempt < 2:
                return (True, "transient_ssl_error")
            return (False, "persistent_ssl_error")
        
        # HTTP status codes
        if http_status:
            # Client errors - don't retry
            if http_status in [400, 401, 403, 404, 410, 413]:
                return (False, f"client_error_{http_status}")
            
            # Rate limiting - retry with backoff
            if http_status == 429:
                return (True, "rate_limited")
            
            # Timeout - retry with separate budget if enabled
            if http_status == 408:
                return (True, "request_timeout")
            
            # Server errors - retry
            if http_status in [500, 502, 503, 504]:
                return (True, f"server_error_{http_status}")
            
            # Unexpected 2xx/3xx during error flow
            if 200 <= http_status < 400:
                return (False, "unexpected_success_status")
        
        # Read timeout (no status code)
        if error_type == "read_timeout":
            return (True, "read_timeout")
        
        # Unknown error - retry cautiously
        return (True, "unknown_error_cautious_retry")
```

## Error Handling

### Enhanced Circuit Breaker Pattern

```python
class AdaptiveCircuitBreaker:
    """
    Maintains separate counters for different failure types
    Uses sliding window for failure rate calculation
    Implements gradual recovery with health checks
    """
    
    def __init__(self, config: CircuitBreakerConfig):
        self.state = "closed"
        self.failure_window = SlidingWindow(duration=60)  # 1 minute
        self.timeout_counter = ConsecutiveCounter()
        self.server_error_counter = ConsecutiveCounter()
        self.success_counter = ConsecutiveCounter()
        self.config = config
    
    def record_attempt(self, outcome: DeliveryOutcome):
        """
        Records delivery attempt and updates state
        Different thresholds for timeouts vs server errors
        """
        if outcome.success:
            self.success_counter.increment()
            self.timeout_counter.reset()
            self.server_error_counter.reset()
            
            if self.state == "half_open":
                if self.success_counter.value >= self.config.success_threshold:
                    self._transition_to_closed()
        else:
            self.success_counter.reset()
            self.failure_window.add(outcome)
            
            if outcome.failure_category == "timeout":
                self.timeout_counter.increment()
                # Timeouts are often transient, higher threshold
                if self.timeout_counter.value >= self.config.timeout_threshold:
                    self._transition_to_open("consecutive_timeouts")
            
            elif outcome.failure_category in ["server_error", "network"]:
                self.server_error_counter.increment()
                # Server errors might indicate endpoint issues
                if self.server_error_counter.increment() >= self.config.failure_threshold:
                    self._transition_to_open("consecutive_failures")
            
            # Check overall failure rate
            failure_rate = self.failure_window.failure_rate()
            if failure_rate > 0.9 and self.failure_window.count() >= 20:
                self._transition_to_open("high_failure_rate")
    
    def should_allow_request(self) -> tuple[bool, str]:
        """
        Returns: (allow, reason)
        """
        if self.state == "closed":
            return (True, "circuit_closed")
        
        if self.state == "open":
            # Check if it's time to try half-open
            if now() >= self.next_attempt_at:
                self._transition_to_half_open()
                return (True, "circuit_half_open_probe")
            return (False, "circuit_open")
        
        if self.state == "half_open":
            # Allow limited requests for health checking
            # Use rate limiting to prevent flood
            return (True, "circuit_half_open_testing")
    
    def _transition_to_open(self, reason: str):
        """Opens circuit, schedules next attempt"""
        self.state = "open"
        self.opened_at = now()
        self.next_attempt_at = now() + timedelta(
            seconds=self.config.half_open_timeout_seconds
        )
        emit_metric("circuit_breaker_opened", {"reason": reason})
        notify_webhook_owner("circuit_opened", reason)
    
    def _transition_to_half_open(self):
        """Enters testing mode"""
        self.state = "half_open"
        self.success_counter.reset()
        emit_metric("circuit_breaker_half_opened")
    
    def _transition_to_closed(self):
        """Recovers to normal operation"""
        self.state = "closed"
        self.timeout_counter.reset()
        self.server_error_counter.reset()
        emit_metric("circuit_breaker_closed")
        notify_webhook_owner("circuit_recovered")
```

### Circuit Breaker Integration with Retry Logic

**Key Principle**: Circuit breaker operates at the webhook level (across events), while retries operate at the delivery level (per event).

```
Decision Flow:
1. Event arrives for delivery
2. Check circuit breaker state for webhook
3. If OPEN: 
   - Don't attempt delivery
   - Requeue event with delay matching circuit open time
   - Don't count as retry attempt
4. If CLOSED or HALF_OPEN:
   - Proceed with delivery attempt
   - Record outcome in circuit breaker
   - If delivery fails:
     a. Check retry eligibility
     b. If retryable: schedule retry per backoff algorithm
     c. If not retryable or exhausted: move to DLQ
5. Circuit breaker state updates independently of retry count
```

### Security

1. **HMAC Signing**
   - Sign payload with webhook secret using HMAC-SHA256
   - Include timestamp to prevent replay attacks
   - Include signature in `X-Webhook-Signature` header
   - Format: `t={timestamp},v1={signature}`

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
User-Agent: WebhookService/1.0
```

3. **Timeout & Rate Limiting**
   - HTTP request timeout: 30 seconds (default), configurable per webhook
   - Separate timeouts for DNS, connection, and read phases
   - Per-webhook rate limit: 100 requests/minute with burst of 20
   - Connection pooling with max 10 connections per host
   - Per-tenant global rate limits to prevent abuse

4. **URL Validation**
   - Block private IP ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
   - Block localhost and link-local addresses
   - Require HTTPS in production environments
   - Optional verification webhook during registration

### Idempotency

- Each event has unique `idempotency_key` (auto-generated if not provided)
- Include in delivery headers and payload
- Consumers should deduplicate using this key (valid for 24h)
- System guarantees at-least-once delivery
- Publisher deduplicates events with same idempotency key within 24h window
- Failed deliveries with same event maintain idempotency key across retries

## Worker Processing Flow

```
1. Worker polls message queue with priority awareness
2. Extract webhook_id and event from message
3. Load webhook subscription from database (with caching)
4. Check if webhook is active:
   - If inactive: ACK message, log skip, exit
5. Check circuit breaker status:
   a. If OPEN:
      - Calculate time until half-open
      - Requeue message with delay (don't count as attempt)
      - Update metrics
      - Exit
   b. If CLOSED or HALF_OPEN: proceed
6. Check rate limiter:
   - If rate limited: requeue with delay, exit
7. Load previous delivery attempts for this event+webhook
8. Evaluate retry eligibility:
   - Check attempt count vs max
   - If exhausted: move to DLQ, ACK message, exit
9. Build HTTP request:
   a. Generate HMAC signature with timestamp
   b. Add all headers including attempt number
   c. Set timeout based on attempt number and config
10. Execute HTTP request with comprehensive error capture:
    a. Record DNS resolution time
    b. Record connection time  
    c. Record total duration
    d. Capture response status, headers, body (truncated)
    e. Capture detailed error info on failure
11. Classify outcome:
    a. Success (2xx): 
       - ACK message
       - Update circuit breaker (success)
       - Update metrics
       - Store delivery attempt as "success"
       - Exit
    b. Retryable failure:
       - Determine failure category (timeout, 5xx, network, etc.)
       - Update circuit breaker (failure with category)
       - Calculate next retry time using adaptive backoff
       - Store delivery attempt as "failed" with details
       - NACK message with delay
       - Exit
    c. Non-retryable failure:
       - Update circuit breaker (failure)
       - Store delivery attempt as "exhausted"
       - Move to DLQ with failure classification
       - ACK message
       - Exit
12. Handle worker-level errors:
    - Database connection failures: NACK without delay, let message retry
    - Unexpected exceptions: log, store partial attempt, NACK
    - Graceful shutdown: NACK all in-flight messages
```

### Failure Mode Handling

**Database Unavailable:**
- Worker cannot proceed without webhook config
- NACK message immediately (no delay)
- Message returns to queue for other workers
- Alert on repeated failures

**Circuit Breaker State Desynchronization:**
- Circuit breaker state cached in Redis with TTL
- If Redis unavailable, fall back to database or fail-safe closed
- Periodic reconciliation between Redis and database
- Use distributed locks for state transitions

**Message Queue Failure:**
- Worker should have local persistent queue for buffering
- Retry queue operations with exponential backoff
- Alert on queue connection issues
- Graceful degradation: reject new events if queue full

**Webhook URL DNS Fails:**
- Treat as network failure (retryable)
- Cache DNS results (with reasonable TTL)
- Alert if DNS fails consistently for many webhooks

**Worker Crash During Delivery:**
- Message remains in queue (not ACKed)
- Other workers will pick it up
- Delivery attempt might be partially recorded
- Use idempotency key to detect duplicate processing

**Partial Response (connection closed mid-stream):**
- Treat as read timeout (retryable)
- Record as much response data as received
- Next attempt should be fresh request

**Webhook Returns 2xx but Processing Fails:**
- System considers it successful (consumer's responsibility)
- Consumer should return 5xx if processing fails
- Document best practices for webhook consumers

## Scalability Considerations

- **Horizontal scaling**: Add more worker instances behind load balancer
- **Partitioning**: Shard webhooks by tenant_id across worker pools
- **Priority queues**: Separate queues for high/normal/low priority events
- **Tenant isolation**: Dedicated worker pools for high-volume tenants
- **Database optimization**:
  - Partition delivery_attempts table by time (monthly partitions)
  - Index on (webhook_id, created_at) for queries
  - Index on (event_id, webhook_id) for deduplication
  - Archive old delivery attempts to cold storage after 90 days
- **Caching strategy**:
  - Cache webhook configs in Redis (TTL 5 minutes)
  - Cache circuit breaker state in Redis (TTL 1 minute)
  - Cache rate limiter state in Redis
- **Connection pooling**: Reuse HTTP connections per worker
- **Batch processing**: Future enhancement to group deliveries to same endpoint

## Monitoring Metrics

- `webhook_deliveries_total{status, event_type, failure_category, tenant_id}`
- `webhook_delivery_duration_seconds{status, phase}` (phase: dns, connection, transfer)
- `webhook_retry_attempts_total{attempt_number, failure_category}`
- `webhook_queue_depth{priority, tenant_id}`
- `webhook_circuit_breaker_state{webhook_id, state}`
- `webhook_circuit_breaker_transitions_total{from_state, to_state, reason}`
- `webhook_dlq_size{tenant_id, failure_category}`
- `webhook_rate_limit_hits_total{webhook_id}`
- `webhook_worker_health{worker_id, status}`
- `webhook_idempotency_duplicates_total{event_type}`

## Alerting Rules

- Circuit breaker opened for webhook
- DLQ size exceeds threshold per tenant
- Webhook delivery success rate drops below 90% (5 min window)
- Worker pool unhealthy (>50% workers failing health checks)
- Queue depth exceeds threshold (potential backlog)
- Unusual spike in specific failure category

## What I Improved

1. **Separate Failure Category Tracking**: Added detailed failure classification (timeout, server_error, network, ssl, rate_limit) to enable better analytics and differentiated retry strategies.

2. **Adaptive Circuit Breaker**: Enhanced circuit breaker to track different failure types with separate thresholds. Timeouts get higher threshold than 5xx errors since they're more often transient. Added failure rate calculation over sliding window to catch degradation patterns.

3. **Circuit Breaker + Retry Separation**: Clarified that circuit breaker operates at webhook level (across events) while retries operate at delivery level (per event). When circuit is open, events are requeued without consuming retry attempts.

4. **Adaptive Retry Backoff**: Added failure-category-specific adjustments to backoff delays. Timeouts get 1.5x longer delays, rate limits get minimum 60s delays, and transient 5xx with high recent success rate retry more aggressively.

5. **Comprehensive Error Capture**: Added fields to capture DNS resolution time, connection time, response headers, and detailed error context to enable better debugging and pattern detection.

6. **Timeout Budget Separation**: Added option for separate timeout retry budget since timeouts often indicate different issues than 5xx errors and might need different retry strategies.

7. **Health Check Mechanism**: Added circuit breaker health check interval and gradual recovery via half-open state with controlled request flow.

8. **Enhanced Retry Eligibility**: Created decision tree that handles edge cases like SSL errors (retry first 2 attempts only), rate limits (respect Retry-After header), and unexpected success codes during error flow.

9. **Worker Failure Modes**: Added detailed handling for database unavailability, circuit breaker desync, message queue failures, DNS failures, worker crashes, partial responses, and consumer-side failures.

10. **Multi-Tenancy Isolation**: Added tenant_id to data models, per-tenant rate limits, tenant-specific worker pools, and tenant-level DLQ filtering.

11. **Idempotency Enforcement**: Added duplicate detection in publisher (24h window) and automatic idempotency key generation if not provided.

12. **Security Enhancements**: Added timestamp to HMAC signature to prevent replay attacks, IP range blocking for webhook URLs, and optional URL verification during registration.

13. **Monitoring Improvements**: Added phase-based duration metrics (DNS, connection, transfer), circuit breaker transition tracking, and alerting rules for common failure patterns.

## What I Kept

1. **Overall Architecture**: The multi-component design with separation of concerns is solid.

2. **PostgreSQL for State**: Correct choice for webhook configs and delivery history requiring queryability.

3. **Message Queue Pattern**: Async processing via queue is the right approach.

4. **HMAC Signing**: Standard webhook security pattern is appropriate.

5. **Exponential Backoff Foundation**: Base algorithm is sound, I just added adaptive enhancements.

6. **DLQ Pattern**: Separate handling for exhausted deliveries is essential.

7. **Data Models**: Core structure of webhook subscription and delivery attempt models is well-designed.

## Remaining Concerns

1. **Event Ordering**: Still unresolved whether we guarantee per-webhook event ordering. This requires serialization which significantly impacts throughput. Need to decide if this is opt-in per webhook or global policy.

2. **Payload Size Impact**: Maximum payload size affects memory usage per worker and queue storage. Need to define limits and handle oversized payloads gracefully (reject vs truncate vs external storage).

3. **Long-Running Requests**: If webhook endpoint takes 25+ seconds to respond (approaching timeout), should we adjust subsequent retry timeouts? Current design increases timeout on retries but unclear if this is optimal.

4. **Circuit Breaker Recovery Edge Case**: During half-open state, if we get mixed results (some success, some failure), how many probe attempts before making open/close decision? Current design requires consecutive successes which might be too strict.

5. **Cross-Tenant Impact**: If one tenant's webhook endpoints are all failing, could their retry traffic impact other tenants' deliveries? Worker pool partitioning helps but needs validation.

6. **Batch Retry from DLQ**: When bulk retrying from DLQ, how do we prevent overwhelming downstream systems? Need rate limiting on batch operations.

## Convergence Status

**ITERATING** - Found significant areas for improvement in error handling, circuit breaker integration, failure mode coverage, and retry strategy differentiation. Design is substantially enhanced but would benefit from architect's review of the adaptive mechanisms.

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
Please review the adaptive retry backoff and differentiated circuit breaker thresholds. Specifically:
1. Does the failure-category-specific backoff adjustment make sense? Are the multipliers (1.5x for timeout, 0.7x for transient 5xx) reasonable?
2. Should the circuit breaker timeout threshold (5) be configurable per webhook, or is a global default sufficient?
3. For the half-open state, I'm requiring consecutive successes to close - should we use a success rate over N attempts instead to handle mixed results better?
4. Does the separation between circuit breaker (webhook-level) and retries (delivery-level) handle the interaction correctly, especially when circuit opens mid-retry-sequence?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

**1. Time-window circuit breaker over separate counters**: The multi-counter approach (separate tracking for timeouts vs 5xx) adds significant complexity. A time-window based error rate is simpler, more predictable, and aligns with industry standard implementations (Hystrix, resilience4j). Operators understand "50% errors in last 60s" more intuitively than "5 consecutive timeouts OR 10 server errors OR 90% failure rate."

**2. Simplified retry backoff**: Removed the adaptive backoff adjustments based on recent success rate. This adds complexity and unpredictability—if a webhook is recovering, the circuit breaker will naturally handle the transition. Retry logic should be simple and deterministic. Category-based minimum delays handle the key cases (rate limits need longer waits) without overcomplicating.

**3. Half-open probe count over consecutive successes**: Using a fixed number of probe attempts (e.g., 3) with a success rate threshold (≥50%) is more robust than requiring consecutive successes. In real systems, you might get intermittent failures even during recovery. A 2-out-of-3 success rate indicates the endpoint is recovering, while requiring 3 consecutive successes might keep the circuit open unnecessarily.

**4. Timeout growth instead of separate budget**: Rather than separate retry budgets for timeouts, grow the timeout value on subsequent attempts (capped at 3x). This handles the case where an endpoint is slow but responsive, without the complexity of dual tracking. If the issue is truly timeout-related, the circuit breaker will open anyway.

**5. Per-webhook circuit breaker config over global**: Making thresholds configurable per webhook adds flexibility without much complexity. Some webhooks call critical real-time systems (need aggressive circuit breaking), others call batch processing endpoints (can tolerate more failures). Default values work for most cases.

**6. Explicit ordering modes**: The original design left ordering unresolved. Making it an explicit webhook configuration with three clear options (none/per_event_type/strict) gives users control and makes the performance trade-offs transparent.

**7. Fixed payload limit with rejection**: Rejecting oversized payloads at publish time is cleaner than runtime handling. If future needs require large payloads, add blob storage with URLs—but start simple.

**8. Fail-safe circuit breaker**: When Redis is unavailable, default to "closed" (allow requests) rather than "open" (block). This prevents cascading failures where Redis issues block all webhook deliveries. Better to risk some failed deliveries than block everything.

## What I Changed

1. **Replaced multi-counter circuit breaker with time-window approach**: Simpler implementation, more predictable behavior, industry-standard pattern. Eliminates separate tracking for timeouts vs 5xx errors.

2. **Removed adaptive backoff adjustments**: Simplified retry logic to basic exponential backoff with category-specific minimums. Circuit breaker handles broader patterns; retries should be deterministic.

3. **Changed half-open recovery to probe-based with success rate**: Instead of requiring consecutive successes, allow N probes and evaluate success rate. More resilient to intermittent failures during recovery.

4. **Added timeout growth factor**: Timeouts grow per attempt (up to 3x) instead of separate retry budget. Simpler, handles slow endpoints without dual tracking.

5. **Made circuit breaker thresholds per-webhook configurable**: Different endpoints have different reliability requirements. Defaults work for most cases, but power users can tune.

6. **Added explicit event ordering modes**: Resolved the unaddressed ordering question with three clear options and documented throughput impact.

7. **Defined payload size limit with rejection policy**: 256KB max, reject at publish time. Clear boundary, prevents runtime surprises.

8. **Changed Redis failure mode to fail-safe**: Circuit breaker defaults to "closed" when Redis unavailable, preventing cascade failures.

9. **Simplified retry eligibility logic**: Removed timeout-specific retry limits, consolidated into single decision tree. SSL errors still have attempt limit (3).

10. **Added batch retry rate limiting**: DLQ batch operations include configurable rate limit to prevent overwhelming downstream systems.

## What I Kept

1. **Overall architecture**: Component separation (publisher, workers, DLQ, circuit breaker) is sound.

2. **Core data models**: Webhook subscription and delivery attempt structures are well-designed.

3. **Technology stack**: PostgreSQL, Redis, RabbitMQ, Go workers—appropriate choices for the requirements.

4. **HMAC signing with timestamp**: Standard webhook security pattern.

5. **Failure classification**: Detailed categorization (timeout, server_error, network, etc.) enables good observability.

6. **Tenant isolation**: Multi-tenancy support with per-tenant rate limits and dedicated worker pools.

7. **Monitoring approach**: Comprehensive metrics and alerting rules.

8. **Idempotency handling**: 24h deduplication window with automatic key generation.

## Open Questions

None remaining. The design is complete and implementable as specified.

## Convergence Status

**PROPOSING_FINAL** - The design has been refined through multiple rounds. All major concerns have been addressed:
- Circuit breaker simplified to industry-standard time-window approach
- Retry logic streamlined while preserving key failure-category handling
- Event ordering resolved with explicit configuration options
- Payload limits defined with clear rejection policy
- Failure modes comprehensively documented
- Circuit breaker and retry interaction clearly specified

The design is production-ready and implementable without ambiguity.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Please review the time-window circuit breaker design and probe-based recovery mechanism. Specifically:
1. Does the 50% error rate threshold over 60s window with 10-request minimum provide appropriate circuit breaker sensitivity?
2. Is the half-open probe mechanism (3 probes, require ≥50% success) sufficient for safe recovery, or should we use more probes or a higher success threshold?
3. Does the fail-safe behavior (default to "closed" when Redis unavailable) create acceptable risk, or should we be more conservative?
4. Are there any edge cases in the circuit breaker and retry interaction that could lead to unexpected behavior?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

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
    "error_threshold_percentage": 60,
    "minimum_throughput": 20,
    "window_size_ms": 60000,
    "sleep_window_ms": 30000,
    "half_open_max_calls": 5,
    "half_open_success_threshold": 0.6,
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
  "circuit_breaker_prevented": false,
  "circuit_breaker_state_at_attempt": "closed|open|half_open"
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
  "half_open_successes": 0,
  "consecutive_half_open_failures": 0,
  "redis_fallback_mode": false
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

### Time-Window Based Circuit Breaker with Improved Defaults

```python
class TimeWindowCircuitBreaker:
    """
    Time-window based circuit breaker with conservative defaults and Redis fallback
    """
    
    def __init__(self, webhook_id: str, config: CircuitBreakerConfig):
        self.webhook_id = webhook_id
        self.config = config
        self.state = "closed"
        self.redis_fallback_mode = False
        
        # Rolling window data stored in Redis sorted set
        # Key: webhook_id, Score: timestamp, Value: success|failure
        self.window_key = f"cb:{webhook_id}:window"
        self.state_key = f"cb:{webhook_id}:state"
        
    def record_attempt(self, success: bool, failure_category: Optional[str] = None):
        """
        Records attempt in time window and evaluates state transition
        Handles Redis failures gracefully with fallback mode
        """
        timestamp = now_ms()
        result = "success" if success else f"failure:{failure_category}"
        
        try:
            # Add to sorted set with timestamp as score
            redis.zadd(self.window_key, {result: timestamp})
            redis.expire(self.window_key, self.config.window_size_ms // 1000 + 60)
            
            # Remove entries outside window
            window_start = timestamp - self.config.window_size_ms
            redis.zremrangebyscore(self.window_key, 0, window_start)
            
            # Update state based on current window
            self._evaluate_state()
            
            # Clear fallback mode on successful Redis operation
            if self.redis_fallback_mode:
                self.redis_fallback_mode = False
                emit_metric("circuit_breaker_redis_recovered", {"webhook_id": self.webhook_id})
                
        except RedisConnectionError as e:
            # Enter fallback mode - maintain last known state
            if not self.redis_fallback_mode:
                self.redis_fallback_mode = True
                emit_metric("circuit_breaker_redis_fallback", {"webhook_id": self.webhook_id})
                log.warning(f"Circuit breaker entering Redis fallback mode: {e}")
            
            # In fallback: keep current state, allow requests unless manually forced open
            # This prevents cascading failures from Redis outage
    
    def _evaluate_state(self):
        """
        Evaluate state transition based on time window metrics
        Uses more conservative thresholds by default
        """
        timestamp = now_ms()
        window_start = timestamp - self.config.window_size_ms
        
        # Get all attempts in window
        attempts = redis.zrangebyscore(self.window_key, window_start, timestamp)
        total = len(attempts)
        failures = sum(1 for a in attempts if a.startswith("failure:"))
        
        if self.state == "closed":
            # Check if we should open
            # Default: 60% error rate with 20 request minimum (more conservative)
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
                # Decision time - use configurable threshold (default 60%)
                success_rate = self.half_open_successes / self.half_open_attempts
                if success_rate >= self.config.half_open_success_threshold:
                    self._transition_to_closed()
                else:
                    # Back to open, with extended sleep window for second+ failures
                    self.consecutive_half_open_failures += 1
                    self._transition_to_open(
                        extended_sleep=self.consecutive_half_open_failures > 1
                    )
    
    def should_allow_request(self) -> tuple[bool, str]:
        """
        Returns: (allow, reason)
        Handles Redis fallback mode gracefully
        """
        # Check force_open override (persisted in DB, not Redis)
        if self.config.force_open_until and now() < self.config.force_open_until:
            return (False, "manually_forced_open")
        
        # In Redis fallback mode: allow requests (fail-safe)
        # unless we're in a manually forced open state
        if self.redis_fallback_mode:
            if self.state == "open" and hasattr(self, 'manual_force_open'):
                return (False, "circuit_open_manual_override")
            return (True, "redis_fallback_allowing")
        
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
    
    def _transition_to_open(self, extended_sleep: bool = False):
        """
        Transition to open state
        If extended_sleep=True, double the sleep window for repeated failures
        """
        self.state = "open"
        self.state_transition_at = now_ms()
        self.half_open_attempts = 0
        self.half_open_successes = 0
        
        # Persist state to DB for fallback
        self._persist_state_to_db()
        
        emit_metric("circuit_breaker_opened", {
            "webhook_id": self.webhook_id,
            "extended_sleep": extended_sleep,
            "consecutive_failures": self.consecutive_half_open_failures
        })
        
        # Notify webhook owner with context
        notify_webhook_owner(
            self.webhook_id, 
            "circuit_opened",
            context={
                "consecutive_failures": self.consecutive_half_open_failures,
                "next_retry": self.state_transition_at + self.config.sleep_window_ms * (2 if extended_sleep else 1)
            }
        )
    
    def _transition_to_half_open(self):
        self.state = "half_open"
        self.state_transition_at = now_ms()
        self.half_open_attempts = 0
        self.half_open_successes = 0
        
        self._persist_state_to_db()
        
        emit_metric("circuit_breaker_half_opened", {"webhook_id": self.webhook_id})
    
    def _transition_to_closed(self):
        self.state = "closed"
        self.state_transition_at = now_ms()
        self.consecutive_half_open_failures = 0  # Reset on successful recovery
        
        # Clear window on successful recovery
        redis.delete(self.window_key)
        
        self._persist_state_to_db()
        
        emit_metric("circuit_breaker_closed", {"webhook_id": self.webhook_id})
        notify_webhook_owner(self.webhook_id, "circuit_recovered")
    
    def _persist_state_to_db(self):
        """
        Persist critical circuit breaker state to DB for Redis fallback
        Only stores: webhook_id, state, state_transition_at, manual_force_open
        TTL: 24 hours (stale data cleanup)
        """
        db.execute(
            """
            INSERT INTO circuit_breaker_state_cache 
            (webhook_id, state, state_transition_at, manual_force_open, updated_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (webhook_id) DO UPDATE SET
                state = EXCLUDED.state,
                state_transition_at = EXCLUDED.state_transition_at,
                manual_force_open = EXCLUDED.manual_force_open,
                updated_at = EXCLUDED.updated_at
            """,
            (self.webhook_id, self.state, self.state_transition_at, 
             hasattr(self, 'manual_force_open'), now())
        )
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
   - Calculate requeue delay:
     * If attempt == 1: requeue with circuit sleep window remaining
     * If attempt > 1: requeue with min(circuit sleep window, next retry backoff)
     * This preserves retry schedule while respecting circuit breaker
   - When circuit transitions to half-open, message will be reprocessed
   
   HALF_OPEN:
   - Allow up to N probe requests (5 by default)
   - If selected as probe: attempt delivery normally
   - If not selected: treat as OPEN (requeue with short delay: 5s)
   - Probes distributed across different events when possible

3. Retry sequence behavior:
   - Retry counter persists across circuit breaker cycles
   - Circuit blocks DO NOT count toward retry limit
   - Example timeline:
     * Attempt 1 (t=0): fails with 500 error
     * Attempt 2 (t=2s): circuit opens due to error rate, blocked
     * Attempt 2 retry (t=32s): circuit half-open, selected as probe, succeeds
     * Circuit closes, event delivered successfully
   - This prevents double-penalization: errors count toward circuit breaker
     OR retry exhaustion, not both

4. Edge case: Circuit opens between retry schedule and execution
   - Retry scheduled for t=10s, circuit opens at t=8s
   - At t=10s: worker checks circuit breaker BEFORE attempting delivery
   - Circuit open → requeue with remaining sleep window
   - Prevents wasted delivery attempts against known-bad endpoints
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
   a. Load circuit state from Redis (with DB fallback on Redis failure)
   b. Call should_allow_request()
   c. If blocked:
      - Record delivery attempt as "circuit_blocked"
      - Calculate requeue delay:
        * attempt == 1: circuit sleep window remaining
        * attempt > 1: min(circuit sleep window, next retry backoff)
      - NACK message with calculated delay
      - Exit
   d. If allowed: proceed
6. Check rate limiter (token bucket in Redis):
   - If rate limited: NACK with 1s delay, exit
7. Evaluate retry eligibility:
   - If attempt >= max_attempts: move to DLQ, ACK, exit
   - Note: circuit_blocked attempts don't count toward max_attempts
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
    - Redis unavailable: 
      * Circuit breaker: use DB fallback state
      * Rate limiter: allow request (fail-safe)
      * Log warning, emit metric
    - DB unavailable: NACK immediately (no delay)
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
- Circuit breaker falls back to DB-persisted state (last known)
  - If DB state exists and not stale (<5min): use that state
  - If no DB state or stale: default to "closed" (fail-safe)
- Rate limiting disabled temporarily (fail-safe: allow requests)
- Deduplication disabled temporarily (risk: duplicate deliveries acceptable)
- Worker logs warning and continues
- Alert on Redis connection issues
- Emit metric: `circuit_breaker_redis_fallback_active{webhook_id}`

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

**Both Redis AND DB Unavailable:**
- Circuit breaker defaults to "closed" (fail-safe)
- Record circuit breaker state in memory (worker local)
- Emit critical alert: `infrastructure_dual_failure`
- System continues with degraded observability
- On recovery: reconcile in-memory state to Redis

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
- `webhook_circuit_breaker_redis_fallback_active{webhook_id}` (gauge)
- `webhook_dlq_size{tenant_id}`
- `webhook_rate_limit_hits_total{webhook_id}`
- `webhook_worker_pool_utilization{pool_id}`
- `webhook_circuit_blocked_deliveries{webhook_id}` (counter)

## Alerting Rules

- Circuit breaker opened (severity: warning)
- Circuit breaker open >1 hour (severity: critical)
- Circuit breaker Redis fallback active >5min (severity: warning)
- DLQ size >1000 per tenant (severity: warning)
- Webhook success rate <90% over 5min (severity: warning)
- Worker pool >80% utilization (severity: warning)
- Queue depth >10000 (severity: critical)
- Redis unavailable >2min (severity: critical)
- DB unavailable >30s (severity: critical)

---

## What I Improved

1. **Increased default circuit breaker thresholds**: Changed from 50% error threshold with 10 requests to **60% error threshold with 20 requests**. This reduces false positives from brief transient failures. A 50% threshold is too aggressive—one bad request out of two could trigger opening unnecessarily.

2. **Increased half-open probe count and made success threshold configurable**: Changed from 3 probes requiring 50% success to **5 probes requiring 60% success** (configurable). More probes provide better signal; 60% success rate (3/5) is more reliable indicator of recovery than 50% (2/3 can be lucky).

3. **Added extended sleep window for repeated half-open failures**: If circuit repeatedly fails to close from half-open state, double the sleep window on subsequent attempts. Prevents thrashing when endpoint has sustained issues.

4. **Improved Redis fallback mechanism**: Instead of just logging and continuing, the system now:
   - Persists critical circuit breaker state to DB as backup
   - Falls back to DB state when Redis unavailable
   - Distinguishes between "no state" vs "stale state" (>5min)
   - Emits specific metrics for fallback mode duration
   - This makes the fail-safe behavior more robust and observable

5. **Added circuit breaker state to delivery attempt records**: Field `circuit_breaker_state_at_attempt` helps debugging and understanding why deliveries were blocked.

6. **Clarified retry/circuit breaker interaction edge case**: Explicitly documented behavior when circuit opens between retry schedule and execution. Worker checks circuit breaker BEFORE attempting delivery.

7. **Improved circuit block requeue logic**: For attempt > 1, use `min(circuit sleep window, next retry backoff)` to preserve retry schedule while respecting circuit breaker. Prevents unnecessarily long delays.

8. **Added half-open probe distribution hint**: Note that probes should be distributed across different events when possible, avoiding concentration on single event retry attempts.

9. **Enhanced failure mode handling**: Added explicit handling for "both Redis AND DB unavailable" scenario with in-memory fallback and critical alerting.

10. **Added circuit-blocked delivery metric**: Track `webhook_circuit_blocked_deliveries` separately to understand circuit breaker intervention frequency.

## What I Kept

1. **Time-window based circuit breaker approach**: Superior to multi-counter approach, correctly identified by architect.

2. **Core architecture and component separation**: Well-designed, clean boundaries.

3. **Simplified retry backoff logic**: Appropriately streamlined from complex adaptive approaches.

4. **Fail-safe philosophy**: Default to allowing requests rather than blocking on infrastructure failures.

5. **Data models and interfaces**: Comprehensive and well-structured.

6. **Security mechanisms**: HMAC signing, timeout growth, rate limiting all appropriate.

7. **Event ordering modes**: Good balance of options with clear trade-offs.

8. **Technology stack choices**: PostgreSQL, Redis, RabbitMQ, Go workers—all solid.

9. **Comprehensive monitoring and alerting**: Strong observability design.

10. **Detailed worker processing flow**: Clear, implementable logic.

## Remaining Concerns

**None**—the design is now production-ready with appropriate conservative defaults and robust fallback mechanisms.

## Convergence Status

**ACCEPTING_FINAL** - The design has been thoroughly refined through multiple rounds:
- Circuit breaker thresholds adjusted to more conservative defaults (60%/20 requests)
- Half-open recovery mechanism strengthened (5 probes, 60% success threshold)
- Redis fallback improved with DB persistence layer
- Circuit breaker/retry interaction edge cases fully specified
- Extended sleep window prevents thrashing
- All failure modes comprehensively handled

The design addresses the architect's specific questions:
1. ✅ 60% error rate over 60s with 20-request minimum provides better sensitivity (less false positives)
2. ✅ 5 probes with 60% success threshold is more robust than 3/50%
3. ✅ Fail-safe with DB fallback layer reduces risk acceptably
4. ✅ Edge cases documented and handled (circuit opens mid-retry, dual infrastructure failure)

This is implementable, secure, scalable, and operationally sound.

**Convergence Signal:** ACCEPTING_FINAL

---

