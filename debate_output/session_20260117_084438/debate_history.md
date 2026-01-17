# Claude Code Debate Session

**Started:** 2026-01-17T08:44:38.025155
**Ended:** 2026-01-17T08:51:53.726388
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a rate limiting system

---

## Round 1

### 🔵 Agent A

## Design

# Distributed Rate Limiting System

## Architecture Overview

A horizontally scalable, distributed rate limiting system using the **Token Bucket algorithm** with Redis as the shared state backend and an optional local cache layer for performance optimization.

## Components

### 1. Rate Limiter Service

```typescript
interface RateLimiterConfig {
  algorithm: 'token_bucket' | 'leaky_bucket' | 'fixed_window' | 'sliding_window';
  limits: RateLimit[];
  storage: StorageBackend;
  localCache?: LocalCacheConfig;
}

interface RateLimit {
  name: string;
  capacity: number;        // Maximum tokens/requests
  refillRate: number;      // Tokens added per second
  refillInterval: number;  // Milliseconds between refills
  keyGenerator: (context: RequestContext) => string;
  scope: 'global' | 'per_user' | 'per_ip' | 'custom';
}

interface RequestContext {
  userId?: string;
  ipAddress?: string;
  endpoint: string;
  method: string;
  customAttributes?: Record<string, string>;
}

class RateLimiter {
  async checkLimit(context: RequestContext, limitName: string): Promise<RateLimitResult>;
  async consumeToken(context: RequestContext, limitName: string, tokens: number = 1): Promise<RateLimitResult>;
  async resetLimit(key: string): Promise<void>;
  async getCurrentState(key: string): Promise<BucketState>;
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: Date;
  retryAfter?: number;  // Seconds until next allowed request
  limit: number;
}

interface BucketState {
  tokens: number;
  lastRefillTime: number;
  capacity: number;
}
```

### 2. Storage Backend Interface

```typescript
interface StorageBackend {
  getBucket(key: string): Promise<BucketState | null>;
  updateBucket(key: string, state: BucketState, ttl: number): Promise<void>;
  atomicConsumeTokens(key: string, tokens: number, config: RateLimit): Promise<RateLimitResult>;
}

class RedisStorage implements StorageBackend {
  // Uses Lua script for atomic token consumption
  private consumeTokensScript = `
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local requested = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    local refill_interval = tonumber(ARGV[5])
    
    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])
    
    if not tokens then
      tokens = capacity
      last_refill = now
    end
    
    -- Calculate refill
    local elapsed = now - last_refill
    local refill_count = math.floor(elapsed / refill_interval) * refill_rate
    tokens = math.min(capacity, tokens + refill_count)
    last_refill = last_refill + (math.floor(elapsed / refill_interval) * refill_interval)
    
    -- Check and consume
    if tokens >= requested then
      tokens = tokens - requested
      redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
      redis.call('PEXPIRE', key, capacity / refill_rate * refill_interval * 2)
      return {1, tokens, last_refill}
    else
      return {0, tokens, last_refill}
    end
  `;
}
```

### 3. Local Cache Layer (Optional)

```typescript
interface LocalCacheConfig {
  enabled: boolean;
  maxSize: number;
  ttlMs: number;
  syncIntervalMs: number;
}

class LocalCacheLayer {
  private cache: LRUCache<string, CachedBucketState>;
  
  async checkAndConsume(key: string, tokens: number): Promise<RateLimitResult | null>;
  async syncWithBackend(key: string): Promise<void>;
  invalidate(key: string): void;
}

interface CachedBucketState extends BucketState {
  cachedAt: number;
  dirty: boolean;
}
```

### 4. Rate Limit Middleware (HTTP)

```typescript
interface MiddlewareConfig {
  rateLimiter: RateLimiter;
  limitName: string;
  keyExtractor?: (req: Request) => RequestContext;
  onLimitExceeded?: (req: Request, result: RateLimitResult) => Response;
  skipCondition?: (req: Request) => boolean;
}

function createRateLimitMiddleware(config: MiddlewareConfig) {
  return async (req: Request, res: Response, next: NextFunction) => {
    if (config.skipCondition?.(req)) {
      return next();
    }
    
    const context = config.keyExtractor?.(req) || extractDefaultContext(req);
    const result = await config.rateLimiter.consumeToken(context, config.limitName);
    
    // Set standard rate limit headers
    res.setHeader('X-RateLimit-Limit', result.limit);
    res.setHeader('X-RateLimit-Remaining', result.remaining);
    res.setHeader('X-RateLimit-Reset', Math.floor(result.resetAt.getTime() / 1000));
    
    if (!result.allowed) {
      res.setHeader('Retry-After', result.retryAfter || 60);
      
      if (config.onLimitExceeded) {
        return config.onLimitExceeded(req, result);
      }
      
      return res.status(429).json({
        error: 'Too Many Requests',
        message: 'Rate limit exceeded',
        retryAfter: result.retryAfter
      });
    }
    
    next();
  };
}
```

## Data Models

### Redis Schema

```
Key Pattern: rate_limit:{scope}:{identifier}:{limit_name}

Example Keys:
- rate_limit:user:user123:api_calls
- rate_limit:ip:192.168.1.1:login_attempts
- rate_limit:global:api:write_operations

Hash Structure:
{
  "tokens": "95.5",
  "last_refill": "1705467890123",
  "capacity": "100",
  "refill_rate": "10",
  "refill_interval": "1000"
}

TTL: 2 * (capacity / refill_rate) * refill_interval
```

### Configuration Schema

```yaml
rate_limits:
  - name: api_global
    algorithm: token_bucket
    capacity: 10000
    refill_rate: 100
    refill_interval: 1000  # ms
    scope: global
    
  - name: api_per_user
    algorithm: token_bucket
    capacity: 1000
    refill_rate: 10
    refill_interval: 1000
    scope: per_user
    
  - name: login_attempts
    algorithm: token_bucket
    capacity: 5
    refill_rate: 1
    refill_interval: 60000  # 1 per minute
    scope: per_ip
    
  - name: expensive_operation
    algorithm: token_bucket
    capacity: 10
    refill_rate: 1
    refill_interval: 3600000  # 1 per hour
    scope: per_user

storage:
  type: redis
  connection:
    host: redis-cluster
    port: 6379
    cluster_mode: true
    
local_cache:
  enabled: true
  max_size: 10000
  ttl_ms: 1000
  sync_interval_ms: 500
```

## Error Handling

### Error Types

```typescript
class RateLimitError extends Error {
  constructor(
    message: string,
    public code: RateLimitErrorCode,
    public retryAfter?: number
  ) {
    super(message);
  }
}

enum RateLimitErrorCode {
  STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE',
  INVALID_CONFIG = 'INVALID_CONFIG',
  KEY_GENERATION_FAILED = 'KEY_GENERATION_FAILED',
  SCRIPT_EXECUTION_FAILED = 'SCRIPT_EXECUTION_FAILED'
}
```

### Fallback Strategies

```typescript
interface FallbackConfig {
  strategy: 'fail_open' | 'fail_closed' | 'local_only';
  degradedModeThreshold: number;  // Error rate to trigger fallback
  recoveryCheckInterval: number;   // ms between backend health checks
}

class FallbackHandler {
  async handleStorageFailure(
    context: RequestContext,
    config: FallbackConfig
  ): Promise<RateLimitResult> {
    switch (config.strategy) {
      case 'fail_open':
        // Allow requests when storage is unavailable
        return { allowed: true, remaining: -1, resetAt: new Date(), limit: -1 };
        
      case 'fail_closed':
        // Deny requests when storage is unavailable
        throw new RateLimitError(
          'Rate limiting service unavailable',
          RateLimitErrorCode.STORAGE_UNAVAILABLE
        );
        
      case 'local_only':
        // Fall back to in-memory rate limiting
        return this.localLimiter.checkLimit(context);
    }
  }
}
```

### Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;    // Failures before opening
  resetTimeout: number;        // ms before attempting reset
  halfOpenRequests: number;    // Test requests in half-open state
}

class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failures: number = 0;
  
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      throw new RateLimitError(
        'Circuit breaker open',
        RateLimitErrorCode.STORAGE_UNAVAILABLE
      );
    }
    
    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
}
```

## Monitoring and Observability

```typescript
interface RateLimitMetrics {
  recordRequest(limitName: string, allowed: boolean): void;
  recordLatency(operation: string, durationMs: number): void;
  recordStorageError(error: Error): void;
  recordCacheHit(hit: boolean): void;
}

// Prometheus-style metrics
const metrics = {
  rate_limit_requests_total: Counter({
    name: 'rate_limit_requests_total',
    help: 'Total rate limit checks',
    labelNames: ['limit_name', 'result']
  }),
  
  rate_limit_check_duration_ms: Histogram({
    name: 'rate_limit_check_duration_ms',
    help: 'Rate limit check latency',
    buckets: [1, 5, 10, 25, 50, 100]
  }),
  
  rate_limit_storage_errors_total: Counter({
    name: 'rate_limit_storage_errors_total',
    help: 'Storage backend errors'
  }),
  
  rate_limit_cache_hits_total: Counter({
    name: 'rate_limit_cache_hits_total',
    help: 'Local cache hits/misses',
    labelNames: ['result']
  })
};
```

## Rationale

1. **Token Bucket Algorithm**: Chosen for its flexibility in handling burst traffic while maintaining average rate limits. It allows unused capacity to accumulate, which is more user-friendly than strict fixed windows.

2. **Redis with Lua Scripts**: Provides atomic operations for distributed systems. The Lua script ensures race conditions are avoided when multiple instances check the same rate limit simultaneously.

3. **Local Cache Layer**: Reduces Redis load and latency for frequently checked limits. The cache is eventually consistent, accepting slight inaccuracy for significant performance gains.

4. **Flexible Key Generation**: Allows rate limiting by multiple dimensions (user, IP, endpoint, custom attributes) without code changes.

5. **Circuit Breaker Pattern**: Prevents cascading failures when storage backend has issues. Protects both the rate limiter and the storage system.

6. **Fail-Open Strategy**: Defaults to allowing requests during storage outages to maintain service availability. This can be configured based on security requirements.

## What I Incorporated

This is the initial design, no prior feedback to incorporate.

## What I Kept

Initial design - establishing baseline architecture and components.

## Open Questions

1. Should we support multiple algorithms (leaky bucket, sliding window) or focus on token bucket initially?
2. What's the acceptable inconsistency window for the local cache layer?
3. Should rate limit configurations be dynamic (stored in database) or static (configuration files)?
4. Do we need support for distributed rate limiting across multiple Redis clusters?
5. Should we implement rate limit "warming" for new users to prevent initial burst issues?

## Convergence Status

**ITERATING**: This is the initial design. It needs collaborative review and refinement to identify gaps, weaknesses, and improvements.

## PROMPT_FOR_CRITIC:

Please review this rate limiting system design and focus on:
1. **Scalability concerns**: Will this architecture handle millions of requests per second? What are the bottlenecks?
2. **Consistency vs. Performance trade-offs**: Is the local cache layer introducing unacceptable rate limit violations?
3. **Algorithm choice**: Is token bucket the right choice, or should we support multiple algorithms?
4. **Edge cases**: What failure scenarios or attack vectors am I missing?
5. **API ergonomics**: Is the interface developer-friendly and flexible enough for diverse use cases?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Distributed Rate Limiting System

## Architecture Overview

A horizontally scalable, distributed rate limiting system using the **Token Bucket algorithm** with Redis as the shared state backend, an optional local cache layer for performance optimization, and comprehensive safeguards against edge cases and attack vectors.

## Components

### 1. Rate Limiter Service

```typescript
interface RateLimiterConfig {
  algorithm: 'token_bucket';
  limits: RateLimit[];
  storage: StorageBackend;
  localCache?: LocalCacheConfig;
  security?: SecurityConfig;
}

interface RateLimit {
  name: string;
  capacity: number;        // Maximum tokens/requests
  refillRate: number;      // Tokens added per second
  refillInterval: number;  // Milliseconds between refills
  keyGenerator: (context: RequestContext) => string;
  scope: 'global' | 'per_user' | 'per_ip' | 'custom';
  costFunction?: (context: RequestContext) => number;  // Variable token costs
  burstMultiplier?: number;  // Max burst = capacity * burstMultiplier (default: 1)
}

interface SecurityConfig {
  maxKeyLength: number;              // Prevent memory exhaustion attacks
  maxConcurrentKeys: number;         // Limit unique rate limit keys
  keyPatternWhitelist?: RegExp[];    // Validate key patterns
  anomalyDetection?: AnomalyConfig;
}

interface AnomalyConfig {
  enabled: boolean;
  suspiciousPatternThreshold: number;  // Requests/sec to flag as suspicious
  autoBlockDuration?: number;          // Auto-block duration in ms
}

interface RequestContext {
  userId?: string;
  ipAddress?: string;
  endpoint: string;
  method: string;
  customAttributes?: Record<string, string>;
  requestWeight?: number;  // For variable-cost operations
  timestamp?: number;      // For replay attack prevention
}

class RateLimiter {
  async checkLimit(context: RequestContext, limitName: string): Promise<RateLimitResult>;
  async consumeToken(context: RequestContext, limitName: string, tokens: number = 1): Promise<RateLimitResult>;
  async resetLimit(key: string): Promise<void>;
  async getCurrentState(key: string): Promise<BucketState>;
  async addQuota(key: string, tokens: number): Promise<void>;  // For quota grants/credits
  async getMetadata(key: string): Promise<RateLimitMetadata>;  // For debugging/admin
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: Date;
  retryAfter?: number;  // Seconds until next allowed request
  limit: number;
  estimatedWaitMs?: number;  // More precise than retryAfter for client backoff
}

interface RateLimitMetadata {
  keyAge: number;  // Milliseconds since key creation
  totalRequests: number;
  violationCount: number;
  lastAccessTime: number;
}

interface BucketState {
  tokens: number;
  lastRefillTime: number;
  capacity: number;
  lastAccessTime?: number;  // For cleanup and monitoring
}
```

### 2. Storage Backend Interface

```typescript
interface StorageBackend {
  getBucket(key: string): Promise<BucketState | null>;
  updateBucket(key: string, state: BucketState, ttl: number): Promise<void>;
  atomicConsumeTokens(key: string, tokens: number, config: RateLimit): Promise<RateLimitResult>;
  cleanupStaleKeys(olderThanMs: number): Promise<number>;  // Return count of cleaned keys
  getKeyCount(): Promise<number>;  // For monitoring cardinality
  healthCheck(): Promise<boolean>;
}

class RedisStorage implements StorageBackend {
  private connectionPool: RedisClusterPool;
  private scriptSha: string;  // Preloaded script SHA for performance
  
  // Enhanced Lua script with security checks and precise timing
  private consumeTokensScript = `
    local key = KEYS[1]
    local capacity = tonumber(ARGV[1])
    local refill_rate = tonumber(ARGV[2])
    local requested = tonumber(ARGV[3])
    local now = tonumber(ARGV[4])
    local refill_interval = tonumber(ARGV[5])
    local max_burst = tonumber(ARGV[6]) or capacity
    local ttl = tonumber(ARGV[7])
    
    -- Security: Validate inputs
    if requested > capacity * 10 then
      return redis.error_reply("Excessive token request")
    end
    
    local bucket = redis.call('HMGET', key, 'tokens', 'last_refill', 'last_access', 'total_requests', 'violations')
    local tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])
    local last_access = tonumber(bucket[3]) or now
    local total_requests = tonumber(bucket[4]) or 0
    local violations = tonumber(bucket[5]) or 0
    
    if not tokens then
      tokens = capacity
      last_refill = now
    end
    
    -- Calculate refill with millisecond precision
    local elapsed = now - last_refill
    local refill_periods = math.floor(elapsed / refill_interval)
    local tokens_to_add = refill_periods * refill_rate
    
    -- Apply burst limiting
    tokens = math.min(max_burst, tokens + tokens_to_add)
    
    -- Update last_refill only by complete periods to prevent drift
    if refill_periods > 0 then
      last_refill = last_refill + (refill_periods * refill_interval)
    end
    
    -- Track request metadata
    total_requests = total_requests + 1
    
    -- Check and consume
    if tokens >= requested then
      tokens = tokens - requested
      redis.call('HMSET', key, 
        'tokens', tokens, 
        'last_refill', last_refill,
        'last_access', now,
        'total_requests', total_requests,
        'violations', violations
      )
      redis.call('PEXPIRE', key, ttl)
      
      -- Return: allowed, remaining, reset_time, estimated_wait_ms, metadata
      local next_refill = refill_interval - (now - last_refill)
      return {1, tokens, last_refill + refill_interval, 0, total_requests, violations}
    else
      -- Calculate precise wait time
      local tokens_needed = requested - tokens
      local refills_needed = math.ceil(tokens_needed / refill_rate)
      local wait_ms = (refills_needed * refill_interval) - (now - last_refill)
      
      violations = violations + 1
      redis.call('HSET', key, 'violations', violations, 'last_access', now, 'total_requests', total_requests)
      redis.call('PEXPIRE', key, ttl)
      
      return {0, tokens, last_refill + (refills_needed * refill_interval), wait_ms, total_requests, violations}
    end
  `;
  
  async preloadScript(): Promise<void> {
    this.scriptSha = await this.connectionPool.scriptLoad(this.consumeTokensScript);
  }
  
  async atomicConsumeTokens(key: string, tokens: number, config: RateLimit): Promise<RateLimitResult> {
    const now = Date.now();
    const ttl = Math.ceil((config.capacity / config.refillRate) * config.refillInterval * 2);
    const maxBurst = config.capacity * (config.burstMultiplier || 1);
    
    try {
      // Use EVALSHA for better performance
      const result = await this.connectionPool.evalsha(
        this.scriptSha,
        1,
        key,
        config.capacity,
        config.refillRate,
        tokens,
        now,
        config.refillInterval,
        maxBurst,
        ttl
      );
      
      return this.parseScriptResult(result, config);
    } catch (error) {
      if (error.message.includes('NOSCRIPT')) {
        // Script not cached, reload and retry
        await this.preloadScript();
        return this.atomicConsumeTokens(key, tokens, config);
      }
      throw error;
    }
  }
  
  async cleanupStaleKeys(olderThanMs: number): Promise<number> {
    // Use SCAN with pattern matching to find and delete stale keys
    const cutoffTime = Date.now() - olderThanMs;
    let cursor = '0';
    let deletedCount = 0;
    
    do {
      const [newCursor, keys] = await this.connectionPool.scan(cursor, 'MATCH', 'rate_limit:*', 'COUNT', 1000);
      cursor = newCursor;
      
      for (const key of keys) {
        const lastAccess = await this.connectionPool.hget(key, 'last_access');
        if (lastAccess && parseInt(lastAccess) < cutoffTime) {
          await this.connectionPool.del(key);
          deletedCount++;
        }
      }
    } while (cursor !== '0');
    
    return deletedCount;
  }
  
  async getKeyCount(): Promise<number> {
    // Approximate count using SCAN
    let cursor = '0';
    let count = 0;
    
    do {
      const [newCursor, keys] = await this.connectionPool.scan(cursor, 'MATCH', 'rate_limit:*', 'COUNT', 1000);
      cursor = newCursor;
      count += keys.length;
    } while (cursor !== '0');
    
    return count;
  }
}
```

### 3. Local Cache Layer (Optional)

```typescript
interface LocalCacheConfig {
  enabled: boolean;
  maxSize: number;
  ttlMs: number;
  syncIntervalMs: number;
  maxDivergence: number;  // Maximum % difference before forcing backend sync
  preemptiveSyncThreshold: number;  // Sync when tokens drop below this %
}

class LocalCacheLayer {
  private cache: LRUCache<string, CachedBucketState>;
  private divergenceTracker: Map<string, number>;  // Track accuracy drift
  
  async checkAndConsume(key: string, tokens: number, config: RateLimit): Promise<RateLimitResult | null> {
    const cached = this.cache.get(key);
    if (!cached) return null;
    
    // Check if cache is fresh enough
    const age = Date.now() - cached.cachedAt;
    if (age > this.config.ttlMs) {
      this.cache.delete(key);
      return null;
    }
    
    // Calculate local refill
    const elapsed = Date.now() - cached.lastRefillTime;
    const refillPeriods = Math.floor(elapsed / config.refillInterval);
    const tokensToAdd = refillPeriods * config.refillRate;
    const maxBurst = config.capacity * (config.burstMultiplier || 1);
    
    let currentTokens = Math.min(maxBurst, cached.tokens + tokensToAdd);
    
    if (currentTokens >= tokens) {
      // Allow request optimistically
      currentTokens -= tokens;
      cached.tokens = currentTokens;
      cached.dirty = true;
      cached.lastRefillTime += (refillPeriods * config.refillInterval);
      
      // Preemptive sync for accuracy
      const utilizationPercent = (currentTokens / config.capacity) * 100;
      if (utilizationPercent < this.config.preemptiveSyncThreshold) {
        this.scheduleSync(key);
      }
      
      return {
        allowed: true,
        remaining: Math.floor(currentTokens),
        resetAt: new Date(cached.lastRefillTime + config.refillInterval),
        limit: config.capacity
      };
    }
    
    // Near-limit: force backend check for accuracy
    return null;
  }
  
  async syncWithBackend(key: string): Promise<void> {
    const cached = this.cache.get(key);
    if (!cached?.dirty) return;
    
    // Push dirty state to backend and fetch authoritative state
    const authoritative = await this.backend.getCurrentState(key);
    
    // Track divergence for monitoring
    const divergence = Math.abs(cached.tokens - authoritative.tokens) / authoritative.capacity;
    this.divergenceTracker.set(key, divergence);
    
    // Update cache with authoritative state
    this.cache.set(key, {
      ...authoritative,
      cachedAt: Date.now(),
      dirty: false
    });
  }
  
  getDivergenceStats(): { avg: number; max: number; p99: number } {
    const values = Array.from(this.divergenceTracker.values()).sort((a, b) => a - b);
    return {
      avg: values.reduce((sum, v) => sum + v, 0) / values.length,
      max: values[values.length - 1] || 0,
      p99: values[Math.floor(values.length * 0.99)] || 0
    };
  }
}

interface CachedBucketState extends BucketState {
  cachedAt: number;
  dirty: boolean;
}
```

### 4. Rate Limit Middleware (HTTP)

```typescript
interface MiddlewareConfig {
  rateLimiter: RateLimiter;
  limitName: string;
  keyExtractor?: (req: Request) => RequestContext;
  onLimitExceeded?: (req: Request, result: RateLimitResult) => Response;
  skipCondition?: (req: Request) => boolean;
  costFunction?: (req: Request) => number;  // Variable costs per request
  whitelistChecker?: (req: Request) => boolean;  // Bypass for trusted sources
}

function createRateLimitMiddleware(config: MiddlewareConfig) {
  return async (req: Request, res: Response, next: NextFunction) => {
    // Early exit for whitelisted requests
    if (config.whitelistChecker?.(req) || config.skipCondition?.(req)) {
      return next();
    }
    
    const context = config.keyExtractor?.(req) || extractDefaultContext(req);
    const tokens = config.costFunction?.(req) || 1;
    
    // Validate token request isn't abusive
    if (tokens > 1000) {
      return res.status(400).json({
        error: 'Bad Request',
        message: 'Invalid token cost'
      });
    }
    
    const result = await config.rateLimiter.consumeToken(context, config.limitName, tokens);
    
    // Set standard rate limit headers (RFC 6585 + draft RateLimit header)
    res.setHeader('X-RateLimit-Limit', result.limit);
    res.setHeader('X-RateLimit-Remaining', Math.max(0, result.remaining));
    res.setHeader('X-RateLimit-Reset', Math.floor(result.resetAt.getTime() / 1000));
    res.setHeader('RateLimit-Policy', `${result.limit};w=${Math.floor(result.resetAt.getTime() / 1000)}`);
    
    if (!result.allowed) {
      const retryAfter = result.retryAfter || Math.ceil((result.estimatedWaitMs || 60000) / 1000);
      res.setHeader('Retry-After', retryAfter);
      
      // Optional: Include more helpful info for client exponential backoff
      if (result.estimatedWaitMs) {
        res.setHeader('X-RateLimit-Reset-Ms', result.estimatedWaitMs);
      }
      
      if (config.onLimitExceeded) {
        return config.onLimitExceeded(req, result);
      }
      
      return res.status(429).json({
        error: 'Too Many Requests',
        message: 'Rate limit exceeded',
        retryAfter: retryAfter,
        limit: result.limit,
        resetAt: result.resetAt.toISOString()
      });
    }
    
    next();
  };
}
```

## Data Models

### Redis Schema

```
Key Pattern: rate_limit:{scope}:{identifier}:{limit_name}

Example Keys:
- rate_limit:user:user123:api_calls
- rate_limit:ip:192.168.1.1:login_attempts
- rate_limit:global:api:write_operations

Hash Structure:
{
  "tokens": "95.5",
  "last_refill": "1705467890123",
  "last_access": "1705467890500",
  "capacity": "100",
  "refill_rate": "10",
  "refill_interval": "1000",
  "total_requests": "1547",
  "violations": "23"
}

TTL: 2 * (capacity / refill_rate) * refill_interval
```

### Configuration Schema

```yaml
rate_limits:
  - name: api_global
    algorithm: token_bucket
    capacity: 10000
    refill_rate: 100
    refill_interval: 1000  # ms
    scope: global
    burst_multiplier: 1.5  # Allow 50% burst above capacity
    
  - name: api_per_user
    algorithm: token_bucket
    capacity: 1000
    refill_rate: 10
    refill_interval: 1000
    scope: per_user
    
  - name: login_attempts
    algorithm: token_bucket
    capacity: 5
    refill_rate: 1
    refill_interval: 60000  # 1 per minute
    scope: per_ip
    burst_multiplier: 1  # No burst for security-sensitive operations
    
  - name: expensive_operation
    algorithm: token_bucket
    capacity: 10
    refill_rate: 1
    refill_interval: 3600000  # 1 per hour
    scope: per_user

storage:
  type: redis
  connection:
    host: redis-cluster
    port: 6379
    cluster_mode: true
    connection_pool_size: 50
    connection_timeout_ms: 100
    operation_timeout_ms: 50
    retry_strategy:
      max_attempts: 3
      backoff_ms: 10
    
security:
  max_key_length: 256
  max_concurrent_keys: 1000000
  key_pattern_whitelist:
    - "^rate_limit:(user|ip|global):[a-zA-Z0-9_-]+:[a-zA-Z0-9_]+$"
  anomaly_detection:
    enabled: true
    suspicious_pattern_threshold: 1000  # req/sec
    auto_block_duration: 300000  # 5 minutes
    
local_cache:
  enabled: true
  max_size: 10000
  ttl_ms: 1000
  sync_interval_ms: 500
  max_divergence: 0.05  # 5% acceptable inaccuracy
  preemptive_sync_threshold: 20  # Sync when below 20% tokens
```

## Scalability Analysis

### Throughput Optimization

**Target: 1M requests/second**

1. **Redis Performance**:
   - Single Redis instance: ~100K ops/sec
   - Redis Cluster (10 nodes): ~1M ops/sec
   - With local cache (95% hit rate): 50K backend ops/sec needed → 1M total requests/sec achievable

2. **Bottleneck Mitigation**:
   - **Network latency**: Use connection pooling, pipelining for batch operations
   - **Lua script execution**: Pre-load scripts with SCRIPT LOAD, use EVALSHA
   - **Key distribution**: Use consistent hashing for even distribution across cluster nodes
   - **Hot keys**: Replicate frequently accessed global limits to all nodes with local cache

3. **Horizontal Scaling**:
   - Stateless rate limiter instances: scale independently
   - Redis Cluster: add nodes for linear throughput scaling
   - Local cache: reduces backend load by 90-95%

### Performance Benchmarks (Expected)

```
Without local cache:
- P50 latency: 2-5ms
- P99 latency: 10-20ms
- Max throughput per instance: 10K req/sec

With local cache (95% hit rate):
- P50 latency: 0.1-0.5ms (cache hit)
- P99 latency: 15ms (cache miss + backend)
- Max throughput per instance: 200K req/sec
```

## Consistency vs. Performance Trade-offs

### Local Cache Accuracy

**Problem**: Local cache introduces rate limit violations during high concurrency

**Quantification**:
- With 10 instances and 100 req/sec burst:
  - Without cache: 0% violation rate
  - With 1s cache: up to 10% over-limit in worst case (all instances cached simultaneously)
  - With 500ms cache + preemptive sync: <2% over-limit

**Mitigation Strategies**:

1. **Adaptive cache TTL**: Reduce TTL as utilization increases
   ```typescript
   const adaptiveTTL = (remainingPercent: number) => {
     if (remainingPercent < 20) return 100;  // 100ms when near limit
     if (remainingPercent < 50) return 500;  // 500ms when half used
     return 1000;  // 1s when plenty of capacity
   };
   ```

2. **Preemptive synchronization**: Force backend check when approaching limit (< 20% remaining)

3. **Probabilistic cache bypass**: Skip cache for N% of requests for continuous accuracy validation
   ```typescript
   const shouldBypassCache = (key: string) => {
     return Math.random() < 0.05;  // 5% of requests bypass for accuracy check
   };
   ```

4. **Divergence monitoring**: Alert when cache drift exceeds acceptable threshold

**Recommendation**: Enable local cache with 500ms TTL and preemptive sync for 95% performance gain with <2% accuracy trade-off. Disable for security-critical limits (login attempts, 2FA).

## Edge Cases and Attack Vectors

### Security Considerations

1. **Key Cardinality Explosion Attack**:
   - **Attack**: Generate millions of unique user IDs to exhaust Redis memory
   - **Mitigation**: 
     - Set `max_concurrent_keys` limit
     - Implement key pattern whitelist validation
     - Monitor key creation rate and auto-block suspicious patterns
     - Background cleanup job for stale keys

2. **Timestamp Manipulation**:
   - **Attack**: Client sends future timestamps to game the system
   - **Mitigation**: Use server-side timestamps only, never trust client input

3. **Token Cost Manipulation**:
   - **Attack**: Request with cost=0 or cost=-1000
   - **Mitigation**: Validate token costs (0 < cost < maxCost) in middleware

4. **Race Condition Exploitation**:
   - **Attack**: Concurrent requests exploit window between check and consume
   - **Mitigation**: Use atomic Lua script (already implemented)

5. **Cache Poisoning**:
   - **Attack**: Corrupt local cache to allow unlimited requests
   - **Mitigation**: Validate cache state against backend periodically, use checksums

6. **Distributed Timing Attack**:
   - **Attack**: Coordinate requests across instances to exploit cache inconsistency
   - **Mitigation**: Reduce cache TTL under high load, implement rate limit on rate limit checks

### Edge Cases

1. **Clock Skew**: Instances have different system times
   - **Mitigation**: Use Redis TIME command for authoritative timestamp

2. **Network Partition**: Can't reach Redis
   - **Mitigation**: Circuit breaker with fail-open/fail-closed strategy

3. **Capacity < Requested Tokens**: User requests 100 tokens but capacity is 50
   - **Mitigation**: Return clear error, suggest breaking request into smaller chunks

4. **Zero or Negative Refill Rates**: Configuration error
   - **Mitigation**: Config validation on startup, reject invalid configs

5. **Integer Overflow**: Token count exceeds language limits
   - **Mitigation**: Use bounded arithmetic, cap at capacity * burst_multiplier

## Error Handling

### Error Types

```typescript
class RateLimitError extends Error {
  constructor(
    message: string,
    public code: RateLimitErrorCode,
    public retryAfter?: number,
    public context?: Record<string, any>
  ) {
    super(message);
  }
}

enum RateLimitErrorCode {
  STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE',
  INVALID_CONFIG = 'INVALID_CONFIG',
  KEY_GENERATION_FAILED = 'KEY_GENERATION_FAILED',
  SCRIPT_EXECUTION_FAILED = 'SCRIPT_EXECUTION_FAILED',
  EXCESSIVE_KEY_CARDINALITY = 'EXCESSIVE_KEY_CARDINALITY',
  INVALID_TOKEN_COST = 'INVALID_TOKEN_COST',
  STORAGE_TIMEOUT = 'STORAGE_TIMEOUT'
}
```

### Fallback Strategies

```typescript
interface FallbackConfig {
  strategy: 'fail_open' | 'fail_closed' | 'local_only';
  degradedModeThreshold: number;  // Error rate % to trigger fallback
  recoveryCheckInterval: number;   // ms between backend health checks
  localFallbackLimits: Record<string, SimplifiedRateLimit>;  // Generous limits for fail-open
}

class FallbackHandler {
  private errorRate: SlidingWindowCounter;
  
  async handleStorageFailure(
    context: RequestContext,
    config: FallbackConfig
  ): Promise<RateLimitResult> {
    const currentErrorRate = this.errorRate.getRate();
    
    if (currentErrorRate > config.degradedModeThreshold) {
      switch (config.strategy) {
        case 'fail_open':
          // Allow requests with generous in-memory limits
          return this.localLimiter.checkLimit(context, config.localFallbackLimits);
          
        case 'fail_closed':
          // Deny all requests when storage is unavailable
          throw new RateLimitError(
            'Rate limiting service unavailable',
            RateLimitErrorCode.STORAGE_UNAVAILABLE,
            60  // Retry after 60s
          );
          
        case 'local_only':
          // Fall back to strict in-memory rate limiting
          return this.localLimiter.checkLimit(context);
      }
    }
    
    // Retry with exponential backoff
    throw new RateLimitError(
      'Temporary storage issue',
      RateLimitErrorCode.STORAGE_TIMEOUT,
      5  // Retry after 5s
    );
  }
}
```

### Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;    // Failures before opening (e.g., 5)
  failureWindowMs: number;     // Time window for counting failures
  resetTimeout: number;        // ms before attempting reset (e.g., 30000)
  halfOpenRequests: number;    // Test requests in half-open state (e.g., 3)
  successThreshold: number;    // Successes needed to close from half-open
}

class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failures: number = 0;
  private lastFailureTime: number = 0;
  private halfOpenSuccesses: number = 0;
  
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastFailureTime > this.config.resetTimeout) {
        this.state = 'half_open';
        this.halfOpenSuccesses = 0;
      } else {
        throw new RateLimitError(
          'Circuit breaker open - storage unavailable',
          RateLimitErrorCode.STORAGE_UNAVAILABLE
        );
      }
    }
    
    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }
  
  private onSuccess(): void {
    if (this.state === 'half_open') {
      this.halfOpenSuccesses++;
      if (this.halfOpenSuccesses >= this.config.successThreshold) {
        this.state = 'closed';
        this.failures = 0;
      }
    } else if (this.state === 'closed') {
      this.failures = Math.max(0, this.failures - 1);  // Gradual recovery
    }
  }
  
  private onFailure(): void {
    this.lastFailureTime = Date.now();
    
    if (this.state === 'half_open') {
      this.state = 'open';
      this.failures = this.config.failureThreshold;
    } else {
      this.failures++;
      if (this.failures >= this.config.failureThreshold) {
        this.state = 'open';
      }
    }
  }
}
```

## Monitoring and Observability

```typescript
interface RateLimitMetrics {
  recordRequest(limitName: string, allowed: boolean, latencyMs: number): void;
  recordStorageError(error: Error): void;
  recordCacheHit(hit: boolean): void;
  recordCacheDivergence(divergencePercent: number): void;
  recordKeyCardinality(count: number): void;
  recordViolationPattern(key: string, violationCount: number): void;
}

// Prometheus-style metrics
const metrics = {
  rate_limit_requests_total: Counter({
    name: 'rate_limit_requests_total',
    help: 'Total rate limit checks',
    labelNames: ['limit_name', 'result', 'cache_hit']
  }),
  
  rate_limit_check_duration_ms: Histogram({
    name: 'rate_limit_check_duration_ms',
    help: 'Rate limit check latency',
    labelNames: ['limit_name', 'cache_hit'],
    buckets: [0.1, 0.5, 1, 5, 10, 25, 50, 100]
  }),
  
  rate_limit_storage_errors_total: Counter({
    name: 'rate_limit_storage_errors_total',
    help: 'Storage backend errors',
    labelNames: ['error_code']
  }),
  
  rate_limit_cache_hits_total: Counter({
    name: 'rate_limit_cache_hits_total',
    help: 'Local cache hits/misses',
    labelNames: ['result']
  }),
  
  rate_limit_cache_divergence: Histogram({
    name: 'rate_limit_cache_divergence',
    help: 'Cache accuracy drift percentage',
    buckets: [0.01, 0.02, 0.05, 0.1, 0.2, 0.5]
  }),
  
  rate_limit_key_cardinality: Gauge({
    name: 'rate_limit_key_cardinality',
    help: 'Number of active rate limit keys'
  }),
  
  rate_limit_circuit_breaker_state: Gauge({
    name: 'rate_limit_circuit_breaker_state',
    help: 'Circuit breaker state (0=closed, 1=open, 2=half_open)'
  }),
  
  rate_limit_violations_total: Counter({
    name: 'rate_limit_violations_total',
    help: 'Total rate limit violations',
    labelNames: ['limit_name', 'key_prefix']
  })
};

// Alerting Rules
const alerts = {
  highErrorRate: 'rate_limit_storage_errors_total > 100 per minute',
  cacheDivergenceHigh: 'rate_limit_cache_divergence p99 > 0.1',  // 10% drift
  keyCardinalityExplosion: 'rate_limit_key_cardinality > 1000000',
  circuitBreakerOpen: 'rate_limit_circuit_breaker_state == 1',
  suspiciousViolationPattern: 'rate_limit_violations_total rate > 100 per second for same key_prefix'
};
```

## Rationale

### Why Token Bucket Only (Not Multi-Algorithm)

**Decision**: Focus on token bucket algorithm exclusively rather than supporting multiple algorithms.

**Reasoning**:
1. **Token bucket handles 95% of use cases**: Covers burst traffic, steady-state limits, and API quotas
2. **Simpler implementation**: One well-tested algorithm is better than multiple mediocre ones
3. **Performance**: Specialized implementation is faster than generic abstraction
4. **Operational simplicity**: Fewer configuration footguns, easier to reason about
5. **If truly needed**: Other algorithms can be added later without breaking changes

**When token bucket isn't ideal**:
- Fixed window might be simpler for coarse-grained limits (e.g., "1000 requests per day")
- Leaky bucket better for strict output rate control (e.g., message queue producers)

**Mitigation**: Support `burstMultiplier` parameter to tune burst behavior, covering most non-standard needs.

### Redis with Lua Scripts

Atomic operations via Lua scripts prevent race conditions in distributed systems. The script ensures consistency without pessimistic locking, achieving both correctness and performance.

### Local Cache Layer

Provides 90-95% latency reduction and throughput increase with acceptable accuracy trade-off (<2% over-limit) when tuned correctly. Critical for scaling to millions of requests/second.

### Security-First Design

Key cardinality limits, input validation, and anomaly detection prevent common attack vectors. The design assumes adversarial users and protects against both intentional attacks and accidental misconfigurations.

## What I Improved

1. **Scalability Deep Dive**:
   - Added concrete throughput numbers (1M req/sec target)
   - Detailed bottleneck analysis and mitigation strategies
   - Performance benchmarks with and without caching
   - Horizontal scaling guidance

2. **Cache Consistency Quantification**:
   - Specific violation rate analysis (<2% with tuning)
   - Four concrete mitigation strategies: adaptive TTL, preemptive sync, probabilistic bypass, divergence monitoring
   - Guidance on when to disable cache (security-critical limits)
   - Added cache divergence tracking and metrics

3. **Algorithm Choice Justification**:
   - Explicit decision to focus on token bucket only
   - Clear rationale with trade-offs
   - Identified edge cases where other algorithms might be better
   - Added `burstMultiplier` parameter for flexibility

4. **Comprehensive Edge Cases**:
   - Six security attack vectors with specific mitigations
   - Five operational edge cases (clock skew, network partition, etc.)
   - Input validation throughout the stack
   - Anomaly detection system

5. **Production-Ready Error Handling**:
   - Enhanced circuit breaker with gradual recovery
   - Failure window tracking instead of simple counters
   - Half-open state with success threshold
   - Better error context for debugging

6. **Developer Experience**:
   - Variable token costs via `costFunction`
   - Whitelist bypass for trusted sources
   - Precise `estimatedWaitMs` for client exponential backoff
   - Admin APIs: `addQuota()`, `getMetadata()` for debugging
   - Standard RFC 6585 + draft RateLimit headers

7. **Operational Excellence**:
   - Key cleanup mechanism to prevent memory leaks
   - Key cardinality monitoring to detect attacks early
   - Request metadata tracking (total_requests, violations) for forensics
   - Comprehensive alerting rules

## What I Kept

- Token bucket core algorithm (excellent choice)
- Redis with Lua scripts (optimal for distributed consistency)
- Flexible key generation and multi-scope support
- Circuit breaker pattern for resilience
- Prometheus metrics for observability
- Clean interface design with `RateLimitResult` and `RequestContext`

## Remaining Considerations

1. **Dynamic Configuration**: Should rate limits be hot-reloadable from database, or is static config sufficient?
   - **Trade-off**: Database adds complexity but enables runtime tuning without restarts

2. **Multi-Region Deployment**: How to handle rate limits across geographically distributed Redis clusters?
   - **Trade-off**: Regional independence (faster) vs. global consistency (stricter)

3. **Token Warming Strategy**: Should new users start with reduced capacity to prevent initial burst abuse?
   - **Trade-off**: User experience vs. abuse prevention

4. **Rate Limit Quotas/Credits**: Support for one-time quota grants (e.g., "promotional 1000 extra requests")?
   - **Current**: Basic `addQuota()` API exists, but no expiration or quota types

5. **Cache Invalidation Strategy**: When a user's limit is manually reset, how to invalidate all instance caches?
   - **Options**: Redis pub/sub, periodic sync, accept eventual consistency

## Convergence Status

**ITERATING**: Design significantly enhanced with scalability analysis, cache consistency quantification, security hardening, and production-ready error handling. Ready for architect's review on trade-offs and implementation priorities.

## PROMPT_FOR_ARCHITECT:

Please review these improvements and focus on:

1. **Implementation Priorities**: Should we build core functionality first (no cache, no anomaly detection) and add optimizations later, or implement full system upfront?

2. **Cache Trade-off Validation**: Is <2% over-limit acceptable for your use case, or do you need stricter guarantees? Should cache be opt-in per limit rather than global?

3. **Multi-Region Strategy**: Will this system run in a single region, or do we need to design for global deployment from the start?

4. **Dynamic Configuration**: Do rate limits need to be adjustable at runtime via API/database, or is config-file-based static configuration sufficient?

5. **Token Cost Granularity**: Will most requests be cost=1, or do you foresee heavy use of variable-cost operations (e.g., bulk uploads costing 10-100 tokens)?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Distributed Rate Limiting System

## Architecture Overview

A horizontally scalable, distributed rate limiting system using the **Token Bucket algorithm** with Redis as the shared state backend. The design prioritizes correctness and operational simplicity, with optional performance optimizations that can be enabled based on specific requirements.

## Core Components

### 1. Rate Limiter Service

```typescript
interface RateLimiterConfig {
  limits: RateLimit[];
  storage: StorageBackend;
  fallback: FallbackConfig;
  monitoring: MonitoringConfig;
  localCache?: LocalCacheConfig;  // Optional performance optimization
}

interface RateLimit {
  name: string;
  capacity: number;              // Maximum tokens
  refillRate: number;            // Tokens added per second
  refillInterval: number;        // Milliseconds between refills
  keyGenerator: (context: RequestContext) => string;
  scope: 'global' | 'per_user' | 'per_ip' | 'custom';
  costFunction?: (context: RequestContext) => number;
  burstAllowance?: number;       // Additional tokens beyond capacity (default: 0)
  priority?: 'strict' | 'standard';  // Cache behavior hint
}

interface RequestContext {
  userId?: string;
  ipAddress?: string;
  endpoint: string;
  method: string;
  customAttributes?: Record<string, string>;
  requestWeight?: number;
  timestamp: number;  // Server-generated only
}

class RateLimiter {
  private storage: StorageBackend;
  private cache?: LocalCacheLayer;
  private circuitBreaker: CircuitBreaker;
  private metrics: MetricsCollector;
  private configProvider: ConfigProvider;
  
  constructor(config: RateLimiterConfig) {
    this.storage = config.storage;
    this.cache = config.localCache ? new LocalCacheLayer(config.localCache, this.storage) : undefined;
    this.circuitBreaker = new CircuitBreaker(config.fallback.circuitBreaker);
    this.metrics = new MetricsCollector(config.monitoring);
    this.configProvider = new ConfigProvider(config);
  }
  
  async checkLimit(context: RequestContext, limitName: string): Promise<RateLimitResult> {
    const limit = this.configProvider.getLimit(limitName);
    const key = this.buildKey(limit, context);
    const tokens = limit.costFunction?.(context) ?? 1;
    
    // Input validation
    this.validateRequest(key, tokens, limit);
    
    return await this.consumeTokensWithFallback(key, tokens, limit, context);
  }
  
  private async consumeTokensWithFallback(
    key: string, 
    tokens: number, 
    limit: RateLimit,
    context: RequestContext
  ): Promise<RateLimitResult> {
    const startTime = Date.now();
    
    try {
      // Optional cache layer for high-throughput scenarios
      if (this.cache && this.shouldUseCache(limit)) {
        const cacheResult = await this.cache.tryConsume(key, tokens, limit);
        if (cacheResult) {
          this.metrics.recordRequest(limit.name, cacheResult.allowed, Date.now() - startTime, true);
          return cacheResult;
        }
      }
      
      // Authoritative backend check
      const result = await this.circuitBreaker.execute(() =>
        this.storage.atomicConsumeTokens(key, tokens, limit, context.timestamp)
      );
      
      this.metrics.recordRequest(limit.name, result.allowed, Date.now() - startTime, false);
      
      // Update cache on backend success
      if (this.cache) {
        await this.cache.updateFromBackend(key, result);
      }
      
      return result;
      
    } catch (error) {
      this.metrics.recordStorageError(error);
      return await this.handleFailure(key, tokens, limit, error);
    }
  }
  
  private shouldUseCache(limit: RateLimit): boolean {
    // Security-critical operations bypass cache
    return limit.priority !== 'strict';
  }
  
  private validateRequest(key: string, tokens: number, limit: RateLimit): void {
    if (key.length > 256) {
      throw new RateLimitError('Key too long', RateLimitErrorCode.INVALID_KEY);
    }
    if (tokens <= 0 || tokens > limit.capacity * 10) {
      throw new RateLimitError('Invalid token cost', RateLimitErrorCode.INVALID_TOKEN_COST);
    }
  }
  
  private buildKey(limit: RateLimit, context: RequestContext): string {
    const identifier = limit.keyGenerator(context);
    return `ratelimit:${limit.scope}:${identifier}:${limit.name}`;
  }
  
  async resetLimit(key: string): Promise<void> {
    await this.storage.deleteKey(key);
    if (this.cache) {
      await this.cache.invalidate(key);
    }
  }
  
  async addQuota(key: string, tokens: number): Promise<void> {
    await this.storage.addTokens(key, tokens);
    if (this.cache) {
      await this.cache.invalidate(key);
    }
  }
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: Date;
  retryAfter?: number;
  limit: number;
  waitTimeMs?: number;
}
```

### 2. Storage Backend (Redis Implementation)

```typescript
interface StorageBackend {
  atomicConsumeTokens(key: string, tokens: number, config: RateLimit, now: number): Promise<RateLimitResult>;
  deleteKey(key: string): Promise<void>;
  addTokens(key: string, tokens: number): Promise<void>;
  healthCheck(): Promise<boolean>;
  getStats(): Promise<StorageStats>;
}

interface StorageStats {
  activeKeys: number;
  memoryUsage: number;
  operationsPerSecond: number;
}

class RedisStorage implements StorageBackend {
  private pool: RedisConnectionPool;
  private scriptSha: string;
  
  constructor(config: RedisConfig) {
    this.pool = new RedisConnectionPool({
      nodes: config.nodes,
      poolSize: config.poolSize ?? 50,
      connectionTimeout: config.connectionTimeout ?? 100,
      operationTimeout: config.operationTimeout ?? 50,
      retryStrategy: {
        maxAttempts: 3,
        backoffMs: [10, 50, 100]
      }
    });
  }
  
  async initialize(): Promise<void> {
    // Pre-load Lua script for performance
    this.scriptSha = await this.pool.scriptLoad(CONSUME_TOKENS_SCRIPT);
  }
  
  async atomicConsumeTokens(
    key: string, 
    tokens: number, 
    config: RateLimit,
    now: number
  ): Promise<RateLimitResult> {
    const maxBurst = config.capacity + (config.burstAllowance ?? 0);
    const ttl = this.calculateTTL(config);
    
    try {
      const result = await this.pool.evalsha(
        this.scriptSha,
        1, // number of keys
        key,
        config.capacity,
        config.refillRate,
        tokens,
        now,
        config.refillInterval,
        maxBurst,
        ttl
      );
      
      return this.parseScriptResult(result, config);
      
    } catch (error) {
      if (error.message?.includes('NOSCRIPT')) {
        await this.initialize();
        return this.atomicConsumeTokens(key, tokens, config, now);
      }
      throw error;
    }
  }
  
  private calculateTTL(config: RateLimit): number {
    // TTL = 2x the time to refill from 0 to capacity
    const secondsToFull = config.capacity / config.refillRate;
    const millisecondsToFull = (secondsToFull * 1000) / (1000 / config.refillInterval);
    return Math.ceil(millisecondsToFull * 2);
  }
  
  private parseScriptResult(result: any[], config: RateLimit): RateLimitResult {
    const [allowed, remaining, resetTime, waitMs] = result;
    
    return {
      allowed: allowed === 1,
      remaining: Math.floor(remaining),
      resetAt: new Date(resetTime),
      retryAfter: allowed === 1 ? undefined : Math.ceil(waitMs / 1000),
      limit: config.capacity,
      waitTimeMs: allowed === 1 ? undefined : waitMs
    };
  }
  
  async deleteKey(key: string): Promise<void> {
    await this.pool.del(key);
  }
  
  async addTokens(key: string, tokens: number): Promise<void> {
    await this.pool.hincrby(key, 'tokens', tokens);
  }
  
  async healthCheck(): Promise<boolean> {
    try {
      await this.pool.ping();
      return true;
    } catch {
      return false;
    }
  }
  
  async getStats(): Promise<StorageStats> {
    const info = await this.pool.info();
    const keyCount = await this.approximateKeyCount();
    
    return {
      activeKeys: keyCount,
      memoryUsage: this.parseMemoryUsage(info),
      operationsPerSecond: this.parseOpsPerSecond(info)
    };
  }
  
  private async approximateKeyCount(): Promise<number> {
    // Sample-based estimation to avoid blocking KEYS command
    let cursor = '0';
    let count = 0;
    let iterations = 0;
    const maxIterations = 10;
    
    do {
      const [newCursor, keys] = await this.pool.scan(
        cursor, 
        'MATCH', 
        'ratelimit:*', 
        'COUNT', 
        1000
      );
      cursor = newCursor;
      count += keys.length;
      iterations++;
    } while (cursor !== '0' && iterations < maxIterations);
    
    // Extrapolate if we stopped early
    if (cursor !== '0') {
      count = Math.ceil(count * (1000 / iterations));
    }
    
    return count;
  }
}

// Lua script for atomic token consumption
const CONSUME_TOKENS_SCRIPT = `
  local key = KEYS[1]
  local capacity = tonumber(ARGV[1])
  local refill_rate = tonumber(ARGV[2])
  local requested = tonumber(ARGV[3])
  local now = tonumber(ARGV[4])
  local refill_interval = tonumber(ARGV[5])
  local max_burst = tonumber(ARGV[6])
  local ttl = tonumber(ARGV[7])
  
  -- Input validation
  if requested > capacity * 10 then
    return redis.error_reply("Token request exceeds reasonable limit")
  end
  
  -- Get current state
  local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
  local tokens = tonumber(bucket[1])
  local last_refill = tonumber(bucket[2])
  
  -- Initialize new bucket
  if not tokens then
    tokens = capacity
    last_refill = now
  end
  
  -- Calculate refill
  local elapsed = now - last_refill
  local refill_periods = math.floor(elapsed / refill_interval)
  
  if refill_periods > 0 then
    local tokens_to_add = refill_periods * refill_rate
    tokens = math.min(max_burst, tokens + tokens_to_add)
    last_refill = last_refill + (refill_periods * refill_interval)
  end
  
  -- Attempt consumption
  if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill)
    redis.call('PEXPIRE', key, ttl)
    
    local next_refill_at = last_refill + refill_interval
    return {1, tokens, next_refill_at, 0}
  else
    -- Calculate wait time
    local tokens_needed = requested - tokens
    local refills_needed = math.ceil(tokens_needed / refill_rate)
    local wait_ms = (refills_needed * refill_interval) - elapsed + (refill_periods * refill_interval)
    local reset_at = last_refill + (refills_needed * refill_interval)
    
    -- Don't update state on denial, but ensure TTL is set
    if redis.call('EXISTS', key) == 1 then
      redis.call('PEXPIRE', key, ttl)
    end
    
    return {0, tokens, reset_at, wait_ms}
  end
`;
```

### 3. Optional Local Cache Layer

```typescript
interface LocalCacheConfig {
  enabled: boolean;
  maxSize: number;
  ttlMs: number;
  accuracyThreshold: number;  // Sync when tokens drop below this % of capacity
}

class LocalCacheLayer {
  private cache: Map<string, CachedBucket>;
  private backend: StorageBackend;
  private config: LocalCacheConfig;
  
  constructor(config: LocalCacheConfig, backend: StorageBackend) {
    this.cache = new Map();
    this.backend = backend;
    this.config = config;
    
    // LRU eviction
    this.startEvictionTimer();
  }
  
  async tryConsume(key: string, tokens: number, limit: RateLimit): Promise<RateLimitResult | null> {
    const cached = this.cache.get(key);
    
    // Cache miss or stale
    if (!cached || this.isStale(cached)) {
      return null;
    }
    
    // Simulate refill
    const now = Date.now();
    const elapsed = now - cached.lastRefillTime;
    const refillPeriods = Math.floor(elapsed / limit.refillInterval);
    const tokensToAdd = refillPeriods * limit.refillRate;
    const maxBurst = limit.capacity + (limit.burstAllowance ?? 0);
    
    let currentTokens = Math.min(maxBurst, cached.tokens + tokensToAdd);
    const utilizationPercent = (currentTokens / limit.capacity) * 100;
    
    // Force backend sync when approaching limit for accuracy
    if (utilizationPercent < this.config.accuracyThreshold) {
      return null;
    }
    
    // Allow optimistically
    if (currentTokens >= tokens) {
      currentTokens -= tokens;
      
      cached.tokens = currentTokens;
      cached.lastRefillTime += (refillPeriods * limit.refillInterval);
      cached.lastAccessTime = now;
      
      return {
        allowed: true,
        remaining: Math.floor(currentTokens),
        resetAt: new Date(cached.lastRefillTime + limit.refillInterval),
        limit: limit.capacity
      };
    }
    
    // Near-limit denial: force backend check
    return null;
  }
  
  async updateFromBackend(key: string, result: RateLimitResult): Promise<void> {
    if (this.cache.size >= this.config.maxSize) {
      this.evictOldest();
    }
    
    this.cache.set(key, {
      tokens: result.remaining,
      lastRefillTime: result.resetAt.getTime(),
      lastAccessTime: Date.now(),
      cachedAt: Date.now()
    });
  }
  
  async invalidate(key: string): Promise<void> {
    this.cache.delete(key);
  }
  
  private isStale(cached: CachedBucket): boolean {
    return (Date.now() - cached.cachedAt) > this.config.ttlMs;
  }
  
  private evictOldest(): void {
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    
    for (const [key, bucket] of this.cache.entries()) {
      if (bucket.lastAccessTime < oldestTime) {
        oldestTime = bucket.lastAccessTime;
        oldestKey = key;
      }
    }
    
    if (oldestKey) {
      this.cache.delete(oldestKey);
    }
  }
  
  private startEvictionTimer(): void {
    setInterval(() => {
      const now = Date.now();
      for (const [key, bucket] of this.cache.entries()) {
        if (now - bucket.cachedAt > this.config.ttlMs) {
          this.cache.delete(key);
        }
      }
    }, this.config.ttlMs);
  }
}

interface CachedBucket {
  tokens: number;
  lastRefillTime: number;
  lastAccessTime: number;
  cachedAt: number;
}
```

### 4. Configuration Provider (Dynamic Config Support)

```typescript
interface ConfigProvider {
  getLimit(name: string): RateLimit;
  getAllLimits(): RateLimit[];
  updateLimit(name: string, limit: RateLimit): Promise<void>;
  reload(): Promise<void>;
}

class StaticConfigProvider implements ConfigProvider {
  private limits: Map<string, RateLimit>;
  
  constructor(config: RateLimiterConfig) {
    this.limits = new Map(config.limits.map(l => [l.name, l]));
  }
  
  getLimit(name: string): RateLimit {
    const limit = this.limits.get(name);
    if (!limit) {
      throw new RateLimitError(`Unknown limit: ${name}`, RateLimitErrorCode.INVALID_CONFIG);
    }
    return limit;
  }
  
  getAllLimits(): RateLimit[] {
    return Array.from(this.limits.values());
  }
  
  async updateLimit(name: string, limit: RateLimit): Promise<void> {
    throw new Error('Static configuration does not support runtime updates');
  }
  
  async reload(): Promise<void> {
    // No-op for static config
  }
}

class DynamicConfigProvider implements ConfigProvider {
  private limits: Map<string, RateLimit>;
  private configStore: ConfigStore;
  private refreshInterval: number;
  
  constructor(configStore: ConfigStore, refreshInterval: number = 60000) {
    this.limits = new Map();
    this.configStore = configStore;
    this.refreshInterval = refreshInterval;
    
    this.startRefreshTimer();
  }
  
  async initialize(): Promise<void> {
    await this.reload();
  }
  
  getLimit(name: string): RateLimit {
    const limit = this.limits.get(name);
    if (!limit) {
      throw new RateLimitError(`Unknown limit: ${name}`, RateLimitErrorCode.INVALID_CONFIG);
    }
    return limit;
  }
  
  getAllLimits(): RateLimit[] {
    return Array.from(this.limits.values());
  }
  
  async updateLimit(name: string, limit: RateLimit): Promise<void> {
    await this.configStore.save(name, limit);
    await this.reload();
  }
  
  async reload(): Promise<void> {
    const limits = await this.configStore.loadAll();
    this.limits = new Map(limits.map(l => [l.name, l]));
  }
  
  private startRefreshTimer(): void {
    setInterval(() => {
      this.reload().catch(err => {
        console.error('Failed to reload config:', err);
      });
    }, this.refreshInterval);
  }
}

interface ConfigStore {
  loadAll(): Promise<RateLimit[]>;
  save(name: string, limit: RateLimit): Promise<void>;
}
```

### 5. HTTP Middleware

```typescript
interface MiddlewareConfig {
  rateLimiter: RateLimiter;
  limitName: string;
  keyExtractor?: (req: Request) => RequestContext;
  onLimitExceeded?: (req: Request, result: RateLimitResult) => Response;
  skipCondition?: (req: Request) => boolean;
}

function createRateLimitMiddleware(config: MiddlewareConfig) {
  return async (req: Request, res: Response, next: NextFunction) => {
    if (config.skipCondition?.(req)) {
      return next();
    }
    
    const context = config.keyExtractor?.(req) ?? {
      userId: req.user?.id,
      ipAddress: req.ip,
      endpoint: req.path,
      method: req.method,
      timestamp: Date.now()
    };
    
    try {
      const result = await config.rateLimiter.checkLimit(context, config.limitName);
      
      // Standard rate limit headers
      res.setHeader('X-RateLimit-Limit', result.limit);
      res.setHeader('X-RateLimit-Remaining', Math.max(0, result.remaining));
      res.setHeader('X-RateLimit-Reset', Math.floor(result.resetAt.getTime() / 1000));
      
      if (!result.allowed) {
        res.setHeader('Retry-After', result.retryAfter ?? 60);
        
        if (config.onLimitExceeded) {
          return config.onLimitExceeded(req, result);
        }
        
        return res.status(429).json({
          error: 'Too Many Requests',
          retryAfter: result.retryAfter,
          resetAt: result.resetAt.toISOString()
        });
      }
      
      next();
      
    } catch (error) {
      // Fail-open on rate limiter failure
      console.error('Rate limiter error:', error);
      next();
    }
  };
}
```

### 6. Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;
  failureWindowMs: number;
  resetTimeoutMs: number;
  halfOpenMaxAttempts: number;
}

class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failures: Array<number> = [];
  private halfOpenAttempts = 0;
  private lastStateChange = Date.now();
  
  constructor(private config: CircuitBreakerConfig) {}
  
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastStateChange >= this.config.resetTimeoutMs) {
        this.transitionTo('half_open');
      } else {
        throw new RateLimitError(
          'Circuit breaker open',
          RateLimitErrorCode.STORAGE_UNAVAILABLE
        );
      }
    }
    
    try {
      const result = await operation();
      this.recordSuccess();
      return result;
      
    } catch (error) {
      this.recordFailure();
      throw error;
    }
  }
  
  private recordSuccess(): void {
    if (this.state === 'half_open') {
      this.halfOpenAttempts++;
      if (this.halfOpenAttempts >= this.config.halfOpenMaxAttempts) {
        this.transitionTo('closed');
      }
    }
  }
  
  private recordFailure(): void {
    const now = Date.now();
    this.failures.push(now);
    
    // Remove old failures outside window
    this.failures = this.failures.filter(
      time => now - time < this.config.failureWindowMs
    );
    
    if (this.state === 'half_open') {
      this.transitionTo('open');
    } else if (this.failures.length >= this.config.failureThreshold) {
      this.transitionTo('open');
    }
  }
  
  private transitionTo(newState: 'closed' | 'open' | 'half_open'): void {
    this.state = newState;
    this.lastStateChange = Date.now();
    
    if (newState === 'closed') {
      this.failures = [];
      this.halfOpenAttempts = 0;
    } else if (newState === 'half_open') {
      this.halfOpenAttempts = 0;
    }
  }
  
  getState(): string {
    return this.state;
  }
}
```

### 7. Fallback Handler

```typescript
interface FallbackConfig {
  strategy: 'fail_open' | 'fail_closed';
  circuitBreaker: CircuitBreakerConfig;
}

class FallbackHandler {
  constructor(private config: FallbackConfig) {}
  
  async handleFailure(
    key: string,
    tokens: number,
    limit: RateLimit,
    error: Error
  ): Promise<RateLimitResult> {
    if (this.config.strategy === 'fail_open') {
      // Allow request when system is down
      return {
        allowed: true,
        remaining: limit.capacity,
        resetAt: new Date(Date.now() + limit.refillInterval),
        limit: limit.capacity
      };
    } else {
      // Deny request when system is down
      throw new RateLimitError(
        'Rate limiting service unavailable',
        RateLimitErrorCode.STORAGE_UNAVAILABLE,
        60
      );
    }
  }
}
```

## Configuration Schema

```yaml
rate_limits:
  - name: api_global
    capacity: 10000
    refill_rate: 100
    refill_interval: 1000  # ms
    scope: global
    burst_allowance: 0
    priority: standard
    
  - name: api_per_user
    capacity: 1000
    refill_rate: 10
    refill_interval: 1000
    scope: per_user
    burst_allowance: 500  # Allow burst to 1500
    priority: standard
    
  - name: login_attempts
    capacity: 5
    refill_rate: 1
    refill_interval: 60000
    scope: per_ip
    burst_allowance: 0
    priority: strict  # Never use cache

storage:
  type: redis
  nodes:
    - host: redis-1.example.com
      port: 6379
    - host: redis-2.example.com
      port: 6379
  pool_size: 50
  connection_timeout_ms: 100
  operation_timeout_ms: 50

fallback:
  strategy: fail_open  # or fail_closed
  circuit_breaker:
    failure_threshold: 5
    failure_window_ms: 10000
    reset_timeout_ms: 30000
    half_open_max_attempts: 3

local_cache:  # Optional
  enabled: true
  max_size: 10000
  ttl_ms: 1000
  accuracy_threshold: 20  # Force backend sync below 20% tokens

config_provider:
  type: static  # or dynamic
  # For dynamic:
  # store: postgres
  # refresh_interval_ms: 60000

monitoring:
  metrics_enabled: true
  prometheus_port: 9090
```

## Monitoring

```typescript
interface MetricsCollector {
  recordRequest(limitName: string, allowed: boolean, latencyMs: number, cacheHit: boolean): void;
  recordStorageError(error: Error): void;
  recordCacheHit(hit: boolean): void;
}

// Prometheus metrics
const metrics = {
  requests_total: new Counter({
    name: 'rate_limit_requests_total',
    help: 'Total rate limit checks',
    labelNames: ['limit_name', 'allowed', 'cache_hit']
  }),
  
  check_duration_seconds: new Histogram({
    name: 'rate_limit_check_duration_seconds',
    help: 'Rate limit check latency',
    labelNames: ['limit_name', 'cache_hit'],
    buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
  }),
  
  storage_errors_total: new Counter({
    name: 'rate_limit_storage_errors_total',
    help: 'Storage errors',
    labelNames: ['error_type']
  }),
  
  circuit_breaker_state: new Gauge({
    name: 'rate_limit_circuit_breaker_state',
    help: 'Circuit breaker state (0=closed, 1=open, 2=half_open)'
  }),
  
  active_keys: new Gauge({
    name: 'rate_limit_active_keys',
    help: 'Number of active rate limit keys'
  })
};
```

## Error Handling

```typescript
class RateLimitError extends Error {
  constructor(
    message: string,
    public code: RateLimitErrorCode,
    public retryAfter?: number
  ) {
    super(message);
    this.name = 'RateLimitError';
  }
}

enum RateLimitErrorCode {
  STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE',
  INVALID_CONFIG = 'INVALID_CONFIG',
  INVALID_KEY = 'INVALID_KEY',
  INVALID_TOKEN_COST = 'INVALID_TOKEN_COST',
  STORAGE_TIMEOUT = 'STORAGE_TIMEOUT'
}
```

## Deployment Phases

### Phase 1: Core Functionality (Week 1-2)
**Goal**: Production-ready basic rate limiting

- Token bucket algorithm with Redis backend
- Atomic Lua script for consistency
- Circuit breaker for resilience
- Basic monitoring (Prometheus metrics)
- Fail-open fallback strategy
- Static configuration
- HTTP middleware

**Deliverables**:
- Single-region deployment
- 10K req/sec per instance
- P99 latency <20ms
- No local cache

### Phase 2: Performance Optimization (Week 3-4)
**Goal**: Scale to high-throughput scenarios

- Local cache layer (opt-in per limit via `priority` field)
- Cache accuracy monitoring
- Script pre-loading (EVALSHA)
- Connection pooling optimization

**Deliverables**:
- 200K req/sec per instance (with cache)
- P99 latency <2ms (cache hits)
- Cache divergence metrics
- Performance benchmarks

### Phase 3: Advanced Features (Week 5-6)
**Goal**: Production operations and flexibility

- Dynamic configuration (database-backed)
- Admin API (reset limits, add quota)
- Key cleanup job
- Variable token costs
- Burst allowance tuning

**Deliverables**:
- Runtime config updates
- Operational playbooks
- Cost-per-operation support

### Phase 4: Multi-Region (Future)
**Goal**: Global deployment

- Regional Redis clusters
- Cross-region sync strategy
- Geolocation-aware routing

## Rationale

### Phased Implementation
**Decision**: Build incrementally rather than all-at-once.

**Reasoning**:
1. **Faster time-to-value**: Core functionality ready in 2 weeks vs. 6+ weeks for full system
2. **Risk mitigation**: Validate architecture with production traffic before adding complexity
3. **Informed optimization**: Real usage patterns guide cache tuning decisions
4. **Operational learning**: Team learns system behavior incrementally

### Cache as Opt-In
**Decision**: Cache disabled by default, enabled per-limit via `priority: standard`.

**Reasoning**:
1. **Correctness first**: Default behavior is strictly accurate
2. **Security-sensitive operations**: Login attempts, 2FA should never use cache (`priority: strict`)
3. **Explicit trade-off**: Teams consciously choose performance vs. accuracy
4. **Gradual rollout**: Can enable cache incrementally per service

**Cache accuracy trade-off**:
- Without cache: 0% over-limit violations, 10K req/sec, 5ms latency
- With cache: <2% over-limit violations, 200K req/sec, 0.5ms latency
- Recommendation: Enable for high-volume APIs, disable for security operations

### Static Config Default
**Decision**: Start with file-based configuration, add dynamic support in Phase 3.

**Reasoning**:
1. **Simplicity**: No database dependency, easier deployment
2. **Version control**: Config changes tracked in git
3. **YAGNI**: Most systems don't need runtime rate limit changes
4. **Migration path**: Can add dynamic provider without breaking existing deployments

**When to use dynamic config**:
- Multi-tenant SaaS with per-customer limits
- Incident response requiring immediate limit adjustments
- A/B testing rate limit thresholds

### Token Bucket Only
**Decision**: Implement only token bucket algorithm.

**Reasoning**:
1. **Covers 95% of use cases**: API throttling, burst handling, quota management
2. **Well-understood**: Standard algorithm with predictable behavior
3. **Implementation quality**: One excellent algorithm better than multiple mediocre ones
4. **Extension point**: Interface supports adding algorithms later if needed

**Alternative algorithms**:
- Fixed window: Simpler but allows burst at window boundaries
- Sliding window: More accurate but computationally expensive
- Leaky bucket: Better for strict output rate control but less flexible

### Single-Region First
**Decision**: Design for single-region deployment, defer multi-region complexity.

**Reasoning**:
1. **Most systems are single-region**: Premature optimization for global scale
2. **Significant complexity**: Cross-region sync, consistency trade-offs, latency
3. **Unclear requirements**: Need production experience to design correctly
4. **Migration path**: Architecture supports regional clusters in Phase 4

**Multi-region considerations** (future):
- Regional Redis clusters with independent rate limits
- Global limits via async aggregation (eventual consistency)
- Geolocation-aware request routing

### Fail-Open Default
**Decision**: Allow requests when rate limiter is unavailable.

**Reasoning**:
1. **Availability over strict enforcement**: Don't take down entire service due to rate limiter failure
2. **Rate limiting is optimization**: Core functionality should work without it
3. **Circuit breaker prevents cascading failure**: Auto-recovery when storage returns
4. **Configurable**: Can set `fail_closed` for strict enforcement scenarios

**When to use fail-closed**:
- Protecting expensive operations (database writes)
- Preventing abuse during incidents
- Regulatory compliance requirements

## What I Incorporated

1. **Comprehensive Lua script**: Atomic token consumption with validation and precise timing
2. **Token bucket algorithm**: Excellent choice for flexibility and performance
3. **Burst allowance**: Support for burst traffic via configurable parameter
4. **Variable token costs**: Cost function for weighted operations
5. **Circuit breaker pattern**: Resilience against backend failures
6. **Prometheus metrics**: Industry-standard observability
7. **Security validation**: Input checks, key length limits
8. **TTL calculation**: Automatic key expiration to prevent memory leaks

## What I Changed

1. **Implementation phases**: Incremental delivery instead of all-at-once to reduce risk and accelerate time-to-value
2. **Cache as opt-in**: Default to correctness, explicitly enable performance optimization per-limit
3. **Static config default**: File-based configuration sufficient for most use cases, add dynamic support later
4. **Single-region focus**: Defer multi-region complexity until proven necessary
5. **Simplified monitoring**: Essential metrics only in Phase 1, expand as needed
6. **Removed premature features**: Anomaly detection, key cardinality limits, cleanup jobs moved to Phase 3
7. **Configuration provider abstraction**: Support both static and dynamic config with same interface

## Open Questions

1. **Cache accuracy tolerance**: Is <2% over-limit acceptable for your high-throughput APIs? Or do you need stricter guarantees?

2. **Config update frequency**: How often do rate limits need to change? Daily? Never? During incidents?

3. **Burst traffic patterns**: Do your APIs experience sudden traffic spikes (e.g., campaign launches), or is load relatively steady?

4. **Failure strategy preference**: Fail-open (better availability) or fail-closed (strict enforcement)?

5. **Regional requirements**: Is your traffic primarily single-region, or do you need global rate limiting from day one?

## Convergence Status

**PROPOSING_FINAL**: This design provides a complete, production-ready rate limiting system with clear implementation phases. The phased approach balances correctness, performance, and operational simplicity while providing explicit extension points for future requirements.

## PROMPT_FOR_CRITIC:

Please review this phased design approach and focus on:

1. **Phase 1 completeness**: Does the core functionality include everything needed for production deployment? Any critical gaps?

2. **Cache opt-in strategy**: Is the per-limit `priority` field (strict vs. standard) clear enough? Should we provide more granular cache control?

3. **Static vs. dynamic config trade-off**: Does starting with static config and adding dynamic support later make sense for your use case? Or is dynamic config essential from day one?

4. **Phase ordering**: Should any Phase 3 features (dynamic config, admin API, key cleanup) be moved earlier? Or can they wait?

5. **Multi-region deferral**: Is single-region acceptable for initial deployment, or do you have global traffic that requires multi-region from the start?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Distributed Rate Limiting System

## Architecture Overview

A horizontally scalable, distributed rate limiting system using the **Token Bucket algorithm** with Redis as the shared state backend. The design prioritizes correctness and operational simplicity, with optional performance optimizations that can be enabled based on specific requirements.

## Core Components

### 1. Rate Limiter Service

```typescript
interface RateLimiterConfig {
  limits: RateLimit[];
  storage: StorageBackend;
  fallback: FallbackConfig;
  monitoring: MonitoringConfig;
  localCache?: LocalCacheConfig;
}

interface RateLimit {
  name: string;
  capacity: number;
  refillRate: number;
  refillInterval: number;
  keyGenerator: (context: RequestContext) => string;
  scope: 'global' | 'per_user' | 'per_ip' | 'custom';
  costFunction?: (context: RequestContext) => number;
  burstAllowance?: number;
  priority?: 'strict' | 'standard';
}

interface RequestContext {
  userId?: string;
  ipAddress?: string;
  endpoint: string;
  method: string;
  customAttributes?: Record<string, string>;
  requestWeight?: number;
  timestamp: number;
}

class RateLimiter {
  private storage: StorageBackend;
  private cache?: LocalCacheLayer;
  private circuitBreaker: CircuitBreaker;
  private metrics: MetricsCollector;
  private configProvider: ConfigProvider;
  private fallbackHandler: FallbackHandler;
  
  constructor(config: RateLimiterConfig) {
    this.storage = config.storage;
    this.cache = config.localCache ? new LocalCacheLayer(config.localCache, this.storage) : undefined;
    this.circuitBreaker = new CircuitBreaker(config.fallback.circuitBreaker);
    this.metrics = new MetricsCollector(config.monitoring);
    this.configProvider = new ConfigProvider(config);
    this.fallbackHandler = new FallbackHandler(config.fallback);
  }
  
  async checkLimit(context: RequestContext, limitName: string): Promise<RateLimitResult> {
    const limit = this.configProvider.getLimit(limitName);
    const key = this.buildKey(limit, context);
    const tokens = limit.costFunction?.(context) ?? 1;
    
    this.validateRequest(key, tokens, limit);
    
    return await this.consumeTokensWithFallback(key, tokens, limit, context);
  }
  
  private async consumeTokensWithFallback(
    key: string, 
    tokens: number, 
    limit: RateLimit,
    context: RequestContext
  ): Promise<RateLimitResult> {
    const startTime = Date.now();
    
    try {
      if (this.cache && this.shouldUseCache(limit)) {
        const cacheResult = await this.cache.tryConsume(key, tokens, limit);
        if (cacheResult) {
          this.metrics.recordRequest(limit.name, cacheResult.allowed, Date.now() - startTime, true);
          return cacheResult;
        }
      }
      
      const result = await this.circuitBreaker.execute(() =>
        this.storage.atomicConsumeTokens(key, tokens, limit, context.timestamp)
      );
      
      this.metrics.recordRequest(limit.name, result.allowed, Date.now() - startTime, false);
      
      if (this.cache) {
        await this.cache.updateFromBackend(key, result);
      }
      
      return result;
      
    } catch (error) {
      this.metrics.recordStorageError(error);
      return await this.fallbackHandler.handleFailure(key, tokens, limit, error);
    }
  }
  
  private shouldUseCache(limit: RateLimit): boolean {
    return limit.priority !== 'strict';
  }
  
  private validateRequest(key: string, tokens: number, limit: RateLimit): void {
    if (key.length > 256) {
      throw new RateLimitError('Key too long', RateLimitErrorCode.INVALID_KEY);
    }
    if (tokens <= 0 || tokens > limit.capacity * 10) {
      throw new RateLimitError('Invalid token cost', RateLimitErrorCode.INVALID_TOKEN_COST);
    }
  }
  
  private buildKey(limit: RateLimit, context: RequestContext): string {
    const identifier = limit.keyGenerator(context);
    return `ratelimit:${limit.scope}:${identifier}:${limit.name}`;
  }
  
  async resetLimit(key: string): Promise<void> {
    await this.storage.deleteKey(key);
    if (this.cache) {
      await this.cache.invalidate(key);
    }
  }
  
  async addQuota(key: string, tokens: number): Promise<void> {
    await this.storage.addTokens(key, tokens);
    if (this.cache) {
      await this.cache.invalidate(key);
    }
  }
  
  async getUtilization(limitName: string): Promise<LimitUtilization[]> {
    const limit = this.configProvider.getLimit(limitName);
    return await this.storage.getUtilization(limitName);
  }
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: Date;
  retryAfter?: number;
  limit: number;
  waitTimeMs?: number;
}

interface LimitUtilization {
  key: string;
  tokens: number;
  capacity: number;
  utilizationPercent: number;
}
```

### 2. Storage Backend (Redis Implementation)

```typescript
interface StorageBackend {
  atomicConsumeTokens(key: string, tokens: number, config: RateLimit, now: number): Promise<RateLimitResult>;
  deleteKey(key: string): Promise<void>;
  addTokens(key: string, tokens: number): Promise<void>;
  healthCheck(): Promise<boolean>;
  getStats(): Promise<StorageStats>;
  getUtilization(limitPrefix: string): Promise<LimitUtilization[]>;
}

interface StorageStats {
  activeKeys: number;
  memoryUsage: number;
  operationsPerSecond: number;
  replicationLag?: number;
}

class RedisStorage implements StorageBackend {
  private pool: RedisConnectionPool;
  private scriptSha: string;
  
  constructor(config: RedisConfig) {
    this.pool = new RedisConnectionPool({
      nodes: config.nodes,
      poolSize: config.poolSize ?? 50,
      connectionTimeout: config.connectionTimeout ?? 100,
      operationTimeout: config.operationTimeout ?? 50,
      retryStrategy: {
        maxAttempts: 3,
        backoffMs: [10, 50, 100]
      },
      enableReadReplicas: config.enableReadReplicas ?? false
    });
  }
  
  async initialize(): Promise<void> {
    this.scriptSha = await this.pool.scriptLoad(CONSUME_TOKENS_SCRIPT);
  }
  
  async atomicConsumeTokens(
    key: string, 
    tokens: number, 
    config: RateLimit,
    now: number
  ): Promise<RateLimitResult> {
    const maxBurst = config.capacity + (config.burstAllowance ?? 0);
    const ttl = this.calculateTTL(config);
    
    try {
      const result = await this.pool.evalsha(
        this.scriptSha,
        1,
        key,
        config.capacity,
        config.refillRate,
        tokens,
        now,
        config.refillInterval,
        maxBurst,
        ttl
      );
      
      return this.parseScriptResult(result, config);
      
    } catch (error) {
      if (error.message?.includes('NOSCRIPT')) {
        await this.initialize();
        return this.atomicConsumeTokens(key, tokens, config, now);
      }
      throw error;
    }
  }
  
  private calculateTTL(config: RateLimit): number {
    const secondsToFull = config.capacity / config.refillRate;
    const millisecondsToFull = (secondsToFull * 1000) / (1000 / config.refillInterval);
    return Math.ceil(millisecondsToFull * 2);
  }
  
  private parseScriptResult(result: any[], config: RateLimit): RateLimitResult {
    const [allowed, remaining, resetTime, waitMs] = result;
    
    return {
      allowed: allowed === 1,
      remaining: Math.floor(remaining),
      resetAt: new Date(resetTime),
      retryAfter: allowed === 1 ? undefined : Math.ceil(waitMs / 1000),
      limit: config.capacity,
      waitTimeMs: allowed === 1 ? undefined : waitMs
    };
  }
  
  async deleteKey(key: string): Promise<void> {
    await this.pool.del(key);
  }
  
  async addTokens(key: string, tokens: number): Promise<void> {
    await this.pool.hincrby(key, 'tokens', tokens);
  }
  
  async healthCheck(): Promise<boolean> {
    try {
      const start = Date.now();
      await this.pool.ping();
      const latency = Date.now() - start;
      return latency < 100;
    } catch {
      return false;
    }
  }
  
  async getStats(): Promise<StorageStats> {
    const info = await this.pool.info();
    const keyCount = await this.approximateKeyCount();
    
    return {
      activeKeys: keyCount,
      memoryUsage: this.parseMemoryUsage(info),
      operationsPerSecond: this.parseOpsPerSecond(info),
      replicationLag: this.parseReplicationLag(info)
    };
  }
  
  async getUtilization(limitPrefix: string): Promise<LimitUtilization[]> {
    const pattern = `ratelimit:*:${limitPrefix}`;
    let cursor = '0';
    const utilization: LimitUtilization[] = [];
    const maxSamples = 100;
    
    do {
      const [newCursor, keys] = await this.pool.scan(cursor, 'MATCH', pattern, 'COUNT', 100);
      cursor = newCursor;
      
      for (const key of keys.slice(0, maxSamples - utilization.length)) {
        const data = await this.pool.hgetall(key);
        if (data.tokens && data.capacity) {
          const tokens = parseFloat(data.tokens);
          const capacity = parseFloat(data.capacity);
          utilization.push({
            key,
            tokens,
            capacity,
            utilizationPercent: ((capacity - tokens) / capacity) * 100
          });
        }
      }
      
      if (utilization.length >= maxSamples) break;
    } while (cursor !== '0');
    
    return utilization.sort((a, b) => b.utilizationPercent - a.utilizationPercent);
  }
  
  private async approximateKeyCount(): Promise<number> {
    let cursor = '0';
    let count = 0;
    let iterations = 0;
    const maxIterations = 10;
    
    do {
      const [newCursor, keys] = await this.pool.scan(cursor, 'MATCH', 'ratelimit:*', 'COUNT', 1000);
      cursor = newCursor;
      count += keys.length;
      iterations++;
    } while (cursor !== '0' && iterations < maxIterations);
    
    if (cursor !== '0') {
      count = Math.ceil(count * (1000 / iterations));
    }
    
    return count;
  }
  
  private parseMemoryUsage(info: string): number {
    const match = info.match(/used_memory:(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }
  
  private parseOpsPerSecond(info: string): number {
    const match = info.match(/instantaneous_ops_per_sec:(\d+)/);
    return match ? parseInt(match[1], 10) : 0;
  }
  
  private parseReplicationLag(info: string): number | undefined {
    const match = info.match(/master_repl_offset:(\d+)/);
    if (!match) return undefined;
    return parseInt(match[1], 10);
  }
}

const CONSUME_TOKENS_SCRIPT = `
  local key = KEYS[1]
  local capacity = tonumber(ARGV[1])
  local refill_rate = tonumber(ARGV[2])
  local requested = tonumber(ARGV[3])
  local now = tonumber(ARGV[4])
  local refill_interval = tonumber(ARGV[5])
  local max_burst = tonumber(ARGV[6])
  local ttl = tonumber(ARGV[7])
  
  if requested > capacity * 10 then
    return redis.error_reply("Token request exceeds reasonable limit")
  end
  
  local bucket = redis.call('HMGET', key, 'tokens', 'last_refill')
  local tokens = tonumber(bucket[1])
  local last_refill = tonumber(bucket[2])
  
  if not tokens then
    tokens = capacity
    last_refill = now
  end
  
  local elapsed = now - last_refill
  local refill_periods = math.floor(elapsed / refill_interval)
  
  if refill_periods > 0 then
    local tokens_to_add = refill_periods * refill_rate
    tokens = math.min(max_burst, tokens + tokens_to_add)
    last_refill = last_refill + (refill_periods * refill_interval)
  end
  
  if tokens >= requested then
    tokens = tokens - requested
    redis.call('HMSET', key, 'tokens', tokens, 'last_refill', last_refill, 'capacity', capacity)
    redis.call('PEXPIRE', key, ttl)
    
    local next_refill_at = last_refill + refill_interval
    return {1, tokens, next_refill_at, 0}
  else
    local tokens_needed = requested - tokens
    local refills_needed = math.ceil(tokens_needed / refill_rate)
    local wait_ms = (refills_needed * refill_interval) - elapsed + (refill_periods * refill_interval)
    local reset_at = last_refill + (refills_needed * refill_interval)
    
    if redis.call('EXISTS', key) == 1 then
      redis.call('PEXPIRE', key, ttl)
    end
    
    return {0, tokens, reset_at, wait_ms}
  end
`;
```

### 3. Local Cache Layer

```typescript
interface LocalCacheConfig {
  enabled: boolean;
  maxSize: number;
  ttlMs: number;
  accuracyThreshold: number;
  syncOnDenial: boolean;
}

class LocalCacheLayer {
  private cache: Map<string, CachedBucket>;
  private backend: StorageBackend;
  private config: LocalCacheConfig;
  
  constructor(config: LocalCacheConfig, backend: StorageBackend) {
    this.cache = new Map();
    this.backend = backend;
    this.config = config;
    
    this.startEvictionTimer();
  }
  
  async tryConsume(key: string, tokens: number, limit: RateLimit): Promise<RateLimitResult | null> {
    const cached = this.cache.get(key);
    
    if (!cached || this.isStale(cached)) {
      return null;
    }
    
    const now = Date.now();
    const elapsed = now - cached.lastRefillTime;
    const refillPeriods = Math.floor(elapsed / limit.refillInterval);
    const tokensToAdd = refillPeriods * limit.refillRate;
    const maxBurst = limit.capacity + (limit.burstAllowance ?? 0);
    
    let currentTokens = Math.min(maxBurst, cached.tokens + tokensToAdd);
    const utilizationPercent = (currentTokens / limit.capacity) * 100;
    
    if (utilizationPercent < this.config.accuracyThreshold) {
      return null;
    }
    
    if (currentTokens >= tokens) {
      currentTokens -= tokens;
      
      cached.tokens = currentTokens;
      cached.lastRefillTime += (refillPeriods * limit.refillInterval);
      cached.lastAccessTime = now;
      
      return {
        allowed: true,
        remaining: Math.floor(currentTokens),
        resetAt: new Date(cached.lastRefillTime + limit.refillInterval),
        limit: limit.capacity
      };
    }
    
    if (this.config.syncOnDenial) {
      return null;
    }
    
    return {
      allowed: false,
      remaining: Math.floor(currentTokens),
      resetAt: new Date(cached.lastRefillTime + limit.refillInterval),
      limit: limit.capacity,
      retryAfter: Math.ceil((tokens - currentTokens) / limit.refillRate * (limit.refillInterval / 1000))
    };
  }
  
  async updateFromBackend(key: string, result: RateLimitResult): Promise<void> {
    if (this.cache.size >= this.config.maxSize) {
      this.evictOldest();
    }
    
    this.cache.set(key, {
      tokens: result.remaining,
      lastRefillTime: result.resetAt.getTime(),
      lastAccessTime: Date.now(),
      cachedAt: Date.now()
    });
  }
  
  async invalidate(key: string): Promise<void> {
    this.cache.delete(key);
  }
  
  private isStale(cached: CachedBucket): boolean {
    return (Date.now() - cached.cachedAt) > this.config.ttlMs;
  }
  
  private evictOldest(): void {
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    
    for (const [key, bucket] of this.cache.entries()) {
      if (bucket.lastAccessTime < oldestTime) {
        oldestTime = bucket.lastAccessTime;
        oldestKey = key;
      }
    }
    
    if (oldestKey) {
      this.cache.delete(oldestKey);
    }
  }
  
  private startEvictionTimer(): void {
    setInterval(() => {
      const now = Date.now();
      for (const [key, bucket] of this.cache.entries()) {
        if (now - bucket.cachedAt > this.config.ttlMs) {
          this.cache.delete(key);
        }
      }
    }, this.config.ttlMs);
  }
}

interface CachedBucket {
  tokens: number;
  lastRefillTime: number;
  lastAccessTime: number;
  cachedAt: number;
}
```

### 4. Configuration Provider

```typescript
interface ConfigProvider {
  getLimit(name: string): RateLimit;
  getAllLimits(): RateLimit[];
  updateLimit(name: string, limit: RateLimit): Promise<void>;
  reload(): Promise<void>;
}

class StaticConfigProvider implements ConfigProvider {
  private limits: Map<string, RateLimit>;
  
  constructor(config: RateLimiterConfig) {
    this.limits = new Map(config.limits.map(l => [l.name, l]));
  }
  
  getLimit(name: string): RateLimit {
    const limit = this.limits.get(name);
    if (!limit) {
      throw new RateLimitError(`Unknown limit: ${name}`, RateLimitErrorCode.INVALID_CONFIG);
    }
    return limit;
  }
  
  getAllLimits(): RateLimit[] {
    return Array.from(this.limits.values());
  }
  
  async updateLimit(name: string, limit: RateLimit): Promise<void> {
    throw new Error('Static configuration does not support runtime updates');
  }
  
  async reload(): Promise<void> {
    // No-op for static config
  }
}

class DynamicConfigProvider implements ConfigProvider {
  private limits: Map<string, RateLimit>;
  private configStore: ConfigStore;
  private refreshInterval: number;
  
  constructor(configStore: ConfigStore, refreshInterval: number = 60000) {
    this.limits = new Map();
    this.configStore = configStore;
    this.refreshInterval = refreshInterval;
    
    this.startRefreshTimer();
  }
  
  async initialize(): Promise<void> {
    await this.reload();
  }
  
  getLimit(name: string): RateLimit {
    const limit = this.limits.get(name);
    if (!limit) {
      throw new RateLimitError(`Unknown limit: ${name}`, RateLimitErrorCode.INVALID_CONFIG);
    }
    return limit;
  }
  
  getAllLimits(): RateLimit[] {
    return Array.from(this.limits.values());
  }
  
  async updateLimit(name: string, limit: RateLimit): Promise<void> {
    await this.configStore.save(name, limit);
    await this.reload();
  }
  
  async reload(): Promise<void> {
    const limits = await this.configStore.loadAll();
    this.limits = new Map(limits.map(l => [l.name, l]));
  }
  
  private startRefreshTimer(): void {
    setInterval(() => {
      this.reload().catch(err => {
        console.error('Failed to reload config:', err);
      });
    }, this.refreshInterval);
  }
}

interface ConfigStore {
  loadAll(): Promise<RateLimit[]>;
  save(name: string, limit: RateLimit): Promise<void>;
}
```

### 5. HTTP Middleware

```typescript
interface MiddlewareConfig {
  rateLimiter: RateLimiter;
  limitName: string;
  keyExtractor?: (req: Request) => RequestContext;
  onLimitExceeded?: (req: Request, result: RateLimitResult) => Response;
  skipCondition?: (req: Request) => boolean;
  includeHeaders?: boolean;
}

function createRateLimitMiddleware(config: MiddlewareConfig) {
  return async (req: Request, res: Response, next: NextFunction) => {
    if (config.skipCondition?.(req)) {
      return next();
    }
    
    const context = config.keyExtractor?.(req) ?? {
      userId: req.user?.id,
      ipAddress: req.ip,
      endpoint: req.path,
      method: req.method,
      timestamp: Date.now()
    };
    
    try {
      const result = await config.rateLimiter.checkLimit(context, config.limitName);
      
      if (config.includeHeaders !== false) {
        res.setHeader('X-RateLimit-Limit', result.limit);
        res.setHeader('X-RateLimit-Remaining', Math.max(0, result.remaining));
        res.setHeader('X-RateLimit-Reset', Math.floor(result.resetAt.getTime() / 1000));
      }
      
      if (!result.allowed) {
        res.setHeader('Retry-After', result.retryAfter ?? 60);
        
        if (config.onLimitExceeded) {
          return config.onLimitExceeded(req, result);
        }
        
        return res.status(429).json({
          error: 'Too Many Requests',
          retryAfter: result.retryAfter,
          resetAt: result.resetAt.toISOString()
        });
      }
      
      next();
      
    } catch (error) {
      console.error('Rate limiter error:', error);
      next();
    }
  };
}
```

### 6. Circuit Breaker

```typescript
interface CircuitBreakerConfig {
  failureThreshold: number;
  failureWindowMs: number;
  resetTimeoutMs: number;
  halfOpenMaxAttempts: number;
}

class CircuitBreaker {
  private state: 'closed' | 'open' | 'half_open' = 'closed';
  private failures: Array<number> = [];
  private halfOpenAttempts = 0;
  private lastStateChange = Date.now();
  
  constructor(private config: CircuitBreakerConfig) {}
  
  async execute<T>(operation: () => Promise<T>): Promise<T> {
    if (this.state === 'open') {
      if (Date.now() - this.lastStateChange >= this.config.resetTimeoutMs) {
        this.transitionTo('half_open');
      } else {
        throw new RateLimitError('Circuit breaker open', RateLimitErrorCode.STORAGE_UNAVAILABLE);
      }
    }
    
    try {
      const result = await operation();
      this.recordSuccess();
      return result;
      
    } catch (error) {
      this.recordFailure();
      throw error;
    }
  }
  
  private recordSuccess(): void {
    if (this.state === 'half_open') {
      this.halfOpenAttempts++;
      if (this.halfOpenAttempts >= this.config.halfOpenMaxAttempts) {
        this.transitionTo('closed');
      }
    }
  }
  
  private recordFailure(): void {
    const now = Date.now();
    this.failures.push(now);
    
    this.failures = this.failures.filter(time => now - time < this.config.failureWindowMs);
    
    if (this.state === 'half_open') {
      this.transitionTo('open');
    } else if (this.failures.length >= this.config.failureThreshold) {
      this.transitionTo('open');
    }
  }
  
  private transitionTo(newState: 'closed' | 'open' | 'half_open'): void {
    this.state = newState;
    this.lastStateChange = Date.now();
    
    if (newState === 'closed') {
      this.failures = [];
      this.halfOpenAttempts = 0;
    } else if (newState === 'half_open') {
      this.halfOpenAttempts = 0;
    }
  }
  
  getState(): string {
    return this.state;
  }
}
```

### 7. Fallback Handler

```typescript
interface FallbackConfig {
  strategy: 'fail_open' | 'fail_closed' | 'local_only';
  circuitBreaker: CircuitBreakerConfig;
  localOnlyConfig?: {
    capacity: number;
    refillRate: number;
  };
}

class FallbackHandler {
  private localBuckets: Map<string, LocalBucket> = new Map();
  
  constructor(private config: FallbackConfig) {}
  
  async handleFailure(
    key: string,
    tokens: number,
    limit: RateLimit,
    error: Error
  ): Promise<RateLimitResult> {
    if (this.config.strategy === 'fail_open') {
      return {
        allowed: true,
        remaining: limit.capacity,
        resetAt: new Date(Date.now() + limit.refillInterval),
        limit: limit.capacity
      };
    } else if (this.config.strategy === 'fail_closed') {
      throw new RateLimitError('Rate limiting service unavailable', RateLimitErrorCode.STORAGE_UNAVAILABLE, 60);
    } else if (this.config.strategy === 'local_only') {
      return this.useLocalBucket(key, tokens, limit);
    }
    
    throw error;
  }
  
  private useLocalBucket(key: string, tokens: number, limit: RateLimit): RateLimitResult {
    const now = Date.now();
    let bucket = this.localBuckets.get(key);
    
    if (!bucket) {
      bucket = {
        tokens: this.config.localOnlyConfig?.capacity ?? limit.capacity,
        lastRefill: now
      };
      this.localBuckets.set(key, bucket);
    }
    
    const elapsed = now - bucket.lastRefill;
    const refillPeriods = Math.floor(elapsed / limit.refillInterval);
    const tokensToAdd = refillPeriods * limit.refillRate;
    bucket.tokens = Math.min(limit.capacity, bucket.tokens + tokensToAdd);
    bucket.lastRefill += refillPeriods * limit.refillInterval;
    
    if (bucket.tokens >= tokens) {
      bucket.tokens -= tokens;
      return {
        allowed: true,
        remaining: Math.floor(bucket.tokens),
        resetAt: new Date(bucket.lastRefill + limit.refillInterval),
        limit: limit.capacity
      };
    } else {
      return {
        allowed: false,
        remaining: Math.floor(bucket.tokens),
        resetAt: new Date(bucket.lastRefill + limit.refillInterval),
        limit: limit.capacity,
        retryAfter: Math.ceil((tokens - bucket.tokens) / limit.refillRate * (limit.refillInterval / 1000))
      };
    }
  }
}

interface LocalBucket {
  tokens: number;
  lastRefill: number;
}
```

### 8. Monitoring

```typescript
interface MetricsCollector {
  recordRequest(limitName: string, allowed: boolean, latencyMs: number, cacheHit: boolean): void;
  recordStorageError(error: Error): void;
  recordCacheHit(hit: boolean): void;
}

const metrics = {
  requests_total: new Counter({
    name: 'rate_limit_requests_total',
    help: 'Total rate limit checks',
    labelNames: ['limit_name', 'allowed', 'cache_hit']
  }),
  
  check_duration_seconds: new Histogram({
    name: 'rate_limit_check_duration_seconds',
    help: 'Rate limit check latency',
    labelNames: ['limit_name', 'cache_hit'],
    buckets: [0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5]
  }),
  
  storage_errors_total: new Counter({
    name: 'rate_limit_storage_errors_total',
    help: 'Storage errors',
    labelNames: ['error_type']
  }),
  
  circuit_breaker_state: new Gauge({
    name: 'rate_limit_circuit_breaker_state',
    help: 'Circuit breaker state (0=closed, 1=open, 2=half_open)'
  }),
  
  active_keys: new Gauge({
    name: 'rate_limit_active_keys',
    help: 'Number of active rate limit keys'
  }),
  
  utilization_percent: new Histogram({
    name: 'rate_limit_utilization_percent',
    help: 'Token utilization distribution',
    labelNames: ['limit_name'],
    buckets: [10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 99]
  })
};
```

### 9. Error Handling

```typescript
class RateLimitError extends Error {
  constructor(
    message: string,
    public code: RateLimitErrorCode,
    public retryAfter?: number
  ) {
    super(message);
    this.name = 'RateLimitError';
  }
}

enum RateLimitErrorCode {
  STORAGE_UNAVAILABLE = 'STORAGE_UNAVAILABLE',
  INVALID_CONFIG = 'INVALID_CONFIG',
  INVALID_KEY = 'INVALID_KEY',
  INVALID_TOKEN_COST = 'INVALID_TOKEN_COST',
  STORAGE_TIMEOUT = 'STORAGE_TIMEOUT'
}
```

## Configuration Schema

```yaml
rate_limits:
  - name: api_global
    capacity: 10000
    refill_rate: 100
    refill_interval: 1000
    scope: global
    burst_allowance: 0
    priority: standard
    
  - name: api_per_user
    capacity: 1000
    refill_rate: 10
    refill_interval: 1000
    scope: per_user
    burst_allowance: 500
    priority: standard
    
  - name: login_attempts
    capacity: 5
    refill_rate: 1
    refill_interval: 60000
    scope: per_ip
    burst_allowance: 0
    priority: strict

storage:
  type: redis
  nodes:
    - host: redis-1.example.com
      port: 6379
    - host: redis-2.example.com
      port: 6379
  pool_size: 50
  connection_timeout_ms: 100
  operation_timeout_ms: 50
  enable_read_replicas: false

fallback:
  strategy: fail_open
  circuit_breaker:
    failure_threshold: 5
    failure_window_ms: 10000
    reset_timeout_ms: 30000
    half_open_max_attempts: 3
  local_only_config:
    capacity: 100
    refill_rate: 10

local_cache:
  enabled: true
  max_size: 10000
  ttl_ms: 1000
  accuracy_threshold: 20
  sync_on_denial: true

config_provider:
  type: static

monitoring:
  metrics_enabled: true
  prometheus_port: 9090
```

## Deployment Phases

### Phase 1: Production-Ready Core (Week 1-2)

**Objective**: Deploy a reliable, observable rate limiting system

**Features**:
- Token bucket with Redis backend
- Atomic Lua script
- Circuit breaker for resilience
- Comprehensive monitoring (Prometheus)
- Fail-open fallback
- Static configuration
- HTTP middleware
- Health checks with latency validation
- Admin API (resetLimit, addQuota)

**Success Criteria**:
- 10K req/sec per instance
- P99 latency <20ms
- Zero data loss during Redis failover
- Circuit breaker triggers within 10 seconds of Redis failure
- 99.9% availability

**Testing Requirements**:
- Load testing at 15K req/sec
- Chaos testing (Redis pod kills)
- Correctness validation (no over-limit requests)

### Phase 2: Performance Optimization (Week 3)

**Objective**: Scale to high-throughput workloads

**Features**:
- Local cache layer with opt-in priority system
- Cache accuracy monitoring
- Script pre-loading (EVALSHA)
- Connection pool tuning
- Utilization metrics and dashboard

**Success Criteria**:
- 200K req/sec per instance (with cache)
- P99 latency <2ms (cache hits)
- Cache divergence <2% measured across 24 hours
- Performance benchmarks documented

**Testing Requirements**:
- Cache accuracy tests (measure over-limit rate)
- High-concurrency stress tests
- Cache invalidation correctness tests

### Phase 3: Operational Features (Week 4)

**Objective**: Enable runtime operations and flexibility

**Features**:
- Dynamic configuration (optional, database-backed)
- Enhanced admin API (getUtilization, bulk operations)
- Variable token costs per operation
- Burst allowance tuning tools
- Operational runbooks

**Success Criteria**:
- Config updates applied within 60 seconds
- Admin API response time <100ms
- Zero downtime during config changes

### Phase 4: Multi-Region Support (Future)

**Objective**: Global deployment with regional accuracy

**Features**:
- Regional Redis clusters
- Cross-region aggregation (eventual consistency)
- Geolocation-aware routing
- Regional failover

**Deferred Until**:
- Traffic spans multiple geographic regions
- Regional latency >50ms impacts user experience
- Compliance requires data residency

## Rationale

### Phase 1 Must Include Admin API

**Decision**: Move `resetLimit` and `addQuota` into Phase 1.

**Reasoning**:
1. **Incident response**: Teams need ability to manually reset limits during incidents (e.g., false positive blocks)
2. **Testing**: QA needs to reset test user limits without Redis access
3. **Customer support**: Support teams may need to add quota credits
4. **Low complexity**: These operations are simple wrappers around storage calls
5. **Production expectation**: Any production rate limiter should support manual overrides

**Implementation**: Basic REST API with authentication.

### Enhanced Fallback Strategy

**Decision**: Add `local_only` fallback mode alongside `fail_open` and `fail_closed`.

**Reasoning**:
1. **Availability vs. abuse trade-off**: `fail_open` allows unlimited requests during outages; `fail_closed` breaks service
2. **Degraded enforcement**: Local buckets provide per-instance limits during Redis outages
3. **Better than nothing**: If Redis is down, 10K req/sec per instance (local) is better than unlimited
4. **Operational clarity**: Teams can choose the right trade-off for each limit

**Trade-offs**:
- Local buckets are per-instance, so global limit of 10K becomes 10K per pod
- Acceptable for short outages (<5 minutes) with circuit breaker auto-recovery

### Cache Sync on Denial

**Decision**: Add `syncOnDenial` config option to force backend check when cache denies.

**Reasoning**:
1. **Accuracy guarantee**: Eliminates false denials from stale cache
2. **User experience**: Avoids incorrectly blocking legitimate traffic
3. **Performance trade-off**: Only impacts requests near the limit
4. **Configurable**: Can disable for performance-critical, denial-tolerant scenarios

**When to enable**:
- User-facing APIs where false denials hurt UX
- Low denial rates (<5%)

**When to disable**:
- Internal APIs where denials are acceptable
- High denial rates (>20%) where backend would be overwhelmed

### Health Check with Latency Validation

**Decision**: Health check fails if Redis latency >100ms.

**Reasoning**:
1. **Prevent cascading failure**: Slow Redis causes request timeouts
2. **Load balancer signal**: K8s/ECS can route traffic away from pods with degraded Redis
3. **Observable degradation**: Metrics show health check failures before user impact
4. **Configurable threshold**: 100ms is reasonable default, can adjust per environment

### Static Config Remains Default

**Decision**: Keep static configuration as the recommended starting point.

**Reasoning**:
1. **YAGNI validation**: Architect correctly identified most systems don't need dynamic config
2. **Operational simplicity**: File-based config is easier to reason about, debug, and version control
3. **Clear migration path**: Teams can add dynamic provider later without breaking changes
4. **Performance**: No database dependency in hot path

**When to use dynamic**:
- Multi-tenant SaaS with per-customer limits
- Experimentation platform testing rate limit thresholds
- Incident response requires immediate limit adjustments across hundreds of services

### Utilization Metrics

**Decision**: Add `getUtilization` method to surface top consumers.

**Reasoning**:
1. **Capacity planning**: Identify which users/IPs are approaching limits
2. **Abuse detection**: Spot suspicious traffic patterns
3. **Alerting**: Trigger proactive outreach before limits are hit
4. **Sampling approach**: Avoid blocking KEYS command by sampling
5. **Operational value**: High ROI for minimal complexity

## What I Improved

1. **Phase 1 includes admin API**: Teams need `resetLimit` and `addQuota` for day-one operations
2. **Local-only fallback**: Degraded enforcement during outages balances availability and abuse protection
3. **Cache sync on denial**: Eliminates false denials from stale cache with configurable trade-off
4. **Health check latency validation**: Prevents slow Redis from causing cascading failures
5. **Utilization metrics**: Operational visibility into top consumers without performance impact
6. **Middleware header control**: `includeHeaders` flag allows disabling rate limit headers for internal APIs
7. **Replication lag monitoring**: Detect Redis replication issues before they impact accuracy
8. **Enhanced storage stats**: Additional operational metrics (replication lag, memory usage)

## What I Kept

1. **Phased implementation strategy**: Excellent approach to balance speed and quality
2. **Cache as opt-in**: Correct default-to-correctness philosophy
3. **Token bucket only**: Smart constraint to ensure quality over feature breadth
4. **Single-region first**: Appropriate deferral of complexity
5. **Circuit breaker design**: Robust implementation with half-open testing
6. **Lua script approach**: Atomicity without distributed transactions
7. **Static config default**: YAGNI principle correctly applied
8. **Comprehensive monitoring**: Production-grade observability from day one

## Remaining Considerations

1. **Admin API authentication**: Should use existing auth system or dedicated API keys?
2. **Utilization sampling size**: 100 samples balances accuracy and performance, but should this be configurable?
3. **Local bucket TTL**: How long should local buckets persist after Redis recovery? Currently unbounded.
4. **Cache memory bounds**: LocalCacheLayer uses LRU eviction, but should we add memory-based limits?
5. **Dynamic config propagation delay**: 60-second refresh interval means changes take up to 1 minute. Is this acceptable?

## Convergence Status

**ITERATING**: Identified key operational improvements for Phase 1 and enhanced fallback strategy. One more round recommended to validate admin API design and finalize cache behavior.

## PROMPT_FOR_ARCHITECT:

Please consider these specific improvements:

1. **Admin API scope**: I moved `resetLimit` and `addQuota` to Phase 1 for incident response. Should we add additional operations like `setLimit` (override capacity temporarily) or `inspectKey` (view current token count)? What authentication mechanism should we use?

2. **Local-only fallback**: The new `local_only` strategy provides per-instance limits during Redis outages. Does this strike the right balance between availability and abuse protection? Should we add cross-instance coordination (e.g., gossip protocol) or is per-instance acceptable?

3. **Cache sync-on-denial**: The `syncOnDenial` flag forces backend check when cache denies a request. This eliminates false denials but adds latency. Should this be enabled by default, or should teams explicitly opt in?

4. **Utilization metrics sampling**: Currently samples up to 100 keys to find top consumers. Is 100 the right limit, or should this be configurable? Should we cache utilization results to avoid repeated scans?

5. **Phase 1 testing**: Does the testing requirements section cover everything needed to validate correctness and performance before production? Should we add specific Redis failure scenarios (network partition, memory pressure)?

**Convergence Signal:** ITERATING

---

