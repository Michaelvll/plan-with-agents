# Claude Code Debate Session

**Started:** 2026-01-17T10:31:22.318020
**Ended:** 2026-01-17T10:42:01.178417
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a notification service with email and push notifications

---

## Round 1

### 🔵 Agent A

## Design

# Notification Service Architecture

## System Overview
A scalable, plugin-based notification service supporting email and push notifications with robust delivery guarantees, retry logic, and audit trails.

## Architecture Components

### 1. Core Components

**NotificationService (Orchestrator)**
```typescript
interface NotificationService {
  send(request: NotificationRequest): Promise<NotificationResult>;
  sendBatch(requests: NotificationRequest[]): Promise<NotificationResult[]>;
  getStatus(notificationId: string): Promise<NotificationStatus>;
  cancelScheduled(notificationId: string): Promise<void>;
}
```

**Channel Providers (Strategy Pattern)**
```typescript
interface ChannelProvider {
  readonly channelType: ChannelType;
  send(payload: ChannelPayload): Promise<SendResult>;
  validateRecipient(recipient: string): boolean;
  estimateCost(payload: ChannelPayload): number;
}

// Implementations
class EmailProvider implements ChannelProvider
class PushProvider implements ChannelProvider
```

**Queue Manager**
```typescript
interface QueueManager {
  enqueue(message: QueuedNotification): Promise<string>;
  dequeue(batchSize: number): Promise<QueuedNotification[]>;
  requeueWithBackoff(id: string, error: Error): Promise<void>;
  markComplete(id: string): Promise<void>;
}
```

**Retry Handler**
```typescript
interface RetryHandler {
  shouldRetry(attempt: number, error: Error): boolean;
  calculateBackoff(attempt: number): number; // milliseconds
  maxAttempts: number;
}
```

### 2. Data Models

```typescript
enum ChannelType {
  EMAIL = 'email',
  PUSH = 'push'
}

enum NotificationPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent'
}

enum NotificationStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  SENDING = 'sending',
  SENT = 'sent',
  DELIVERED = 'delivered',
  FAILED = 'failed',
  CANCELLED = 'cancelled'
}

interface NotificationRequest {
  id?: string; // Auto-generated if not provided
  channel: ChannelType;
  recipient: Recipient;
  content: NotificationContent;
  priority: NotificationPriority;
  metadata?: Record<string, any>;
  scheduledFor?: Date;
  expiresAt?: Date;
  idempotencyKey?: string;
}

interface Recipient {
  // Email channel
  email?: string;
  
  // Push channel
  deviceTokens?: string[];
  userId?: string; // To lookup device tokens
  
  // Personalization
  firstName?: string;
  lastName?: string;
  locale?: string;
  timezone?: string;
}

interface NotificationContent {
  // Email-specific
  subject?: string;
  htmlBody?: string;
  textBody?: string;
  attachments?: Attachment[];
  
  // Push-specific
  title?: string;
  body: string;
  icon?: string;
  badge?: number;
  sound?: string;
  data?: Record<string, any>;
  
  // Common
  templateId?: string;
  templateVariables?: Record<string, any>;
}

interface Attachment {
  filename: string;
  contentType: string;
  content: Buffer | string; // Base64 encoded
  size: number;
}

interface NotificationResult {
  notificationId: string;
  status: NotificationStatus;
  channel: ChannelType;
  sentAt?: Date;
  deliveredAt?: Date;
  error?: NotificationError;
  providerResponse?: any;
}

interface NotificationError {
  code: string;
  message: string;
  retryable: boolean;
  originalError?: any;
}
```

### 3. Database Schema

```sql
-- Main notification records
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(20) NOT NULL,
  recipient JSONB NOT NULL,
  content JSONB NOT NULL,
  priority VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL,
  metadata JSONB,
  scheduled_for TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE,
  idempotency_key VARCHAR(255) UNIQUE,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  sent_at TIMESTAMP WITH TIME ZONE,
  delivered_at TIMESTAMP WITH TIME ZONE,
  
  attempt_count INTEGER DEFAULT 0,
  last_error JSONB,
  provider_response JSONB,
  
  INDEX idx_status (status),
  INDEX idx_scheduled (scheduled_for) WHERE status = 'pending',
  INDEX idx_idempotency (idempotency_key)
);

-- Audit trail for state transitions
CREATE TABLE notification_events (
  id BIGSERIAL PRIMARY KEY,
  notification_id UUID NOT NULL REFERENCES notifications(id),
  event_type VARCHAR(50) NOT NULL,
  from_status VARCHAR(20),
  to_status VARCHAR(20),
  metadata JSONB,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  INDEX idx_notification (notification_id, created_at DESC)
);

-- User device tokens for push notifications
CREATE TABLE device_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  token VARCHAR(500) NOT NULL UNIQUE,
  platform VARCHAR(20) NOT NULL, -- 'ios', 'android', 'web'
  is_active BOOLEAN DEFAULT true,
  last_used_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  INDEX idx_user (user_id, is_active)
);

-- Template storage
CREATE TABLE notification_templates (
  id VARCHAR(100) PRIMARY KEY,
  channel VARCHAR(20) NOT NULL,
  name VARCHAR(255) NOT NULL,
  template_data JSONB NOT NULL,
  version INTEGER NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### 4. Service Workflow

```
┌─────────────────┐
│ Client Request  │
└────────┬────────┘
         │
         ▼
┌─────────────────────┐
│ NotificationService │
│  - Validate         │
│  - Check idempotency│
│  - Assign ID        │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Template Renderer  │ (if templateId provided)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│   Queue Manager     │
│  - Priority queue   │
│  - Schedule future  │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Worker Process     │
│  - Dequeue batch    │
│  - Route to channel │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Channel Provider   │
│  - EmailProvider    │
│  - PushProvider     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  External Service   │
│  - SendGrid/SES     │
│  - FCM/APNs         │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  Result Handler     │
│  - Update status    │
│  - Log event        │
│  - Retry on failure │
└─────────────────────┘
```

### 5. Error Handling Strategy

**Error Categories:**
```typescript
enum ErrorCategory {
  VALIDATION = 'validation',      // Invalid input, don't retry
  RATE_LIMIT = 'rate_limit',      // Retry with backoff
  TEMPORARY = 'temporary',         // Network issues, retry
  PERMANENT = 'permanent',         // Invalid recipient, don't retry
  PROVIDER = 'provider',           // External service issue
  INTERNAL = 'internal'            // Our system issue
}

class NotificationError extends Error {
  constructor(
    public category: ErrorCategory,
    public code: string,
    message: string,
    public retryable: boolean,
    public originalError?: Error
  ) {
    super(message);
  }
}
```

**Retry Policy:**
```typescript
class ExponentialBackoffRetry implements RetryHandler {
  maxAttempts = 5;
  baseDelay = 1000; // 1 second
  maxDelay = 300000; // 5 minutes
  
  shouldRetry(attempt: number, error: Error): boolean {
    if (attempt >= this.maxAttempts) return false;
    if (!(error instanceof NotificationError)) return false;
    return error.retryable;
  }
  
  calculateBackoff(attempt: number): number {
    const exponential = this.baseDelay * Math.pow(2, attempt);
    const jitter = Math.random() * 1000;
    return Math.min(exponential + jitter, this.maxDelay);
  }
}
```

**Circuit Breaker:**
```typescript
class ProviderCircuitBreaker {
  private failureCount = 0;
  private lastFailureTime?: Date;
  private state: 'closed' | 'open' | 'half-open' = 'closed';
  
  constructor(
    private threshold: number = 5,
    private timeout: number = 60000 // 1 minute
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime!.getTime() > this.timeout) {
        this.state = 'half-open';
      } else {
        throw new NotificationError(
          ErrorCategory.PROVIDER,
          'CIRCUIT_OPEN',
          'Provider circuit breaker is open',
          true
        );
      }
    }
    
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
  
  private onSuccess() {
    this.failureCount = 0;
    this.state = 'closed';
  }
  
  private onFailure() {
    this.failureCount++;
    this.lastFailureTime = new Date();
    if (this.failureCount >= this.threshold) {
      this.state = 'open';
    }
  }
}
```

### 6. Provider Implementations

**Email Provider (SendGrid Example):**
```typescript
class SendGridEmailProvider implements ChannelProvider {
  readonly channelType = ChannelType.EMAIL;
  private circuitBreaker: ProviderCircuitBreaker;
  
  constructor(private apiKey: string) {
    this.circuitBreaker = new ProviderCircuitBreaker();
  }
  
  async send(payload: ChannelPayload): Promise<SendResult> {
    return this.circuitBreaker.execute(async () => {
      const { recipient, content } = payload;
      
      if (!this.validateRecipient(recipient.email!)) {
        throw new NotificationError(
          ErrorCategory.VALIDATION,
          'INVALID_EMAIL',
          `Invalid email: ${recipient.email}`,
          false
        );
      }
      
      try {
        const response = await fetch('https://api.sendgrid.com/v3/mail/send', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.apiKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            personalizations: [{
              to: [{ email: recipient.email }],
              subject: content.subject
            }],
            from: { email: 'noreply@example.com' },
            content: [
              { type: 'text/plain', value: content.textBody || '' },
              { type: 'text/html', value: content.htmlBody || '' }
            ]
          })
        });
        
        if (response.status === 429) {
          throw new NotificationError(
            ErrorCategory.RATE_LIMIT,
            'RATE_LIMITED',
            'SendGrid rate limit exceeded',
            true
          );
        }
        
        if (!response.ok) {
          const error = await response.text();
          throw new NotificationError(
            ErrorCategory.PROVIDER,
            'PROVIDER_ERROR',
            `SendGrid error: ${error}`,
            response.status >= 500
          );
        }
        
        return {
          success: true,
          providerMessageId: response.headers.get('x-message-id'),
          timestamp: new Date()
        };
      } catch (error) {
        if (error instanceof NotificationError) throw error;
        
        throw new NotificationError(
          ErrorCategory.TEMPORARY,
          'NETWORK_ERROR',
          'Network error contacting SendGrid',
          true,
          error as Error
        );
      }
    });
  }
  
  validateRecipient(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
  }
  
  estimateCost(payload: ChannelPayload): number {
    return 0.001; // $0.001 per email
  }
}
```

**Push Provider (FCM Example):**
```typescript
class FCMPushProvider implements ChannelProvider {
  readonly channelType = ChannelType.PUSH;
  private circuitBreaker: ProviderCircuitBreaker;
  
  constructor(private serverKey: string) {
    this.circuitBreaker = new ProviderCircuitBreaker();
  }
  
  async send(payload: ChannelPayload): Promise<SendResult> {
    return this.circuitBreaker.execute(async () => {
      const { recipient, content } = payload;
      const tokens = recipient.deviceTokens || [];
      
      if (tokens.length === 0) {
        throw new NotificationError(
          ErrorCategory.VALIDATION,
          'NO_TOKENS',
          'No device tokens provided',
          false
        );
      }
      
      const message = {
        notification: {
          title: content.title,
          body: content.body,
          icon: content.icon,
          sound: content.sound
        },
        data: content.data,
        tokens: tokens
      };
      
      try {
        const response = await fetch('https://fcm.googleapis.com/v1/projects/PROJECT_ID/messages:send', {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.serverKey}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(message)
        });
        
        const result = await response.json();
        
        // Handle invalid tokens
        if (result.failure > 0) {
          // Mark invalid tokens for cleanup
          this.handleInvalidTokens(result.results, tokens);
        }
        
        return {
          success: result.success > 0,
          providerMessageId: result.multicast_id,
          timestamp: new Date(),
          metadata: {
            successCount: result.success,
            failureCount: result.failure
          }
        };
      } catch (error) {
        throw new NotificationError(
          ErrorCategory.TEMPORARY,
          'NETWORK_ERROR',
          'Network error contacting FCM',
          true,
          error as Error
        );
      }
    });
  }
  
  private async handleInvalidTokens(results: any[], tokens: string[]) {
    // Remove invalid tokens from database
    const invalidTokens = tokens.filter((token, i) => 
      results[i]?.error === 'InvalidRegistration'
    );
    // Mark as inactive in device_tokens table
  }
  
  validateRecipient(recipient: string): boolean {
    return recipient.length > 0;
  }
  
  estimateCost(payload: ChannelPayload): number {
    return 0; // FCM is free
  }
}
```

### 7. Configuration & Scalability

**Configuration:**
```typescript
interface NotificationConfig {
  providers: {
    email: {
      type: 'sendgrid' | 'ses' | 'smtp';
      apiKey: string;
      defaultFrom: string;
    };
    push: {
      type: 'fcm' | 'apns';
      credentials: any;
    };
  };
  queue: {
    type: 'redis' | 'sqs' | 'rabbitmq';
    connectionString: string;
    batchSize: number;
  };
  retry: {
    maxAttempts: number;
    baseDelay: number;
  };
  workers: {
    count: number;
    pollInterval: number;
  };
}
```

**Horizontal Scaling:**
- Multiple worker processes dequeue from shared queue
- Database-backed queue with row-level locking for concurrency
- Stateless workers can scale independently
- Rate limiting per provider to respect API limits

## Rationale

1. **Queue-based architecture**: Ensures reliability and allows for retry logic without blocking client requests
2. **Strategy pattern for channels**: Makes it easy to add new notification channels (SMS, Slack, etc.)
3. **Idempotency keys**: Prevents duplicate notifications if client retries
4. **Circuit breaker**: Protects against cascading failures when providers are down
5. **Exponential backoff**: Balances retry aggressiveness with resource usage
6. **Audit trail**: Every status change is logged for debugging and compliance
7. **Priority queue**: Critical notifications (password reset) processed before marketing emails
8. **Template support**: Separates content from code, enables non-technical content updates

## What I Changed

This is the initial design proposal.

## What I Kept

N/A - First iteration.

## Open Questions

1. Should we support webhook callbacks for delivery status?
2. Do we need multi-tenancy support (different API keys per tenant)?
3. Should batch sends be atomic or best-effort?
4. What's the data retention policy for notifications and events?

## Convergence Status

**ITERATING** - This is the first draft and needs critical review.

PROMPT_FOR_CRITIC:
Focus on scalability bottlenecks, edge cases in error handling, and potential race conditions in the queue management. Are there failure modes I haven't considered?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Notification Service Architecture

## System Overview
A scalable, plugin-based notification service supporting email and push notifications with robust delivery guarantees, distributed queue management, and comprehensive observability.

## Architecture Components

### 1. Core Components

**NotificationService (Orchestrator)**
```typescript
interface NotificationService {
  send(request: NotificationRequest): Promise<NotificationResult>;
  sendBatch(requests: NotificationRequest[]): Promise<BatchNotificationResult>;
  getStatus(notificationId: string): Promise<NotificationStatus>;
  cancelScheduled(notificationId: string): Promise<CancelResult>;
  retryFailed(notificationId: string): Promise<NotificationResult>;
}

interface BatchNotificationResult {
  results: NotificationResult[];
  successCount: number;
  failureCount: number;
  partialFailure: boolean;
}

interface CancelResult {
  notificationId: string;
  cancelled: boolean;
  reason?: string; // e.g., "already sent", "not found"
}
```

**Channel Providers (Strategy Pattern)**
```typescript
interface ChannelProvider {
  readonly channelType: ChannelType;
  readonly capabilities: ProviderCapabilities;
  send(payload: ChannelPayload): Promise<SendResult>;
  validateRecipient(recipient: Recipient): ValidationResult;
  estimateCost(payload: ChannelPayload): number;
  healthCheck(): Promise<HealthStatus>;
}

interface ProviderCapabilities {
  supportsBatch: boolean;
  maxBatchSize?: number;
  supportsScheduling: boolean;
  supportsDeliveryTracking: boolean;
  rateLimit: RateLimit;
}

interface RateLimit {
  requestsPerSecond: number;
  requestsPerMinute: number;
  requestsPerDay?: number;
}

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings?: string[];
}

interface HealthStatus {
  healthy: boolean;
  latency?: number;
  lastChecked: Date;
  details?: any;
}

// Implementations
class EmailProvider implements ChannelProvider
class PushProvider implements ChannelProvider
```

**Distributed Queue Manager**
```typescript
interface QueueManager {
  enqueue(message: QueuedNotification, priority: NotificationPriority): Promise<string>;
  enqueueBatch(messages: QueuedNotification[]): Promise<string[]>;
  dequeue(workerId: string, batchSize: number): Promise<QueuedNotification[]>;
  requeueWithBackoff(id: string, error: Error, attempt: number): Promise<void>;
  markComplete(id: string): Promise<void>;
  markFailed(id: string, error: Error): Promise<void>;
  extendLease(id: string, workerId: string, durationMs: number): Promise<boolean>;
  releaseStuckMessages(timeoutMs: number): Promise<number>;
}

interface QueuedNotification {
  id: string;
  notification: NotificationRequest;
  enqueuedAt: Date;
  visibleAt: Date; // For scheduled notifications or retry backoff
  leaseExpiry?: Date;
  workerId?: string;
  attempt: number;
}
```

**Retry Handler with Jitter**
```typescript
interface RetryHandler {
  shouldRetry(attempt: number, error: NotificationError): RetryDecision;
  calculateBackoff(attempt: number, error: NotificationError): number;
  maxAttempts: number;
}

interface RetryDecision {
  shouldRetry: boolean;
  reason: string;
  delayMs?: number;
}

class AdaptiveRetryHandler implements RetryHandler {
  maxAttempts = 5;
  baseDelay = 1000;
  maxDelay = 300000;
  
  shouldRetry(attempt: number, error: NotificationError): RetryDecision {
    if (attempt >= this.maxAttempts) {
      return { shouldRetry: false, reason: 'max_attempts_exceeded' };
    }
    
    if (!error.retryable) {
      return { shouldRetry: false, reason: 'non_retryable_error' };
    }
    
    // Don't retry validation errors
    if (error.category === ErrorCategory.VALIDATION) {
      return { shouldRetry: false, reason: 'validation_error' };
    }
    
    // Rate limits get longer backoff
    if (error.category === ErrorCategory.RATE_LIMIT) {
      return { 
        shouldRetry: true, 
        reason: 'rate_limit',
        delayMs: this.calculateBackoff(attempt, error)
      };
    }
    
    return { 
      shouldRetry: true, 
      reason: 'temporary_error',
      delayMs: this.calculateBackoff(attempt, error)
    };
  }
  
  calculateBackoff(attempt: number, error: NotificationError): number {
    let multiplier = 1;
    
    // Longer backoff for rate limits
    if (error.category === ErrorCategory.RATE_LIMIT) {
      multiplier = 3;
    }
    
    const exponential = this.baseDelay * Math.pow(2, attempt) * multiplier;
    const jitter = Math.random() * 1000; // Full jitter
    return Math.min(exponential + jitter, this.maxDelay);
  }
}
```

### 2. Data Models

```typescript
enum ChannelType {
  EMAIL = 'email',
  PUSH = 'push'
}

enum NotificationPriority {
  LOW = 'low',
  NORMAL = 'normal',
  HIGH = 'high',
  URGENT = 'urgent'
}

enum NotificationStatus {
  PENDING = 'pending',
  QUEUED = 'queued',
  PROCESSING = 'processing',
  SENT = 'sent',
  DELIVERED = 'delivered',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
  EXPIRED = 'expired'
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
  callbackUrl?: string; // Webhook for delivery status
  maxAttempts?: number; // Override default retry policy
}

interface Recipient {
  email?: string;
  deviceTokens?: string[];
  userId?: string;
  firstName?: string;
  lastName?: string;
  locale?: string;
  timezone?: string;
}

interface NotificationContent {
  subject?: string;
  htmlBody?: string;
  textBody?: string;
  attachments?: Attachment[];
  title?: string;
  body: string;
  icon?: string;
  badge?: number;
  sound?: string;
  data?: Record<string, any>;
  templateId?: string;
  templateVariables?: Record<string, any>;
}

interface Attachment {
  filename: string;
  contentType: string;
  content: Buffer | string;
  size: number;
}

interface NotificationResult {
  notificationId: string;
  status: NotificationStatus;
  channel: ChannelType;
  enqueuedAt: Date;
  sentAt?: Date;
  deliveredAt?: Date;
  failedAt?: Date;
  error?: NotificationError;
  providerResponse?: any;
  attemptCount: number;
}

interface NotificationError {
  code: string;
  message: string;
  category: ErrorCategory;
  retryable: boolean;
  originalError?: any;
}
```

### 3. Enhanced Database Schema

```sql
-- Main notification records with optimistic locking
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(20) NOT NULL,
  recipient JSONB NOT NULL,
  content JSONB NOT NULL,
  priority VARCHAR(20) NOT NULL,
  status VARCHAR(20) NOT NULL,
  metadata JSONB,
  scheduled_for TIMESTAMP WITH TIME ZONE,
  expires_at TIMESTAMP WITH TIME ZONE,
  idempotency_key VARCHAR(255) UNIQUE,
  callback_url TEXT,
  max_attempts INTEGER DEFAULT 5,
  
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  enqueued_at TIMESTAMP WITH TIME ZONE,
  sent_at TIMESTAMP WITH TIME ZONE,
  delivered_at TIMESTAMP WITH TIME ZONE,
  failed_at TIMESTAMP WITH TIME ZONE,
  
  attempt_count INTEGER DEFAULT 0,
  last_error JSONB,
  provider_response JSONB,
  
  -- For distributed queue management
  visible_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  lease_expiry TIMESTAMP WITH TIME ZONE,
  worker_id VARCHAR(100),
  version INTEGER DEFAULT 0, -- Optimistic locking
  
  INDEX idx_status (status),
  INDEX idx_priority_visible (priority DESC, visible_at) WHERE status = 'queued',
  INDEX idx_scheduled (scheduled_for) WHERE status = 'pending',
  INDEX idx_idempotency (idempotency_key) WHERE idempotency_key IS NOT NULL,
  INDEX idx_expires (expires_at) WHERE expires_at IS NOT NULL AND status NOT IN ('sent', 'delivered', 'failed', 'cancelled'),
  INDEX idx_stuck_leases (lease_expiry, worker_id) WHERE lease_expiry IS NOT NULL
);

-- Audit trail for state transitions
CREATE TABLE notification_events (
  id BIGSERIAL PRIMARY KEY,
  notification_id UUID NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
  event_type VARCHAR(50) NOT NULL,
  from_status VARCHAR(20),
  to_status VARCHAR(20),
  metadata JSONB,
  error JSONB,
  worker_id VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  INDEX idx_notification (notification_id, created_at DESC),
  INDEX idx_event_type_time (event_type, created_at DESC)
);

-- User device tokens for push notifications
CREATE TABLE device_tokens (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(255) NOT NULL,
  token VARCHAR(500) NOT NULL UNIQUE,
  platform VARCHAR(20) NOT NULL,
  is_active BOOLEAN DEFAULT true,
  last_used_at TIMESTAMP WITH TIME ZONE,
  invalid_since TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  INDEX idx_user_active (user_id, is_active) WHERE is_active = true,
  INDEX idx_cleanup (invalid_since) WHERE invalid_since IS NOT NULL
);

-- Template storage with versioning
CREATE TABLE notification_templates (
  id VARCHAR(100) NOT NULL,
  channel VARCHAR(20) NOT NULL,
  name VARCHAR(255) NOT NULL,
  template_data JSONB NOT NULL,
  version INTEGER NOT NULL,
  is_active BOOLEAN DEFAULT true,
  created_by VARCHAR(255),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  PRIMARY KEY (id, version),
  INDEX idx_active_templates (id, is_active, version DESC) WHERE is_active = true
);

-- Rate limiting tracking per provider
CREATE TABLE provider_rate_limits (
  provider_id VARCHAR(100) NOT NULL,
  window_start TIMESTAMP WITH TIME ZONE NOT NULL,
  window_type VARCHAR(20) NOT NULL, -- 'second', 'minute', 'hour', 'day'
  request_count INTEGER DEFAULT 0,
  last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  PRIMARY KEY (provider_id, window_start, window_type),
  INDEX idx_current_windows (provider_id, window_type, window_start DESC)
);

-- Dead letter queue for permanently failed notifications
CREATE TABLE notification_dlq (
  id UUID PRIMARY KEY,
  notification_id UUID NOT NULL,
  original_request JSONB NOT NULL,
  final_error JSONB NOT NULL,
  attempt_count INTEGER NOT NULL,
  failed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  
  INDEX idx_failed_time (failed_at DESC)
);
```

### 4. Enhanced Service Workflow

```
┌─────────────────┐
│ Client Request  │
└────────┬────────┘
         │
         ▼
┌──────────────────────────┐
│  NotificationService     │
│  - Validate input        │
│  - Check idempotency     │  ◄── Race condition: Use UPSERT with
│  - Assign ID             │      ON CONFLICT (idempotency_key)
│  - Check expiry          │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Template Renderer       │
│  - Fetch active version  │
│  - Compile variables     │
│  - Validate output       │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Priority Queue Manager  │
│  - Enqueue with priority │  ◄── Distributed: Use SELECT FOR UPDATE
│  - Schedule future sends │      SKIP LOCKED for dequeue
│  - Set visible_at        │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Worker Pool (N workers) │
│  - Dequeue batch         │  ◄── Lease-based processing with
│  - Acquire lease         │      lease_expiry and worker_id
│  - Update to PROCESSING  │
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Rate Limiter            │
│  - Check provider limits │  ◄── Token bucket per provider
│  - Delay if needed       │      to prevent API throttling
└────────┬─────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Channel Provider        │
│  - Circuit breaker check │  ◄── Per-provider circuit breaker
│  - Send via external API │      with health monitoring
│  - Handle provider errors│
└────────┬─────────────────┘
         │
         ├─────► Success
         │       │
         │       ▼
         │    ┌──────────────────────┐
         │    │  Success Handler     │
         │    │  - Mark SENT         │
         │    │  - Log event         │
         │    │  - Call webhook      │
         │    │  - Release lease     │
         │    └──────────────────────┘
         │
         └─────► Failure
                 │
                 ▼
              ┌──────────────────────┐
              │  Failure Handler     │
              │  - Classify error    │
              │  - Check retry policy│
              │  - Requeue w/ backoff│  ◄── Or move to DLQ
              │  - Update visible_at │      if max attempts
              │  - Release lease     │
              └──────────────────────┘

┌──────────────────────────┐
│  Background Jobs         │
│  - Expire old messages   │  ◄── Periodic cleanup
│  - Release stuck leases  │      every 60s
│  - Clean invalid tokens  │
│  - Archive to cold store │
└──────────────────────────┘
```

### 5. Comprehensive Error Handling

**Error Categories:**
```typescript
enum ErrorCategory {
  VALIDATION = 'validation',
  RATE_LIMIT = 'rate_limit',
  TEMPORARY = 'temporary',
  PERMANENT = 'permanent',
  PROVIDER = 'provider',
  INTERNAL = 'internal',
  TIMEOUT = 'timeout',
  AUTHENTICATION = 'authentication'
}

class NotificationError extends Error {
  constructor(
    public category: ErrorCategory,
    public code: string,
    message: string,
    public retryable: boolean,
    public originalError?: Error,
    public metadata?: Record<string, any>
  ) {
    super(message);
    this.name = 'NotificationError';
  }
}
```

**Enhanced Circuit Breaker with Half-Open Testing:**
```typescript
class ProviderCircuitBreaker {
  private failureCount = 0;
  private successCount = 0;
  private lastFailureTime?: Date;
  private lastSuccessTime?: Date;
  private state: 'closed' | 'open' | 'half-open' = 'closed';
  
  constructor(
    private threshold: number = 5,
    private timeout: number = 60000,
    private halfOpenSuccessThreshold: number = 2
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime!.getTime() > this.timeout) {
        this.state = 'half-open';
        this.successCount = 0;
      } else {
        throw new NotificationError(
          ErrorCategory.PROVIDER,
          'CIRCUIT_OPEN',
          `Provider circuit breaker is open until ${new Date(this.lastFailureTime!.getTime() + this.timeout).toISOString()}`,
          true,
          undefined,
          { reopensAt: new Date(this.lastFailureTime!.getTime() + this.timeout) }
        );
      }
    }
    
    // In half-open, limit concurrent requests
    if (this.state === 'half-open') {
      // Only allow one test request at a time
      // Implementation would use a semaphore/mutex here
    }
    
    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure(error);
      throw error;
    }
  }
  
  private onSuccess() {
    this.lastSuccessTime = new Date();
    
    if (this.state === 'half-open') {
      this.successCount++;
      if (this.successCount >= this.halfOpenSuccessThreshold) {
        this.state = 'closed';
        this.failureCount = 0;
      }
    } else {
      this.failureCount = 0;
      this.state = 'closed';
    }
  }
  
  private onFailure(error: any) {
    this.failureCount++;
    this.lastFailureTime = new Date();
    
    if (this.state === 'half-open') {
      // Immediately reopen circuit on half-open failure
      this.state = 'open';
    } else if (this.failureCount >= this.threshold) {
      this.state = 'open';
    }
  }
  
  getStatus(): { state: string; failureCount: number; lastFailure?: Date } {
    return {
      state: this.state,
      failureCount: this.failureCount,
      lastFailure: this.lastFailureTime
    };
  }
}
```

**Distributed Rate Limiter:**
```typescript
class DistributedRateLimiter {
  constructor(
    private db: Database,
    private providerId: string,
    private limits: RateLimit
  ) {}
  
  async checkAndAcquire(): Promise<{ allowed: boolean; retryAfter?: number }> {
    const now = new Date();
    const windows = [
      { type: 'second', limit: this.limits.requestsPerSecond, durationMs: 1000 },
      { type: 'minute', limit: this.limits.requestsPerMinute, durationMs: 60000 },
    ];
    
    if (this.limits.requestsPerDay) {
      windows.push({ 
        type: 'day', 
        limit: this.limits.requestsPerDay, 
        durationMs: 86400000 
      });
    }
    
    for (const window of windows) {
      const windowStart = new Date(Math.floor(now.getTime() / window.durationMs) * window.durationMs);
      
      // Atomic increment and check
      const result = await this.db.query(`
        INSERT INTO provider_rate_limits (provider_id, window_start, window_type, request_count)
        VALUES ($1, $2, $3, 1)
        ON CONFLICT (provider_id, window_start, window_type)
        DO UPDATE SET 
          request_count = provider_rate_limits.request_count + 1,
          last_updated = NOW()
        RETURNING request_count
      `, [this.providerId, windowStart, window.type]);
      
      const currentCount = result.rows[0].request_count;
      
      if (currentCount > window.limit) {
        const retryAfter = windowStart.getTime() + window.durationMs - now.getTime();
        return { allowed: false, retryAfter };
      }
    }
    
    return { allowed: true };
  }
}
```

### 6. Distributed Queue Implementation

```typescript
class PostgresQueueManager implements QueueManager {
  constructor(private db: Database) {}
  
  async enqueue(message: QueuedNotification, priority: NotificationPriority): Promise<string> {
    const result = await this.db.query(`
      UPDATE notifications
      SET 
        status = 'queued',
        enqueued_at = NOW(),
        visible_at = COALESCE(scheduled_for, NOW()),
        updated_at = NOW()
      WHERE id = $1
      RETURNING id
    `, [message.id]);
    
    return result.rows[0].id;
  }
  
  async dequeue(workerId: string, batchSize: number): Promise<QueuedNotification[]> {
    const leaseDuration = 300000; // 5 minutes
    const now = new Date();
    const leaseExpiry = new Date(now.getTime() + leaseDuration);
    
    // Use SELECT FOR UPDATE SKIP LOCKED for lock-free dequeue
    const result = await this.db.query(`
      UPDATE notifications
      SET 
        status = 'processing',
        worker_id = $1,
        lease_expiry = $2,
        updated_at = NOW(),
        version = version + 1
      WHERE id IN (
        SELECT id
        FROM notifications
        WHERE status = 'queued'
          AND visible_at <= NOW()
          AND (expires_at IS NULL OR expires_at > NOW())
        ORDER BY 
          CASE priority
            WHEN 'urgent' THEN 1
            WHEN 'high' THEN 2
            WHEN 'normal' THEN 3
            WHEN 'low' THEN 4
          END,
          visible_at ASC
        LIMIT $3
        FOR UPDATE SKIP LOCKED
      )
      RETURNING *
    `, [workerId, leaseExpiry, batchSize]);
    
    return result.rows.map(row => this.mapRowToQueuedNotification(row));
  }
  
  async extendLease(id: string, workerId: string, durationMs: number): Promise<boolean> {
    const newExpiry = new Date(Date.now() + durationMs);
    
    const result = await this.db.query(`
      UPDATE notifications
      SET 
        lease_expiry = $1,
        updated_at = NOW()
      WHERE id = $2 
        AND worker_id = $3
        AND status = 'processing'
        AND lease_expiry > NOW()
      RETURNING id
    `, [newExpiry, id, workerId]);
    
    return result.rowCount > 0;
  }
  
  async releaseStuckMessages(timeoutMs: number): Promise<number> {
    const cutoff = new Date(Date.now() - timeoutMs);
    
    const result = await this.db.query(`
      UPDATE notifications
      SET 
        status = 'queued',
        worker_id = NULL,
        lease_expiry = NULL,
        visible_at = NOW() + interval '30 seconds', -- Brief delay before retry
        updated_at = NOW()
      WHERE status = 'processing'
        AND lease_expiry < $1
      RETURNING id
    `, [cutoff]);
    
    return result.rowCount;
  }
  
  async requeueWithBackoff(id: string, error: Error, attempt: number): Promise<void> {
    const retryHandler = new AdaptiveRetryHandler();
    const notificationError = error instanceof NotificationError 
      ? error 
      : new NotificationError(ErrorCategory.INTERNAL, 'UNKNOWN', error.message, true, error);
    
    const decision = retryHandler.shouldRetry(attempt, notificationError);
    
    if (!decision.shouldRetry) {
      // Move to DLQ
      await this.moveToDLQ(id, notificationError, attempt);
      return;
    }
    
    const visibleAt = new Date(Date.now() + decision.delayMs!);
    
    await this.db.query(`
      UPDATE notifications
      SET 
        status = 'queued',
        worker_id = NULL,
        lease_expiry = NULL,
        visible_at = $1,
        attempt_count = $2,
        last_error = $3,
        updated_at = NOW()
      WHERE id = $4
    `, [visibleAt, attempt, JSON.stringify(notificationError), id]);
  }
  
  async markComplete(id: string): Promise<void> {
    await this.db.query(`
      UPDATE notifications
      SET 
        status = 'sent',
        sent_at = NOW(),
        worker_id = NULL,
        lease_expiry = NULL,
        updated_at = NOW()
      WHERE id = $1
    `, [id]);
  }
  
  async markFailed(id: string, error: Error): Promise<void> {
    await this.db.query(`
      UPDATE notifications
      SET 
        status = 'failed',
        failed_at = NOW(),
        worker_id = NULL,
        lease_expiry = NULL,
        last_error = $1,
        updated_at = NOW()
      WHERE id = $2
    `, [JSON.stringify(error), id]);
  }
  
  private async moveToDLQ(id: string, error: NotificationError, attempts: number): Promise<void> {
    await this.db.query(`
      WITH original AS (
        SELECT * FROM notifications WHERE id = $1
      )
      INSERT INTO notification_dlq (notification_id, original_request, final_error, attempt_count)
      SELECT 
        id,
        jsonb_build_object(
          'channel', channel,
          'recipient', recipient,
          'content', content,
          'priority', priority
        ),
        $2,
        $3
      FROM original
    `, [id, JSON.stringify(error), attempts]);
    
    await this.markFailed(id, error);
  }
  
  private mapRowToQueuedNotification(row: any): QueuedNotification {
    // Implementation details
    return {} as QueuedNotification;
  }
}
```

### 7. Background Maintenance Jobs

```typescript
class MaintenanceScheduler {
  constructor(
    private db: Database,
    private queueManager: QueueManager
  ) {}
  
  start() {
    // Release stuck messages every 60 seconds
    setInterval(() => this.releaseStuckLeases(), 60000);
    
    // Expire old notifications every 5 minutes
    setInterval(() => this.expireNotifications(), 300000);
    
    // Clean invalid device tokens daily
    setInterval(() => this.cleanInvalidTokens(), 86400000);
    
    // Archive old records weekly
    setInterval(() => this.archiveOldRecords(), 604800000);
  }
  
  private async releaseStuckLeases() {
    const released = await this.queueManager.releaseStuckMessages(600000); // 10 min timeout
    if (released > 0) {
      console.log(`Released ${released} stuck messages`);
    }
  }
  
  private async expireNotifications() {
    await this.db.query(`
      UPDATE notifications
      SET 
        status = 'expired',
        updated_at = NOW()
      WHERE status IN ('pending', 'queued')
        AND expires_at IS NOT NULL
        AND expires_at <= NOW()
    `);
  }
  
  private async cleanInvalidTokens() {
    await this.db.query(`
      DELETE FROM device_tokens
      WHERE invalid_since IS NOT NULL
        AND invalid_since < NOW() - interval '30 days'
    `);
  }
  
  private async archiveOldRecords() {
    // Move notifications older than 90 days to cold storage
    const archiveThreshold = new Date(Date.now() - 90 * 24 * 60 * 60 * 1000);
    
    await this.db.query(`
      INSERT INTO notifications_archive
      SELECT * FROM notifications
      WHERE created_at < $1
        AND status IN ('sent', 'delivered', 'failed', 'cancelled', 'expired')
    `, [archiveThreshold]);
    
    await this.db.query(`
      DELETE FROM notifications
      WHERE created_at < $1
        AND status IN ('sent', 'delivered', 'failed', 'cancelled', 'expired')
    `, [archiveThreshold]);
  }
}
```

### 8. Configuration & Deployment

```typescript
interface NotificationConfig {
  providers: {
    email: {
      type: 'sendgrid' | 'ses' | 'smtp';
      apiKey: string;
      defaultFrom: string;
      rateLimit: RateLimit;
    };
    push: {
      type: 'fcm' | 'apns';
      credentials: any;
      rateLimit: RateLimit;
    };
  };
  database: {
    connectionString: string;
    poolSize: number;
    maxRetries: number;
  };
  queue: {
    batchSize: number;
    pollIntervalMs: number;
    leaseTimeoutMs: number;
    visibilityTimeoutMs: number;
  };
  retry: {
    maxAttempts: number;
    baseDelayMs: number;
    maxDelayMs: number;
  };
  workers: {
    count: number;
    workerId: string; // Unique per instance
  };
  circuitBreaker: {
    failureThreshold: number;
    timeoutMs: number;
    halfOpenSuccessThreshold: number;
  };
  observability: {
    metricsEnabled: boolean;
    metricsPort: number;
    tracingEnabled: boolean;
  };
}
```

### 9. Observability & Monitoring

```typescript
interface NotificationMetrics {
  // Counters
  notificationsSent: Counter;
  notificationsFailed: Counter;
  notificationsRetried: Counter;
  
  // Gauges
  queueDepth: Gauge;
  activeWorkers: Gauge;
  circuitBreakerState: Gauge;
  
  // Histograms
  processingLatency: Histogram;
  providerLatency: Histogram;
  queueWaitTime: Histogram;
}

// Example Prometheus metrics
class PrometheusMetrics {
  private registry: Registry;
  
  constructor() {
    this.registry = new Registry();
    this.registerMetrics();
  }
  
  private registerMetrics() {
    new Counter({
      name: 'notifications_sent_total',
      help: 'Total notifications sent',
      labelNames: ['channel', 'priority', 'status'],
      registers: [this.registry]
    });
    
    new Histogram({
      name: 'notification_processing_duration_seconds',
      help: 'Time to process notification',
      labelNames: ['channel', 'status'],
      buckets: [0.1, 0.5, 1, 2, 5, 10],
      registers: [this.registry]
    });
    
    new Gauge({
      name: 'notification_queue_depth',
      help: 'Current queue depth by priority',
      labelNames: ['priority'],
      registers: [this.registry]
    });
  }
}
```

## What I Improved

### 1. **Race Condition Prevention**
- Added optimistic locking with `version` field to prevent double-processing
- Used `SELECT FOR UPDATE SKIP LOCKED` for lock-free queue operations
- Implemented lease-based processing with `lease_expiry` and `worker_id` to handle worker crashes
- Added `extendLease()` for long-running operations

### 2. **Distributed Queue Robustness**
- Added `visible_at` field for both scheduled notifications and retry backoff
- Implemented stuck message recovery with `releaseStuckMessages()`
- Added Dead Letter Queue (DLQ) for permanently failed notifications
- Proper priority queue ordering with efficient indexes

### 3. **Edge Cases Handled**
- **Expiration**: Added `EXPIRED` status and background job to expire old messages
- **Idempotency with race conditions**: Use `ON CONFLICT (idempotency_key) DO UPDATE` for atomic upsert
- **Invalid device tokens**: Track `invalid_since` and clean up periodically
- **Webhook failures**: Non-blocking callback execution (should be async/best-effort)
- **Batch partial failures**: Added `BatchNotificationResult` with `partialFailure` flag

### 4. **Enhanced Error Handling**
- Added `TIMEOUT` and `AUTHENTICATION` error categories
- Adaptive backoff based on error type (longer for rate limits)
- Half-open circuit breaker testing with success threshold before fully closing
- Circuit breaker exposes status for monitoring

### 5. **Scalability Improvements**
- Database-backed distributed rate limiter to prevent API throttling across workers
- Provider capability metadata for intelligent routing
- Health check interface for provider monitoring
- Archive old data to cold storage to keep hot tables small
- Separate indexes for active queries (`WHERE status = 'queued'`)

### 6. **Operational Excellence**
- Comprehensive maintenance jobs (stuck leases, expiration, cleanup, archival)
- Prometheus metrics integration with business and system metrics
- Retry decision includes reason for debugging
- Provider-specific rate limit tracking table
- Cascade delete on events for GDPR compliance

## What I Kept

- Queue-based architecture with strategy pattern for channels
- Exponential backoff with jitter
- Circuit breaker pattern per provider
- Template versioning system
- Priority queue implementation
- Idempotency key support
- Audit trail with events table
- Core data models and interfaces

## Remaining Concerns

### 1. **Database as Queue Trade-offs**
- PostgreSQL queue works well up to ~10K msgs/sec, but may need Redis/SQS beyond that
- Consider adding `notifications_queue` table separate from `notifications` for higher throughput
- Dead letter processing: Should there be automated retry or require manual intervention?

### 2. **Webhook Delivery Guarantees**
- Callback URLs should be called async with their own retry logic
- Should failed webhooks block notification completion? (Current design: no)
- Consider separate webhook delivery queue

### 3. **Multi-tenancy**
- Current design supports single API keys per provider
- For SaaS, need tenant-specific provider configs and rate limits
- Add `tenant_id` column and tenant-aware queries

### 4. **Provider Failover**
- No fallback provider if primary is down (e.g., SendGrid → SES)
- Could add provider priority list per channel type

### 5. **Cost Tracking**
- `estimateCost()` exists but not persisted or aggregated
- Should we track actual costs per notification for billing?

### 6. **Horizontal Scaling Considerations**
- Worker ID must be unique per instance (use hostname + PID or UUID)
- Connection pool sizing: `workers * poolSize` shouldn't exceed DB max connections
- Consider leader election for maintenance jobs (currently all workers would run them)

## Convergence Status

**ITERATING** - Added significant improvements but want architect's feedback on database scaling strategy and webhook semantics.

PROMPT_FOR_ARCHITECT:
Please review the distributed queue implementation with lease-based processing. Are there any race conditions I missed in the dequeue/requeue flow? Also, should webhook callbacks be blocking (current: non-blocking best-effort) and how should we handle scenarios where the database becomes the bottleneck (10K+ msgs/sec)? Consider whether we need a separate queue table or should migrate to Redis/SQS at scale.

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

### Why Hybrid Queue Architecture?
**PostgreSQL for < 5K msg/sec**: Simple, reliable, no additional infrastructure. Perfect for most use cases. The `pg_try_advisory_xact_lock` prevents phantom reads during dequeue.

**Redis for 5K-50K msg/sec**: When PostgreSQL becomes the bottleneck, Redis sorted sets provide microsecond latency with Lua scripts for atomic operations.

**SQS for > 50K msg/sec**: Fully managed, infinite scale, but adds network latency. Use when horizontal scaling is more important than latency.

### Why Separate Queue Table?
The `notification_queue` table isolates high-churn queue operations from the canonical `notifications` record. This prevents index bloat and allows efficient archival of old notifications without affecting queue performance.

### Why Lease-Based Processing?
Worker crashes are inevitable. Leases with expiry ensure messages are automatically recovered without manual intervention. The `lease_expiry` and `worker_id` columns enable precise ownership tracking.

### Why Advisory Locks in PostgreSQL?
`SELECT FOR UPDATE SKIP LOCKED` prevents lock contention but doesn't prevent the same row being returned to multiple transactions in edge cases (serialization anomalies). Advisory locks guarantee exactly-once dequeue.

### Webhook Design Decision
**Non-blocking, best-effort**: Webhooks are delivered asynchronously in a separate queue with retry logic. Failed webhooks don't block notification delivery because:
1. The notification provider has already accepted the message
2. Webhook endpoints are outside our control and may be unreliable
3. Users can query status via API if webhook fails

## What I Changed

### 1. **Fixed Dequeue Race Condition**
Added `pg_try_advisory_xact_lock` to prevent the subtle race where two workers can dequeue the same message under high concurrency (serialization anomalies). The previous design's `SELECT FOR UPDATE SKIP LOCKED` is necessary but not sufficient.

### 2. **Separated Queue Table from Notifications**
Created `notification_queue` as a separate high-churn table. This:
- Prevents bloat in the canonical `notifications` table
- Enables efficient cleanup (delete from queue, keep notification history)
- Improves index performance (smaller, more focused indexes)
- Allows queue-specific fields (lease_expiry, visible_at) without cluttering main record

### 3. **Clarified Webhook Semantics**
Made webhooks explicitly **non-blocking and best-effort** with a separate delivery queue. Previous design was ambiguous about whether webhook failures should block notification completion.

### 4. **Added Hybrid Queue Architecture**
Provided three queue implementations (Postgres, Redis, SQS) with clear scaling thresholds. This gives a migration path as load increases without rewriting the entire system.

### 5. **Simplified Worker Lifecycle**
Added explicit worker health tracking, heartbeat loop, and lease extension loop. This makes worker management observable and debuggable.

### 6. **Enhanced Circuit Breaker**
Improved half-open state to gradually increase allowed concurrent requests (starting with 1, growing to N) rather than immediately allowing full traffic. This prevents thundering herd on recovery.

### 7. **Removed Optimistic Locking Version**
The `version` field is redundant when using advisory locks for dequeue. Removed to simplify the design (YAGNI principle).

## What I Kept

- Priority queue with efficient indexing
- Exponential backoff with jitter
- Separate DLQ for permanent failures
- Distributed rate limiting with token bucket
- Circuit breaker per provider
- Template versioning system
- Device token management
- Comprehensive audit trail
- Maintenance jobs for cleanup/archival
- Prometheus metrics integration

## Open Questions

### 1. **Queue Migration Strategy**
When transitioning from Postgres → Redis → SQS, how do we handle in-flight messages? Options:
- **Drain old queue first** (simple but causes processing pause)
- **Dual-write to both queues** (complex but zero downtime)
- **Message forwarding** (old queue forwards to new queue during transition)

### 2. **Provider Failover**
Should we support automatic failover between providers (e.g., SendGrid → AWS SES)? This adds complexity:
- Need provider priority/preference configuration
- Cost implications (backup provider may be more expensive)
- Different providers have different capabilities (templates, tracking, etc.)
- Recipient's provider preference may matter (deliverability)

### 3. **Multi-Tenancy**
For SaaS use cases:
- Should tenants provide their own API keys (better security, cost attribution)?
- Or use shared provider pool (simpler but commingled rate limits)?
- Need `tenant_id` throughout schema if supporting multi-tenancy

### 4. **Delivery Tracking**
Some providers (FCM, SES) support delivery webhooks. Should we:
- Update `status` from `sent` to `delivered` when webhook received?
- Store delivery latency for SLA monitoring?
- Retry on delivery failure vs. send failure?

### 5. **Cost Attribution**
The `estimateCost()` method exists but costs aren't persisted. For billing/attribution:
- Add `estimated_cost` and `actual_cost` columns?
- Aggregate by tenant/user/channel for billing?
- Track provider pricing changes over time?

## Convergence Status

**ITERATING** - Core architecture is solid but need feedback on queue migration strategy and multi-tenancy approach before finalizing.

PROMPT_FOR_CRITIC:
Focus on the **dequeue race condition fix** with advisory locks - does this actually prevent all race conditions in high-concurrency scenarios? Also, critique the **queue migration strategy** from Postgres → Redis → SQS: is dual-write viable, or should we mandate drain-first? Finally, challenge the **webhook semantics** - is best-effort acceptable, or should webhook failures retry indefinitely with exponential backoff?

**Convergence Signal:** ITERATING

### 🟣 Agent B

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

### 2. Hybrid Queue Architecture with Safe Migration

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
  
  // Migration support
  migrateMessage?(message: QueueMessage, targetQueue: QueueAdapter): Promise<void>;
  isDraining?(): boolean;
}

interface EnqueueOptions {
  priority: NotificationPriority;
  visibilityDelay: number;
  deduplicationId?: string;
  skipIfDraining?: boolean; // For migration: route to new queue if true
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
  sourceQueue?: string; // Track which queue implementation owns this message
}

// Implementations for different scales
class PostgresQueueAdapter implements QueueAdapter // < 5K msg/sec
class RedisQueueAdapter implements QueueAdapter    // 5K-50K msg/sec
class SQSQueueAdapter implements QueueAdapter      // > 50K msg/sec
```

**Critical Fix: PostgreSQL Queue with Advisory Locks + Row Versioning**
```typescript
class PostgresQueueAdapter implements QueueAdapter {
  private draining = false;
  private targetQueue?: QueueAdapter;
  
  async dequeue(workerId: string, count: number): Promise<QueueMessage[]> {
    const leaseMs = 300000; // 5 minutes
    
    // CRITICAL: Combine advisory locks + CTE + optimistic locking
    const result = await this.db.query(`
      WITH selected AS (
        SELECT 
          id,
          version,
          hashtext(id::text) as lock_id
        FROM notification_queue
        WHERE status = 'pending'
          AND visible_at <= NOW()
          AND (expires_at IS NULL OR expires_at > NOW())
          AND pg_try_advisory_xact_lock(hashtext(id::text))
        ORDER BY 
          priority_order ASC,
          visible_at ASC
        LIMIT $1
        FOR UPDATE SKIP LOCKED  -- Double protection against phantom reads
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
        AND nq.version = selected.version  -- Optimistic lock check
      RETURNING nq.*
    `, [count, workerId, leaseMs]);
    
    // Advisory locks auto-release at transaction end
    return result.rows.map(this.mapToQueueMessage);
  }
  
  async ack(messageId: string, workerId: string): Promise<void> {
    const result = await this.db.transaction(async (tx) => {
      // Move to notifications table and delete from queue atomically
      const result = await tx.query(`
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
          processing_time_ms = EXTRACT(EPOCH FROM (NOW() - deleted.last_dequeued_at)) * 1000,
          source_queue = deleted.source_queue
        FROM deleted
        WHERE notifications.id = deleted.notification_id
        RETURNING notifications.id
      `, [messageId, workerId]);
      
      return result;
    });
    
    if (result.rowCount === 0) {
      throw new Error(`Cannot ack message ${messageId}: not owned by worker ${workerId}`);
    }
  }
  
  async nack(messageId: string, workerId: string, reason: string): Promise<void> {
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
          ELSE NOW() + (power(2, LEAST(dequeue_count, 8)) * interval '1 second') -- Cap at 256s
        END,
        version = version + 1
      WHERE id = $1 
        AND worker_id = $2
        AND status = 'processing'
    `, [messageId, workerId, JSON.stringify({ reason, timestamp: new Date() })]);
  }
  
  // Migration support
  enableDraining(targetQueue: QueueAdapter): void {
    this.draining = true;
    this.targetQueue = targetQueue;
  }
  
  isDraining(): boolean {
    return this.draining;
  }
  
  async enqueue(message: QueueMessage, options: EnqueueOptions): Promise<string> {
    // If draining, route new messages to target queue
    if (this.draining && options.skipIfDraining && this.targetQueue) {
      return this.targetQueue.enqueue(message, options);
    }
    
    // Otherwise, enqueue normally
    const priority = this.getPriorityOrder(options.priority);
    
    const result = await this.db.query(`
      INSERT INTO notification_queue (
        id,
        notification_id,
        priority_order,
        visible_at,
        expires_at,
        max_attempts,
        source_queue
      ) VALUES ($1, $2, $3, $4, $5, 5, 'postgres')
      ON CONFLICT (id) DO NOTHING
      RETURNING id
    `, [
      message.id,
      message.notificationId,
      priority,
      new Date(Date.now() + options.visibilityDelay),
      message.payload.expiresAt,
    ]);
    
    return result.rows[0]?.id || message.id;
  }
}
```

**Queue Migration Orchestrator**
```typescript
class QueueMigrationOrchestrator {
  constructor(
    private sourceQueue: QueueAdapter,
    private targetQueue: QueueAdapter,
    private db: Database
  ) {}
  
  async migrate(strategy: 'drain-first' | 'live-forward'): Promise<void> {
    if (strategy === 'drain-first') {
      await this.drainFirstMigration();
    } else {
      await this.liveForwardMigration();
    }
  }
  
  private async drainFirstMigration(): Promise<void> {
    console.log('Starting drain-first migration...');
    
    // Step 1: Stop accepting new messages to source queue
    if (this.sourceQueue.enableDraining) {
      this.sourceQueue.enableDraining(this.targetQueue);
    }
    
    // Step 2: Wait for source queue to drain (with timeout)
    const maxWaitMs = 3600000; // 1 hour
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitMs) {
      const depth = await this.sourceQueue.getDepth();
      console.log(`Source queue depth: ${depth}`);
      
      if (depth === 0) {
        console.log('Source queue drained successfully');
        break;
      }
      
      await this.sleep(5000); // Check every 5s
    }
    
    // Step 3: Switch all workers to target queue
    await this.db.query(`
      UPDATE worker_config
      SET queue_implementation = $1
    `, [this.getQueueType(this.targetQueue)]);
    
    // Step 4: Verify no stuck messages
    const stuckCount = await this.checkStuckMessages();
    if (stuckCount > 0) {
      throw new Error(`Migration aborted: ${stuckCount} stuck messages in source queue`);
    }
    
    console.log('Migration complete');
  }
  
  private async liveForwardMigration(): Promise<void> {
    console.log('Starting live-forward migration...');
    
    // Step 1: Enable forwarding mode (new messages go to target)
    if (this.sourceQueue.enableDraining) {
      this.sourceQueue.enableDraining(this.targetQueue);
    }
    
    // Step 2: Spawn dedicated drain workers for source queue
    const drainWorkerCount = 5;
    const drainWorkers = Array.from({ length: drainWorkerCount }, (_, i) =>
      this.spawnDrainWorker(`drain-worker-${i}`)
    );
    
    // Step 3: Monitor drain progress
    const progressInterval = setInterval(async () => {
      const depth = await this.sourceQueue.getDepth();
      console.log(`Source queue remaining: ${depth}`);
    }, 10000);
    
    // Step 4: Wait for all drain workers to finish
    await Promise.all(drainWorkers);
    clearInterval(progressInterval);
    
    // Step 5: Switch all workers to target queue
    await this.db.query(`
      UPDATE worker_config
      SET queue_implementation = $1
    `, [this.getQueueType(this.targetQueue)]);
    
    console.log('Live-forward migration complete');
  }
  
  private async spawnDrainWorker(workerId: string): Promise<void> {
    while (true) {
      const messages = await this.sourceQueue.dequeue(workerId, 10);
      
      if (messages.length === 0) {
        console.log(`${workerId} finished draining`);
        break;
      }
      
      // Process normally (will be acked from source queue)
      for (const msg of messages) {
        try {
          await this.processMessage(msg);
          await this.sourceQueue.ack(msg.id, workerId);
        } catch (error) {
          await this.sourceQueue.nack(msg.id, workerId, error.message);
        }
      }
    }
  }
  
  private async checkStuckMessages(): Promise<number> {
    const result = await this.db.query(`
      SELECT COUNT(*)
      FROM notification_queue
      WHERE status = 'processing'
        AND lease_expiry < NOW()
    `);
    
    return parseInt(result.rows[0].count);
  }
  
  private getQueueType(queue: QueueAdapter): string {
    if (queue instanceof PostgresQueueAdapter) return 'postgres';
    if (queue instanceof RedisQueueAdapter) return 'redis';
    if (queue instanceof SQSQueueAdapter) return 'sqs';
    throw new Error('Unknown queue type');
  }
  
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  private async processMessage(msg: QueueMessage): Promise<void> {
    // Delegate to actual worker implementation
    // This is a stub for migration purposes
    throw new Error('Must be implemented by actual worker');
  }
}
```

**Redis Queue (for high scale)**
```typescript
class RedisQueueAdapter implements QueueAdapter {
  async enqueue(message: QueueMessage, options: EnqueueOptions): Promise<string> {
    const priority = this.getPriorityMultiplier(options.priority);
    const score = priority * 1e12 + options.visibilityDelay + Date.now();
    
    const pipeline = this.redis.pipeline();
    
    pipeline.hset(`msg:${message.id}`, {
      payload: JSON.stringify(message.payload),
      notificationId: message.notificationId,
      enqueuedAt: message.enqueuedAt.toISOString(),
      dequeueCount: 0,
      maxAttempts: 5,
      sourceQueue: 'redis',
    });
    
    pipeline.zadd('notification_queue', score, message.id);
    
    // Deduplication with atomic check
    if (options.deduplicationId) {
      const dedupKey = `dedup:${options.deduplicationId}`;
      pipeline.set(dedupKey, message.id, 'EX', 3600, 'NX');
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
      
      local ids = redis.call('ZRANGEBYSCORE', queue_key, 0, now, 'LIMIT', 0, count)
      
      if #ids == 0 then
        return {}
      end
      
      local messages = {}
      for _, id in ipairs(ids) do
        redis.call('ZREM', queue_key, id)
        redis.call('ZADD', processing_key, now + lease_ms, id)
        
        redis.call('HMSET', 'msg:' .. id, 
          'workerId', worker_id,
          'leaseExpiry', now + lease_ms
        )
        
        local dequeue_count = redis.call('HINCRBY', 'msg:' .. id, 'dequeueCount', 1)
        redis.call('HSET', 'msg:' .. id, 'dequeueCount', dequeue_count)
        
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
  private processingMessages = new Map<string, QueueMessage>(); // Track for lease extension
  
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
    
    // Track for lease extension
    this.processingMessages.set(message.id, message);
    
    try {
      trackingSpan = this.tracer.startSpan('process_notification', {
        attributes: {
          notificationId: message.notificationId,
          channel: message.payload.channel,
          priority: message.payload.priority,
        }
      });
      
      const provider = this.providers.get(message.payload.channel);
      if (!provider) {
        throw new NotificationError(
          ErrorCategory.INTERNAL,
          'NO_PROVIDER',
          `No provider for channel ${message.payload.channel}`,
          false
        );
      }
      
      const rateLimiter = this.rateLimiters.get(provider.type);
      await rateLimiter.acquire();
      
      const circuitBreaker = this.circuitBreakers.get(provider.type);
      
      const result = await circuitBreaker.execute(() =>
        provider.send(this.buildChannelMessage(message.payload))
      );
      
      await this.db.query(`
        UPDATE notifications
        SET 
          provider_message_id = $1,
          provider_response = $2
        WHERE id = $3
      `, [result.providerMessageId, result.metadata, message.notificationId]);
      
      await this.queue.ack(message.id, this.workerId);
      
      // Fire webhook asynchronously (non-blocking)
      if (message.payload.callbackUrl) {
        this.fireWebhookAsync(message.payload.callbackUrl, {
          notificationId: message.notificationId,
          status: 'sent',
          sentAt: new Date(),
        }).catch(err => {
          console.error('Webhook delivery failed:', err);
        });
      }
      
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
      
      const shouldRetry = this.shouldRetry(message.dequeueCount, notifError);
      
      if (shouldRetry) {
        await this.queue.nack(message.id, this.workerId, notifError.message);
        
        this.metrics.notificationsRetried.inc({
          channel: message.payload.channel,
          errorCategory: notifError.category,
        });
      } else {
        await this.moveToDLQ(message, notifError);
        await this.queue.ack(message.id, this.workerId);
        
        this.metrics.notificationsFailed.inc({
          channel: message.payload.channel,
          errorCategory: notifError.category,
        });
      }
      
    } finally {
      trackingSpan?.end();
      this.processingMessages.delete(message.id);
    }
  }
  
  private async leaseExtensionLoop(): Promise<void> {
    while (this.running) {
      await this.sleep(60000); // Every minute
      
      const now = Date.now();
      
      for (const [msgId, msg] of this.processingMessages.entries()) {
        if (!msg.leaseExpiry) continue;
        
        const timeLeft = msg.leaseExpiry.getTime() - now;
        
        // Extend if less than 2 minutes remaining
        if (timeLeft < 120000 && timeLeft > 0) {
          try {
            await this.queue.extendVisibility(msgId, this.workerId, 300000);
            // Update local tracking
            msg.leaseExpiry = new Date(now + 300000);
          } catch (error) {
            console.error(`Failed to extend lease for ${msgId}:`, error);
          }
        }
      }
    }
  }
  
  private async heartbeatLoop(): Promise<void> {
    while (this.running) {
      await this.db.query(`
        INSERT INTO worker_health (worker_id, last_heartbeat, processing_count)
        VALUES ($1, NOW(), $2)
        ON CONFLICT (worker_id) 
        DO UPDATE SET 
          last_heartbeat = NOW(),
          processing_count = $2
      `, [this.workerId, this.processingMessages.size]);
      
      await this.sleep(30000); // Every 30 seconds
    }
  }
}
```

### 4. Configurable Webhook Delivery System

```typescript
enum WebhookRetryPolicy {
  BEST_EFFORT = 'best_effort',         // 3 retries over 5 minutes
  AGGRESSIVE = 'aggressive',           // 10 retries over 24 hours
  PERSISTENT = 'persistent',           // Retry indefinitely with exponential backoff (max 1 week intervals)
}

interface WebhookConfig {
  url: string;
  retryPolicy: WebhookRetryPolicy;
  timeoutMs: number;
  maxRetries?: number;  // Override policy default
  authHeader?: string;  // Custom auth
}

class WebhookDeliveryService {
  private webhookQueue: Queue;
  
  async enqueueWebhook(webhook: WebhookPayload, config: WebhookConfig): Promise<void> {
    const policyConfig = this.getPolicyConfig(config.retryPolicy);
    
    await this.webhookQueue.enqueue({
      url: config.url,
      payload: webhook.payload,
      maxAttempts: config.maxRetries ?? policyConfig.maxAttempts,
      timeoutMs: config.timeoutMs,
      retryPolicy: config.retryPolicy,
      authHeader: config.authHeader,
      backoffConfig: policyConfig.backoff,
    });
  }
  
  private getPolicyConfig(policy: WebhookRetryPolicy) {
    switch (policy) {
      case WebhookRetryPolicy.BEST_EFFORT:
        return {
          maxAttempts: 3,
          backoff: { base: 30000, max: 120000, multiplier: 2 }, // 30s, 60s, 120s
        };
      case WebhookRetryPolicy.AGGRESSIVE:
        return {
          maxAttempts: 10,
          backoff: { base: 60000, max: 3600000, multiplier: 2 }, // Up to 1 hour intervals
        };
      case WebhookRetryPolicy.PERSISTENT:
        return {
          maxAttempts: Number.MAX_SAFE_INTEGER, // Effectively infinite
          backoff: { base: 60000, max: 604800000, multiplier: 2 }, // Up to 1 week intervals
        };
    }
  }
  
  async deliverWebhook(webhook: WebhookJob): Promise<void> {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), webhook.timeoutMs);
      
      const response = await fetch(webhook.url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Notification-Event': webhook.payload.event,
          'X-Notification-ID': webhook.payload.notificationId,
          'X-Signature': this.signPayload(webhook.payload),
          'X-Attempt': webhook.attempt.toString(),
          ...(webhook.authHeader && { 'Authorization': webhook.authHeader }),
        },
        body: JSON.stringify(webhook.payload),
        signal: controller.signal,
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) {
        throw new Error(`Webhook returned ${response.status}: ${await response.text()}`);
      }
      
      await this.logWebhookDelivery(webhook, 'success', { 
        statusCode: response.status,
        latencyMs: Date.now() - webhook.startTime 
      });
      
    } catch (error) {
      await this.logWebhookDelivery(webhook, 'failed', { error: error.message });
      
      // Calculate backoff
      const backoffMs = this.calculateBackoff(
        webhook.attempt,
        webhook.backoffConfig
      );
      
      // Determine if should retry
      const shouldRetry = 
        webhook.attempt < webhook.maxAttempts &&
        this.isRetryableError(error);
      
      if (shouldRetry) {
        await this.webhookQueue.requeueWithDelay(webhook.id, backoffMs);
      } else {
        // Move to webhook DLQ after exhausting retries
        await this.moveWebhookToDLQ(webhook, error);
        
        // Update notification record with webhook failure
        await this.db.query(`
          UPDATE notifications
          SET webhook_failed = true, webhook_failure_reason = $1
          WHERE id = $2
        `, [error.message, webhook.payload.notificationId]);
      }
    }
  }
  
  private calculateBackoff(attempt: number, config: BackoffConfig): number {
    const exponential = config.base * Math.pow(config.multiplier, attempt - 1);
    const withJitter = exponential * (0.5 + Math.random() * 0.5); // 50-100% jitter
    return Math.min(withJitter, config.max);
  }
  
  private isRetryableError(error: any): boolean {
    // Network errors, timeouts, and 5xx are retryable
    // 4xx (except 429) are not retryable
    if (error.name === 'AbortError') return true; // Timeout
    if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') return true;
    
    const statusCode = error.response?.status;
    if (statusCode) {
      if (statusCode === 429) return true; // Rate limit
      if (statusCode >= 500) return true;  // Server error
      return false; // Client error (4xx)
    }
    
    return true; // Unknown errors are retryable
  }
  
  private signPayload(payload: any): string {
    return crypto
      .createHmac('sha256', process.env.WEBHOOK_SECRET!)
      .update(JSON.stringify(payload))
      .digest('hex');
  }
}
```

### 5. Enhanced Circuit Breaker with Gradual Recovery

```typescript
class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failureCount = 0;
  private successCount = 0;
  private lastStateChange = Date.now();
  private halfOpenRequestsAllowed = 1;
  private activeHalfOpenRequests = 0;
  private lastErrors: Array<{ time: number; error: any }> = [];
  
  constructor(
    private readonly config: {
      failureThreshold: number;
      failureRateThreshold: number; // Percentage (0-100)
      windowMs: number; // Time window for calculating failure rate
      openDurationMs: number;
      halfOpenSuccessThreshold: number;
      halfOpenMaxConcurrent: number;
    }
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
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
    this.cleanupOldErrors();
    
    if (this.state === 'half_open') {
      this.successCount++;
      
      if (this.successCount >= this.config.halfOpenSuccessThreshold) {
        this.transitionToClosed();
      } else {
        // Gradually increase allowed concurrent requests (multiplicative increase)
        this.halfOpenRequestsAllowed = Math.min(
          Math.ceil(this.halfOpenRequestsAllowed * 1.5),
          this.config.halfOpenMaxConcurrent
        );
      }
    } else if (this.state === 'closed') {
      // Decay failure count on success (graceful forgiveness)
      this.failureCount = Math.max(0, this.failureCount - 1);
    }
  }
  
  private onFailure(error: any): void {
    const now = Date.now();
    this.lastErrors.push({ time: now, error });
    this.cleanupOldErrors();
    
    if (this.state === 'half_open') {
      // Immediate reopen on any failure in half-open (conservative)
      this.transitionToOpen();
    } else if (this.state === 'closed') {
      this.failureCount++;
      
      // Check both absolute count and failure rate thresholds
      const failureRate = this.calculateFailureRate();
      
      const shouldOpen = 
        this.failureCount >= this.config.failureThreshold ||
        failureRate >= this.config.failureRateThreshold;
      
      if (shouldOpen) {
        this.transitionToOpen();
      }
    }
  }
  
  private calculateFailureRate(): number {
    if (this.lastErrors.length === 0) return 0;
    
    const totalRequests = this.failureCount + this.successCount;
    if (totalRequests === 0) return 0;
    
    return (this.lastErrors.length / totalRequests) * 100;
  }
  
  private cleanupOldErrors(): void {
    const cutoff = Date.now() - this.config.windowMs;
    this.lastErrors = this.lastErrors.filter(e => e.time > cutoff);
  }
  
  private transitionToOpen(): void {
    this.state = 'open';
    this.lastStateChange = Date.now();
    this.successCount = 0;
    console.warn(`Circuit breaker opened: ${this.failureCount} failures, ${this.calculateFailureRate().toFixed(1)}% failure rate`);
  }
  
  private transitionToHalfOpen(): void {
    this.state = 'half_open';
    this.lastStateChange = Date.now();
    this.successCount = 0;
    this.halfOpenRequestsAllowed = 1; // Start conservative
    this.activeHalfOpenRequests = 0;
    console.info('Circuit breaker entering half-open state');
  }
  
  private transitionToClosed(): void {
    this.state = 'closed';
    this.lastStateChange = Date.now();
    this.failureCount = 0;
    this.successCount = 0;
    this.lastErrors = [];
    console.info('Circuit breaker closed after successful recovery');
  }
}
```

### 6. Database Schema

```sql
-- Core notifications table
CREATE TABLE notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  channel VARCHAR(20) NOT NULL,
  recipient JSONB NOT NULL,
  content JSONB NOT NULL,
  priority SMALLINT NOT NULL,
  status VARCHAR(20) NOT NULL,
  
  idempotency_key VARCHAR(255),
  callback_url TEXT,
  webhook_retry_policy VARCHAR(20) DEFAULT 'best_effort',
  webhook_failed BOOLEAN DEFAULT false,
  webhook_failure_reason TEXT,
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
  source_queue VARCHAR(20), -- Track which queue processed this
  
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
  priority_order INTEGER NOT NULL,
  
  visible_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMPTZ,
  
  worker_id VARCHAR(255),
  lease_expiry TIMESTAMPTZ,
  
  dequeue_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 5,
  last_error JSONB,
  last_dequeued_at TIMESTAMPTZ,
  
  source_queue VARCHAR(20) NOT NULL, -- 'postgres', 'redis', 'sqs'
  
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_queue_processing ON notification_queue(
  priority_order ASC,
  visible_at ASC
) WHERE status = 'pending';

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
  source_queue VARCHAR(20),
  
  INDEX idx_dlq_failed_at (failed_at DESC)
);

-- Webhook DLQ (separate from notification DLQ)
CREATE TABLE webhook_dlq (
  id UUID PRIMARY KEY,
  notification_id UUID NOT NULL,
  webhook_url TEXT NOT NULL,
  webhook_payload JSONB NOT NULL,
  retry_policy VARCHAR(20) NOT NULL,
  final_error JSONB NOT NULL,
  attempt_count INTEGER NOT NULL,
  failed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  INDEX idx_webhook_dlq_notification (notification_id),
  INDEX idx_webhook_dlq_failed_at (failed_at DESC)
);

-- Worker health tracking
CREATE TABLE worker_health (
  worker_id VARCHAR(255) PRIMARY KEY,
  last_heartbeat TIMESTAMPTZ NOT NULL,
  processing_count INTEGER NOT NULL DEFAULT 0,
  queue_implementation VARCHAR(20), -- 'postgres', 'redis', 'sqs'
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  
  INDEX idx_worker_heartbeat (last_heartbeat DESC)
);

-- Worker configuration (for migration)
CREATE TABLE worker_config (
  id SERIAL PRIMARY KEY,
  queue_implementation VARCHAR(20) NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
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

-- Provider rate limiting
CREATE TABLE provider_rate_limits (
  provider_id VARCHAR(100) NOT NULL,
  window_start TIMESTAMPTZ NOT NULL,
  window_type VARCHAR(10) NOT NULL,
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

### 7. Data Models (unchanged)
[Same as original - omitted for brevity]

### 8. Monitoring & Observability (unchanged)
[Same as original - omitted for brevity]

## What I Improved

### 1. **Fixed Subtle Dequeue Race Condition**
The advisory lock alone isn't sufficient - I added **optimistic locking with version field** back in, but only for the final UPDATE. The combination prevents:
- **Phantom reads**: `FOR UPDATE SKIP LOCKED` prevents within-transaction phantoms
- **Lost updates**: Version check prevents overwriting concurrent updates
- **Cross-transaction races**: Advisory lock serializes access across transactions

The three-layer defense is necessary because:
- Advisory lock prevents concurrent dequeues in Postgres
- `FOR UPDATE SKIP LOCKED` prevents lock contention and timeouts
- Version check catches any edge cases where advisory lock expires or fails

### 2. **Solved Queue Migration Problem**
Added `QueueMigrationOrchestrator` with two concrete strategies:
- **Drain-first**: Simple, causes brief processing pause (~minutes), safest
- **Live-forward**: Complex, zero downtime, requires dedicated drain workers

Key insight: **Don't dual-write to both queues** - this creates split-brain problems for deduplication and status tracking. Instead, use forwarding mode where old queue routes new messages to new queue.

### 3. **Made Webhooks Configurable**
Introduced `WebhookRetryPolicy` enum with three profiles:
- **BEST_EFFORT**: 3 retries over 5 minutes (default for most use cases)
- **AGGRESSIVE**: 10 retries over 24 hours (critical integrations)
- **PERSISTENT**: Infinite retries with exponential backoff up to 1 week intervals (financial/audit systems)

This solves the debate: Let users choose based on their requirements. Some integrations (payment confirmations) need persistent retries; others (analytics) can tolerate loss.

### 4. **Enhanced Circuit Breaker with Failure Rate**
Added failure rate threshold alongside absolute count. This prevents spurious opens during traffic spikes (100 failures out of 10,000 requests is fine; 100 out of 150 is not).

Also improved half-open recovery with multiplicative increase (1 → 1.5x → 2.25x) rather than linear, striking balance between caution and speed.

### 5. **Added Webhook DLQ Separation**
Created separate `webhook_dlq` table. Webhooks failing shouldn't pollute notification DLQ because:
- Notification delivery succeeded (provider accepted it)
- Webhook is a side-effect, not the primary operation
- Different retry/alerting requirements

### 6. **Tracked Source Queue in Schema**
Added `source_queue` column to track which queue implementation processed each message. This enables:
- Post-migration audit (did we lose messages?)
- Performance comparison (Postgres vs Redis latency)
- Debugging (which queue had the failure?)

### 7. **Added Queue Implementation to Worker Health**
Workers report their queue implementation in heartbeat. This lets you:
- Verify all workers migrated to new queue
- Monitor mixed fleets during migration
- Debug routing issues

## What I Kept

- Separate queue table from notifications (excellent separation of concerns)
- Lease-based processing with extension loop
- Priority queue with efficient indexing
- Exponential backoff with jitter
- Circuit breaker per provider
- Token bucket rate limiting
- Template versioning
- Device token management
- Comprehensive audit trail
- Maintenance jobs
- Prometheus metrics

## Remaining Concerns

### 1. **Deduplication During Queue Migration**
If a message is deduplicating via `idempotency_key` in the notifications table, and we're forwarding new messages to the new queue during migration, the dedup check happens before queueing. This should work correctly, but we need to verify that:
- Dedup keys are checked at enqueue time (API layer), not queue layer
- Both queues honor the same dedup semantics

**Recommendation**: Document that idempotency keys are checked before queue selection.

### 2. **Cost of Advisory Locks at Scale**
Advisory locks in PostgreSQL are limited resources (shared memory). At very high concurrency (hundreds of workers), we might exhaust available locks. Need to:
- Monitor `pg_locks` for advisory lock contention
- Set `max_locks_per_transaction` appropriately
- Document when to migrate to Redis (not just throughput, but concurrency)

### 3. **Webhook Signature Verification**
The webhook signature is computed server-side, but how does the receiving service verify it? Need to:
- Document the HMAC verification process for webhook consumers
- Consider adding timestamp to prevent replay attacks
- Provide SDK/library for webhook verification

### 4. **Multi-Region Deployments**
For global deployments with regional queues:
- How do we route notifications to the nearest queue?
- Can workers in one region process messages from another region's queue?
- Does webhook delivery respect regional restrictions (GDPR)?

**Recommendation**: Add `region` field to worker config and queue routing logic.

### 5. **Circuit Breaker Coordination**
Each worker has its own circuit breaker state. In a fleet of 50 workers, they'll independently trip and recover. Should we:
- Share circuit breaker state via Redis (adds complexity, improves coordination)
- Keep local state but share trip signals (hybrid approach)
- Accept eventual consistency (simplest, current design)

Current design is acceptable for most cases, but distributed circuit breaking should be documented as a future enhancement.

## Convergence Status

**ITERATING** - The dequeue race condition fix and queue migration strategy are solid, but need feedback on webhook retry policy flexibility and circuit breaker coordination approach.

## Prompt for Architect

PROMPT_FOR_ARCHITECT:
Review the **three-layer dequeue protection** (advisory lock + FOR UPDATE SKIP LOCKED + version check) - is this over-engineered, or does it actually prevent subtle races that would occur with only two layers? Challenge the **queue migration live-forward strategy**: are dedicated drain workers necessary, or can we reuse existing workers with a "draining mode" flag? Finally, evaluate the **webhook retry policy configurability** - should this be per-notification, per-tenant, or system-wide default? Consider the API ergonomics and common use cases.

**Convergence Signal:** ITERATING

---

