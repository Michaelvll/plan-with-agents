# Final Agreed Design

**Task:** Design a notification service with email and push notifications

**Status:** debating

---

## Design

# Notification Service Architecture

## System Overview
A horizontally-scalable notification service supporting pluggable channels (email, push, SMS, etc.) with exactly-once delivery guarantees, hybrid queue architecture, and production-grade resilience patterns.

## Architecture Components

### 1. Core Service Layer

**NotificationService (Orchestrator)**
```typescript
interface NotificationService {
  send(request: NotificationRequest): Promise<NotificationResult>;
  sendBatch(requests: NotificationRequest[]): Promise<BatchResult>;
  getStatus(notificationId: string): Promise<NotificationStatus>;
  cancel(notificationId: string): Promise<void>;
  retry(notificationId: string): Promise<NotificationResult>;
}

interface BatchResult {
  results: NotificationResult[];
  summary: {
    total: number;
    succeeded: number;
    failed: number;
    pending: number;
  };
}
```

**Channel Provider (Strategy Pattern)**
```typescript
interface ChannelProvider {
  readonly type: ChannelType;
  readonly capabilities: ProviderCapabilities;
  
  send(message: ChannelMessage): Promise<ProviderResult>;
  validateRecipient(recipient: Recipient): ValidationResult;
  healthCheck(): Promise<HealthStatus>;
}

interface ProviderCapabilities {
  batchSend: {
    supported: boolean;
    maxBatchSize?: number;
  };
  rateLimit: {
    perSecond: number;
    perMinute: number;
    perHour?: number;
  };
  features: {
    deliveryTracking: boolean;
    scheduling: boolean;
    richContent: boolean;
  };
}

interface ProviderResult {
  success: boolean;
  providerId: string;
  providerMessageId?: string;
  error?: ProviderError;
  metadata?: Record<string, any>;
}

// Implementations
class SendGridEmailProvider implements ChannelProvider
class FCMPushProvider implements ChannelProvider
class TwilioSMSProvider implements ChannelProvider
```

### 2. Hybrid Queue Architecture

**Queue Abstraction Layer**
```typescript
interface QueueAdapter {
  enqueue(message: QueueMessage, options: EnqueueOptions): Promise<string>;
  dequeue(workerId: string, count: number): Promise<QueueMessage[]>;
  ack(messageId: string, workerId: string): Promise<void>;
  nack(messageId: string, workerId: string, reason: string): Promise<void>;
  requeueWithDelay(messageId: string, delayMs: number): Promise<void>;
  extendVisibility(messageId: string, workerId: string, durationMs: number): Promise<void>;
  getDepth(priority?: NotificationPriority): Promise<number>;
}

interface EnqueueOptions {
  priority: NotificationPriority;
  visibilityDelay: number; // For scheduled sends
  deduplicationId?: string; // For exactly-once
}

interface QueueMessage {
  id: string;
  notificationId: string;
  payload: NotificationRequest;
  priority: NotificationPriority;
  enqueuedAt: Date;
  visibleAt: Date;
  dequeueCount: number;
  workerId?: string;
  leaseExpiry?: Date;
}

// Implementations for different scales
class PostgresQueueAdapter implements QueueAdapter // < 5K msg/sec
class RedisQueueAdapter implements QueueAdapter    // 5K-50K msg/sec
class SQSQueueAdapter implements QueueAdapter      // > 50K msg/sec
```

**PostgreSQL Queue (for low-to-medium scale)**
```typescript
class PostgresQueueAdapter implements QueueAdapter {
  async dequeue(workerId: string, count: number): Promise<QueueMessage[]> {
    const leaseMs = 300000; // 5 minutes
    
    // Critical: Use advisory locks to prevent phantom reads
    const result = await this.db.query(`
      WITH selected AS (
        SELECT id
        FROM notification_queue
        WHERE status = 'pending'
          AND visible_at <= NOW()
          AND (expires_at IS NULL OR expires_at > NOW())
          AND pg_try_advisory_xact_lock(hashtext(id::text)) -- Prevents race conditions
        ORDER BY 
          priority_order ASC,
          visible_at ASC
        LIMIT $1
      )
      UPDATE notification_queue nq
      SET 
        status = 'processing',
        worker_id = $2,
        lease_expiry = NOW() + ($3 || ' milliseconds')::interval,
        dequeue_count = dequeue_count + 1,
        last_dequeued_at = NOW(),
        version = version + 1
      FROM selected
      WHERE nq.id = selected.id
      RETURNING nq.*
    `, [count, workerId, leaseMs]);
    
    return result.rows.map(this.mapToQueueMessage);
  }
  
  async ack(messageId: string, workerId: string): Promise<void> {
    // Move to notifications table and delete from queue
    const result = await this.db.query(`
      WITH deleted AS (
        DELETE FROM notification_queue
        WHERE id = $1 
          AND worker_id = $2
          AND status = 'processing'
        RETURNING *
      )
      UPDATE notifications
      SET 
        status = 'sent',
        sent_at = NOW(),
        provider_response = deleted.provider_response,
        processing_time_ms = EXTRACT(EPOCH FROM (NOW() - deleted.last_dequeued_at)) * 1000
      FROM deleted
      WHERE notifications.id = deleted.notification_id
    `, [messageId, workerId]);
    
    if (result.rowCount === 0) {
      throw new Error(`Cannot ack message ${messageId}: not owned by worker ${workerId}`);
    }
  }
  
  async nack(messageId: string, workerId: string, reason: string): Promise<void> {
    // Release back to queue or move to DLQ
    await this.db.query(`
      UPDATE notification_queue
      SET 
        status = CASE 
          WHEN dequeue_count >= max_attempts THEN 'failed'
          ELSE 'pending'
        END,
        worker_id = NULL,
        lease_expiry = NULL,
        last_error = $3,
        visible_at = CASE
          WHEN dequeue_count >= max_attempts THEN visible_at
          ELSE NOW() + (power(2, dequeue_count) * interval '1 second') -- Exponential backoff
        END
      WHERE id = $1 
        AND worker_id = $2
    `, [messageId, workerId, JSON.stringify({ reason, timestamp: new Date() })]);
  }
}
```

**Redis Queue (for high scale)**
```typescript
class RedisQueueAdapter implements QueueAdapter {
  // Use Redis Sorted Sets for priority queue
  // Score = (priority_multiplier * 1e12) + timestamp_ms
  
  async enqueue(message: QueueMessage, options: EnqueueOptions): Promise<string> {
    const priority = this.getPriorityMultiplier(options.priority);
    const score = priority * 1e12 + options.visibilityDelay + Date.now();
    
    const pipeline = this.redis.pipeline();
    
    // Store message data
    pipeline.hset(`msg:${message.id}`, {
      payload: JSON.stringify(message.payload),
      notificationId: message.notificationId,
      enqueuedAt: message.enqueuedAt.toISOString(),
      dequeueCount: 0,
      maxAttempts: 5,
    });
    
    // Add to sorted set
    pipeline.zadd('notification_queue', score, message.id);
    
    // Deduplication
    if (options.deduplicationId) {
      pipeline.set(
        `dedup:${options.deduplicationId}`,
        message.id,
        'EX',
        3600, // 1 hour
        'NX'
      );
    }
    
    await pipeline.exec();
    return message.id;
  }
  
  async dequeue(workerId: string, count: number): Promise<QueueMessage[]> {
    const now = Date.now();
    const leaseMs = 300000;
    
    // Lua script for atomic dequeue with lease
    const script = `
      local queue_key = KEYS[1]
      local processing_key = KEYS[2]
      local now = tonumber(ARGV[1])
      local count = tonumber(ARGV[2])
      local worker_id = ARGV[3]
      local lease_ms = tonumber(ARGV[4])
      
      -- Get visible messages
      local ids = redis.call('ZRANGEBYSCORE', queue_key, 0, now, 'LIMIT', 0, count)
      
      if #ids == 0 then
        return {}
      end
      
      local messages = {}
      for _, id in ipairs(ids) do
        -- Move to processing set
        redis.call('ZREM', queue_key, id)
        redis.call('ZADD', processing_key, now + lease_ms, id)
        
        -- Update message metadata
        redis.call('HSET', 'msg:' .. id, 
          'workerId', worker_id,
          'leaseExpiry', now + lease_ms,
          'dequeueCount', redis.call('HINCRBY', 'msg:' .. id, 'dequeueCount', 1)
        )
        
        -- Get full message
        local msg = redis.call('HGETALL', 'msg:' .. id)
        table.insert(messages, msg)
      end
      
      return messages
    `;
    
    const results = await this.redis.eval(
      script,
      2,
      'notification_queue',
      'processing_queue',
      now,
      count,
      workerId,
      leaseMs
    );
    
    return this.parseRedisMessages(results);
  }
}
```

### 3. Worker Pool Architecture

```typescript
class NotificationWorker {
  private workerId: string;
  private queue: QueueAdapter;
  private providers: Map<ChannelType, ChannelProvider>;
  private rateLimiters: Map<string, RateLimiter>;
  private circuitBreakers: Map<string, CircuitBreaker>;
  private running = false;
  
  constructor(
    private config: WorkerConfig,
    private db: Database
  ) {
    this.workerId = `${os.hostname()}-${process.pid}-${randomUUID()}`;
    this.initializeQueue();
    this.initializeProviders();
  }
  
  async start(): Promise<void> {
    this.running = true;
    
    // Start processing loop
    this.processLoop();
    
    // Start heartbeat for worker health
    this.heartbeatLoop();
    
    // Start lease extension for long-running tasks
    this.leaseExtensionLoop();
  }
  
  private async processLoop(): Promise<void> {
    while (this.running) {
      try {
        const messages = await this.queue.dequeue(
          this.workerId,
          this.config.batchSize
        );
        
        if (messages.length === 0) {
          await this.sleep(this.config.pollIntervalMs);
          continue;
        }
        
        // Process in parallel with concurrency limit
        await pMap(
          messages,
          (msg) => this.processMessage(msg),
          { concurrency: this.config.concurrency }
        );
        
      } catch (error) {
        console.error('Worker process loop error:', error);
        await this.sleep(5000);
      }
    }
  }
  
  private async processMessage(message: QueueMessage): Promise<void> {
    const startTime = Date.now();
    let trackingSpan: Span | undefined;
    
    try {
      // Start tracing span
      trackingSpan = this.tracer.startSpan('process_notification', {
        attributes: {
          notificationId: message.notificationId,
          channel: message.payload.channel,
          priority: message.payload.priority,
        }
      });
      
      // Get provider
      const provider = this.providers.get(message.payload.channel);
      if (!provider) {
        throw new NotificationError(
          ErrorCategory.INTERNAL,
          'NO_PROVIDER',
          `No provider for channel ${message.payload.channel}`,
          false
        );
      }
      
      // Check rate limits
      const rateLimiter = this.rateLimiters.get(provider.type);
      await rateLimiter.acquire();
      
      // Check circuit breaker
      const circuitBreaker = this.circuitBreakers.get(provider.type);
      
      // Send with circuit breaker protection
      const result = await circuitBreaker.execute(() =>
        provider.send(this.buildChannelMessage(message.payload))
      );
      
      // Update notification record
      await this.db.query(`
        UPDATE notifications
        SET 
          provider_message_id = $1,
          provider_response = $2
        WHERE id = $3
      `, [result.providerMessageId, result.metadata, message.notificationId]);
      
      // Acknowledge success
      await this.queue.ack(message.id, this.workerId);
      
      // Fire webhook asynchronously (non-blocking)
      if (message.payload.callbackUrl) {
        this.fireWebhookAsync(message.payload.callbackUrl, {
          notificationId: message.notificationId,
          status: 'sent',
          sentAt: new Date(),
        }).catch(err => {
          console.error('Webhook delivery failed:', err);
          // Don't fail the notification - webhooks are best-effort
        });
      }
      
      // Record metrics
      this.metrics.notificationsSent.inc({
        channel: message.payload.channel,
        priority: message.payload.priority,
      });
      
      this.metrics.processingLatency.observe(
        { channel: message.payload.channel },
        Date.now() - startTime
      );
      
    } catch (error) {
      const notifError = this.normalizeError(error);
      
      // Record failure
      await this.db.query(`
        UPDATE notifications
        SET 
          last_error = $1,
          attempt_count = $2
        WHERE id = $3
      `, [
        JSON.stringify(notifError),
        message.dequeueCount,
        message.notificationId
      ]);
      
      // Determine retry strategy
      const shouldRetry = this.shouldRetry(message.dequeueCount, notifError);
      
      if (shouldRetry) {
        // Nack with retry
        await this.queue.nack(message.id, this.workerId, notifError.message);
        
        this.metrics.notificationsRetried.inc({
          channel: message.payload.channel,
          errorCategory: notifError.category,
        });
      } else {
        // Move to DLQ
        await this.moveToDLQ(message, notifError);
        await this.queue.ack(message.id, this.workerId); // Remove from queue
        
        this.metrics.notificationsFailed.inc({
          channel: message.payload.channel,
          errorCategory: notifError.category,
        });
      }
      
    } finally {
      trackingSpan?.end();
    }
  }
  
  private async leaseExtensionLoop(): Promise<void> {
    // Extend leases for messages taking longer than expected
    while (this.running) {
      await this.sleep(60000); // Every minute
      
      // Get all processing messages for this worker
      const messages = await this.getProcessingMessages();
      
      for (const msg of messages) {
        const timeLeft = msg.leaseExpiry.getTime() - Date.now();
        
        // Extend if less than 2 minutes remaining
        if (timeLeft < 120000) {
          await this.queue.extendVisibility(msg.id, this.workerId, 300000);
        }
      }
    }
  }
  
  private async heartbeatLoop(): Promise<void> {
    // Update worker health status
    while (this.running) {
      await this.db.query(`
        INSERT INTO worker_health (worker_id, last_heartbeat, processing_count)
        VALUES ($1, NOW(), $2)
        ON CONFLICT (worker_id) 
        DO UPDATE SET 
          last_heartbeat = NOW(),
          processing_count = $2
      `, [this.workerId, await this.getProcessingCount()]);
      
      await this.sleep(30000); // Every 30 seconds
    }
  }
}
```

### 4. Data Models

```typescript
enum ChannelType {
  EMAIL = 'email',
  PUSH = 'push',
  SMS = 'sms',
  WEBHOOK = 'webhook'
}

enum NotificationPriority {
  LOW = 0,
  NORMAL = 1,
  HIGH = 2,
  URGENT = 3
}

enum NotificationStatus {
  PENDING = 'pending',      // Created, not yet queued
  QUEUED = 'queued',        // In queue
  PROCESSING = 'processing', // Being processed
  SENT = 'sent',            // Successfully sent to provider
  DELIVERED = 'delivered',   // Confirmed delivered (if tracking available)
  FAILED = 'failed',        // Permanently failed
  CANCELLED = 'cancelled',   // User cancelled
  EXPIRED = 'expired'       // Expired before sending
}

interface NotificationRequest {
  id?: string;
  channel: ChannelType;
  recipient: Recipient;
  content: NotificationContent;
  priority: NotificationPriority;
  metadata?: Record<string, any>;
  scheduledFor?: Date;
  expiresAt?: Date;
  idempotencyKey?: string;
  callbackUrl?: string;
  retryPolicy?: RetryPolicy;
}

interface RetryPolicy {
  maxAttempts: number;
  backoffMultiplier: number;
  maxBackoffMs: number;
}

interface Recipient {
  userId?: string;
  email?: string;
  phone?: string;
  deviceTokens?: string[];
  locale?: string;
  timezone?: string;
  metadata?: Record<string, any>;
}

interface NotificationContent {
  // Email fields
  subject?: string;
  htmlBody?: string;
  textBody?: string;
  
  // Push fields
  title?: string;
  body: string;
  imageUrl?: string;
  clickAction?: string;
  
  // Common
  templateId?: string;
  variables?: Record<string, any>;
  attachments?: Attachment[];
}

interface NotificationResult {
  notificationId: string;
  status: NotificationStatus;
  enqueuedAt: Date;
  sentAt?: Date;
  error?: NotificationError;
  providerMessageId?: string;
  estimatedDeliveryAt?: Date;
}
```

### 5. Database Schema

```sql
-- Core notifications table (canonical record)
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(20) NOT NULL,
  recipient JSONB NOT NULL,
  content JSONB NOT NULL,
  priority SMALLINT NOT NULL,
  status VARCHAR(20) NOT NULL,
  
  idempotency_key VARCHAR(255),
  callback_url TEXT,
  metadata JSONB,
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  scheduled_for TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  
  sent_at TIMESTAMPTZ,
  delivered_at TIMESTAMPTZ,
  failed_at TIMESTAMPTZ,
  
  attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  last_error JSONB,
  
  provider_message_id VARCHAR(255),
  provider_response JSONB,
  processing_time_ms INTEGER,
  
  CONSTRAINT uq_idempotency UNIQUE (idempotency_key)
);

CREATE INDEX idx_notifications_status ON notifications(status, created_at DESC);
CREATE INDEX idx_notifications_scheduled ON notifications(scheduled_for) 
  WHERE status = 'pending' AND scheduled_for IS NOT NULL;
CREATE INDEX idx_notifications_expires ON notifications(expires_at) 
  WHERE status IN ('pending', 'queued') AND expires_at IS NOT NULL;

-- Separate queue table for high-throughput processing
CREATE TABLE notification_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  
  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  priority_order INTEGER NOT NULL, -- Computed from priority for sorting
  
  visible_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  
  worker_id VARCHAR(255),
  lease_expiry TIMESTAMPTZ,
  
  dequeue_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  last_error JSONB,
  last_dequeued_at TIMESTAMPTZ,
  
  version INTEGER NOT NULL DEFAULT 0, -- Optimistic locking
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Critical index for dequeue performance
CREATE INDEX idx_queue_processing ON notification_queue(
  priority_order ASC,
  visible_at ASC
) WHERE status = 'pending';

-- Index for stuck message cleanup
CREATE INDEX idx_queue_stuck ON notification_queue(lease_expiry, worker_id)
  WHERE status = 'processing' AND lease_expiry IS NOT NULL;

-- Dead letter queue
CREATE TABLE notification_dlq (
  id UUID PRIMARY KEY,
  notification_id UUID NOT NULL,
  original_request JSONB NOT NULL,
  final_error JSONB NOT NULL,
  attempt_count INTEGER NOT NULL,
  failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  requeued_at TIMESTAMPTZ,
  
  INDEX idx_dlq_failed_at (failed_at DESC)
);

-- Worker health tracking
CREATE TABLE worker_health (
  worker_id VARCHAR(255) PRIMARY KEY,
  last_heartbeat TIMESTAMPTZ NOT NULL,
  processing_count INTEGER NOT NULL DEFAULT 0,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  INDEX idx_worker_heartbeat (last_heartbeat DESC)
);

-- Audit trail
CREATE TABLE notification_events (
  id BIGSERIAL PRIMARY KEY,
  notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
  from_status VARCHAR(20),
  to_status VARCHAR(20),
  worker_id VARCHAR(255),
  error JSONB,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  INDEX idx_events_notification (notification_id, created_at DESC),
  INDEX idx_events_type (event_type, created_at DESC)
);

-- Provider rate limiting (distributed)
CREATE TABLE provider_rate_limits (
  provider_id VARCHAR(100) NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_type VARCHAR(10) NOT NULL, -- 'second', 'minute', 'hour'
  token_count INTEGER NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  PRIMARY KEY (provider_id, window_start, window_type)
);

CREATE INDEX idx_rate_limits_active ON provider_rate_limits(
  provider_id, window_type, window_start DESC
);

-- Device token management
CREATE TABLE device_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  token VARCHAR(500) NOT NULL,
  platform VARCHAR(20) NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  last_used_at TIMESTAMPTZ,
  invalidated_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  CONSTRAINT uq_device_token UNIQUE (token),
  INDEX idx_tokens_user_active (user_id, is_active) WHERE is_active = true
);

-- Template storage
CREATE TABLE notification_templates (
  id VARCHAR(100) NOT NULL,
  channel VARCHAR(20) NOT NULL,
  version INTEGER NOT NULL,
  name VARCHAR(255) NOT NULL,
  template_data JSONB NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  PRIMARY KEY (id, version),
  INDEX idx_templates_active (id, is_active, version DESC) WHERE is_active = true
);
```

### 6. Resilience Patterns

**Adaptive Circuit Breaker**
```typescript
class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failureCount = 0;
  private successCount = 0;
  private lastStateChange = Date.now();
  private halfOpenRequestsAllowed = 1; // Start with 1 test request
  private activeHalfOpenRequests = 0;
  
  constructor(
    private readonly config: {
      failureThreshold: number;
      openDurationMs: number;
      halfOpenSuccessThreshold: number;
      halfOpenMaxConcurrent: number;
    }
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    // Check if should transition to half-open
    if (this.state === 'open') {
      const timeSinceOpen = Date.now() - this.lastStateChange;
      if (timeSinceOpen >= this.config.openDurationMs) {
        this.transitionToHalfOpen();
      } else {
        throw new CircuitOpenError(
          `Circuit open, retry after ${this.config.openDurationMs - timeSinceOpen}ms`
        );
      }
    }
    
    // Limit concurrent half-open requests
    if (this.state === 'half_open') {
      if (this.activeHalfOpenRequests >= this.halfOpenRequestsAllowed) {
        throw new CircuitOpenError('Half-open circuit at capacity');
      }
      this.activeHalfOpenRequests++;
    }
    
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure(error);
      throw error;
    } finally {
      if (this.state === 'half_open') {
        this.activeHalfOpenRequests--;
      }
    }
  }
  
  private onSuccess(): void {
    if (this.state === 'half_open') {
      this.successCount++;
      
      if (this.successCount >= this.config.halfOpenSuccessThreshold) {
        this.transitionToClosed();
      } else {
        // Gradually increase allowed concurrent requests
        this.halfOpenRequestsAllowed = Math.min(
          this.halfOpenRequestsAllowed + 1,
          this.config.halfOpenMaxConcurrent
        );
      }
    } else if (this.state === 'closed') {
      this.failureCount = Math.max(0, this.failureCount - 1); // Decay failures
    }
  }
  
  private onFailure(error: any): void {
    if (this.state === 'half_open') {
      // Immediate reopen on any failure in half-open
      this.transitionToOpen();
    } else if (this.state === 'closed') {
      this.failureCount++;
      if (this.failureCount >= this.config.failureThreshold) {
        this.transitionToOpen();
      }
    }
  }
  
  private transitionToOpen(): void {
    this.state = 'open';
    this.lastStateChange = Date.now();
    this.successCount = 0;
    console.warn(`Circuit breaker opened after ${this.failureCount} failures`);
  }
  
  private transitionToHalfOpen(): void {
    this.state = 'half_open';
    this.lastStateChange = Date.now();
    this.successCount = 0;
    this.halfOpenRequestsAllowed = 1;
    this.activeHalfOpenRequests = 0;
    console.info('Circuit breaker entering half-open state');
  }
  
  private transitionToClosed(): void {
    this.state = 'closed';
    this.lastStateChange = Date.now();
    this.failureCount = 0;
    this.successCount = 0;
    console.info('Circuit breaker closed after successful recovery');
  }
}
```

**Token Bucket Rate Limiter**
```typescript
class DistributedRateLimiter {
  constructor(
    private db: Database,
    private providerId: string,
    private limits: {
      perSecond: number;
      perMinute: number;
      perHour?: number;
    }
  ) {}
  
  async acquire(): Promise<void> {
    const windows = [
      { type: 'second', limit: this.limits.perSecond, durationMs: 1000 },
      { type: 'minute', limit: this.limits.perMinute, durationMs: 60000 },
    ];
    
    if (this.limits.perHour) {
      windows.push({ type: 'hour', limit: this.limits.perHour, durationMs: 3600000 });
    }
    
    for (const window of windows) {
      const windowStart = new Date(
        Math.floor(Date.now() / window.durationMs) * window.durationMs
      );
      
      const result = await this.db.query(`
        INSERT INTO provider_rate_limits (provider_id, window_start, window_type, token_count)
        VALUES ($1, $2, $3, 1)
        ON CONFLICT (provider_id, window_start, window_type)
        DO UPDATE SET 
          token_count = provider_rate_limits.token_count + 1,
          updated_at = NOW()
        RETURNING token_count
      `, [this.providerId, windowStart, window.type]);
      
      const currentCount = result.rows[0].token_count;
      
      if (currentCount > window.limit) {
        const retryAfterMs = windowStart.getTime() + window.durationMs - Date.now();
        
        // Exponential backoff for rate limit
        await this.sleep(Math.min(retryAfterMs, 5000));
        
        throw new RateLimitError(
          `Rate limit exceeded for ${window.type} window`,
          retryAfterMs
        );
      }
    }
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

**Retry Handler with Jitter**
```typescript
class RetryHandler {
  shouldRetry(attempt: number, error: NotificationError): boolean {
    if (attempt >= 5) return false;
    if (error.category === ErrorCategory.VALIDATION) return false;
    if (error.category === ErrorCategory.PERMANENT) return false;
    return error.retryable;
  }
  
  calculateBackoff(attempt: number, error: NotificationError): number {
    const baseMs = 1000;
    const maxMs = 300000; // 5 minutes
    
    // Longer backoff for rate limits
    const multiplier = error.category === ErrorCategory.RATE_LIMIT ? 3 : 1;
    
    // Exponential backoff: base * 2^attempt * multiplier
    const exponential = baseMs * Math.pow(2, attempt) * multiplier;
    
    // Full jitter: random between 0 and exponential
    const withJitter = Math.random() * exponential;
    
    return Math.min(withJitter, maxMs);
  }
}
```

### 7. Webhook Delivery System

```typescript
class WebhookDeliveryService {
  private webhookQueue: Queue; // Separate queue for webhooks
  
  async enqueueWebhook(webhook: WebhookPayload): Promise<void> {
    // Non-blocking: fire and forget
    await this.webhookQueue.enqueue({
      url: webhook.url,
      payload: webhook.payload,
      maxAttempts: 3,
      timeoutMs: 5000,
    });
  }
  
  async deliverWebhook(webhook: WebhookJob): Promise<void> {
    try {
      const response = await fetch(webhook.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Notification-Event': webhook.payload.event,
          'X-Notification-ID': webhook.payload.notificationId,
          'X-Signature': this.signPayload(webhook.payload),
        },
        body: JSON.stringify(webhook.payload),
        signal: AbortSignal.timeout(webhook.timeoutMs),
      });
      
      if (!response.ok) {
        throw new Error(`Webhook returned ${response.status}`);
      }
      
      // Log success
      await this.logWebhookDelivery(webhook, 'success');
      
    } catch (error) {
      // Log failure but don't block notification
      await this.logWebhookDelivery(webhook, 'failed', error);
      
      // Retry with backoff
      if (webhook.attempt < webhook.maxAttempts) {
        await this.webhookQueue.requeueWithDelay(
          webhook.id,
          this.calculateBackoff(webhook.attempt)
        );
      }
    }
  }
  
  private signPayload(payload: any): string {
    // HMAC signature for webhook verification
    return crypto
      .createHmac('sha256', process.env.WEBHOOK_SECRET!)
      .update(JSON.stringify(payload))
      .digest('hex');
  }
}
```

### 8. Background Maintenance

```typescript
class MaintenanceService {
  async start(): Promise<void> {
    // Release stuck messages (every 60s)
    setInterval(() => this.releaseStuckMessages(), 60000);
    
    // Expire old notifications (every 5 min)
    setInterval(() => this.expireNotifications(), 300000);
    
    // Cleanup dead workers (every 5 min)
    setInterval(() => this.cleanupDeadWorkers(), 300000);
    
    // Archive old records (daily)
    setInterval(() => this.archiveOldRecords(), 86400000);
  }
  
  private async releaseStuckMessages(): Promise<void> {
    // Messages with expired leases
    await this.db.query(`
      UPDATE notification_queue
      SET 
        status = 'pending',
        worker_id = NULL,
        lease_expiry = NULL,
        visible_at = NOW() + interval '30 seconds'
      WHERE status = 'processing'
        AND lease_expiry < NOW()
    `);
  }
  
  private async expireNotifications(): Promise<void> {
    await this.db.transaction(async (tx) => {
      // Mark as expired
      await tx.query(`
        UPDATE notifications
        SET status = 'expired', updated_at = NOW()
        WHERE status IN ('pending', 'queued')
          AND expires_at <= NOW()
      `);
      
      // Remove from queue
      await tx.query(`
        DELETE FROM notification_queue
        WHERE notification_id IN (
          SELECT id FROM notifications WHERE status = 'expired'
        )
      `);
    });
  }
  
  private async cleanupDeadWorkers(): Promise<void> {
    const cutoff = new Date(Date.now() - 600000); // 10 min
    
    await this.db.query(`
      DELETE FROM worker_health
      WHERE last_heartbeat < $1
    `, [cutoff]);
  }
  
  private async archiveOldRecords(): Promise<void> {
    const archiveThreshold = new Date(Date.now() - 90 * 86400000); // 90 days
    
    await this.db.transaction(async (tx) => {
      // Archive to cold storage (S3, etc.)
      const oldRecords = await tx.query(`
        SELECT * FROM notifications
        WHERE created_at < $1
          AND status IN ('sent', 'delivered', 'failed', 'expired', 'cancelled')
      `, [archiveThreshold]);
      
      if (oldRecords.rows.length > 0) {
        await this.archiveToS3(oldRecords.rows);
        
        await tx.query(`
          DELETE FROM notifications
          WHERE created_at < $1
            AND status IN ('sent', 'delivered', 'failed', 'expired', 'cancelled')
        `, [archiveThreshold]);
      }
    });
  }
}
```

### 9. Monitoring & Observability

```typescript
interface NotificationMetrics {
  // Counters
  notificationsSent: Counter<{ channel: string; priority: string }>;
  notificationsFailed: Counter<{ channel: string; errorCategory: string }>;
  notificationsRetried: Counter<{ channel: string; attempt: number }>;
  webhooksDelivered: Counter<{ success: boolean }>;
  
  // Gauges
  queueDepth: Gauge<{ priority: string }>;
  activeWorkers: Gauge;
  circuitBreakerState: Gauge<{ provider: string }>; // 0=closed, 1=half-open, 2=open
  oldestQueuedMessage: Gauge; // Age in seconds
  
  // Histograms
  processingLatency: Histogram<{ channel: string }>; // End-to-end processing time
  providerLatency: Histogram<{ provider: string }>; // Provider API call time
  queueWaitTime: Histogram<{ priority: string }>; // Time in queue before processing
  
  // Business metrics
  deliveryRate: Gauge<{ channel: string }>; // Success rate over time window
  costPerNotification: Histogram<{ channel: string }>;
}

// Health check endpoint
app.get('/health', async (req, res) => {
  const checks = await Promise.all([
    checkDatabase(),
    checkQueue(),
    checkProviders(),
  ]);
  
  const healthy = checks.every(c => c.healthy);
  
  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'healthy' : 'unhealthy',
    checks,
    uptime: process.uptime(),
    memory: process.memoryUsage(),
  });
});

// Metrics endpoint (Prometheus format)
app.get('/metrics', async (req, res) => {
  res.set('Content-Type', register.contentType);
  res.send(await register.metrics());
});
```