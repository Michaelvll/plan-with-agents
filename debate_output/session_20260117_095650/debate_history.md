# Claude Code Debate Session

**Started:** 2026-01-17T09:56:50.123599
**Ended:** 2026-01-17T10:13:27.340882
**Status:** debating
**Rounds:** 4

## Initial Prompt

Design a rate limiting system for a REST API

Requirements:
- Multiple rate limit tiers (free, pro, enterprise)
- Support both user-level and IP-level limiting
- Handle burst traffic gracefully
- Provide clear feedback in headers
- Support distributed deployment
- Consider Redis-based implementation

---

## Round 1

### 🔵 Agent A

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture:**
1. **API Gateway Layer**: Request interception and rate limit enforcement
2. **Rate Limit Service**: Core limiting logic and state management
3. **Storage Layer**: Redis cluster for distributed state

```
Client Request → API Gateway → Rate Limit Service → Redis Cluster
                      ↓                                    ↓
                 Add Headers                         Token Buckets
                      ↓                                    ↓
                Upstream API ← (allow/deny) ← State Updates
```

## Core Components

### 1. Rate Limit Middleware (API Gateway)

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const identifier = extractIdentifier(request);
    const tier = await getTier(identifier);
    
    const result = await rateLimitService.checkAndConsume(
      identifier,
      tier,
      request.path,
      request.method
    );
    
    if (!result.allowed) {
      return new Response(429, {
        headers: buildRateLimitHeaders(result),
        body: { error: "Rate limit exceeded", retryAfter: result.retryAfter }
      });
    }
    
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result));
    return response;
  }
}
```

### 2. Rate Limit Service

```typescript
class RateLimitService {
  constructor(
    private redis: RedisCluster,
    private config: RateLimitConfig
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    method: string
  ): Promise<RateLimitResult> {
    const limits = this.config.getLimitsForTier(tier, path, method);
    const results = await Promise.all(
      limits.map(limit => this.checkLimit(identifier, limit))
    );
    
    // Return most restrictive result
    const blocked = results.find(r => !r.allowed);
    return blocked || results[0];
  }

  private async checkLimit(
    identifier: Identifier,
    limit: RateLimit
  ): Promise<RateLimitResult> {
    const key = buildRedisKey(identifier, limit.window);
    
    // Token bucket algorithm with burst support
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local burst = tonumber(ARGV[3])
      local requested = tonumber(ARGV[4])
      local now = tonumber(ARGV[5])
      
      local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
      local tokens = tonumber(bucket[1]) or capacity
      local last_update = tonumber(bucket[2]) or now
      
      -- Refill tokens based on elapsed time
      local elapsed = now - last_update
      local refilled = math.min(capacity + burst, tokens + (elapsed * refill_rate))
      
      if refilled >= requested then
        local new_tokens = refilled - requested
        redis.call('HMSET', key, 'tokens', new_tokens, 'last_update', now)
        redis.call('EXPIRE', key, 3600)
        return {1, new_tokens, capacity, refill_rate}
      else
        return {0, refilled, capacity, refill_rate}
      end
    `;
    
    const result = await this.redis.eval(script, [key], [
      limit.capacity,
      limit.refillRate,
      limit.burst,
      1, // requested tokens
      Date.now() / 1000
    ]);
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: this.calculateResetTime(result[1], result[3]),
      retryAfter: this.calculateRetryAfter(result[1], result[3])
    };
  }
}
```

### 3. Identifier Extraction

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'composite';
  userId?: string;
  ipAddress?: string;
  apiKey?: string;
}

function extractIdentifier(request: Request): Identifier {
  const apiKey = request.headers.get('X-API-Key');
  
  if (apiKey) {
    return {
      type: 'user',
      userId: decodeApiKey(apiKey).userId,
      apiKey: apiKey
    };
  }
  
  // Fallback to IP-based limiting
  const ip = getClientIP(request);
  return {
    type: 'ip',
    ipAddress: ip
  };
}

function getClientIP(request: Request): string {
  // Check proxy headers in order of preference
  return (
    request.headers.get('X-Forwarded-For')?.split(',')[0]?.trim() ||
    request.headers.get('X-Real-IP') ||
    request.socket.remoteAddress
  );
}
```

## Data Models

### Rate Limit Configuration

```typescript
interface RateLimitConfig {
  tiers: {
    free: TierConfig;
    pro: TierConfig;
    enterprise: TierConfig;
  };
}

interface TierConfig {
  global: RateLimit;
  byEndpoint?: Map<string, RateLimit>;
  burstMultiplier: number;
}

interface RateLimit {
  capacity: number;        // tokens in bucket
  refillRate: number;      // tokens per second
  window: number;          // sliding window in seconds
  burst: number;           // additional tokens for burst
}

// Example configuration
const config: RateLimitConfig = {
  tiers: {
    free: {
      global: {
        capacity: 100,
        refillRate: 100 / 3600,  // 100 per hour
        window: 3600,
        burst: 10
      },
      byEndpoint: new Map([
        ['/api/search', {
          capacity: 10,
          refillRate: 10 / 60,    // 10 per minute
          window: 60,
          burst: 2
        }]
      ]),
      burstMultiplier: 1.1
    },
    pro: {
      global: {
        capacity: 1000,
        refillRate: 1000 / 3600,  // 1000 per hour
        window: 3600,
        burst: 100
      },
      byEndpoint: new Map([
        ['/api/search', {
          capacity: 100,
          refillRate: 100 / 60,    // 100 per minute
          window: 60,
          burst: 20
        }]
      ]),
      burstMultiplier: 1.2
    },
    enterprise: {
      global: {
        capacity: 10000,
        refillRate: 10000 / 3600,
        window: 3600,
        burst: 1000
      },
      burstMultiplier: 1.5
    }
  }
};
```

### Redis Data Structure

```typescript
// Key pattern: ratelimit:{type}:{identifier}:{window}
// Example: ratelimit:user:user123:3600

// Hash structure:
{
  "tokens": "87.5",           // current tokens in bucket
  "last_update": "1704123456.789"  // last refill timestamp
}

// TTL: Set to window duration + buffer (e.g., 3600s + 300s)
```

## Response Headers

```typescript
interface RateLimitHeaders {
  'X-RateLimit-Limit': string;        // max requests per window
  'X-RateLimit-Remaining': string;    // remaining requests
  'X-RateLimit-Reset': string;        // unix timestamp when limit resets
  'X-RateLimit-Reset-After': string;  // seconds until reset
  'Retry-After': string;              // (on 429 only) seconds to wait
}

function buildRateLimitHeaders(result: RateLimitResult): RateLimitHeaders {
  return {
    'X-RateLimit-Limit': result.limit.toString(),
    'X-RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'X-RateLimit-Reset': result.resetAt.toString(),
    'X-RateLimit-Reset-After': Math.max(0, result.resetAt - Math.floor(Date.now() / 1000)).toString(),
    ...(result.retryAfter && { 'Retry-After': result.retryAfter.toString() })
  };
}
```

## Distributed Deployment

### Redis Cluster Configuration

```typescript
const redisCluster = new Redis.Cluster([
  { host: 'redis-node-1', port: 6379 },
  { host: 'redis-node-2', port: 6379 },
  { host: 'redis-node-3', port: 6379 }
], {
  redisOptions: {
    password: process.env.REDIS_PASSWORD,
    tls: {}
  },
  clusterRetryStrategy: (times) => Math.min(times * 100, 2000),
  enableReadyCheck: true,
  maxRetriesPerRequest: 3
});
```

### Consistency Guarantees

- **Lua scripts ensure atomicity**: Token bucket operations are atomic within Redis
- **No distributed locks needed**: Per-key operations avoid race conditions
- **Clock skew handling**: Use Redis TIME command for synchronized timestamps
- **Failover strategy**: Redis Sentinel for automatic failover

```typescript
// Clock synchronization
async function getRedisTime(): Promise<number> {
  const [seconds, microseconds] = await redis.time();
  return parseFloat(`${seconds}.${microseconds}`);
}
```

## Error Handling

### Circuit Breaker for Redis

```typescript
class CircuitBreaker {
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private failures = 0;
  private lastFailureTime = 0;
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > 30000) {
        this.state = 'HALF_OPEN';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }
    
    try {
      const result = await fn();
      if (this.state === 'HALF_OPEN') {
        this.state = 'CLOSED';
        this.failures = 0;
      }
      return result;
    } catch (error) {
      this.failures++;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= 5) {
        this.state = 'OPEN';
      }
      throw error;
    }
  }
}

// Fallback strategy when Redis is unavailable
class RateLimitServiceWithFallback {
  private circuitBreaker = new CircuitBreaker();
  
  async checkAndConsume(...args): Promise<RateLimitResult> {
    try {
      return await this.circuitBreaker.execute(
        () => this.rateLimitService.checkAndConsume(...args)
      );
    } catch (error) {
      logger.error('Rate limit check failed, allowing request', error);
      
      // Fail open: allow request but log for monitoring
      return {
        allowed: true,
        remaining: -1,  // indicates degraded mode
        limit: -1,
        resetAt: Date.now() / 1000 + 3600,
        retryAfter: null
      };
    }
  }
}
```

### Error Response Structure

```typescript
interface ErrorResponse {
  error: string;
  message: string;
  retryAfter?: number;
  documentation?: string;
  code: string;
}

// 429 Too Many Requests
{
  "error": "Rate limit exceeded",
  "message": "You have exceeded the rate limit for the free tier (100 requests per hour)",
  "retryAfter": 1847,
  "documentation": "https://api.example.com/docs/rate-limits",
  "code": "RATE_LIMIT_EXCEEDED"
}

// 503 Service Unavailable (Redis down)
{
  "error": "Rate limiting unavailable",
  "message": "Rate limiting service is temporarily unavailable. Your request was allowed.",
  "documentation": "https://api.example.com/docs/status",
  "code": "RATE_LIMIT_DEGRADED"
}
```

## Monitoring & Observability

```typescript
interface RateLimitMetrics {
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitLatency: Histogram;
  redisErrors: Counter;
  circuitBreakerState: Gauge;
  tokenBucketUtilization: Histogram;
}

// Emit metrics after each rate limit check
function recordMetrics(result: RateLimitResult, duration: number) {
  if (result.allowed) {
    metrics.requestsAllowed.inc({ tier: result.tier });
  } else {
    metrics.requestsBlocked.inc({ tier: result.tier });
  }
  
  metrics.rateLimitLatency.observe({ tier: result.tier }, duration);
  metrics.tokenBucketUtilization.observe(
    { tier: result.tier },
    result.remaining / result.limit
  );
}
```

## Burst Traffic Handling

The token bucket algorithm naturally handles bursts:

1. **Burst capacity**: Additional tokens beyond base capacity
2. **Refill rate**: Steady token regeneration prevents sustained abuse
3. **Example**: Free tier with 100 capacity + 10 burst
   - Can handle 110 immediate requests
   - Then limited to refill rate (100/hour = ~1 per 36 seconds)

```typescript
// Burst calculation
function calculateBurst(tier: TierConfig, baseCapacity: number): number {
  return Math.floor(baseCapacity * (tier.burstMultiplier - 1));
}
```

## Rationale

- **Token bucket algorithm**: Better than fixed/sliding window for handling bursts naturally while preventing sustained abuse
- **Lua scripts in Redis**: Ensures atomic operations without distributed locks, critical for correctness
- **Composite limiting**: Both user and IP limiting prevents abuse from compromised keys or distributed attacks
- **Fail-open circuit breaker**: Availability over strict rate limiting when Redis fails
- **Endpoint-specific limits**: Expensive operations (search, analytics) get tighter limits
- **Standard headers**: RateLimit-* headers follow draft RFC standards for client compatibility

## What I Changed

N/A - Initial design proposal

## What I Kept

N/A - Initial design proposal

## Open Questions

1. Should we support dynamic tier upgrades mid-request (e.g., user upgrades during high traffic)?
2. How to handle shared quotas for team/organization accounts?
3. Should there be separate read/write rate limits?
4. Cost-based limiting (e.g., expensive queries consume more tokens)?

## Convergence Status

**ITERATING** - This is the initial design and requires critical review before finalization.

## PROMPT_FOR_CRITIC:

Please focus on:
1. **Distributed correctness**: Are there race conditions or edge cases in the Redis token bucket implementation?
2. **Burst handling**: Does the burst capacity mechanism adequately protect against abuse while allowing legitimate spikes?
3. **Error handling**: Is the fail-open strategy appropriate, or should we fail-closed when Redis is unavailable?
4. **Performance**: Will the Lua script approach scale to high request volumes (100K+ req/s)?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Four-tier architecture:**
1. **API Gateway Layer**: Request interception and rate limit enforcement
2. **Rate Limit Service**: Core limiting logic with dual-algorithm support
3. **Storage Layer**: Redis cluster for distributed state + local cache
4. **Analytics Layer**: Metrics aggregation for anomaly detection

```
Client Request → API Gateway → Local Cache (read-through)
                      ↓              ↓
                Rate Limit ← Redis Cluster (authoritative)
                 Service          ↓
                      ↓       Metrics Stream
                 Enforce → Analytics Pipeline
                      ↓
                Upstream API
```

## Core Components

### 1. Rate Limit Middleware (API Gateway)

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const identifier = extractIdentifier(request);
    const tier = await getTier(identifier);
    const cost = calculateCost(request.path, request.method);
    
    const result = await rateLimitService.checkAndConsume(
      identifier,
      tier,
      request.path,
      request.method,
      cost
    );
    
    if (!result.allowed) {
      // Log rejection for analytics
      await analytics.recordRejection(identifier, tier, result.reason);
      
      return new Response(429, {
        headers: buildRateLimitHeaders(result),
        body: { 
          error: "Rate limit exceeded", 
          retryAfter: result.retryAfter,
          tier: tier,
          upgradeUrl: tier === 'free' ? '/upgrade' : undefined
        }
      });
    }
    
    // Async metric recording (non-blocking)
    analytics.recordAllowed(identifier, tier, cost).catch(err => 
      logger.warn('Metric recording failed', err)
    );
    
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result));
    return response;
  }
}
```

### 2. Rate Limit Service with Hybrid Approach

```typescript
class RateLimitService {
  constructor(
    private redis: RedisCluster,
    private localCache: LRUCache,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    method: string,
    cost: number = 1
  ): Promise<RateLimitResult> {
    const limits = this.config.getLimitsForTier(tier, path, method);
    
    // Check all applicable limits (global + endpoint-specific)
    const results = await Promise.all(
      limits.map(limit => this.checkLimit(identifier, limit, cost))
    );
    
    // Return most restrictive result
    const blocked = results.find(r => !r.allowed);
    return blocked || results[0];
  }

  private async checkLimit(
    identifier: Identifier,
    limit: RateLimit,
    cost: number
  ): Promise<RateLimitResult> {
    try {
      return await this.circuitBreaker.execute(async () => {
        // Try local cache first (eventually consistent, optimistic)
        const cached = this.localCache.get(this.getCacheKey(identifier, limit));
        if (cached && cached.remaining >= cost) {
          // Optimistic fast path - update local state
          cached.remaining -= cost;
          this.localCache.set(this.getCacheKey(identifier, limit), cached, 5000);
          
          // Async sync to Redis (fire-and-forget with retry)
          this.syncToRedis(identifier, limit, cost).catch(err =>
            logger.warn('Cache sync failed', err)
          );
          
          return {
            ...cached,
            allowed: true,
            source: 'cache'
          };
        }
        
        // Cache miss or insufficient tokens - check Redis (authoritative)
        return await this.checkRedis(identifier, limit, cost);
      });
    } catch (error) {
      // Circuit breaker open or Redis failure
      return this.handleFailure(identifier, limit, cost, error);
    }
  }

  private async checkRedis(
    identifier: Identifier,
    limit: RateLimit,
    cost: number
  ): Promise<RateLimitResult> {
    const key = buildRedisKey(identifier, limit.window);
    
    // Enhanced token bucket with cost support
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local burst = tonumber(ARGV[3])
      local requested = tonumber(ARGV[4])
      local now = tonumber(ARGV[5])
      local ttl = tonumber(ARGV[6])
      
      local bucket = redis.call('HMGET', key, 'tokens', 'last_update')
      local tokens = tonumber(bucket[1])
      local last_update = tonumber(bucket[2])
      
      -- Initialize if not exists
      if not tokens then
        tokens = capacity
        last_update = now
      end
      
      -- Refill tokens based on elapsed time
      local elapsed = math.max(0, now - last_update)
      local refilled = math.min(capacity + burst, tokens + (elapsed * refill_rate))
      
      if refilled >= requested then
        local new_tokens = refilled - requested
        redis.call('HSET', key, 'tokens', new_tokens, 'last_update', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Return: allowed, remaining, capacity, refill_rate, reset_at
        local reset_at = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, refill_rate, reset_at}
      else
        -- Update last_update even on rejection to prevent token accumulation
        redis.call('HSET', key, 'tokens', refilled, 'last_update', now)
        redis.call('EXPIRE', key, ttl)
        
        local reset_at = now + ((capacity - refilled + requested) / refill_rate)
        local retry_after = math.ceil((requested - refilled) / refill_rate)
        return {0, refilled, capacity, refill_rate, reset_at, retry_after}
      end
    `;
    
    const result = await this.redis.eval(script, [key], [
      limit.capacity,
      limit.refillRate,
      limit.burst,
      cost,
      await this.getRedisTime(), // Synchronized timestamp
      limit.window + 300  // TTL with buffer
    ]);
    
    const rateLimitResult = {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[4],
      retryAfter: result[5] || null,
      source: 'redis',
      reason: result[0] === 0 ? 'QUOTA_EXCEEDED' : null
    };
    
    // Update local cache
    this.localCache.set(
      this.getCacheKey(identifier, limit),
      rateLimitResult,
      5000 // 5 second TTL
    );
    
    return rateLimitResult;
  }
  
  private async getRedisTime(): Promise<number> {
    // Use Redis TIME for clock-synchronized timestamp across distributed nodes
    const [seconds, microseconds] = await this.redis.time();
    return parseFloat(`${seconds}.${(microseconds / 1000000).toFixed(6).substring(2)}`);
  }
  
  private handleFailure(
    identifier: Identifier,
    limit: RateLimit,
    cost: number,
    error: Error
  ): RateLimitResult {
    // Decision matrix for failure handling
    const failureMode = this.determineFailureMode(identifier, limit);
    
    if (failureMode === 'FAIL_CLOSED') {
      // Conservative: reject requests during outage
      return {
        allowed: false,
        remaining: 0,
        limit: limit.capacity,
        resetAt: Date.now() / 1000 + 60,
        retryAfter: 60,
        source: 'failsafe',
        reason: 'RATE_LIMIT_UNAVAILABLE'
      };
    } else {
      // Optimistic: allow with degraded tracking
      const degradedLimit = Math.floor(limit.capacity * 0.5); // 50% of normal
      
      return {
        allowed: true,
        remaining: degradedLimit,
        limit: degradedLimit,
        resetAt: Date.now() / 1000 + limit.window,
        retryAfter: null,
        source: 'degraded',
        reason: 'DEGRADED_MODE'
      };
    }
  }
  
  private determineFailureMode(
    identifier: Identifier,
    limit: RateLimit
  ): 'FAIL_OPEN' | 'FAIL_CLOSED' {
    // Fail closed for high-cost operations or untrusted sources
    if (limit.window < 60) {
      return 'FAIL_CLOSED'; // Tight limits = expensive operations
    }
    
    if (identifier.type === 'ip' && !identifier.userId) {
      return 'FAIL_CLOSED'; // Anonymous users = higher risk
    }
    
    // Fail open for authenticated users with generous limits
    return 'FAIL_OPEN';
  }
}
```

### 3. Enhanced Identifier Extraction with Composite Keys

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'composite';
  userId?: string;
  ipAddress?: string;
  apiKey?: string;
  fingerprint?: string; // Browser fingerprint for additional tracking
}

function extractIdentifier(request: Request): Identifier {
  const apiKey = request.headers.get('X-API-Key') || 
                 request.headers.get('Authorization')?.replace('Bearer ', '');
  
  const ip = getClientIP(request);
  const fingerprint = request.headers.get('X-Fingerprint');
  
  if (apiKey) {
    const decoded = decodeApiKey(apiKey);
    return {
      type: 'composite',
      userId: decoded.userId,
      ipAddress: ip,
      apiKey: apiKey,
      fingerprint: fingerprint
    };
  }
  
  // Fallback to IP-based limiting with fingerprint
  return {
    type: 'ip',
    ipAddress: ip,
    fingerprint: fingerprint
  };
}

function getClientIP(request: Request): string {
  // Check proxy headers with validation
  const forwardedFor = request.headers.get('X-Forwarded-For');
  if (forwardedFor) {
    const ip = forwardedFor.split(',')[0].trim();
    if (isValidIP(ip)) return ip;
  }
  
  const realIP = request.headers.get('X-Real-IP');
  if (realIP && isValidIP(realIP)) return realIP;
  
  return request.socket.remoteAddress || '0.0.0.0';
}

function isValidIP(ip: string): boolean {
  // Reject private/internal IPs in production
  if (process.env.NODE_ENV === 'production') {
    return !ip.match(/^(10|172\.(1[6-9]|2[0-9]|3[01])|192\.168)\./);
  }
  return true;
}
```

## Data Models

### Rate Limit Configuration with Cost Factors

```typescript
interface RateLimitConfig {
  tiers: {
    free: TierConfig;
    pro: TierConfig;
    enterprise: TierConfig;
  };
  costFactors: Map<string, number>; // endpoint -> cost multiplier
}

interface TierConfig {
  global: RateLimit;
  byEndpoint?: Map<string, RateLimit>;
  burstMultiplier: number;
}

interface RateLimit {
  capacity: number;        // tokens in bucket
  refillRate: number;      // tokens per second
  window: number;          // sliding window in seconds
  burst: number;           // additional tokens for burst (computed)
}

// Cost calculation
function calculateCost(path: string, method: string): number {
  const baseCost = 1;
  
  // Expensive operations cost more tokens
  const costFactors: Record<string, number> = {
    'POST /api/search': 3,
    'POST /api/analyze': 5,
    'GET /api/export': 10,
    'POST /api/batch': 20
  };
  
  const key = `${method} ${path}`;
  return costFactors[key] || baseCost;
}

// Enhanced configuration with cost awareness
const config: RateLimitConfig = {
  tiers: {
    free: {
      global: {
        capacity: 100,
        refillRate: 100 / 3600,  // 100 per hour
        window: 3600,
        burst: 10  // 10% burst capacity
      },
      byEndpoint: new Map([
        ['POST /api/search', {
          capacity: 20,          // 20 searches (at 3 cost = ~7 actual calls)
          refillRate: 20 / 60,   // 20 tokens per minute
          window: 60,
          burst: 5
        }]
      ]),
      burstMultiplier: 1.1
    },
    pro: {
      global: {
        capacity: 1000,
        refillRate: 1000 / 3600,
        window: 3600,
        burst: 200  // 20% burst
      },
      byEndpoint: new Map([
        ['POST /api/search', {
          capacity: 300,
          refillRate: 300 / 60,
          window: 60,
          burst: 60
        }]
      ]),
      burstMultiplier: 1.2
    },
    enterprise: {
      global: {
        capacity: 100000,
        refillRate: 100000 / 3600,
        window: 3600,
        burst: 50000  // 50% burst for high-volume customers
      },
      burstMultiplier: 1.5
    }
  },
  costFactors: new Map([
    ['POST /api/search', 3],
    ['POST /api/analyze', 5],
    ['GET /api/export', 10],
    ['POST /api/batch', 20]
  ])
};
```

### Redis Data Structure with Metadata

```typescript
// Key pattern: ratelimit:{type}:{identifier}:{window}:{endpoint_hash}
// Example: ratelimit:user:user123:3600:global
// Example: ratelimit:user:user123:60:search_endpoint

// Hash structure:
{
  "tokens": "87.5",                    // current tokens
  "last_update": "1704123456.789123",  // last refill timestamp (microsecond precision)
  "total_consumed": "1234",            // total tokens consumed (for analytics)
  "rejection_count": "5"               // times limit was hit (for abuse detection)
}

// TTL: window + 300 seconds buffer
// Additional analytics key for monitoring:
// ratelimit:metrics:{identifier}:{date} -> sorted set of {timestamp, cost}
```

## Response Headers (RFC 9110 compliant)

```typescript
interface RateLimitHeaders {
  'RateLimit-Limit': string;        // max requests per window
  'RateLimit-Remaining': string;    // remaining requests
  'RateLimit-Reset': string;        // unix timestamp when limit resets
  'Retry-After': string;            // (on 429 only) seconds to wait
  'X-RateLimit-Cost': string;       // cost of this request
  'X-RateLimit-Source': string;     // 'redis' | 'cache' | 'degraded'
}

function buildRateLimitHeaders(result: RateLimitResult): RateLimitHeaders {
  const headers: RateLimitHeaders = {
    'RateLimit-Limit': result.limit.toString(),
    'RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'RateLimit-Reset': result.resetAt.toString(),
    'X-RateLimit-Cost': result.cost?.toString() || '1',
    'X-RateLimit-Source': result.source
  };
  
  if (result.retryAfter) {
    headers['Retry-After'] = result.retryAfter.toString();
  }
  
  return headers;
}
```

## Distributed Deployment

### Redis Cluster with Sentinel

```typescript
const redisCluster = new Redis.Cluster([
  { host: 'redis-node-1', port: 6379 },
  { host: 'redis-node-2', port: 6379 },
  { host: 'redis-node-3', port: 6379 }
], {
  redisOptions: {
    password: process.env.REDIS_PASSWORD,
    tls: {
      rejectUnauthorized: true,
      ca: fs.readFileSync('/path/to/ca-cert.pem')
    },
    // Enable replica reads for lower latency (eventually consistent)
    enableReadyCheck: true,
    lazyConnect: false
  },
  clusterRetryStrategy: (times) => {
    if (times > 10) return null; // Stop retrying after 10 attempts
    return Math.min(times * 100, 2000);
  },
  enableReadyCheck: true,
  maxRetriesPerRequest: 3,
  // Optimize for rate limiting workload
  scaleReads: 'slave', // Read from replicas
  redisOptions: {
    // Connection pooling
    maxRetriesPerRequest: 2,
    enableOfflineQueue: false // Fail fast
  }
});

// Sentinel for high availability
const sentinelRedis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'mymaster',
  password: process.env.REDIS_PASSWORD,
  sentinelPassword: process.env.SENTINEL_PASSWORD
});
```

### Local Cache for Performance

```typescript
import LRU from 'lru-cache';

const localCache = new LRU<string, RateLimitResult>({
  max: 100000,  // 100k entries
  ttl: 5000,    // 5 second TTL
  updateAgeOnGet: false,
  updateAgeOnHas: false,
  // Evict stale entries
  ttlAutopurge: true
});
```

## Error Handling & Circuit Breaker

### Enhanced Circuit Breaker with Half-Open Testing

```typescript
class CircuitBreaker {
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private lastStateChange = Date.now();
  
  private readonly FAILURE_THRESHOLD = 5;
  private readonly SUCCESS_THRESHOLD = 3;
  private readonly OPEN_TIMEOUT = 30000;  // 30s
  private readonly HALF_OPEN_MAX_CALLS = 3;
  private halfOpenCalls = 0;
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastStateChange > this.OPEN_TIMEOUT) {
        this.transitionTo('HALF_OPEN');
      } else {
        throw new Error('Circuit breaker is OPEN - Redis unavailable');
      }
    }
    
    if (this.state === 'HALF_OPEN') {
      if (this.halfOpenCalls >= this.HALF_OPEN_MAX_CALLS) {
        throw new Error('Circuit breaker HALF_OPEN - max test calls reached');
      }
      this.halfOpenCalls++;
    }
    
    try {
      const result = await Promise.race([
        fn(),
        this.timeout(2000) // 2s timeout for Redis operations
      ]);
      
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure(error);
      throw error;
    }
  }
  
  private onSuccess(): void {
    this.failures = 0;
    
    if (this.state === 'HALF_OPEN') {
      this.successes++;
      if (this.successes >= this.SUCCESS_THRESHOLD) {
        this.transitionTo('CLOSED');
      }
    }
  }
  
  private onFailure(error: Error): void {
    this.failures++;
    this.lastFailureTime = Date.now();
    
    if (this.state === 'HALF_OPEN') {
      this.transitionTo('OPEN');
    } else if (this.failures >= this.FAILURE_THRESHOLD) {
      this.transitionTo('OPEN');
    }
    
    logger.error('Circuit breaker failure', {
      state: this.state,
      failures: this.failures,
      error: error.message
    });
  }
  
  private transitionTo(newState: 'CLOSED' | 'OPEN' | 'HALF_OPEN'): void {
    const oldState = this.state;
    this.state = newState;
    this.lastStateChange = Date.now();
    this.halfOpenCalls = 0;
    this.successes = 0;
    
    if (newState === 'CLOSED') {
      this.failures = 0;
    }
    
    logger.warn('Circuit breaker state change', {
      from: oldState,
      to: newState,
      failures: this.failures
    });
    
    // Emit metric
    metrics.circuitBreakerState.set({ state: newState }, 1);
  }
  
  private timeout(ms: number): Promise<never> {
    return new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Operation timed out')), ms)
    );
  }
  
  getState(): string {
    return this.state;
  }
}
```

## Monitoring & Analytics

```typescript
interface RateLimitMetrics {
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitLatency: Histogram;
  redisErrors: Counter;
  circuitBreakerState: Gauge;
  tokenBucketUtilization: Histogram;
  cacheHitRate: Counter;
  degradedModeRequests: Counter;
}

// Anomaly detection for abuse patterns
class AbuseDetector {
  private readonly REJECTION_THRESHOLD = 10; // 10 rejections in window
  private readonly WINDOW_MS = 60000; // 1 minute
  
  async checkForAbuse(identifier: Identifier): Promise<boolean> {
    const key = `abuse:${identifier.type}:${identifier.userId || identifier.ipAddress}`;
    
    const rejections = await redis.get(key);
    if (rejections && parseInt(rejections) >= this.REJECTION_THRESHOLD) {
      // Trigger alert or additional mitigation
      await this.handleAbuse(identifier);
      return true;
    }
    
    return false;
  }
  
  async recordRejection(identifier: Identifier): Promise<void> {
    const key = `abuse:${identifier.type}:${identifier.userId || identifier.ipAddress}`;
    
    await redis.multi()
      .incr(key)
      .expire(key, 60)
      .exec();
  }
  
  private async handleAbuse(identifier: Identifier): Promise<void> {
    logger.alert('Abuse detected', {
      type: identifier.type,
      userId: identifier.userId,
      ip: identifier.ipAddress
    });
    
    // Could trigger temporary ban, CAPTCHA requirement, etc.
    await redis.setex(
      `ban:${identifier.ipAddress}`,
      3600, // 1 hour ban
      'ABUSE_DETECTED'
    );
  }
}

// Metrics recording
function recordMetrics(
  result: RateLimitResult,
  duration: number,
  identifier: Identifier,
  tier: Tier
) {
  const labels = { tier, source: result.source };
  
  if (result.allowed) {
    metrics.requestsAllowed.inc(labels);
  } else {
    metrics.requestsBlocked.inc(labels);
    abuseDetector.recordRejection(identifier);
  }
  
  metrics.rateLimitLatency.observe(labels, duration);
  metrics.tokenBucketUtilization.observe(
    labels,
    result.remaining / result.limit
  );
  
  if (result.source === 'cache') {
    metrics.cacheHitRate.inc({ tier, hit: 'true' });
  } else if (result.source === 'redis') {
    metrics.cacheHitRate.inc({ tier, hit: 'false' });
  } else if (result.source === 'degraded') {
    metrics.degradedModeRequests.inc({ tier });
  }
}
```

## Security Enhancements

### API Key Validation & Rotation

```typescript
interface APIKeyMetadata {
  userId: string;
  tier: Tier;
  createdAt: number;
  expiresAt?: number;
  scopes: string[];
}

async function validateApiKey(apiKey: string): Promise<APIKeyMetadata | null> {
  // Check revocation list first (cached)
  const isRevoked = await cache.get(`revoked:${apiKey}`);
  if (isRevoked) {
    return null;
  }
  
  try {
    const decoded = jwt.verify(apiKey, process.env.JWT_SECRET);
    
    // Check expiration
    if (decoded.expiresAt && decoded.expiresAt < Date.now()) {
      return null;
    }
    
    return decoded as APIKeyMetadata;
  } catch (error) {
    logger.warn('API key validation failed', { error: error.message });
    return null;
  }
}

// Gradual key rotation
async function rotateApiKey(oldKey: string): Promise<string> {
  const metadata = await validateApiKey(oldKey);
  if (!metadata) throw new Error('Invalid API key');
  
  const newKey = generateApiKey(metadata);
  
  // Grace period: both keys work for 7 days
  await redis.setex(`key:rotation:${oldKey}`, 7 * 24 * 3600, newKey);
  
  return newKey;
}
```

### DDoS Mitigation Layer

```typescript
class DDoSProtection {
  private readonly SPIKE_THRESHOLD = 100; // 100x normal rate
  private readonly BASELINE_WINDOW = 300; // 5 min baseline
  
  async checkForDDoS(ip: string): Promise<boolean> {
    const currentRate = await this.getCurrentRate(ip);
    const baselineRate = await this.getBaselineRate(ip);
    
    if (currentRate > baselineRate * this.SPIKE_THRESHOLD) {
      logger.alert('Possible DDoS detected', { ip, currentRate, baselineRate });
      
      // Temporary aggressive rate limiting
      await this.applyEmergencyLimits(ip);
      return true;
    }
    
    return false;
  }
  
  private async applyEmergencyLimits(ip: string): Promise<void> {
    // Reduce limits to 1% for 10 minutes
    await redis.setex(
      `emergency:${ip}`,
      600,
      JSON.stringify({ limit: 10, window: 60 })
    );
  }
}
```

## Performance Optimizations

### Connection Pooling & Pipeline Batching

```typescript
class OptimizedRedisClient {
  private pipeline: Pipeline | null = null;
  private pipelineCommands = 0;
  private readonly MAX_PIPELINE_SIZE = 100;
  
  async batchOperation(
    operations: Array<() => Promise<any>>
  ): Promise<any[]> {
    const pipeline = this.redis.pipeline();
    
    operations.forEach(op => {
      // Execute operation in pipeline context
      op.call(pipeline);
    });
    
    const results = await pipeline.exec();
    return results.map(([err, result]) => {
      if (err) throw err;
      return result;
    });
  }
}

// Batch multiple rate limit checks
async function checkMultipleLimits(
  requests: Array<{ identifier: Identifier; limit: RateLimit }>
): Promise<RateLimitResult[]> {
  return await redisClient.batchOperation(
    requests.map(req => 
      () => checkLimit(req.identifier, req.limit)
    )
  );
}
```

## Rationale for Improvements

### 1. **Distributed Correctness (Addressed)**
- **Redis TIME command**: Eliminates clock skew across distributed nodes
- **Atomic Lua scripts**: All read-modify-write operations are atomic
- **Update on rejection**: Prevents token accumulation during sustained overload
- **TTL safety margin**: Prevents premature key expiration (window + 300s buffer)

### 2. **Burst Handling (Enhanced)**
- **Cost-based limiting**: Expensive operations consume proportionally more tokens
- **Dynamic burst calculation**: Scales with tier (10-50% additional capacity)
- **Per-endpoint limits**: Critical paths get dedicated quotas independent of global limits
- **Refill on rejection**: Updates timestamp even when blocked to prevent gaming

### 3. **Error Handling (Hybrid Approach)**
- **Context-aware failure mode**: Fail-closed for risky operations (anonymous + tight limits), fail-open for trusted users
- **Degraded mode with reduced limits**: When failing open, allow 50% of normal capacity
- **Enhanced circuit breaker**: Half-open state with success threshold prevents flapping
- **Timeout protection**: 2s timeout on Redis operations prevents cascade failures

### 4. **Performance (Optimized)**
- **Local LRU cache**: 5s TTL cache reduces Redis load by ~70% for hot keys
- **Async metric recording**: Non-blocking analytics prevents latency impact
- **Connection pooling**: Reuses connections efficiently
- **Read from replicas**: Offloads read traffic from master (eventual consistency acceptable)
- **Pipeline batching**: Reduces round trips for bulk operations

### 5. **Additional Improvements**
- **Abuse detection**: Tracks rejection patterns to identify malicious actors
- **Security hardening**: API key validation, rotation, DDoS protection layer
- **Cost awareness**: Different operations have different resource costs
- **Observability**: Comprehensive metrics for debugging and capacity planning

## What I Improved

1. **Race Condition Fix**: Added `last_update` update even on rejection to prevent token accumulation during sustained abuse
2. **Clock Synchronization**: Use Redis TIME command for distributed timestamp consistency
3. **Hybrid Failure Mode**: Context-aware fail-open vs fail-closed based on risk profile
4. **Local Caching**: Added LRU cache layer for 5s eventual consistency, dramatically reducing Redis load
5. **Cost-Based Limiting**: Expensive operations consume more tokens proportionally
6. **Enhanced Circuit Breaker**: Added half-open state with graduated recovery
7. **Timeout Protection**: 2s timeout on Redis operations to prevent hanging
8. **Abuse Detection**: Pattern recognition for malicious actors with automated mitigation
9. **Security Layer**: API key validation, rotation, and DDoS protection
10. **Performance Optimization**: Pipeline batching, replica reads, async metrics

## What I Kept

1. **Token bucket algorithm**: Superior for burst handling vs fixed/sliding window
2. **Lua scripts for atomicity**: Correct approach for distributed rate limiting
3. **Composite limiting**: Both user and IP limiting prevents various attack vectors
4. **Endpoint-specific limits**: Critical for protecting expensive operations
5. **Standard RateLimit headers**: Good for client compatibility
6. **Redis cluster architecture**: Appropriate for distributed deployment
7. **Tiered configuration**: Clear separation of free/pro/enterprise limits

## Remaining Concerns

1. **Cache Consistency**: 5s local cache means users could exceed limits by ~5% during high traffic if multiple gateway nodes have stale data. Acceptable trade-off for performance, but should be monitored.

2. **Redis Scripting Performance**: Lua scripts block the Redis event loop. At 100K+ req/s, should consider:
   - Pre-loading scripts with `SCRIPT LOAD`
   - Monitoring `SLOWLOG` for script execution time
   - Possible migration to Redis modules (e.g., RedisBloom) for >500K req/s

3. **Cost Model Complexity**: Maintaining accurate cost factors for endpoints requires governance. Could drift over time if not regularly audited.

4. **Degraded Mode Risk**: When Redis fails, degraded mode allows 50% capacity. Coordinated attack during outage could still overwhelm system. Consider additional layers (WAF, CDN rate limiting).

5. **Analytics Storage**: Current design stores metrics in Redis. For high-volume production (>1M req/s), should stream to dedicated analytics store (ClickHouse, TimescaleDB) to avoid memory pressure.

## Convergence Status

**ITERATING** - Substantial improvements made, but would benefit from architect's review of trade-offs.

## PROMPT_FOR_ARCHITECT:

Please review these specific design decisions:

1. **Local cache trade-off**: Is 5s TTL acceptable for ~5% potential overage during traffic spikes? Would you prefer tighter consistency or is performance gain worth it?

2. **Hybrid failure mode**: Do you agree with context-aware fail-open/fail-closed logic, or should we default to one strategy for simplicity?

3. **Cost-based limiting**: Is the added complexity of per-endpoint cost factors worth the improved resource protection, or would simpler per-endpoint limits suffice?

4. **Abuse detection placement**: Should abuse detection be in the rate limiter, or separated into a dedicated security service layer?

5. **Redis cluster vs Sentinel**: For initial deployment (<10K req/s), would Redis Sentinel be sufficient, or jump straight to cluster for future-proofing?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with clear separation of concerns:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket algorithm with atomic operations     │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (with 2s local cache)        ↓ (authoritative)    │
│  ┌──────────────┐              ┌─────────────────────┐     │
│  │  Local       │              │  Redis Primary      │     │
│  │  LRU Cache   │              │  + Read Replicas    │     │
│  └──────────────┘              └─────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Security                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Abuse       │  │  Audit       │     │
│  │  Collector   │  │  Detector    │  │  Logger      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limit Middleware (Gateway Layer)

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const startTime = performance.now();
    
    // Step 1: Extract and enrich identifier
    const identifier = await identifierResolver.resolve(request);
    
    // Step 2: Determine tier from identifier
    const tier = await tierResolver.getTier(identifier);
    
    // Step 3: Calculate request cost
    const cost = costCalculator.calculate(request.path, request.method);
    
    // Step 4: Check rate limits (this is the core operation)
    const result = await rateLimiter.checkAndConsume(
      identifier,
      tier,
      request.path,
      cost
    );
    
    // Step 5: Record metrics (non-blocking)
    const duration = performance.now() - startTime;
    metricsCollector.record(result, duration, identifier, tier).catch(
      err => logger.warn('Metric recording failed', { error: err })
    );
    
    // Step 6: Handle rejection
    if (!result.allowed) {
      return new Response(null, {
        status: 429,
        headers: buildRateLimitHeaders(result, cost),
        body: JSON.stringify({
          error: 'rate_limit_exceeded',
          message: 'Rate limit exceeded. Please retry after the specified time.',
          retryAfter: result.retryAfter,
          tier: tier,
          limit: result.limit,
          upgradeUrl: tier === 'free' ? '/api/upgrade' : undefined
        })
      });
    }
    
    // Step 7: Forward request with rate limit headers
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result, cost));
    
    return response;
  }
}
```

### 2. Rate Limiter Service (Core Logic)

```typescript
interface RateLimiter {
  checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult>;
}

class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private localCache: Cache,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    // Get all applicable limits for this request
    const limits = this.config.getLimits(tier, path);
    
    // Check all limits concurrently (global + endpoint-specific)
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost))
    );
    
    // Return the most restrictive result (first blocked or least remaining)
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    
    // Try local cache first (2s TTL for balance between performance and accuracy)
    const cached = this.localCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      // Only use cache if we have enough headroom (prevent overage)
      if (cached.remaining >= cost * 1.5) {
        return {
          ...cached,
          source: 'cache'
        };
      }
    }
    
    // Cache miss or insufficient tokens - check Redis (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost);
        
        // Update local cache with result
        this.localCache.set(cacheKey, result, 2000); // 2s TTL
        
        return result;
      });
    } catch (error) {
      // Circuit breaker open or Redis failure
      logger.error('Rate limit check failed', { 
        identifier, 
        limit: limit.name, 
        error 
      });
      
      // Use degraded mode
      return this.handleFailure(identifier, limit, error);
    }
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    
    // Token bucket algorithm with Redis Lua script for atomicity
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      
      -- Get current state (tokens, last_refill_time)
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      -- Calculate tokens to add based on elapsed time
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Check if we can consume
      if tokens >= cost then
        -- Consume tokens
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Return: allowed=1, remaining, limit, reset_time
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      else
        -- Insufficient tokens - still update refill time to prevent gaming
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Calculate retry delay
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        -- Return: allowed=0, remaining, limit, reset_time, retry_after
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const now = await this.getRedisTime();
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60 // TTL with 1min buffer
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: 'redis',
      expiresAt: now + 2000 // For local cache
    };
  }
  
  private async getRedisTime(): Promise<number> {
    // Use Redis TIME for clock synchronization
    const [seconds, microseconds] = await this.redis.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private handleFailure(
    identifier: Identifier,
    limit: LimitConfig,
    error: Error
  ): RateLimitResult {
    // Simple fail-open for read operations, fail-closed for writes
    const isWriteOperation = limit.scope === 'write';
    
    if (isWriteOperation) {
      // Fail closed - reject the request
      return {
        allowed: false,
        remaining: 0,
        limit: limit.capacity,
        resetAt: Date.now() + 60000,
        retryAfter: 60,
        source: 'failsafe',
        expiresAt: Date.now() + 60000
      };
    } else {
      // Fail open - allow with warning
      return {
        allowed: true,
        remaining: limit.capacity * 0.5,
        limit: limit.capacity,
        resetAt: Date.now() + limit.windowSeconds * 1000,
        retryAfter: null,
        source: 'degraded',
        expiresAt: Date.now() + 2000
      };
    }
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
}
```

### 3. Identifier Resolution

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'apikey';
  key: string;
  userId?: string;
  ipAddress?: string;
}

class IdentifierResolver {
  async resolve(request: Request): Promise<Identifier> {
    // Priority: API Key > User Session > IP Address
    
    // 1. Check for API key
    const apiKey = this.extractApiKey(request);
    if (apiKey) {
      const validated = await this.validateApiKey(apiKey);
      if (validated) {
        return {
          type: 'apikey',
          key: validated.keyId,
          userId: validated.userId,
          ipAddress: this.getClientIP(request)
        };
      }
    }
    
    // 2. Check for authenticated user session
    const userId = await this.getUserFromSession(request);
    if (userId) {
      return {
        type: 'user',
        key: userId,
        userId: userId,
        ipAddress: this.getClientIP(request)
      };
    }
    
    // 3. Fallback to IP-based limiting
    const ip = this.getClientIP(request);
    return {
      type: 'ip',
      key: ip,
      ipAddress: ip
    };
  }
  
  private extractApiKey(request: Request): string | null {
    // Check Authorization header
    const authHeader = request.headers.get('Authorization');
    if (authHeader?.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    
    // Check X-API-Key header
    return request.headers.get('X-API-Key');
  }
  
  private getClientIP(request: Request): string {
    // Trust proxy headers in production with validation
    const forwardedFor = request.headers.get('X-Forwarded-For');
    if (forwardedFor) {
      const ips = forwardedFor.split(',').map(ip => ip.trim());
      // Return leftmost IP (original client)
      return ips[0];
    }
    
    const realIP = request.headers.get('X-Real-IP');
    if (realIP) return realIP;
    
    return request.socket.remoteAddress || '0.0.0.0';
  }
  
  private async validateApiKey(apiKey: string): Promise<{keyId: string, userId: string} | null> {
    // Implementation depends on your auth system
    // Should verify signature and check revocation
    return await apiKeyService.validate(apiKey);
  }
  
  private async getUserFromSession(request: Request): Promise<string | null> {
    // Extract from session cookie or JWT
    return await sessionService.getUserId(request);
  }
}
```

### 4. Configuration Model

```typescript
interface RateLimitConfig {
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
}

interface TierConfig {
  name: string;
  limits: LimitConfig[];
}

interface LimitConfig {
  name: string;           // e.g., "global", "search_endpoint"
  scope: 'read' | 'write'; // For failure mode decisions
  capacity: number;       // Max tokens in bucket
  refillRate: number;     // Tokens per second
  windowSeconds: number;  // Time window for the limit
  appliesTo?: string[];   // Specific paths (if endpoint-specific)
}

interface EndpointConfig {
  pattern: string;        // e.g., "/api/search"
  method?: string;
  baseCost: number;       // Cost multiplier
}

// Example configuration
const config: RateLimitConfig = {
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,  // 100 per hour
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',
          capacity: 10,
          refillRate: 10 / 60,     // 10 per minute
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 3600,   // 20 per hour
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 60,
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 500,
          refillRate: 500 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600
        }
      ]
    }
  },
  endpoints: [
    { pattern: '/api/search', method: 'POST', baseCost: 3 },
    { pattern: '/api/analyze', method: 'POST', baseCost: 5 },
    { pattern: '/api/export', method: 'GET', baseCost: 10 },
    { pattern: '/api/batch', method: 'POST', baseCost: 20 }
  ]
};

class ConfigManager {
  getLimits(tier: string, path: string): LimitConfig[] {
    const tierConfig = config.tiers[tier];
    if (!tierConfig) {
      throw new Error(`Unknown tier: ${tier}`);
    }
    
    // Return limits that apply to this path
    return tierConfig.limits.filter(limit => {
      if (!limit.appliesTo) return true; // Global limit
      return limit.appliesTo.some(pattern => this.matchPath(pattern, path));
    });
  }
  
  private matchPath(pattern: string, path: string): boolean {
    // Simple prefix matching (can be enhanced with regex)
    return path.startsWith(pattern);
  }
}
```

### 5. Cost Calculator

```typescript
class CostCalculator {
  constructor(private config: RateLimitConfig) {}
  
  calculate(path: string, method: string): number {
    const endpoint = this.config.endpoints.find(e => 
      path.startsWith(e.pattern) && 
      (!e.method || e.method === method)
    );
    
    return endpoint?.baseCost || 1;
  }
}
```

### 6. Circuit Breaker (Simplified)

```typescript
class CircuitBreaker {
  private failures = 0;
  private lastFailureTime = 0;
  private state: 'CLOSED' | 'OPEN' = 'CLOSED';
  
  private readonly FAILURE_THRESHOLD = 5;
  private readonly TIMEOUT_MS = 30000; // 30s
  private readonly OPERATION_TIMEOUT_MS = 2000; // 2s per operation
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.TIMEOUT_MS) {
        // Try to recover
        this.state = 'CLOSED';
        this.failures = 0;
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT_MS);
      this.failures = 0; // Reset on success
      return result;
    } catch (error) {
      this.failures++;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD) {
        this.state = 'OPEN';
        logger.error('Circuit breaker opened', { failures: this.failures });
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
}
```

### 7. Response Headers (Standards-Compliant)

```typescript
function buildRateLimitHeaders(
  result: RateLimitResult,
  cost: number
): Record<string, string> {
  const headers: Record<string, string> = {
    'RateLimit-Limit': result.limit.toString(),
    'RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'RateLimit-Reset': Math.ceil(result.resetAt / 1000).toString(),
  };
  
  // Add cost header for transparency
  if (cost > 1) {
    headers['X-RateLimit-Cost'] = cost.toString();
  }
  
  // Add retry-after on 429 responses
  if (!result.allowed && result.retryAfter) {
    headers['Retry-After'] = result.retryAfter.toString();
  }
  
  return headers;
}
```

## Deployment Architecture

### Redis Setup

**For initial deployment (<10K req/s): Redis with Sentinel**

```typescript
// Primary + 2 replicas with Sentinel for automatic failover
const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'ratelimit-primary',
  sentinelPassword: process.env.SENTINEL_PASSWORD,
  password: process.env.REDIS_PASSWORD,
  db: 0,
  // Connection settings
  connectTimeout: 5000,
  maxRetriesPerRequest: 2,
  enableReadyCheck: true,
  enableOfflineQueue: false, // Fail fast
});
```

**For scale (>50K req/s): Redis Cluster**

```typescript
const redis = new Redis.Cluster([
  { host: 'redis-1', port: 6379 },
  { host: 'redis-2', port: 6379 },
  { host: 'redis-3', port: 6379 }
], {
  redisOptions: {
    password: process.env.REDIS_PASSWORD,
    connectTimeout: 5000
  },
  clusterRetryStrategy: (times) => Math.min(times * 100, 2000)
});
```

### Local Cache

```typescript
import { LRUCache } from 'lru-cache';

const localCache = new LRUCache<string, RateLimitResult>({
  max: 50000,        // 50K entries (adjust based on memory)
  ttl: 2000,         // 2s TTL (balance between accuracy and performance)
  updateAgeOnGet: false,
  updateAgeOnHas: false
});
```

## Observability

### Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Cache metrics
  cacheHits: Counter;
  cacheMisses: Counter;
  
  // Error metrics
  redisErrors: Counter;
  circuitBreakerState: Gauge;
  
  // Business metrics
  tokenBucketUtilization: Histogram;
}

class MetricsCollector {
  async record(
    result: RateLimitResult,
    duration: number,
    identifier: Identifier,
    tier: string
  ): Promise<void> {
    const labels = { tier, source: result.source, type: identifier.type };
    
    if (result.allowed) {
      this.metrics.requestsAllowed.inc(labels);
    } else {
      this.metrics.requestsBlocked.inc(labels);
    }
    
    this.metrics.rateLimitCheckDuration.observe(labels, duration);
    
    // Utilization: how full is the bucket?
    const utilization = 1 - (result.remaining / result.limit);
    this.metrics.tokenBucketUtilization.observe(labels, utilization);
    
    // Cache performance
    if (result.source === 'cache') {
      this.metrics.cacheHits.inc(labels);
    } else if (result.source === 'redis') {
      this.metrics.cacheMisses.inc(labels);
    }
  }
}
```

### Abuse Detection (Separate Service)

```typescript
class AbuseDetector {
  private readonly REJECTION_WINDOW_SEC = 60;
  private readonly REJECTION_THRESHOLD = 20;
  
  async checkForAbuse(identifier: Identifier): Promise<boolean> {
    const key = `abuse:${identifier.type}:${identifier.key}`;
    
    const rejections = await redis.get(key);
    if (rejections && parseInt(rejections) >= this.REJECTION_THRESHOLD) {
      logger.alert('Abuse pattern detected', {
        identifierType: identifier.type,
        identifierKey: identifier.key,
        rejections: rejections
      });
      return true;
    }
    
    return false;
  }
  
  async recordRejection(identifier: Identifier): Promise<void> {
    const key = `abuse:${identifier.type}:${identifier.key}`;
    
    await redis.multi()
      .incr(key)
      .expire(key, this.REJECTION_WINDOW_SEC)
      .exec();
  }
}
```

## Security Considerations

### IP Validation

```typescript
class IPValidator {
  validate(ip: string): boolean {
    // Reject obviously invalid IPs
    if (ip === '0.0.0.0' || !ip) return false;
    
    // In production, reject private IPs from X-Forwarded-For
    if (process.env.NODE_ENV === 'production') {
      if (this.isPrivateIP(ip)) {
        logger.warn('Private IP in X-Forwarded-For', { ip });
        return false;
      }
    }
    
    return true;
  }
  
  private isPrivateIP(ip: string): boolean {
    return /^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)/.test(ip);
  }
}
```

### API Key Management

```typescript
// API keys should be:
// 1. Hashed in database (never store plaintext)
// 2. Include revocation check (fast cache lookup)
// 3. Have expiration dates
// 4. Be rotatable without downtime

async function validateApiKey(apiKey: string): Promise<ValidationResult> {
  // Check revocation cache first (fast path)
  const isRevoked = await cache.get(`revoked:${apiKey}`);
  if (isRevoked) {
    return { valid: false, reason: 'revoked' };
  }
  
  // Verify signature and decode
  try {
    const decoded = await verifyJWT(apiKey, process.env.API_KEY_SECRET);
    
    // Check expiration
    if (decoded.exp && decoded.exp < Date.now() / 1000) {
      return { valid: false, reason: 'expired' };
    }
    
    return { 
      valid: true, 
      keyId: decoded.kid,
      userId: decoded.sub,
      tier: decoded.tier
    };
  } catch (error) {
    return { valid: false, reason: 'invalid_signature' };
  }
}
```

## Rationale

### 1. **Simplified Architecture**
- **Three clear layers**: Gateway (routing), Core (limiting logic), Observability (metrics/security)
- **Removed complex abstractions**: No analytics pipeline, no DDoS layer - these are separate concerns
- **Single responsibility**: Rate limiter does rate limiting, not abuse detection or security

### 2. **2-Second Cache TTL (Not 5 Seconds)**
- **Lower overage risk**: With 2s TTL, maximum overage is ~2% (vs 5% with 5s)
- **Still performant**: 2s is enough to absorb traffic spikes and reduce Redis load by 60-70%
- **Better consistency**: Shorter window means users see limits update faster
- **Conservative approach**: Only use cache when we have 1.5x headroom to prevent edge cases

### 3. **Simplified Failure Mode**
- **Read vs Write distinction**: Simple, clear rule everyone understands
- **No complex risk scoring**: Context-aware logic adds cognitive overhead and maintenance burden
- **Predictable behavior**: Developers know what to expect during outages
- **Write operations fail-closed**: Protects data integrity and expensive operations
- **Read operations fail-open**: Maintains availability for queries

### 4. **Cost-Based Limiting with Clear Trade-off**
- **Keep it**: Cost factors are essential for protecting expensive operations (searches, exports, batch jobs)
- **Simplify governance**: Cost factors live in config, are version-controlled, and have clear ownership
- **Monitor drift**: Expose cost factors in metrics to track if they need adjustment
- **Alternative**: Per-endpoint limits alone don't capture resource usage (1 batch = 1 search in simple model)

### 5. **Abuse Detection as Separate Service**
- **Clear separation**: Rate limiting ≠ security/abuse detection
- **Different scaling needs**: Abuse detection needs ML, historical analysis, threat intel
- **Different team ownership**: Security team owns abuse detection, platform team owns rate limiting
- **Async operation**: Abuse detector reads rate limit rejection metrics, doesn't block requests

### 6. **Redis Sentinel for Initial Deployment**
- **Start simple**: Sentinel is operationally simpler than Cluster (no sharding, no hash slots)
- **Sufficient capacity**: Sentinel handles 10K-50K req/s easily with proper hardware
- **Easier debugging**: Single master means no shard routing issues
- **Migration path**: Can migrate to Cluster later without changing application code
- **Cost-effective**: 3 nodes (1 primary + 2 replicas) vs 6+ for cluster minimum

### 7. **Token Bucket Algorithm Improvements**
- **Update refill time on rejection**: Prevents users from "saving up" rejections to game the system
- **Redis TIME command**: Ensures clock sync across distributed API gateway nodes
- **Atomic Lua scripts**: All read-modify-write operations in single transaction
- **TTL safety margin**: window + 60s prevents premature expiration during clock drift

### 8. **Simplified Circuit Breaker**
- **Removed half-open state**: Adds complexity, and in practice either Redis works or it doesn't
- **Fast recovery**: 30s timeout means system recovers quickly when Redis comes back
- **Per-operation timeout**: 2s timeout prevents cascade failures from slow Redis operations
- **Binary state**: Either OPEN (fail fast) or CLOSED (try Redis)

## What I Changed

1. **Reduced cache TTL from 5s → 2s**: Better consistency with minimal performance impact
2. **Simplified failure mode to read/write**: Removed complex context-aware logic
3. **Moved abuse detection to separate service**: Clear separation of concerns
4. **Recommended Sentinel over Cluster initially**: Simpler operations, sufficient capacity
5. **Simplified circuit breaker**: Removed half-open state, kept essential functionality
6. **Removed analytics pipeline**: Over-engineering for initial deployment
7. **Removed DDoS protection layer**: Should be handled at network edge (CDN/WAF)
8. **Simplified identifier resolution**: Clear priority order, no fingerprinting complexity
9. **Clearer configuration model**: Explicit read/write scopes for limits
10. **Conservative cache usage**: Only use cache when 1.5x headroom available

## What I Kept

1. **Token bucket algorithm**: Superior burst handling
2. **Atomic Lua scripts**: Correct distributed rate limiting
3. **Redis TIME for clock sync**: Eliminates distributed clock skew
4. **Cost-based limiting**: Essential for resource protection
5. **Multi-tier limiting (global + endpoint)**: Protects both overall and specific resources
6. **Local cache layer**: Significant performance improvement
7. **Standards-compliant headers**: Good client compatibility
8. **Composite identifier (user + IP)**: Prevents various attack vectors
9. **Circuit breaker pattern**: Prevents cascade failures
10. **Comprehensive metrics**: Essential for operations

## Open Questions

1. **Cache headroom factor**: Is 1.5x the right threshold for using cache, or should it be 2x for more conservative behavior?

2. **Cost factor governance**: Who owns the cost factors? How often should they be audited? Should there be automated alerts when an endpoint's cost seems misaligned with its actual resource usage?

3. **Failure mode for mixed operations**: Some endpoints read and write (e.g., GET with side effects, POST that's mostly reads). Should we add a third category or force classification?

4. **Migration strategy**: If we start with Sentinel and later need Cluster, what's the zero-downtime migration path?

5. **Burst handling during cache**: With local cache + 1.5x headroom check, are we effectively giving users a burst capacity they didn't pay for?

## Convergence Status

**ITERATING** - First iteration with significant simplifications, needs architect review.

## PROMPT_FOR_CRITIC:

Focus your review on these key architectural decisions:

1. **2s cache TTL**: Is this the right balance between performance and consistency? Would you prefer 1s (more accurate) or 3s (more performant)?

2. **Read/write failure mode**: Is this distinction too simplistic? Should we have a middle category (e.g., "read-with-side-effects")?

3. **Abuse detection separation**: Do you agree this should be a separate service, or is there value in tight coupling with rate limiter?

4. **Sentinel recommendation**: For <10K req/s, would you start with Sentinel or jump straight to Cluster for future-proofing?

5. **Cost governance**: How would you handle the operational burden of maintaining accurate cost factors as the API evolves?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with enhanced reliability and observability:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket algorithm with atomic operations     │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  │  • Adaptive degradation with health scoring          │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (1s local cache)             ↓ (authoritative)    │
│  ┌──────────────┐              ┌─────────────────────┐     │
│  │  Local       │              │  Redis Sentinel     │     │
│  │  LRU Cache   │              │  Primary + Replicas │     │
│  └──────────────┘              └─────────────────────┘     │
│         ↓ (fallback tracking)                               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Degradation State Manager                           │   │
│  │  • Per-identifier health scores                      │   │
│  │  • Probabilistic allowance during outages            │   │
│  │  • Recovery tracking and gradual restoration         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Operations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Audit       │  │  Config      │     │
│  │  Collector   │  │  Logger      │  │  Hot Reload  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limit Middleware (Gateway Layer)

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const startTime = performance.now();
    
    // Step 1: Extract and enrich identifier
    const identifier = await identifierResolver.resolve(request);
    
    // Step 2: Determine tier from identifier
    const tier = await tierResolver.getTier(identifier);
    
    // Step 3: Calculate request cost
    const cost = costCalculator.calculate(request.path, request.method, request);
    
    // Step 4: Check rate limits (this is the core operation)
    const result = await rateLimiter.checkAndConsume(
      identifier,
      tier,
      request.path,
      cost
    );
    
    // Step 5: Record metrics (non-blocking, with error suppression)
    const duration = performance.now() - startTime;
    setImmediate(() => {
      metricsCollector.record(result, duration, identifier, tier, cost)
        .catch(err => logger.debug('Metric recording failed', { error: err.message }));
    });
    
    // Step 6: Handle rejection
    if (!result.allowed) {
      // Audit high-value rejections asynchronously
      if (tier === 'enterprise' || tier === 'pro') {
        setImmediate(() => {
          auditLogger.logRejection(identifier, tier, request.path, result)
            .catch(err => logger.debug('Audit logging failed', { error: err.message }));
        });
      }
      
      return new Response(null, {
        status: 429,
        headers: buildRateLimitHeaders(result, cost),
        body: JSON.stringify({
          error: 'rate_limit_exceeded',
          message: 'Rate limit exceeded. Please retry after the specified time.',
          retryAfter: result.retryAfter,
          tier: tier,
          limit: result.limit,
          upgradeUrl: tier === 'free' ? '/api/upgrade' : undefined
        })
      });
    }
    
    // Step 7: Forward request with rate limit headers
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result, cost));
    
    return response;
  }
}
```

### 2. Rate Limiter Service (Enhanced Core Logic)

```typescript
interface RateLimiter {
  checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult>;
}

class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private localCache: Cache,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker,
    private degradationManager: DegradationStateManager
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    // Get all applicable limits for this request
    const limits = this.config.getLimits(tier, path);
    
    // Check all limits concurrently (global + endpoint-specific)
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost, path))
    );
    
    // Return the most restrictive result (first blocked or least remaining)
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    path: string
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    
    // Try local cache first (1s TTL for better accuracy)
    const cached = this.localCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      // Only use cache if we have enough headroom (prevent overage)
      // Use 2x headroom for conservative behavior
      if (cached.remaining >= cost * 2) {
        return {
          ...cached,
          source: 'cache'
        };
      }
    }
    
    // Cache miss or insufficient tokens - check Redis (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost);
        
        // Update local cache with result (1s TTL)
        this.localCache.set(cacheKey, result, 1000);
        
        // Update health score on success
        this.degradationManager.recordSuccess(identifier, limit);
        
        return result;
      });
    } catch (error) {
      // Circuit breaker open or Redis failure
      logger.error('Rate limit check failed', { 
        identifier, 
        limit: limit.name, 
        error: error.message,
        path
      });
      
      // Update health score on failure
      this.degradationManager.recordFailure(identifier, limit);
      
      // Use adaptive degradation mode
      return this.handleFailureWithDegradation(identifier, limit, cost, error);
    }
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    
    // Token bucket algorithm with Redis Lua script for atomicity
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      
      -- Get current state (tokens, last_refill_time)
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      -- Calculate tokens to add based on elapsed time
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Check if we can consume
      if tokens >= cost then
        -- Consume tokens
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Return: allowed=1, remaining, limit, reset_time
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      else
        -- Insufficient tokens - still update refill time to prevent gaming
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Calculate retry delay
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        -- Return: allowed=0, remaining, limit, reset_time, retry_after
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const now = await this.getRedisTime();
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60 // TTL with 1min buffer
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: 'redis',
      expiresAt: now + 1000 // For local cache (1s)
    };
  }
  
  private async getRedisTime(): Promise<number> {
    // Use Redis TIME for clock synchronization
    const [seconds, microseconds] = await this.redis.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private handleFailureWithDegradation(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    error: Error
  ): RateLimitResult {
    // Get health score for this identifier+limit combination
    const health = this.degradationManager.getHealthScore(identifier, limit);
    
    // Calculate allowance probability based on health and limit type
    const baseAllowance = limit.scope === 'write' ? 0.1 : 0.7; // 10% writes, 70% reads
    const tierMultiplier = this.getTierMultiplier(identifier.tier);
    const allowanceProbability = baseAllowance * tierMultiplier * health;
    
    // Probabilistic decision
    const allowed = Math.random() < allowanceProbability;
    
    const now = Date.now();
    return {
      allowed,
      remaining: allowed ? limit.capacity * 0.3 : 0, // Conservative estimate
      limit: limit.capacity,
      resetAt: now + limit.windowSeconds * 1000,
      retryAfter: allowed ? null : 60,
      source: 'degraded',
      degradationReason: error.message,
      healthScore: health,
      expiresAt: now + 1000
    };
  }
  
  private getTierMultiplier(tier?: string): number {
    // Higher-tier customers get better treatment during degradation
    switch (tier) {
      case 'enterprise': return 1.0;
      case 'pro': return 0.8;
      case 'free': return 0.6;
      default: return 0.5; // Unknown/IP-based
    }
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
}
```

### 3. Degradation State Manager (NEW)

```typescript
interface HealthState {
  successCount: number;
  failureCount: number;
  lastUpdate: number;
  score: number; // 0.0 to 1.0
}

class DegradationStateManager {
  private healthStates = new LRUCache<string, HealthState>({
    max: 10000,
    ttl: 300000, // 5 minutes
  });
  
  private readonly DECAY_FACTOR = 0.95;
  private readonly SUCCESS_WEIGHT = 0.1;
  private readonly FAILURE_WEIGHT = 0.3;
  
  recordSuccess(identifier: Identifier, limit: LimitConfig): void {
    const key = this.getKey(identifier, limit);
    const state = this.healthStates.get(key) || this.getInitialState();
    
    state.successCount++;
    state.lastUpdate = Date.now();
    
    // Gradual recovery: increase score by small amount
    state.score = Math.min(1.0, state.score + this.SUCCESS_WEIGHT);
    
    this.healthStates.set(key, state);
  }
  
  recordFailure(identifier: Identifier, limit: LimitConfig): void {
    const key = this.getKey(identifier, limit);
    const state = this.healthStates.get(key) || this.getInitialState();
    
    state.failureCount++;
    state.lastUpdate = Date.now();
    
    // Rapid degradation: decrease score by larger amount
    state.score = Math.max(0.0, state.score - this.FAILURE_WEIGHT);
    
    this.healthStates.set(key, state);
  }
  
  getHealthScore(identifier: Identifier, limit: LimitConfig): number {
    const key = this.getKey(identifier, limit);
    const state = this.healthStates.get(key);
    
    if (!state) {
      return 1.0; // Assume healthy until proven otherwise
    }
    
    // Apply time-based decay (old failures don't count as much)
    const age = Date.now() - state.lastUpdate;
    const decayMultiplier = Math.pow(this.DECAY_FACTOR, age / 1000); // Per second
    
    return Math.min(1.0, state.score + (1.0 - state.score) * (1 - decayMultiplier));
  }
  
  private getKey(identifier: Identifier, limit: LimitConfig): string {
    return `health:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private getInitialState(): HealthState {
    return {
      successCount: 0,
      failureCount: 0,
      lastUpdate: Date.now(),
      score: 1.0
    };
  }
  
  // Observability: export health metrics
  getMetrics(): HealthMetrics {
    const allStates = Array.from(this.healthStates.entries());
    const unhealthy = allStates.filter(([_, state]) => state.score < 0.5);
    
    return {
      totalTracked: allStates.length,
      unhealthyCount: unhealthy.length,
      averageScore: allStates.reduce((sum, [_, s]) => sum + s.score, 0) / allStates.length,
      worstScores: allStates
        .sort((a, b) => a[1].score - b[1].score)
        .slice(0, 10)
        .map(([key, state]) => ({ key, score: state.score }))
    };
  }
}
```

### 4. Enhanced Cost Calculator

```typescript
interface CostContext {
  path: string;
  method: string;
  bodySize?: number;
  queryParams?: Record<string, string>;
  headers?: Record<string, string>;
}

class CostCalculator {
  constructor(private config: RateLimitConfig) {}
  
  calculate(path: string, method: string, request?: Request): number {
    const endpoint = this.config.endpoints.find(e => 
      this.matchPath(e.pattern, path) && 
      (!e.method || e.method === method)
    );
    
    let baseCost = endpoint?.baseCost || 1;
    
    // Dynamic cost adjustments
    if (request && endpoint?.dynamicCost) {
      baseCost = this.applyDynamicCost(baseCost, request, endpoint.dynamicCost);
    }
    
    return baseCost;
  }
  
  private applyDynamicCost(
    baseCost: number,
    request: Request,
    dynamicRules: DynamicCostRule[]
  ): number {
    let cost = baseCost;
    
    for (const rule of dynamicRules) {
      switch (rule.type) {
        case 'body_size':
          // Scale cost with payload size
          const bodySize = parseInt(request.headers.get('content-length') || '0');
          if (bodySize > rule.threshold) {
            const multiplier = 1 + Math.floor((bodySize - rule.threshold) / rule.increment);
            cost += rule.costPerUnit * multiplier;
          }
          break;
          
        case 'query_param':
          // Scale cost with query parameters (e.g., batch size)
          const param = new URL(request.url).searchParams.get(rule.paramName);
          if (param) {
            const value = parseInt(param);
            if (value > rule.threshold) {
              cost += rule.costPerUnit * Math.ceil((value - rule.threshold) / rule.increment);
            }
          }
          break;
      }
    }
    
    return cost;
  }
  
  private matchPath(pattern: string, path: string): boolean {
    // Support wildcards: /api/users/* matches /api/users/123
    const regex = new RegExp('^' + pattern.replace(/\*/g, '[^/]+') + '$');
    return regex.test(path);
  }
}

interface DynamicCostRule {
  type: 'body_size' | 'query_param';
  threshold: number;
  increment: number;
  costPerUnit: number;
  paramName?: string; // For query_param type
}
```

### 5. Configuration Model with Hot Reload

```typescript
interface RateLimitConfig {
  version: string;
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
}

interface TierConfig {
  name: string;
  limits: LimitConfig[];
}

interface LimitConfig {
  name: string;           // e.g., "global", "search_endpoint"
  scope: 'read' | 'write' | 'mixed'; // Added 'mixed' for hybrid operations
  capacity: number;       // Max tokens in bucket
  refillRate: number;     // Tokens per second
  windowSeconds: number;  // Time window for the limit
  appliesTo?: string[];   // Specific paths (if endpoint-specific)
}

interface EndpointConfig {
  pattern: string;        // e.g., "/api/search", "/api/users/*"
  method?: string;
  baseCost: number;       // Cost multiplier
  dynamicCost?: DynamicCostRule[]; // Optional dynamic cost adjustments
}

// Example configuration with enhanced features
const config: RateLimitConfig = {
  version: '1.0.0',
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,  // 100 per hour
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'mixed',  // Search can have side effects (logging, analytics)
          capacity: 10,
          refillRate: 10 / 60,     // 10 per minute
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 3600,   // 20 per hour
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'mixed',
          capacity: 100,
          refillRate: 100 / 60,
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 500,
          refillRate: 500 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600
        }
      ]
    }
  },
  endpoints: [
    { 
      pattern: '/api/search', 
      method: 'POST', 
      baseCost: 3,
      dynamicCost: [
        {
          type: 'body_size',
          threshold: 1024, // 1KB
          increment: 1024,
          costPerUnit: 1
        }
      ]
    },
    { 
      pattern: '/api/analyze', 
      method: 'POST', 
      baseCost: 5 
    },
    { 
      pattern: '/api/export', 
      method: 'GET', 
      baseCost: 10 
    },
    { 
      pattern: '/api/batch', 
      method: 'POST', 
      baseCost: 5,
      dynamicCost: [
        {
          type: 'query_param',
          paramName: 'batch_size',
          threshold: 10,
          increment: 10,
          costPerUnit: 2
        }
      ]
    }
  ]
};

class ConfigManager {
  private currentConfig: RateLimitConfig;
  private configWatcher?: FSWatcher;
  
  constructor(configPath: string) {
    this.currentConfig = this.loadConfig(configPath);
    this.setupHotReload(configPath);
  }
  
  private setupHotReload(configPath: string): void {
    // Watch config file for changes
    this.configWatcher = fs.watch(configPath, (eventType) => {
      if (eventType === 'change') {
        try {
          const newConfig = this.loadConfig(configPath);
          
          // Validate before applying
          if (this.validateConfig(newConfig)) {
            const oldVersion = this.currentConfig.version;
            this.currentConfig = newConfig;
            logger.info('Config hot-reloaded', { 
              oldVersion, 
              newVersion: newConfig.version 
            });
            
            // Emit metrics
            metrics.configReloads.inc({ success: 'true' });
          } else {
            logger.error('Config validation failed, keeping old config');
            metrics.configReloads.inc({ success: 'false' });
          }
        } catch (error) {
          logger.error('Config reload failed', { error });
          metrics.configReloads.inc({ success: 'false' });
        }
      }
    });
  }
  
  private loadConfig(path: string): RateLimitConfig {
    const raw = fs.readFileSync(path, 'utf-8');
    return JSON.parse(raw);
  }
  
  private validateConfig(config: RateLimitConfig): boolean {
    // Validate structure
    if (!config.version || !config.tiers || !config.endpoints) {
      return false;
    }
    
    // Validate tiers
    for (const [tierName, tierConfig] of Object.entries(config.tiers)) {
      if (!tierConfig.limits || tierConfig.limits.length === 0) {
        return false;
      }
      
      for (const limit of tierConfig.limits) {
        if (limit.capacity <= 0 || limit.refillRate <= 0) {
          return false;
        }
        
        if (!['read', 'write', 'mixed'].includes(limit.scope)) {
          return false;
        }
      }
    }
    
    return true;
  }
  
  getLimits(tier: string, path: string): LimitConfig[] {
    const tierConfig = this.currentConfig.tiers[tier];
    if (!tierConfig) {
      throw new Error(`Unknown tier: ${tier}`);
    }
    
    // Return limits that apply to this path
    return tierConfig.limits.filter(limit => {
      if (!limit.appliesTo) return true; // Global limit
      return limit.appliesTo.some(pattern => this.matchPath(pattern, path));
    });
  }
  
  private matchPath(pattern: string, path: string): boolean {
    const regex = new RegExp('^' + pattern.replace(/\*/g, '[^/]+') + '$');
    return regex.test(path);
  }
  
  getConfig(): RateLimitConfig {
    return this.currentConfig;
  }
}
```

### 6. Enhanced Circuit Breaker with Metrics

```typescript
class CircuitBreaker {
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private state: 'CLOSED' | 'OPEN' = 'CLOSED';
  
  private readonly FAILURE_THRESHOLD = 5;
  private readonly SUCCESS_THRESHOLD = 3; // Successes needed to stay closed
  private readonly TIMEOUT_MS = 30000; // 30s
  private readonly OPERATION_TIMEOUT_MS = 2000; // 2s per operation
  
  constructor(private name: string) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.TIMEOUT_MS) {
        // Try to recover
        logger.info('Circuit breaker attempting recovery', { name: this.name });
        this.state = 'CLOSED';
        this.failures = 0;
        this.successes = 0;
      } else {
        metrics.circuitBreakerRejections.inc({ breaker: this.name });
        throw new Error(`Circuit breaker is OPEN for ${this.name}`);
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT_MS);
      
      // Track successes
      this.successes++;
      this.failures = 0; // Reset failures on success
      
      metrics.circuitBreakerState.set({ breaker: this.name }, 0); // CLOSED
      
      return result;
    } catch (error) {
      this.failures++;
      this.successes = 0; // Reset successes on failure
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD) {
        this.state = 'OPEN';
        logger.error('Circuit breaker opened', { 
          name: this.name, 
          failures: this.failures 
        });
        metrics.circuitBreakerState.set({ breaker: this.name }, 1); // OPEN
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
  
  getState(): { state: string; failures: number; successes: number } {
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes
    };
  }
}
```

### 7. Identifier Resolution (Same as Original)

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'apikey';
  key: string;
  userId?: string;
  ipAddress?: string;
  tier?: string; // For degradation tier multiplier
}

class IdentifierResolver {
  async resolve(request: Request): Promise<Identifier> {
    // Priority: API Key > User Session > IP Address
    
    // 1. Check for API key
    const apiKey = this.extractApiKey(request);
    if (apiKey) {
      const validated = await this.validateApiKey(apiKey);
      if (validated) {
        return {
          type: 'apikey',
          key: validated.keyId,
          userId: validated.userId,
          ipAddress: this.getClientIP(request),
          tier: validated.tier
        };
      }
    }
    
    // 2. Check for authenticated user session
    const userId = await this.getUserFromSession(request);
    if (userId) {
      const tier = await this.getUserTier(userId);
      return {
        type: 'user',
        key: userId,
        userId: userId,
        ipAddress: this.getClientIP(request),
        tier
      };
    }
    
    // 3. Fallback to IP-based limiting
    const ip = this.getClientIP(request);
    return {
      type: 'ip',
      key: ip,
      ipAddress: ip,
      tier: 'free' // IPs default to free tier
    };
  }
  
  private extractApiKey(request: Request): string | null {
    const authHeader = request.headers.get('Authorization');
    if (authHeader?.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    
    return request.headers.get('X-API-Key');
  }
  
  private getClientIP(request: Request): string {
    const forwardedFor = request.headers.get('X-Forwarded-For');
    if (forwardedFor) {
      const ips = forwardedFor.split(',').map(ip => ip.trim());
      return ips[0];
    }
    
    const realIP = request.headers.get('X-Real-IP');
    if (realIP) return realIP;
    
    return request.socket.remoteAddress || '0.0.0.0';
  }
  
  private async validateApiKey(apiKey: string): Promise<{
    keyId: string;
    userId: string;
    tier: string;
  } | null> {
    return await apiKeyService.validate(apiKey);
  }
  
  private async getUserFromSession(request: Request): Promise<string | null> {
    return await sessionService.getUserId(request);
  }
  
  private async getUserTier(userId: string): Promise<string> {
    return await userService.getTier(userId);
  }
}
```

### 8. Response Headers (Standards-Compliant)

```typescript
function buildRateLimitHeaders(
  result: RateLimitResult,
  cost: number
): Record<string, string> {
  const headers: Record<string, string> = {
    'RateLimit-Limit': result.limit.toString(),
    'RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'RateLimit-Reset': Math.ceil(result.resetAt / 1000).toString(),
  };
  
  // Add cost header for transparency
  if (cost > 1) {
    headers['X-RateLimit-Cost'] = cost.toString();
  }
  
  // Add retry-after on 429 responses
  if (!result.allowed && result.retryAfter) {
    headers['Retry-After'] = result.retryAfter.toString();
  }
  
  // Add degradation warning header
  if (result.source === 'degraded') {
    headers['X-RateLimit-Degraded'] = 'true';
    headers['Warning'] = '199 - "Rate limiting in degraded mode"';
  }
  
  return headers;
}
```

## Deployment Architecture

### Redis Setup (Sentinel for Start)

```typescript
// Primary + 2 replicas with Sentinel for automatic failover
const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'ratelimit-primary',
  sentinelPassword: process.env.SENTINEL_PASSWORD,
  password: process.env.REDIS_PASSWORD,
  db: 0,
  // Connection settings
  connectTimeout: 2000, // Reduced from 5s for faster failure detection
  commandTimeout: 2000,
  maxRetriesPerRequest: 1, // Reduced from 2 - fail faster
  enableReadyCheck: true,
  enableOfflineQueue: false, // Fail fast
  lazyConnect: false,
  // Connection pool
  maxRetriesPerRequest: 1,
  retryStrategy: (times) => {
    if (times > 3) return null; // Give up after 3 retries
    return Math.min(times * 50, 200); // Exponential backoff, max 200ms
  }
});

// Health check
setInterval(async () => {
  try {
    await redis.ping();
    metrics.redisHealth.set(1);
  } catch (error) {
    metrics.redisHealth.set(0);
    logger.error('Redis health check failed', { error });
  }
}, 5000); // Every 5 seconds
```

### Local Cache (Optimized)

```typescript
import { LRUCache } from 'lru-cache';

const localCache = new LRUCache<string, RateLimitResult>({
  max: 100000,       // Increased from 50K for better hit rate
  ttl: 1000,         // 1s TTL (down from 2s for better accuracy)
  ttlAutopurge: true,
  updateAgeOnGet: false,
  updateAgeOnHas: false,
  // Memory limit (256MB)
  maxSize: 256 * 1024 * 1024,
  sizeCalculation: (value) => {
    // Rough estimation: ~2KB per entry
    return 2048;
  }
});

// Cache metrics
setInterval(() => {
  const size = localCache.size;
  const calculatedSize = localCache.calculatedSize || 0;
  
  metrics.cacheSize.set(size);
  metrics.cacheMemory.set(calculatedSize);
}, 10000); // Every 10 seconds
```

## Observability

### Comprehensive Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Cache metrics
  cacheHits: Counter;
  cacheMisses: Counter;
  cacheSize: Gauge;
  cacheMemory: Gauge;
  
  // Redis metrics
  redisErrors: Counter;
  redisLatency: Histogram;
  redisHealth: Gauge; // 0 or 1
  
  // Circuit breaker metrics
  circuitBreakerState: Gauge; // 0=CLOSED, 1=OPEN
  circuitBreakerRejections: Counter;
  
  // Degradation metrics
  degradedRequests: Counter;
  healthScoreDistribution: Histogram;
  
  // Business metrics
  tokenBucketUtilization: Histogram;
  costDistribution: Histogram;
  tierRejections: Counter; // By tier
}

class MetricsCollector {
  async record(
    result: RateLimitResult,
    duration: number,
    identifier: Identifier,
    tier: string,
    cost: number
  ): Promise<void> {
    const labels = { 
      tier, 
      source: result.source, 
      type: identifier.type 
    };
    
    if (result.allowed) {
      this.metrics.requestsAllowed.inc(labels);
    } else {
      this.metrics.requestsBlocked.inc(labels);
      this.metrics.tierRejections.inc({ tier });
    }
    
    this.metrics.rateLimitCheckDuration.observe(labels, duration);
    
    // Utilization: how full is the bucket?
    const utilization = 1 - (result.remaining / result.limit);
    this.metrics.tokenBucketUtilization.observe(labels, utilization);
    
    // Cost tracking
    this.metrics.costDistribution.observe({ tier }, cost);
    
    // Cache performance
    if (result.source === 'cache') {
      this.metrics.cacheHits.inc(labels);
    } else if (result.source === 'redis') {
      this.metrics.cacheMisses.inc(labels);
    }
    
    // Degradation tracking
    if (result.source === 'degraded') {
      this.metrics.degradedRequests.inc(labels);
      if (result.healthScore !== undefined) {
        this.metrics.healthScoreDistribution.observe(labels, result.healthScore);
      }
    }
  }
}
```

### Audit Logging

```typescript
class AuditLogger {
  async logRejection(
    identifier: Identifier,
    tier: string,
    path: string,
    result: RateLimitResult
  ): Promise<void> {
    const logEntry = {
      timestamp: new Date().toISOString(),
      event: 'rate_limit_rejection',
      identifier: {
        type: identifier.type,
        key: this.maskSensitive(identifier.key),
        userId: identifier.userId,
        ipAddress: identifier.ipAddress
      },
      tier,
      path,
      limit: result.limit,
      remaining: result.remaining,
      retryAfter: result.retryAfter,
      source: result.source,
      degraded: result.source === 'degraded'
    };
    
    // Send to logging service (async, fire-and-forget)
    await loggingService.log(logEntry);
  }
  
  private maskSensitive(key: string): string {
    // Mask all but last 4 characters
    if (key.length <= 4) return '****';
    return '*'.repeat(key.length - 4) + key.slice(-4);
  }
}
```

## What I Improved

1. **1s Cache TTL (from 2s)**: Better accuracy with minimal performance impact. 1s gives ~1% max overage vs 2% with 2s, while still providing excellent cache hit rates.

2. **2x Headroom for Cache (from 1.5x)**: More conservative to prevent bursting through limits during high load.

3. **Added 'mixed' Scope**: Addresses the read-with-side-effects problem. Search endpoints, analytics, and similar operations that read but also trigger side effects get adaptive treatment during outages (better than pure write, worse than pure read).

4. **Adaptive Degradation System**: Instead of binary fail-open/fail-closed, track health per identifier+limit. Gradual recovery prevents thundering herd when Redis comes back. Probabilistic allowance based on health score, tier, and operation type.

5. **Enhanced Cost Calculator**: Support dynamic costs based on payload size and query parameters. This addresses the governance concern - costs automatically adjust to actual resource usage.

6. **Config Hot Reload**: Cost factors and limits can be adjusted without redeployment. Version tracking and validation prevent bad configs from being applied.

7. **Circuit Breaker Metrics**: Export state, failures, and successes for visibility. Helps operators understand when and why degradation occurs.

8. **Tier-Aware Degradation**: Enterprise customers get better treatment (100% allowance) during outages, free tier gets more restrictive treatment (60% base). Fair business logic.

9. **Health Score Decay**: Old failures decay over time, preventing permanent degradation. Rapid degradation (0.3 penalty) but slow recovery (0.1 reward) prevents flapping.

10. **Degradation Warning Headers**: Clients know when they're in degraded mode via `X-RateLimit-Degraded` header and can adjust behavior.

11. **Reduced Redis Timeouts**: 2s connect/command timeout (from 5s) for faster failure detection. 1 retry (from 2) to fail faster and trigger degradation sooner.

12. **Memory-Limited Cache**: 256MB size limit prevents unbounded memory growth. Auto-purge and size calculation.

13. **Wildcard Path Matching**: `/api/users/*` pattern support makes configuration more maintainable.

14. **Audit Logging for High-Value Rejections**: Enterprise/pro rejections are logged for customer support and analysis.

## What I Kept

1. **Token bucket algorithm**: Superior burst handling
2. **Atomic Lua scripts**: Correct distributed rate limiting  
3. **Redis TIME for clock sync**: Eliminates clock skew
4. **Multi-tier limiting**: Global + endpoint protection
5. **Sentinel recommendation**: Right choice for initial deployment
6. **Cost-based limiting**: Essential for resource protection
7. **Standards-compliant headers**: Good client compatibility
8. **Composite identifier**: Security and flexibility
9. **Three-layer architecture**: Clear separation of concerns
10. **Non-blocking metrics**: Performance over perfect observability

## Remaining Concerns

1. **Degradation Complexity**: The adaptive degradation system adds significant complexity. Is the benefit worth the operational overhead? Could simpler tiered allowances (e.g., enterprise=80%, pro=50%, free=20%) be sufficient?

2. **Cache Consistency During Bursts**: With 1s TTL and 2x headroom, legitimate burst traffic might get rejected when the cache thinks there are enough tokens but Redis has fewer. How acceptable is this false rejection rate?

3. **Dynamic Cost Governance**: While hot reload helps, who monitors cost accuracy? Should there be automated alerts when an endpoint's actual resource usage diverges from its configured cost?

4. **Health Score Persistence**: Health scores are in-memory only. If a gateway node restarts during a Redis outage, it assumes everything is healthy. Should health state be shared across nodes?

5. **Mixed Scope Failure Mode**: 'mixed' scope gets 40% allowance during outages (0.7 base * 0.6 free tier). Is this the right balance? Too restrictive or too permissive?

6. **Migration Path**: If we need to migrate from Sentinel to Cluster later, what's the process? How do we ensure no rate limit state is lost during migration?

## Convergence Status

**ITERATING** - Second iteration with significant enhancements around failure modes and observability.

## PROMPT_FOR_ARCHITECT:

Focus your review on these enhanced aspects:

1. **Adaptive Degradation System**: Is the health-score-based probabilistic allowance worth the complexity, or should we stick with simpler binary fail-open/fail-closed based on tier?

2. **1s Cache TTL + 2x Headroom**: Does this strike the right balance, or are we being too conservative (hurting performance) or too aggressive (risking overages)?

3. **'mixed' Scope Category**: Is adding a third category (read/write/mixed) the right approach for operations with side effects, or should we force them into read or write buckets?

4. **Dynamic Cost Calculation**: Does the enhanced cost calculator (body size, query params) solve the governance problem, or does it make costs too unpredictable for users?

5. **Hot Reload Implementation**: Should config hot reload be sync (block until loaded) or async (apply on next request)? Current implementation is async - is that safe?

6. **Cross-Node Health State**: Should degradation health scores be shared across gateway nodes via Redis, or is per-node tracking sufficient?

**Convergence Signal:** ITERATING

---

## Round 3

### 🔵 Agent A

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with pragmatic reliability:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket with atomic Redis operations         │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  │  • Tiered degradation (simple, predictable)         │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (2s local cache)             ↓ (authoritative)    │
│  ┌──────────────┐              ┌─────────────────────┐     │
│  │  Local       │              │  Redis Sentinel     │     │
│  │  LRU Cache   │              │  Primary + Replicas │     │
│  └──────────────┘              └─────────────────────┘     │
│         ↓ (on failure)                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Tier-Based Degradation Handler                      │   │
│  │  • Simple tier-based allowances (no tracking)       │   │
│  │  • Deterministic quotas during outages              │   │
│  │  • Safe recovery (sync from Redis on reconnect)    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Operations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Audit       │  │  Config      │     │
│  │  Collector   │  │  Logger      │  │  Hot Reload  │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limit Middleware

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const startTime = performance.now();
    
    // Step 1: Extract and enrich identifier
    const identifier = await identifierResolver.resolve(request);
    
    // Step 2: Determine tier from identifier
    const tier = await tierResolver.getTier(identifier);
    
    // Step 3: Calculate request cost
    const cost = costCalculator.calculate(request.path, request.method, request);
    
    // Step 4: Check rate limits (core operation)
    const result = await rateLimiter.checkAndConsume(
      identifier,
      tier,
      request.path,
      cost
    );
    
    // Step 5: Record metrics (non-blocking, fire-and-forget)
    const duration = performance.now() - startTime;
    setImmediate(() => {
      metricsCollector.record(result, duration, identifier, tier, cost)
        .catch(err => logger.debug('Metric recording failed', { error: err.message }));
    });
    
    // Step 6: Handle rejection
    if (!result.allowed) {
      // Audit high-value rejections asynchronously
      if (tier === 'enterprise' || tier === 'pro') {
        setImmediate(() => {
          auditLogger.logRejection(identifier, tier, request.path, result)
            .catch(err => logger.debug('Audit logging failed', { error: err.message }));
        });
      }
      
      return new Response(null, {
        status: 429,
        headers: buildRateLimitHeaders(result, cost),
        body: JSON.stringify({
          error: 'rate_limit_exceeded',
          message: 'Rate limit exceeded. Please retry after the specified time.',
          retryAfter: result.retryAfter,
          tier: tier,
          limit: result.limit,
          upgradeUrl: tier === 'free' ? '/api/upgrade' : undefined
        })
      });
    }
    
    // Step 7: Forward request with rate limit headers
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result, cost));
    
    return response;
  }
}
```

### 2. Rate Limiter Service (Simplified Core Logic)

```typescript
interface RateLimiter {
  checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult>;
}

class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private localCache: Cache,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker,
    private degradationHandler: DegradationHandler
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    // Get all applicable limits for this request
    const limits = this.config.getLimits(tier, path);
    
    // Check all limits concurrently (global + endpoint-specific)
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost, path))
    );
    
    // Return the most restrictive result (first blocked or least remaining)
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    path: string
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    
    // Try local cache first (2s TTL - increased back from 1s)
    const cached = this.localCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      // Use cache if we have sufficient headroom
      // 1.5x headroom: good balance between performance and safety
      if (cached.remaining >= cost * 1.5) {
        return {
          ...cached,
          remaining: cached.remaining - cost, // Optimistic decrement
          source: 'cache'
        };
      }
    }
    
    // Cache miss or insufficient tokens - check Redis (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost);
        
        // Update local cache with result (2s TTL)
        this.localCache.set(cacheKey, result, 2000);
        
        return result;
      });
    } catch (error) {
      // Circuit breaker open or Redis failure
      logger.error('Rate limit check failed', { 
        identifier, 
        limit: limit.name, 
        error: error.message,
        path
      });
      
      // Use tier-based degradation (simple, no state tracking)
      return this.degradationHandler.handleFailure(identifier, limit, cost, tier);
    }
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    
    // Token bucket algorithm with Redis Lua script for atomicity
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      
      -- Get current state (tokens, last_refill_time)
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      -- Calculate tokens to add based on elapsed time
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Check if we can consume
      if tokens >= cost then
        -- Consume tokens
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Return: allowed=1, remaining, limit, reset_time
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      else
        -- Insufficient tokens - still update refill time to prevent gaming
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Calculate retry delay
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        -- Return: allowed=0, remaining, limit, reset_time, retry_after
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const now = await this.getRedisTime();
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60 // TTL with 1min buffer
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: 'redis',
      expiresAt: now + 2000 // For local cache (2s)
    };
  }
  
  private async getRedisTime(): Promise<number> {
    // Use Redis TIME for clock synchronization
    const [seconds, microseconds] = await this.redis.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
}
```

### 3. Simplified Degradation Handler

```typescript
interface DegradationQuota {
  requestsPerMinute: number;
  costMultiplier: number; // Applied to base cost
}

class DegradationHandler {
  // Simple, stateless degradation quotas by tier
  private readonly DEGRADATION_QUOTAS: Record<string, DegradationQuota> = {
    enterprise: {
      requestsPerMinute: 100, // Generous quota
      costMultiplier: 1.0     // Full cost consideration
    },
    pro: {
      requestsPerMinute: 50,
      costMultiplier: 1.0
    },
    free: {
      requestsPerMinute: 10,
      costMultiplier: 1.5     // More restrictive (higher cost = fewer requests)
    },
    ip: { // Unknown/unauthenticated
      requestsPerMinute: 5,
      costMultiplier: 2.0     // Most restrictive
    }
  };
  
  private degradationState = new LRUCache<string, DegradationState>({
    max: 10000,
    ttl: 60000, // 1 minute TTL
  });
  
  handleFailure(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    tier: string
  ): RateLimitResult {
    const stateKey = this.buildStateKey(identifier, limit);
    const quota = this.DEGRADATION_QUOTAS[tier] || this.DEGRADATION_QUOTAS.ip;
    
    // Get or initialize degradation state
    let state = this.degradationState.get(stateKey);
    const now = Date.now();
    
    if (!state || now - state.windowStart >= 60000) {
      // New window
      state = {
        windowStart: now,
        tokensUsed: 0,
        requestCount: 0
      };
    }
    
    // Apply cost multiplier
    const adjustedCost = cost * quota.costMultiplier;
    
    // Check if request would exceed quota
    const capacityInWindow = quota.requestsPerMinute;
    const wouldExceed = (state.tokensUsed + adjustedCost) > capacityInWindow;
    
    if (!wouldExceed) {
      // Allow request
      state.tokensUsed += adjustedCost;
      state.requestCount++;
      this.degradationState.set(stateKey, state);
      
      return {
        allowed: true,
        remaining: Math.max(0, capacityInWindow - state.tokensUsed),
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: null,
        source: 'degraded',
        expiresAt: now + 2000
      };
    } else {
      // Reject request
      const timeUntilReset = (state.windowStart + 60000) - now;
      
      return {
        allowed: false,
        remaining: 0,
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: Math.ceil(timeUntilReset / 1000),
        source: 'degraded',
        expiresAt: now + 2000
      };
    }
  }
  
  private buildStateKey(identifier: Identifier, limit: LimitConfig): string {
    return `degraded:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  // Observability: export degradation metrics
  getMetrics(): DegradationMetrics {
    const allStates = Array.from(this.degradationState.entries());
    
    return {
      activeWindows: allStates.length,
      totalRequests: allStates.reduce((sum, [_, state]) => sum + state.requestCount, 0),
      byTier: this.groupByTier(allStates)
    };
  }
  
  private groupByTier(states: [string, DegradationState][]): Record<string, number> {
    const grouped: Record<string, number> = {};
    
    for (const [key, state] of states) {
      // Extract tier from key format: "degraded:type:key:limit"
      const parts = key.split(':');
      const tier = parts[1]; // Simplified tier extraction
      grouped[tier] = (grouped[tier] || 0) + state.requestCount;
    }
    
    return grouped;
  }
}

interface DegradationState {
  windowStart: number;
  tokensUsed: number;
  requestCount: number;
}
```

### 4. Simplified Cost Calculator (Static Costs Only)

```typescript
interface CostContext {
  path: string;
  method: string;
}

class CostCalculator {
  constructor(private config: RateLimitConfig) {}
  
  calculate(path: string, method: string, request?: Request): number {
    // Find matching endpoint configuration
    const endpoint = this.config.endpoints.find(e => 
      this.matchPath(e.pattern, path) && 
      (!e.method || e.method === method)
    );
    
    // Return configured base cost (no dynamic adjustments)
    return endpoint?.cost || 1;
  }
  
  private matchPath(pattern: string, path: string): boolean {
    // Support wildcards: /api/users/* matches /api/users/123
    const regex = new RegExp('^' + pattern.replace(/\*/g, '[^/]+') + '$');
    return regex.test(path);
  }
}
```

### 5. Configuration Model with Safe Hot Reload

```typescript
interface RateLimitConfig {
  version: string;
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
}

interface TierConfig {
  name: string;
  limits: LimitConfig[];
}

interface LimitConfig {
  name: string;           // e.g., "global", "search_endpoint"
  scope: 'read' | 'write'; // Simplified: only two categories
  capacity: number;       // Max tokens in bucket
  refillRate: number;     // Tokens per second
  windowSeconds: number;  // Time window for the limit
  appliesTo?: string[];   // Specific paths (if endpoint-specific)
}

interface EndpointConfig {
  pattern: string;        // e.g., "/api/search", "/api/users/*"
  method?: string;
  cost: number;           // Static cost only
}

// Example configuration
const config: RateLimitConfig = {
  version: '1.0.0',
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,  // 100 per hour
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',  // Search is read-heavy, treat as read
          capacity: 10,
          refillRate: 10 / 60,     // 10 per minute
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 3600,   // 20 per hour
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 60,
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 500,
          refillRate: 500 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600
        }
      ]
    }
  },
  endpoints: [
    { pattern: '/api/search', method: 'POST', cost: 3 },
    { pattern: '/api/analyze', method: 'POST', cost: 5 },
    { pattern: '/api/export', method: 'GET', cost: 10 },
    { pattern: '/api/batch', method: 'POST', cost: 5 }
  ]
};

class ConfigManager {
  private currentConfig: RateLimitConfig;
  private pendingConfig: RateLimitConfig | null = null;
  private configWatcher?: FSWatcher;
  private reloadLock = false;
  
  constructor(configPath: string) {
    this.currentConfig = this.loadConfig(configPath);
    this.setupHotReload(configPath);
  }
  
  private setupHotReload(configPath: string): void {
    // Watch config file for changes
    this.configWatcher = fs.watch(configPath, (eventType) => {
      if (eventType === 'change' && !this.reloadLock) {
        this.reloadLock = true;
        
        // Debounce: wait 100ms for file write to complete
        setTimeout(() => {
          try {
            const newConfig = this.loadConfig(configPath);
            
            // Validate before applying
            if (this.validateConfig(newConfig)) {
              const oldVersion = this.currentConfig.version;
              
              // Stage config for next request (async application)
              this.pendingConfig = newConfig;
              
              logger.info('Config staged for reload', { 
                oldVersion, 
                newVersion: newConfig.version 
              });
              
              metrics.configReloads.inc({ success: 'true' });
            } else {
              logger.error('Config validation failed, keeping old config');
              metrics.configReloads.inc({ success: 'false' });
            }
          } catch (error) {
            logger.error('Config reload failed', { error });
            metrics.configReloads.inc({ success: 'false' });
          } finally {
            this.reloadLock = false;
          }
        }, 100);
      }
    });
  }
  
  private loadConfig(path: string): RateLimitConfig {
    const raw = fs.readFileSync(path, 'utf-8');
    return JSON.parse(raw);
  }
  
  private validateConfig(config: RateLimitConfig): boolean {
    // Validate structure
    if (!config.version || !config.tiers || !config.endpoints) {
      return false;
    }
    
    // Validate tiers
    for (const [tierName, tierConfig] of Object.entries(config.tiers)) {
      if (!tierConfig.limits || tierConfig.limits.length === 0) {
        return false;
      }
      
      for (const limit of tierConfig.limits) {
        if (limit.capacity <= 0 || limit.refillRate <= 0) {
          return false;
        }
        
        if (!['read', 'write'].includes(limit.scope)) {
          return false;
        }
      }
    }
    
    return true;
  }
  
  getLimits(tier: string, path: string): LimitConfig[] {
    // Apply pending config if available (async reload)
    if (this.pendingConfig) {
      this.currentConfig = this.pendingConfig;
      this.pendingConfig = null;
      logger.info('Config applied', { version: this.currentConfig.version });
    }
    
    const tierConfig = this.currentConfig.tiers[tier];
    if (!tierConfig) {
      throw new Error(`Unknown tier: ${tier}`);
    }
    
    // Return limits that apply to this path
    return tierConfig.limits.filter(limit => {
      if (!limit.appliesTo) return true; // Global limit
      return limit.appliesTo.some(pattern => this.matchPath(pattern, path));
    });
  }
  
  private matchPath(pattern: string, path: string): boolean {
    const regex = new RegExp('^' + pattern.replace(/\*/g, '[^/]+') + '$');
    return regex.test(path);
  }
  
  getConfig(): RateLimitConfig {
    return this.currentConfig;
  }
}
```

### 6. Circuit Breaker (Same as Previous)

```typescript
class CircuitBreaker {
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private state: 'CLOSED' | 'OPEN' = 'CLOSED';
  
  private readonly FAILURE_THRESHOLD = 5;
  private readonly SUCCESS_THRESHOLD = 3;
  private readonly TIMEOUT_MS = 30000; // 30s
  private readonly OPERATION_TIMEOUT_MS = 2000; // 2s per operation
  
  constructor(private name: string) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.TIMEOUT_MS) {
        // Try to recover
        logger.info('Circuit breaker attempting recovery', { name: this.name });
        this.state = 'CLOSED';
        this.failures = 0;
        this.successes = 0;
      } else {
        metrics.circuitBreakerRejections.inc({ breaker: this.name });
        throw new Error(`Circuit breaker is OPEN for ${this.name}`);
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT_MS);
      
      this.successes++;
      this.failures = 0;
      
      metrics.circuitBreakerState.set({ breaker: this.name }, 0); // CLOSED
      
      return result;
    } catch (error) {
      this.failures++;
      this.successes = 0;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD) {
        this.state = 'OPEN';
        logger.error('Circuit breaker opened', { 
          name: this.name, 
          failures: this.failures 
        });
        metrics.circuitBreakerState.set({ breaker: this.name }, 1); // OPEN
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
  
  getState(): { state: string; failures: number; successes: number } {
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes
    };
  }
}
```

### 7. Identifier Resolution (Same as Previous)

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'apikey';
  key: string;
  userId?: string;
  ipAddress?: string;
  tier?: string;
}

class IdentifierResolver {
  async resolve(request: Request): Promise<Identifier> {
    // Priority: API Key > User Session > IP Address
    
    // 1. Check for API key
    const apiKey = this.extractApiKey(request);
    if (apiKey) {
      const validated = await this.validateApiKey(apiKey);
      if (validated) {
        return {
          type: 'apikey',
          key: validated.keyId,
          userId: validated.userId,
          ipAddress: this.getClientIP(request),
          tier: validated.tier
        };
      }
    }
    
    // 2. Check for authenticated user session
    const userId = await this.getUserFromSession(request);
    if (userId) {
      const tier = await this.getUserTier(userId);
      return {
        type: 'user',
        key: userId,
        userId: userId,
        ipAddress: this.getClientIP(request),
        tier
      };
    }
    
    // 3. Fallback to IP-based limiting
    const ip = this.getClientIP(request);
    return {
      type: 'ip',
      key: ip,
      ipAddress: ip,
      tier: 'free'
    };
  }
  
  private extractApiKey(request: Request): string | null {
    const authHeader = request.headers.get('Authorization');
    if (authHeader?.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    
    return request.headers.get('X-API-Key');
  }
  
  private getClientIP(request: Request): string {
    const forwardedFor = request.headers.get('X-Forwarded-For');
    if (forwardedFor) {
      const ips = forwardedFor.split(',').map(ip => ip.trim());
      return ips[0];
    }
    
    const realIP = request.headers.get('X-Real-IP');
    if (realIP) return realIP;
    
    return request.socket.remoteAddress || '0.0.0.0';
  }
  
  private async validateApiKey(apiKey: string): Promise<{
    keyId: string;
    userId: string;
    tier: string;
  } | null> {
    return await apiKeyService.validate(apiKey);
  }
  
  private async getUserFromSession(request: Request): Promise<string | null> {
    return await sessionService.getUserId(request);
  }
  
  private async getUserTier(userId: string): Promise<string> {
    return await userService.getTier(userId);
  }
}
```

### 8. Response Headers (Standards-Compliant)

```typescript
function buildRateLimitHeaders(
  result: RateLimitResult,
  cost: number
): Record<string, string> {
  const headers: Record<string, string> = {
    'RateLimit-Limit': result.limit.toString(),
    'RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'RateLimit-Reset': Math.ceil(result.resetAt / 1000).toString(),
  };
  
  // Add cost header for transparency
  if (cost > 1) {
    headers['X-RateLimit-Cost'] = cost.toString();
  }
  
  // Add retry-after on 429 responses
  if (!result.allowed && result.retryAfter) {
    headers['Retry-After'] = result.retryAfter.toString();
  }
  
  // Add degradation warning header
  if (result.source === 'degraded') {
    headers['X-RateLimit-Degraded'] = 'true';
    headers['Warning'] = '199 - "Rate limiting in degraded mode"';
  }
  
  return headers;
}
```

## Deployment Architecture

### Redis Setup (Sentinel)

```typescript
// Primary + 2 replicas with Sentinel for automatic failover
const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'ratelimit-primary',
  sentinelPassword: process.env.SENTINEL_PASSWORD,
  password: process.env.REDIS_PASSWORD,
  db: 0,
  // Connection settings
  connectTimeout: 2000,
  commandTimeout: 2000,
  maxRetriesPerRequest: 1,
  enableReadyCheck: true,
  enableOfflineQueue: false,
  lazyConnect: false,
  retryStrategy: (times) => {
    if (times > 3) return null;
    return Math.min(times * 50, 200);
  }
});

// Health check
setInterval(async () => {
  try {
    await redis.ping();
    metrics.redisHealth.set(1);
  } catch (error) {
    metrics.redisHealth.set(0);
    logger.error('Redis health check failed', { error });
  }
}, 5000);
```

### Local Cache

```typescript
import { LRUCache } from 'lru-cache';

const localCache = new LRUCache<string, RateLimitResult>({
  max: 100000,
  ttl: 2000,         // 2s TTL
  ttlAutopurge: true,
  updateAgeOnGet: false,
  updateAgeOnHas: false,
  // Memory limit (256MB)
  maxSize: 256 * 1024 * 1024,
  sizeCalculation: (value) => {
    return 2048; // ~2KB per entry
  }
});

// Cache metrics
setInterval(() => {
  const size = localCache.size;
  const calculatedSize = localCache.calculatedSize || 0;
  
  metrics.cacheSize.set(size);
  metrics.cacheMemory.set(calculatedSize);
}, 10000);
```

## Observability

### Comprehensive Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Cache metrics
  cacheHits: Counter;
  cacheMisses: Counter;
  cacheSize: Gauge;
  cacheMemory: Gauge;
  
  // Redis metrics
  redisErrors: Counter;
  redisLatency: Histogram;
  redisHealth: Gauge;
  
  // Circuit breaker metrics
  circuitBreakerState: Gauge;
  circuitBreakerRejections: Counter;
  
  // Degradation metrics
  degradedRequests: Counter;
  degradedRequestsByTier: Counter;
  
  // Business metrics
  tokenBucketUtilization: Histogram;
  costDistribution: Histogram;
  tierRejections: Counter;
}

class MetricsCollector {
  async record(
    result: RateLimitResult,
    duration: number,
    identifier: Identifier,
    tier: string,
    cost: number
  ): Promise<void> {
    const labels = { 
      tier, 
      source: result.source, 
      type: identifier.type 
    };
    
    if (result.allowed) {
      this.metrics.requestsAllowed.inc(labels);
    } else {
      this.metrics.requestsBlocked.inc(labels);
      this.metrics.tierRejections.inc({ tier });
    }
    
    this.metrics.rateLimitCheckDuration.observe(labels, duration);
    
    // Utilization: how full is the bucket?
    const utilization = 1 - (result.remaining / result.limit);
    this.metrics.tokenBucketUtilization.observe(labels, utilization);
    
    // Cost tracking
    this.metrics.costDistribution.observe({ tier }, cost);
    
    // Cache performance
    if (result.source === 'cache') {
      this.metrics.cacheHits.inc(labels);
    } else if (result.source === 'redis') {
      this.metrics.cacheMisses.inc(labels);
    }
    
    // Degradation tracking
    if (result.source === 'degraded') {
      this.metrics.degradedRequests.inc(labels);
      this.metrics.degradedRequestsByTier.inc({ tier });
    }
  }
}
```

### Audit Logging

```typescript
class AuditLogger {
  async logRejection(
    identifier: Identifier,
    tier: string,
    path: string,
    result: RateLimitResult
  ): Promise<void> {
    const logEntry = {
      timestamp: new Date().toISOString(),
      event: 'rate_limit_rejection',
      identifier: {
        type: identifier.type,
        key: this.maskSensitive(identifier.key),
        userId: identifier.userId,
        ipAddress: identifier.ipAddress
      },
      tier,
      path,
      limit: result.limit,
      remaining: result.remaining,
      retryAfter: result.retryAfter,
      source: result.source,
      degraded: result.source === 'degraded'
    };
    
    await loggingService.log(logEntry);
  }
  
  private maskSensitive(key: string): string {
    if (key.length <= 4) return '****';
    return '*'.repeat(key.length - 4) + key.slice(-4);
  }
}
```

## Rationale

### 1. **2s Cache TTL Instead of 1s**
The previous design reduced cache TTL to 1s for "better accuracy," but this hurts performance significantly. With 2s TTL:
- Cache hit rate improves by ~40% (requests within 2s reuse same entry)
- Maximum overage is still only 2% (vs 1% with 1s TTL)
- 2% overage is acceptable for burst tolerance - rate limits are protective, not billing
- Reduced Redis load means better scalability and lower costs

### 2. **1.5x Cache Headroom Instead of 2x**
2x headroom is overly conservative and wastes cache effectiveness:
- 1.5x provides sufficient safety margin against cache staleness
- Allows more requests to be served from cache (better performance)
- Still prevents overage during normal operation
- 2x headroom would reject ~30% more requests unnecessarily

### 3. **Eliminated 'mixed' Scope - Only Read/Write**
Adding a third category creates more problems than it solves:
- Operations either modify state (write) or don't (read) - there's no true "middle"
- "Read with side effects" (analytics, logging) are still fundamentally reads
- Side effects like logging should be async/best-effort, not impacting categorization
- Two categories are easier to reason about, configure, and maintain
- Forces clear architectural decisions about operation semantics

### 4. **Static Costs Only (No Dynamic Calculation)**
Dynamic cost calculation based on payload size/query params is governance nightmare:
- Users can't predict their rate limit consumption
- Makes cost optimization adversarial (users game the system)
- Adds complexity to every request (parsing bodies, query params)
- Better approach: design endpoints with fixed costs, use separate endpoints for bulk operations
- Example: `/api/batch?size=100` has cost 5, regardless of size. If that's insufficient, add `/api/bulk` with cost 20.

### 5. **Async Config Hot Reload**
Previous design was ambiguous about sync vs async reload. Async is correct:
- Config changes apply on next request (not mid-request)
- No risk of inconsistent state during request processing
- Simple implementation with pending config staging
- Failed validation doesn't disrupt active requests
- Operators can test config changes by monitoring metrics after reload

### 6. **Simplified Degradation (Tier-Based Quotas)**
Replaced complex health score tracking with simple tier-based quotas:
- **Predictable**: Each tier gets fixed degraded quota (enterprise=100/min, pro=50/min, free=10/min)
- **Stateless**: No cross-node health state synchronization needed
- **Fair**: Better tiers get better service during outages (business logic)
- **Simple**: No decay calculations, no probabilistic decisions
- **Observable**: Easy to understand and debug
- **Cost-aware**: Applies cost multipliers (free=1.5x, ip=2x) for resource protection

The health score system was over-engineered:
- Added state synchronization concerns across nodes
- Probabilistic decisions made debugging difficult
- Decay algorithms required tuning and monitoring
- Recovery behavior was unpredictable

### 7. **Kept Token Bucket with Redis Lua**
Atomic Lua scripts are essential:
- Prevents race conditions in distributed environment
- Accurate token consumption across concurrent requests
- Single round-trip to Redis (performance)
- No possibility of over-consumption

### 8. **Kept Circuit Breaker Pattern**
Essential for graceful degradation:
- Prevents cascading failures when Redis is slow/down
- 30s timeout provides reasonable recovery window
- 5 failure threshold prevents flapping on transient errors
- Metrics export enables operational visibility

### 9. **Kept Redis TIME for Clock Sync**
Critical for distributed correctness:
- Eliminates clock skew between gateway nodes
- All rate limit calculations use consistent time source
- Prevents time-based exploits (fast-forwarding local clocks)

### 10. **Kept Multi-Tier Limiting (Global + Endpoint)**
Essential for comprehensive protection:
- Global limits prevent total abuse
- Endpoint limits protect expensive operations
- Concurrent checking finds most restrictive limit
- Flexible configuration per tier

## What I Changed

1. **2s cache TTL** (from 1s) - Better performance, acceptable accuracy trade-off
2. **1.5x cache headroom** (from 2x) - Better cache utilization
3. **Removed 'mixed' scope** - Simplified to read/write only
4. **Static costs only** - Removed dynamic cost calculation
5. **Async config reload** - Clarified implementation, safe staging
6. **Tier-based degradation** - Replaced health score system with simple quotas
7. **Cost multipliers in degradation** - Protect resources during outages
8. **Removed cross-node health state** - No synchronization needed
9. **Simplified metrics** - Removed health score histograms, focused on actionable metrics

## What I Kept

1. **Token bucket algorithm** - Correct burst handling
2. **Atomic Lua scripts** - Distributed correctness
3. **Redis TIME** - Clock synchronization
4. **Multi-tier limiting** - Comprehensive protection
5. **Sentinel architecture** - Right for initial deployment
6. **Circuit breaker** - Graceful failure handling
7. **Non-blocking metrics** - Performance over perfect observability
8. **Audit logging for high-value tiers** - Customer support needs
9. **Standards-compliant headers** - Client compatibility
10. **Composite identifier resolution** - Security and flexibility

## Open Questions

1. **Should degradation quotas be configurable?** Current implementation has hardcoded quotas per tier. Should these be in the config file for operational flexibility?

2. **Is 2% maximum overage acceptable?** With 2s cache TTL, burst traffic can exceed limits by up to 2%. Is this acceptable for all use cases, or should critical endpoints bypass cache?

3. **Migration to Redis Cluster?** Current design uses Sentinel. If we need to scale to Cluster later (100K+ req/s), what's the migration path? Cluster doesn't support Lua scripts across slots.

4. **Should cost be visible to users?** We expose cost in headers (`X-RateLimit-Cost`). Should we also expose it in API documentation? Does transparency help or create gaming behavior?

5. **Degradation mode for writes?** Current degradation allows writes (with lower quotas). Should we be more conservative and reject all writes during Redis outages?

## Convergence Status

**ITERATING** - Second iteration with significant simplifications around degradation and cost calculation.

## PROMPT_FOR_CRITIC:

Focus your review on these key decisions:

1. **2s cache TTL + 1.5x headroom**: Is this the right balance between performance and accuracy? Would you prefer tighter accuracy (1s TTL) or better performance (3s TTL)?

2. **Removed dynamic costs**: Is static cost configuration sufficient, or are there legitimate use cases where payload-based costs are necessary?

3. **Tier-based degradation quotas**: Is this simpler approach better than health score tracking? Does it provide sufficient protection and fairness?

4. **Two-category scope (read/write)**: Is forcing operations into binary categories acceptable, or does "mixed" scope serve a real need?

5. **Async config reload**: Should config changes apply immediately (sync) or on next request (async)? What are the safety trade-offs?

6. **Should we support cache bypass for critical endpoints?** Some operations might want 100% accuracy over performance.

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with pragmatic reliability:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket with atomic Redis operations         │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  │  • Tiered degradation with automatic recovery       │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (configurable cache)          ↓ (authoritative)   │
│  ┌──────────────┐              ┌─────────────────────┐     │
│  │  Adaptive    │              │  Redis Sentinel     │     │
│  │  LRU Cache   │              │  Primary + Replicas │     │
│  └──────────────┘              └─────────────────────┘     │
│         ↓ (on failure)                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Degradation Handler with Automatic Recovery         │   │
│  │  • Tier-based quotas with cost awareness            │   │
│  │  • Gradual recovery via success rate tracking       │   │
│  │  • Safe state transitions                           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Operations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Audit       │  │  Config      │     │
│  │  Collector   │  │  Logger      │  │  Manager     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limit Middleware

```typescript
interface RateLimitMiddleware {
  async handle(request: Request): Promise<Response> {
    const startTime = performance.now();
    
    // Step 1: Extract and enrich identifier
    const identifier = await identifierResolver.resolve(request);
    
    // Step 2: Determine tier from identifier
    const tier = await tierResolver.getTier(identifier);
    
    // Step 3: Calculate request cost
    const cost = costCalculator.calculate(request.path, request.method);
    
    // Step 4: Check rate limits (core operation)
    const result = await rateLimiter.checkAndConsume(
      identifier,
      tier,
      request.path,
      cost
    );
    
    // Step 5: Record metrics (non-blocking, fire-and-forget)
    const duration = performance.now() - startTime;
    setImmediate(() => {
      metricsCollector.record(result, duration, identifier, tier, cost, request.path)
        .catch(err => logger.debug('Metric recording failed', { error: err.message }));
    });
    
    // Step 6: Handle rejection
    if (!result.allowed) {
      // Audit high-value rejections asynchronously
      if (tier === 'enterprise' || tier === 'pro') {
        setImmediate(() => {
          auditLogger.logRejection(identifier, tier, request.path, result)
            .catch(err => logger.debug('Audit logging failed', { error: err.message }));
        });
      }
      
      return new Response(null, {
        status: 429,
        headers: buildRateLimitHeaders(result, cost),
        body: JSON.stringify({
          error: 'rate_limit_exceeded',
          message: 'Rate limit exceeded. Please retry after the specified time.',
          retryAfter: result.retryAfter,
          tier: tier,
          limit: result.limit,
          remaining: result.remaining,
          upgradeUrl: tier === 'free' ? '/api/upgrade' : undefined
        })
      });
    }
    
    // Step 7: Forward request with rate limit headers
    const response = await next(request);
    response.headers.merge(buildRateLimitHeaders(result, cost));
    
    return response;
  }
}
```

### 2. Rate Limiter Service with Adaptive Caching

```typescript
interface RateLimiter {
  checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult>;
}

class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private localCache: AdaptiveCache,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker,
    private degradationHandler: DegradationHandler
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    // Get all applicable limits for this request
    const limits = this.config.getLimits(tier, path);
    
    // Check all limits concurrently (global + endpoint-specific)
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost, path))
    );
    
    // Return the most restrictive result (first blocked or least remaining)
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    path: string
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    
    // Try local cache first with adaptive TTL
    const cached = this.localCache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      // Use cache if we have sufficient headroom
      const headroom = limit.bypassCache ? 1.0 : 1.5; // Critical endpoints: no headroom
      if (cached.remaining >= cost * headroom) {
        return {
          ...cached,
          remaining: cached.remaining - cost, // Optimistic decrement
          source: 'cache'
        };
      }
    }
    
    // Cache miss or insufficient tokens - check Redis (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost);
        
        // Update local cache with adaptive TTL
        const cacheTTL = limit.bypassCache ? 0 : this.localCache.getAdaptiveTTL();
        if (cacheTTL > 0) {
          this.localCache.set(cacheKey, result, cacheTTL);
        }
        
        return result;
      });
    } catch (error) {
      // Circuit breaker open or Redis failure
      logger.error('Rate limit check failed', { 
        identifier: `${identifier.type}:${this.maskKey(identifier.key)}`, 
        limit: limit.name, 
        error: error.message,
        path
      });
      
      // Use tier-based degradation
      return this.degradationHandler.handleFailure(identifier, limit, cost, tier, path);
    }
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    
    // Token bucket algorithm with Redis Lua script for atomicity
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      
      -- Get current state (tokens, last_refill_time)
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      -- Calculate tokens to add based on elapsed time
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Check if we can consume
      if tokens >= cost then
        -- Consume tokens
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Return: allowed=1, remaining, limit, reset_time
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      else
        -- Insufficient tokens - still update refill time to prevent gaming
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        -- Calculate retry delay
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        -- Return: allowed=0, remaining, limit, reset_time, retry_after
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const now = await this.getRedisTime();
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60 // TTL with 1min buffer
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: 'redis',
      expiresAt: now + this.localCache.getAdaptiveTTL()
    };
  }
  
  private async getRedisTime(): Promise<number> {
    // Use Redis TIME for clock synchronization
    const [seconds, microseconds] = await this.redis.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private maskKey(key: string): string {
    if (key.length <= 4) return '****';
    return key.slice(0, 4) + '****';
  }
}
```

### 3. Adaptive Cache

```typescript
class AdaptiveCache {
  private cache: LRUCache<string, RateLimitResult>;
  private redisHealthy = true;
  private baseTTL = 1500; // Default: 1.5s
  
  constructor(
    private config: CacheConfig = {
      minTTL: 1000,    // 1s minimum
      maxTTL: 3000,    // 3s maximum
      baseTTL: 1500,   // 1.5s default
      adaptiveEnabled: true
    }
  ) {
    this.cache = new LRUCache<string, RateLimitResult>({
      max: 100000,
      ttl: this.baseTTL,
      ttlAutopurge: true,
      updateAgeOnGet: false,
      updateAgeOnHas: false,
      maxSize: 256 * 1024 * 1024,
      sizeCalculation: () => 2048
    });
  }
  
  getAdaptiveTTL(): number {
    if (!this.config.adaptiveEnabled) {
      return this.config.baseTTL;
    }
    
    // Extend cache TTL when Redis is unhealthy
    return this.redisHealthy ? this.config.baseTTL : this.config.maxTTL;
  }
  
  setRedisHealth(healthy: boolean): void {
    if (this.redisHealthy !== healthy) {
      this.redisHealthy = healthy;
      logger.info('Cache TTL adapted', { 
        healthy, 
        ttl: this.getAdaptiveTTL() 
      });
    }
  }
  
  get(key: string): RateLimitResult | undefined {
    return this.cache.get(key);
  }
  
  set(key: string, value: RateLimitResult, ttl?: number): void {
    this.cache.set(key, value, { ttl: ttl || this.getAdaptiveTTL() });
  }
  
  clear(): void {
    this.cache.clear();
  }
  
  getMetrics(): CacheMetrics {
    return {
      size: this.cache.size,
      memoryUsage: this.cache.calculatedSize || 0,
      currentTTL: this.getAdaptiveTTL(),
      redisHealthy: this.redisHealthy
    };
  }
}

interface CacheConfig {
  minTTL: number;
  maxTTL: number;
  baseTTL: number;
  adaptiveEnabled: boolean;
}
```

### 4. Degradation Handler with Automatic Recovery

```typescript
interface DegradationQuota {
  requestsPerMinute: number;
  costMultiplier: number;
}

class DegradationHandler {
  private readonly DEGRADATION_QUOTAS: Record<string, DegradationQuota> = {
    enterprise: {
      requestsPerMinute: 100,
      costMultiplier: 1.0
    },
    pro: {
      requestsPerMinute: 50,
      costMultiplier: 1.0
    },
    free: {
      requestsPerMinute: 10,
      costMultiplier: 1.5
    },
    ip: {
      requestsPerMinute: 5,
      costMultiplier: 2.0
    }
  };
  
  private degradationState = new LRUCache<string, DegradationState>({
    max: 10000,
    ttl: 60000, // 1 minute TTL
  });
  
  private recoveryTracker = new LRUCache<string, RecoveryState>({
    max: 10000,
    ttl: 300000, // 5 minute TTL
  });
  
  private inDegradedMode = false;
  
  handleFailure(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    tier: string,
    path: string
  ): RateLimitResult {
    this.inDegradedMode = true;
    
    const stateKey = this.buildStateKey(identifier, limit);
    const quota = this.DEGRADATION_QUOTAS[tier] || this.DEGRADATION_QUOTAS.ip;
    
    // Get or initialize degradation state
    let state = this.degradationState.get(stateKey);
    const now = Date.now();
    
    if (!state || now - state.windowStart >= 60000) {
      // New window
      state = {
        windowStart: now,
        tokensUsed: 0,
        requestCount: 0
      };
    }
    
    // Apply cost multiplier
    const adjustedCost = cost * quota.costMultiplier;
    
    // Check if request would exceed quota
    const capacityInWindow = quota.requestsPerMinute;
    const wouldExceed = (state.tokensUsed + adjustedCost) > capacityInWindow;
    
    if (!wouldExceed) {
      // Allow request
      state.tokensUsed += adjustedCost;
      state.requestCount++;
      this.degradationState.set(stateKey, state);
      
      return {
        allowed: true,
        remaining: Math.max(0, capacityInWindow - state.tokensUsed),
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: null,
        source: 'degraded',
        expiresAt: now + 2000
      };
    } else {
      // Reject request
      const timeUntilReset = (state.windowStart + 60000) - now;
      
      return {
        allowed: false,
        remaining: 0,
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: Math.ceil(timeUntilReset / 1000),
        source: 'degraded',
        expiresAt: now + 2000
      };
    }
  }
  
  // Called by circuit breaker on successful Redis operations
  recordSuccess(identifier: Identifier, limit: LimitConfig): void {
    if (!this.inDegradedMode) return;
    
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now()
      };
    }
    
    recovery.successCount++;
    recovery.totalCount++;
    recovery.lastSuccessTime = Date.now();
    
    this.recoveryTracker.set(recoveryKey, recovery);
    
    // Check if we should exit degraded mode
    if (recovery.successCount >= 10 && recovery.successCount / recovery.totalCount > 0.9) {
      this.exitDegradedMode(identifier, limit);
    }
  }
  
  recordFailure(identifier: Identifier, limit: LimitConfig): void {
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now()
      };
    }
    
    recovery.totalCount++;
    this.recoveryTracker.set(recoveryKey, recovery);
  }
  
  private exitDegradedMode(identifier: Identifier, limit: LimitConfig): void {
    const stateKey = this.buildStateKey(identifier, limit);
    
    // Clear degradation state for this key
    this.degradationState.delete(stateKey);
    this.recoveryTracker.delete(stateKey);
    
    logger.info('Exiting degraded mode', {
      identifier: `${identifier.type}:${identifier.key}`,
      limit: limit.name
    });
    
    metrics.degradationRecoveries.inc({
      tier: identifier.tier || 'unknown',
      limit: limit.name
    });
    
    // Check if any degradation state remains
    if (this.degradationState.size === 0) {
      this.inDegradedMode = false;
      logger.info('All rate limiters recovered from degraded mode');
    }
  }
  
  private buildStateKey(identifier: Identifier, limit: LimitConfig): string {
    return `degraded:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  isInDegradedMode(): boolean {
    return this.inDegradedMode;
  }
  
  getMetrics(): DegradationMetrics {
    const allStates = Array.from(this.degradationState.entries());
    
    return {
      inDegradedMode: this.inDegradedMode,
      activeWindows: allStates.length,
      totalRequests: allStates.reduce((sum, [_, state]) => sum + state.requestCount, 0),
      byTier: this.groupByTier(allStates)
    };
  }
  
  private groupByTier(states: [string, DegradationState][]): Record<string, number> {
    const grouped: Record<string, number> = {};
    
    for (const [key, state] of states) {
      const parts = key.split(':');
      const tier = parts[1];
      grouped[tier] = (grouped[tier] || 0) + state.requestCount;
    }
    
    return grouped;
  }
}

interface DegradationState {
  windowStart: number;
  tokensUsed: number;
  requestCount: number;
}

interface RecoveryState {
  successCount: number;
  totalCount: number;
  lastSuccessTime: number;
}
```

### 5. Cost Calculator (Static Only)

```typescript
interface CostContext {
  path: string;
  method: string;
}

class CostCalculator {
  constructor(private config: RateLimitConfig) {}
  
  calculate(path: string, method: string): number {
    // Find matching endpoint configuration
    const endpoint = this.config.endpoints.find(e => 
      this.matchPath(e.pattern, path) && 
      (!e.method || e.method === method)
    );
    
    // Return configured base cost
    return endpoint?.cost || 1;
  }
  
  private matchPath(pattern: string, path: string): boolean {
    // Support wildcards: /api/users/* matches /api/users/123
    // Support ** for multi-segment: /api/**/export matches /api/v1/users/export
    const regexPattern = pattern
      .replace(/\*\*/g, '___MULTI___')
      .replace(/\*/g, '[^/]+')
      .replace(/___MULTI___/g, '.*');
    const regex = new RegExp('^' + regexPattern + '$');
    return regex.test(path);
  }
}
```

### 6. Configuration Model with Per-Endpoint Cache Control

```typescript
interface RateLimitConfig {
  version: string;
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
  cacheConfig: CacheConfig;
}

interface TierConfig {
  name: string;
  limits: LimitConfig[];
}

interface LimitConfig {
  name: string;
  scope: 'read' | 'write';
  capacity: number;
  refillRate: number;
  windowSeconds: number;
  appliesTo?: string[];
  bypassCache?: boolean; // NEW: Force Redis check for critical limits
}

interface EndpointConfig {
  pattern: string;
  method?: string;
  cost: number;
}

// Example configuration
const config: RateLimitConfig = {
  version: '1.0.0',
  cacheConfig: {
    minTTL: 1000,
    maxTTL: 3000,
    baseTTL: 1500,
    adaptiveEnabled: true
  },
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',
          capacity: 10,
          refillRate: 10 / 60,
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'search',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 60,
          windowSeconds: 60,
          appliesTo: ['/api/search']
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 500,
          refillRate: 500 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete']
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 10,
          refillRate: 10 / 300,  // 10 per 5 minutes
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          bypassCache: true // Critical: always check Redis
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 100,
          refillRate: 100 / 300,
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          bypassCache: true
        }
      ]
    }
  },
  endpoints: [
    { pattern: '/api/search', method: 'POST', cost: 3 },
    { pattern: '/api/analyze', method: 'POST', cost: 5 },
    { pattern: '/api/export', method: 'GET', cost: 10 },
    { pattern: '/api/batch', method: 'POST', cost: 5 },
    { pattern: '/api/payment/*', method: 'POST', cost: 1 }
  ]
};

class ConfigManager {
  private currentConfig: RateLimitConfig;
  private pendingConfig: RateLimitConfig | null = null;
  private configWatcher?: FSWatcher;
  private reloadLock = false;
  
  constructor(configPath: string) {
    this.currentConfig = this.loadConfig(configPath);
    this.setupHotReload(configPath);
  }
  
  private setupHotReload(configPath: string): void {
    this.configWatcher = fs.watch(configPath, (eventType) => {
      if (eventType === 'change' && !this.reloadLock) {
        this.reloadLock = true;
        
        setTimeout(() => {
          try {
            const newConfig = this.loadConfig(configPath);
            
            if (this.validateConfig(newConfig)) {
              const oldVersion = this.currentConfig.version;
              this.pendingConfig = newConfig;
              
              logger.info('Config staged for reload', { 
                oldVersion, 
                newVersion: newConfig.version 
              });
              
              metrics.configReloads.inc({ success: 'true' });
            } else {
              logger.error('Config validation failed, keeping old config');
              metrics.configReloads.inc({ success: 'false' });
            }
          } catch (error) {
            logger.error('Config reload failed', { error });
            metrics.configReloads.inc({ success: 'false' });
          } finally {
            this.reloadLock = false;
          }
        }, 100);
      }
    });
  }
  
  private loadConfig(path: string): RateLimitConfig {
    const raw = fs.readFileSync(path, 'utf-8');
    return JSON.parse(raw);
  }
  
  private validateConfig(config: RateLimitConfig): boolean {
    if (!config.version || !config.tiers || !config.endpoints) {
      return false;
    }
    
    for (const [tierName, tierConfig] of Object.entries(config.tiers)) {
      if (!tierConfig.limits || tierConfig.limits.length === 0) {
        return false;
      }
      
      for (const limit of tierConfig.limits) {
        if (limit.capacity <= 0 || limit.refillRate <= 0) {
          return false;
        }
        
        if (!['read', 'write'].includes(limit.scope)) {
          return false;
        }
      }
    }
    
    // Validate cache config if present
    if (config.cacheConfig) {
      const cc = config.cacheConfig;
      if (cc.minTTL >= cc.maxTTL || cc.baseTTL < cc.minTTL || cc.baseTTL > cc.maxTTL) {
        return false;
      }
    }
    
    return true;
  }
  
  getLimits(tier: string, path: string): LimitConfig[] {
    // Apply pending config if available
    if (this.pendingConfig) {
      this.currentConfig = this.pendingConfig;
      this.pendingConfig = null;
      logger.info('Config applied', { version: this.currentConfig.version });
    }
    
    const tierConfig = this.currentConfig.tiers[tier];
    if (!tierConfig) {
      throw new Error(`Unknown tier: ${tier}`);
    }
    
    return tierConfig.limits.filter(limit => {
      if (!limit.appliesTo) return true;
      return limit.appliesTo.some(pattern => this.matchPath(pattern, path));
    });
  }
  
  private matchPath(pattern: string, path: string): boolean {
    const regexPattern = pattern
      .replace(/\*\*/g, '___MULTI___')
      .replace(/\*/g, '[^/]+')
      .replace(/___MULTI___/g, '.*');
    const regex = new RegExp('^' + regexPattern + '$');
    return regex.test(path);
  }
  
  getConfig(): RateLimitConfig {
    return this.currentConfig;
  }
  
  getCacheConfig(): CacheConfig {
    return this.currentConfig.cacheConfig || {
      minTTL: 1000,
      maxTTL: 3000,
      baseTTL: 1500,
      adaptiveEnabled: true
    };
  }
}
```

### 7. Enhanced Circuit Breaker with Health Feedback

```typescript
class CircuitBreaker {
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  
  private readonly FAILURE_THRESHOLD = 5;
  private readonly SUCCESS_THRESHOLD = 3;
  private readonly TIMEOUT_MS = 30000;
  private readonly OPERATION_TIMEOUT_MS = 2000;
  
  constructor(
    private name: string,
    private onStateChange?: (healthy: boolean) => void
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.TIMEOUT_MS) {
        logger.info('Circuit breaker entering half-open state', { name: this.name });
        this.state = 'HALF_OPEN';
      } else {
        metrics.circuitBreakerRejections.inc({ breaker: this.name });
        throw new Error(`Circuit breaker is OPEN for ${this.name}`);
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT_MS);
      
      this.successes++;
      this.failures = 0;
      
      if (this.state === 'HALF_OPEN' && this.successes >= this.SUCCESS_THRESHOLD) {
        logger.info('Circuit breaker recovered', { name: this.name });
        this.state = 'CLOSED';
        this.onStateChange?.(true);
      }
      
      metrics.circuitBreakerState.set({ breaker: this.name }, 0);
      
      return result;
    } catch (error) {
      this.failures++;
      this.successes = 0;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD && this.state !== 'OPEN') {
        this.state = 'OPEN';
        logger.error('Circuit breaker opened', { 
          name: this.name, 
          failures: this.failures 
        });
        metrics.circuitBreakerState.set({ breaker: this.name }, 1);
        this.onStateChange?.(false);
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
  
  getState(): { state: string; failures: number; successes: number } {
    return {
      state: this.state,
      failures: this.failures,
      successes: this.successes
    };
  }
}
```

### 8. Identifier Resolution (Same)

```typescript
interface Identifier {
  type: 'user' | 'ip' | 'apikey';
  key: string;
  userId?: string;
  ipAddress?: string;
  tier?: string;
}

class IdentifierResolver {
  async resolve(request: Request): Promise<Identifier> {
    const apiKey = this.extractApiKey(request);
    if (apiKey) {
      const validated = await this.validateApiKey(apiKey);
      if (validated) {
        return {
          type: 'apikey',
          key: validated.keyId,
          userId: validated.userId,
          ipAddress: this.getClientIP(request),
          tier: validated.tier
        };
      }
    }
    
    const userId = await this.getUserFromSession(request);
    if (userId) {
      const tier = await this.getUserTier(userId);
      return {
        type: 'user',
        key: userId,
        userId: userId,
        ipAddress: this.getClientIP(request),
        tier
      };
    }
    
    const ip = this.getClientIP(request);
    return {
      type: 'ip',
      key: ip,
      ipAddress: ip,
      tier: 'free'
    };
  }
  
  private extractApiKey(request: Request): string | null {
    const authHeader = request.headers.get('Authorization');
    if (authHeader?.startsWith('Bearer ')) {
      return authHeader.substring(7);
    }
    return request.headers.get('X-API-Key');
  }
  
  private getClientIP(request: Request): string {
    const forwardedFor = request.headers.get('X-Forwarded-For');
    if (forwardedFor) {
      const ips = forwardedFor.split(',').map(ip => ip.trim());
      return ips[0];
    }
    
    const realIP = request.headers.get('X-Real-IP');
    if (realIP) return realIP;
    
    return request.socket.remoteAddress || '0.0.0.0';
  }
  
  private async validateApiKey(apiKey: string): Promise<{
    keyId: string;
    userId: string;
    tier: string;
  } | null> {
    return await apiKeyService.validate(apiKey);
  }
  
  private async getUserFromSession(request: Request): Promise<string | null> {
    return await sessionService.getUserId(request);
  }
  
  private async getUserTier(userId: string): Promise<string> {
    return await userService.getTier(userId);
  }
}
```

### 9. Response Headers

```typescript
function buildRateLimitHeaders(
  result: RateLimitResult,
  cost: number
): Record<string, string> {
  const headers: Record<string, string> = {
    'RateLimit-Limit': result.limit.toString(),
    'RateLimit-Remaining': Math.floor(result.remaining).toString(),
    'RateLimit-Reset': Math.ceil(result.resetAt / 1000).toString(),
  };
  
  if (cost > 1) {
    headers['X-RateLimit-Cost'] = cost.toString();
  }
  
  if (!result.allowed && result.retryAfter) {
    headers['Retry-After'] = result.retryAfter.toString();
  }
  
  if (result.source === 'degraded') {
    headers['X-RateLimit-Degraded'] = 'true';
    headers['Warning'] = '199 - "Rate limiting in degraded mode"';
  }
  
  return headers;
}
```

### 10. Deployment Architecture (Same)

```typescript
const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'ratelimit-primary',
  sentinelPassword: process.env.SENTINEL_PASSWORD,
  password: process.env.REDIS_PASSWORD,
  db: 0,
  connectTimeout: 2000,
  commandTimeout: 2000,
  maxRetriesPerRequest: 1,
  enableReadyCheck: true,
  enableOfflineQueue: false,
  lazyConnect: false,
  retryStrategy: (times) => {
    if (times > 3) return null;
    return Math.min(times * 50, 200);
  }
});

setInterval(async () => {
  try {
    await redis.ping();
    metrics.redisHealth.set(1);
    // Feed health status to cache
    adaptiveCache.setRedisHealth(true);
  } catch (error) {
    metrics.redisHealth.set(0);
    adaptiveCache.setRedisHealth(false);
    logger.error('Redis health check failed', { error });
  }
}, 5000);
```

### 11. Enhanced Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Cache metrics
  cacheHits: Counter;
  cacheMisses: Counter;
  cacheSize: Gauge;
  cacheMemory: Gauge;
  cacheTTL: Gauge; // NEW: Track adaptive TTL
  
  // Redis metrics
  redisErrors: Counter;
  redisLatency: Histogram;
  redisHealth: Gauge;
  
  // Circuit breaker metrics
  circuitBreakerState: Gauge;
  circuitBreakerRejections: Counter;
  
  // Degradation metrics
  degradedRequests: Counter;
  degradedRequestsByTier: Counter;
  degradationRecoveries: Counter; // NEW: Track recoveries
  
  // Business metrics
  tokenBucketUtilization: Histogram;
  costDistribution: Histogram;
  tierRejections: Counter;
  
  // Per-endpoint metrics (NEW)
  endpointRejections: Counter;
}

class MetricsCollector {
  async record(
    result: RateLimitResult,
    duration: number,
    identifier: Identifier,
    tier: string,
    cost: number,
    path: string
  ): Promise<void> {
    const labels = { 
      tier, 
      source: result.source, 
      type: identifier.type 
    };
    
    if (result.allowed) {
      this.metrics.requestsAllowed.inc(labels);
    } else {
      this.metrics.requestsBlocked.inc(labels);
      this.metrics.tierRejections.inc({ tier });
      this.metrics.endpointRejections.inc({ tier, path }); // NEW
    }
    
    this.metrics.rateLimitCheckDuration.observe(labels, duration);
    
    const utilization = 1 - (result.remaining / result.limit);
    this.metrics.tokenBucketUtilization.observe(labels, utilization);
    
    this.metrics.costDistribution.observe({ tier }, cost);
    
    if (result.source === 'cache') {
      this.metrics.cacheHits.inc(labels);
    } else if (result.source === 'redis') {
      this.metrics.cacheMisses.inc(labels);
    }
    
    if (result.source === 'degraded') {
      this.metrics.degradedRequests.inc(labels);
      this.metrics.degradedRequestsByTier.inc({ tier });
    }
    
    // Track adaptive cache TTL (NEW)
    this.metrics.cacheTTL.set(adaptiveCache.getAdaptiveTTL());
  }
}
```

## What I Improved

1. **Adaptive Cache TTL**: Instead of fixed 2s, cache TTL extends to 3s when Redis is unhealthy, reducing load during degradation while maintaining 1.5s during normal operation.

2. **Per-Limit Cache Control**: Added `bypassCache` flag for critical endpoints (payments, writes) requiring 100% accuracy. These always check Redis.

3. **Automatic Recovery Tracking**: Degradation handler now tracks success rate and automatically exits degraded mode when Redis recovers (>90% success rate over 10 requests).

4. **Circuit Breaker Health Feedback**: Circuit breaker now notifies cache of health changes, enabling immediate TTL adaptation.

5. **Better Path Matching**: Enhanced glob support with `**` for multi-segment wildcards (`/api/**/export` matches `/api/v1/users/export`).

6. **Improved Observability**:
   - Added `degradationRecoveries` metric to track automatic recovery
   - Added `cacheTTL` gauge to monitor adaptive behavior
   - Added per-endpoint rejection tracking for hotspot identification

7. **Safer Error Handling**: Masked sensitive keys in logs, added path context to error messages.

8. **Half-Open Circuit State**: Circuit breaker now uses HALF_OPEN state for gradual recovery testing.

## What I Kept

1. **Token bucket with atomic Lua scripts** - Distributed correctness
2. **Redis TIME for clock sync** - Prevents time-based exploits
3. **Multi-tier limiting (global + endpoint)** - Comprehensive protection
4. **Tier-based degradation quotas** - Simple, predictable
5. **Cost multipliers in degradation** - Resource protection during outages
6. **Static cost configuration** - Predictable consumption
7. **Read/write scope only** - Clear categorization
8. **Async config reload** - Safe, non-disruptive
9. **Sentinel architecture** - Appropriate for initial scale
10. **Non-blocking metrics and audit logging** - Performance over perfect observability
11. **1.5x cache headroom** - Good balance

## Remaining Concerns

1. **Recovery Threshold Tuning**: Is 90% success rate over 10 requests the right threshold for exiting degraded mode? Too aggressive may cause flapping.

2. **Adaptive Cache Memory Impact**: Extending TTL to 3s during degradation increases memory usage by 50%. Is 256MB cache sufficient?

3. **Critical Endpoint Performance**: `bypassCache` forces Redis check on every request. Could this create a bottleneck for high-volume payment endpoints?

4. **Degradation State Cleanup**: LRU cache has 5min TTL for recovery tracking. Should this be shorter to prevent stale state during rapid Redis recovery/failure cycles?

5. **Metrics Cardinality**: Per-endpoint rejection tracking could explode cardinality with many endpoints. Should this be sampled or aggregated?

## Convergence Status

**ITERATING** - Third iteration adding adaptive behavior and automatic recovery.

## PROMPT_FOR_ARCHITECT:

Focus your review on these adaptive and recovery mechanisms:

1. **Adaptive Cache TTL (1.5s → 3s)**: Does extending TTL during Redis outages create unacceptable overage (up to 3% vs 1.5%)? Is the memory impact (50% increase) acceptable?

2. **Automatic Recovery Logic**: Is the recovery threshold (90% success over 10 requests) appropriate? Could this cause flapping between degraded/normal modes?

3. **Per-Limit Cache Bypass**: Should critical endpoints like payments bypass cache entirely, or is 1.5x headroom with Redis fallback sufficient?

4. **Half-Open Circuit State**: Does the gradual recovery via HALF_OPEN state add meaningful resilience, or is it unnecessary complexity?

5. **Recovery State TTL**: Is 5 minutes appropriate for tracking recovery state, or should it be shorter (1-2 min) to respond faster to Redis stability changes?

6. **Trade-off Between Accuracy and Availability**: This design prioritizes availability (adaptive cache, graceful degradation) over strict accuracy. Is this the right balance for a REST API rate limiter?

**Convergence Signal:** ITERATING

---

## Round 4

### 🔵 Agent A

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with adaptive resilience:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket with atomic Redis operations         │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  │  • Adaptive caching with health-based policy        │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (tiered cache)                ↓ (authoritative)   │
│  ┌──────────────────────┐      ┌─────────────────────┐     │
│  │  Tiered Cache        │      │  Redis Sentinel     │     │
│  │  • L1: In-memory     │      │  Primary + Replicas │     │
│  │  • L2: Read replicas │      └─────────────────────┘     │
│  └──────────────────────┘                                    │
│         ↓ (on failure)                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Degradation Handler with Exponential Recovery       │   │
│  │  • Tier-based quotas with cost awareness            │   │
│  │  • Exponential backoff recovery tracking            │   │
│  │  • Jittered retry windows                           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Operations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Audit       │  │  Config      │     │
│  │  Collector   │  │  Logger      │  │  Manager     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limiter Service with Tiered Caching

```typescript
class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private l1Cache: AdaptiveLRUCache,
    private l2Strategy: ReadReplicaStrategy,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker,
    private degradationHandler: DegradationHandler
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    const limits = this.config.getLimits(tier, path);
    
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost, path, tier))
    );
    
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    path: string,
    tier: string
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    const policy = this.getCachePolicy(limit, tier);
    
    // L1: In-memory cache with policy-based headroom
    const cached = this.l1Cache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      if (cached.remaining >= cost * policy.headroom) {
        return {
          ...cached,
          remaining: cached.remaining - cost,
          source: 'l1-cache'
        };
      }
    }
    
    // L2: Read replicas for non-critical reads
    if (policy.allowL2 && !limit.requiresPrimary) {
      try {
        const l2Result = await this.l2Strategy.checkReplica(identifier, limit, cost);
        if (l2Result && l2Result.remaining >= cost * 1.1) {
          this.l1Cache.set(cacheKey, l2Result, policy.l1TTL);
          return { ...l2Result, source: 'l2-replica' };
        }
      } catch (error) {
        // L2 failure, fall through to primary
        logger.debug('L2 cache miss or failure', { error: error.message });
      }
    }
    
    // Primary: Redis check (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost, true);
        
        if (policy.l1TTL > 0) {
          this.l1Cache.set(cacheKey, result, policy.l1TTL);
        }
        
        return result;
      });
    } catch (error) {
      logger.error('Rate limit check failed', { 
        identifier: `${identifier.type}:${this.maskKey(identifier.key)}`, 
        limit: limit.name, 
        error: error.message,
        path
      });
      
      return this.degradationHandler.handleFailure(
        identifier, 
        limit, 
        cost, 
        tier, 
        path
      );
    }
  }

  private getCachePolicy(limit: LimitConfig, tier: string): CachePolicy {
    // Critical endpoints: minimal caching
    if (limit.criticality === 'critical') {
      return {
        l1TTL: 500,        // 500ms only
        headroom: 1.0,     // No headroom tolerance
        allowL2: false     // Never use replicas
      };
    }
    
    // High-value tiers: conservative caching
    if (tier === 'enterprise' || tier === 'pro') {
      return {
        l1TTL: 1000,       // 1s cache
        headroom: 1.2,     // 20% headroom
        allowL2: true
      };
    }
    
    // Free tier: aggressive caching to reduce load
    return {
      l1TTL: 2000,         // 2s cache
      headroom: 1.5,       // 50% headroom
      allowL2: true
    };
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    isPrimary: boolean
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    const now = await this.getRedisTime(isPrimary);
    
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      local is_primary = tonumber(ARGV[6])
      
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Only consume on primary
      if is_primary == 1 and tokens >= cost then
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      elseif is_primary == 0 then
        -- Read-only check for replicas
        return {tokens >= cost and 1 or 0, tokens, capacity, now}
      else
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60,
        isPrimary ? 1 : 0
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: isPrimary ? 'redis-primary' : 'redis-replica',
      expiresAt: now + this.l1Cache.getBaseTTL()
    };
  }
  
  private async getRedisTime(isPrimary: boolean): Promise<number> {
    const client = isPrimary ? this.redis : this.l2Strategy.getReplicaClient();
    const [seconds, microseconds] = await client.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private maskKey(key: string): string {
    if (key.length <= 4) return '****';
    return key.slice(0, 4) + '****';
  }
}
```

### 2. Tiered Cache Architecture

```typescript
class AdaptiveLRUCache {
  private cache: LRUCache<string, RateLimitResult>;
  private healthState: HealthState = { healthy: true, lastCheck: Date.now() };
  
  constructor(private config: CacheConfig) {
    this.cache = new LRUCache<string, RateLimitResult>({
      max: config.maxEntries || 100000,
      ttl: config.baseTTL,
      ttlAutopurge: true,
      updateAgeOnGet: false,
      updateAgeOnHas: false,
      maxSize: config.maxMemoryBytes || 256 * 1024 * 1024,
      sizeCalculation: () => 2048
    });
  }
  
  getBaseTTL(): number {
    return this.config.baseTTL;
  }
  
  setHealthState(healthy: boolean): void {
    if (this.healthState.healthy !== healthy) {
      this.healthState = { healthy, lastCheck: Date.now() };
      logger.info('Cache health state changed', { healthy });
    }
  }
  
  get(key: string): RateLimitResult | undefined {
    return this.cache.get(key);
  }
  
  set(key: string, value: RateLimitResult, ttl: number): void {
    this.cache.set(key, value, { ttl });
  }
  
  clear(): void {
    this.cache.clear();
  }
  
  getMetrics(): CacheMetrics {
    return {
      size: this.cache.size,
      memoryUsage: this.cache.calculatedSize || 0,
      healthy: this.healthState.healthy
    };
  }
}

class ReadReplicaStrategy {
  private replicaClients: RedisClient[];
  private currentReplicaIndex = 0;
  
  constructor(
    private config: ReplicaConfig,
    private primaryClient: RedisClient
  ) {
    this.replicaClients = config.replicaHosts.map(host =>
      new Redis({
        host,
        port: config.port,
        password: config.password,
        db: 0,
        connectTimeout: 1000,
        commandTimeout: 1000,
        maxRetriesPerRequest: 1,
        enableReadyCheck: false,
        lazyConnect: false,
        readOnly: true
      })
    );
  }
  
  getReplicaClient(): RedisClient {
    if (this.replicaClients.length === 0) {
      return this.primaryClient;
    }
    
    // Round-robin replica selection
    const client = this.replicaClients[this.currentReplicaIndex];
    this.currentReplicaIndex = (this.currentReplicaIndex + 1) % this.replicaClients.length;
    return client;
  }
  
  async checkReplica(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number
  ): Promise<RateLimitResult | null> {
    const client = this.getReplicaClient();
    const key = `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
    
    try {
      const [seconds] = await client.time();
      const now = parseInt(seconds) * 1000;
      
      const state = await client.hmget(key, 'tokens', 'last_refill');
      const tokens = parseInt(state[0]) || limit.capacity;
      const lastRefill = parseInt(state[1]) || now;
      
      const elapsed = Math.max(0, now - lastRefill);
      const tokensToAdd = elapsed * limit.refillRate;
      const currentTokens = Math.min(limit.capacity, tokens + tokensToAdd);
      
      return {
        allowed: currentTokens >= cost,
        remaining: currentTokens,
        limit: limit.capacity,
        resetAt: now + ((limit.capacity - currentTokens) / limit.refillRate),
        retryAfter: null,
        source: 'redis-replica',
        expiresAt: now + 1000
      };
    } catch (error) {
      logger.debug('Replica check failed', { error: error.message });
      return null;
    }
  }
}

interface CachePolicy {
  l1TTL: number;      // L1 cache TTL in ms
  headroom: number;   // Token headroom multiplier (1.0 = exact, 1.5 = 50% buffer)
  allowL2: boolean;   // Whether to use L2 read replicas
}
```

### 3. Degradation Handler with Exponential Recovery

```typescript
class DegradationHandler {
  private readonly DEGRADATION_QUOTAS: Record<string, DegradationQuota> = {
    enterprise: {
      requestsPerMinute: 100,
      costMultiplier: 1.0
    },
    pro: {
      requestsPerMinute: 50,
      costMultiplier: 1.0
    },
    free: {
      requestsPerMinute: 10,
      costMultiplier: 1.5
    },
    ip: {
      requestsPerMinute: 5,
      costMultiplier: 2.0
    }
  };
  
  private degradationState = new LRUCache<string, DegradationState>({
    max: 10000,
    ttl: 120000, // 2 minutes TTL (extended from 1min)
  });
  
  private recoveryTracker = new LRUCache<string, RecoveryState>({
    max: 10000,
    ttl: 180000, // 3 minutes TTL (reduced from 5min)
  });
  
  private globalRecoveryPhase: RecoveryPhase = RecoveryPhase.NORMAL;
  
  handleFailure(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    tier: string,
    path: string
  ): RateLimitResult {
    const stateKey = this.buildStateKey(identifier, limit);
    const quota = this.DEGRADATION_QUOTAS[tier] || this.DEGRADATION_QUOTAS.ip;
    
    let state = this.degradationState.get(stateKey);
    const now = Date.now();
    
    if (!state || now - state.windowStart >= 60000) {
      state = {
        windowStart: now,
        tokensUsed: 0,
        requestCount: 0,
        failureTime: now
      };
    }
    
    const adjustedCost = cost * quota.costMultiplier;
    const capacityInWindow = quota.requestsPerMinute;
    const wouldExceed = (state.tokensUsed + adjustedCost) > capacityInWindow;
    
    if (!wouldExceed) {
      state.tokensUsed += adjustedCost;
      state.requestCount++;
      this.degradationState.set(stateKey, state);
      
      return {
        allowed: true,
        remaining: Math.max(0, capacityInWindow - state.tokensUsed),
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: null,
        source: 'degraded',
        expiresAt: now + 1000 // Shorter cache during degradation
      };
    } else {
      const timeUntilReset = (state.windowStart + 60000) - now;
      
      return {
        allowed: false,
        remaining: 0,
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: Math.ceil(timeUntilReset / 1000),
        source: 'degraded',
        expiresAt: now + 1000
      };
    }
  }
  
  recordSuccess(identifier: Identifier, limit: LimitConfig): void {
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now(),
        consecutiveSuccesses: 0,
        phase: RecoveryPhase.TESTING
      };
    }
    
    recovery.successCount++;
    recovery.totalCount++;
    recovery.consecutiveSuccesses++;
    recovery.lastSuccessTime = Date.now();
    
    this.recoveryTracker.set(recoveryKey, recovery);
    
    // Exponential recovery thresholds
    const shouldProgress = this.shouldProgressRecovery(recovery);
    
    if (shouldProgress) {
      this.progressRecoveryPhase(identifier, limit, recovery);
    }
  }
  
  recordFailure(identifier: Identifier, limit: LimitConfig): void {
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now(),
        consecutiveSuccesses: 0,
        phase: RecoveryPhase.TESTING
      };
    }
    
    recovery.totalCount++;
    recovery.consecutiveSuccesses = 0; // Reset on failure
    this.recoveryTracker.set(recoveryKey, recovery);
    
    // Regression: move back a phase
    if (recovery.phase !== RecoveryPhase.TESTING) {
      recovery.phase = Math.max(RecoveryPhase.TESTING, recovery.phase - 1);
      logger.warn('Recovery regression', {
        identifier: `${identifier.type}:${identifier.key}`,
        limit: limit.name,
        phase: RecoveryPhase[recovery.phase]
      });
    }
  }
  
  private shouldProgressRecovery(recovery: RecoveryState): boolean {
    // Phase-based thresholds with exponential backoff
    switch (recovery.phase) {
      case RecoveryPhase.TESTING:
        // Initial testing: need 5 consecutive successes
        return recovery.consecutiveSuccesses >= 5;
      
      case RecoveryPhase.PARTIAL:
        // Partial recovery: need 15 consecutive successes
        return recovery.consecutiveSuccesses >= 15;
      
      case RecoveryPhase.STABILIZING:
        // Stabilizing: need 30 consecutive successes + 95% success rate
        return recovery.consecutiveSuccesses >= 30 && 
               (recovery.successCount / recovery.totalCount) >= 0.95;
      
      case RecoveryPhase.NORMAL:
        return false; // Already fully recovered
      
      default:
        return false;
    }
  }
  
  private progressRecoveryPhase(
    identifier: Identifier,
    limit: LimitConfig,
    recovery: RecoveryState
  ): void {
    const oldPhase = recovery.phase;
    recovery.phase = Math.min(RecoveryPhase.NORMAL, recovery.phase + 1);
    
    logger.info('Recovery phase progression', {
      identifier: `${identifier.type}:${identifier.key}`,
      limit: limit.name,
      oldPhase: RecoveryPhase[oldPhase],
      newPhase: RecoveryPhase[recovery.phase],
      consecutiveSuccesses: recovery.consecutiveSuccesses,
      successRate: (recovery.successCount / recovery.totalCount).toFixed(3)
    });
    
    // Fully recovered
    if (recovery.phase === RecoveryPhase.NORMAL) {
      this.exitDegradedMode(identifier, limit);
    }
    
    metrics.recoveryPhaseTransitions.inc({
      tier: identifier.tier || 'unknown',
      limit: limit.name,
      phase: RecoveryPhase[recovery.phase]
    });
  }
  
  private exitDegradedMode(identifier: Identifier, limit: LimitConfig): void {
    const stateKey = this.buildStateKey(identifier, limit);
    
    this.degradationState.delete(stateKey);
    this.recoveryTracker.delete(stateKey);
    
    logger.info('Fully recovered from degraded mode', {
      identifier: `${identifier.type}:${identifier.key}`,
      limit: limit.name
    });
    
    metrics.degradationRecoveries.inc({
      tier: identifier.tier || 'unknown',
      limit: limit.name
    });
    
    // Update global recovery phase
    if (this.degradationState.size === 0) {
      this.globalRecoveryPhase = RecoveryPhase.NORMAL;
      logger.info('All rate limiters fully recovered');
    }
  }
  
  private buildStateKey(identifier: Identifier, limit: LimitConfig): string {
    return `degraded:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  isInDegradedMode(): boolean {
    return this.degradationState.size > 0;
  }
  
  getRecoveryPhase(): RecoveryPhase {
    return this.globalRecoveryPhase;
  }
}

enum RecoveryPhase {
  TESTING = 0,      // Initial recovery attempts (5 successes)
  PARTIAL = 1,      // Partial recovery (15 successes)
  STABILIZING = 2,  // Stabilizing (30 successes + 95% rate)
  NORMAL = 3        // Fully recovered
}

interface DegradationState {
  windowStart: number;
  tokensUsed: number;
  requestCount: number;
  failureTime: number;
}

interface RecoveryState {
  successCount: number;
  totalCount: number;
  lastSuccessTime: number;
  consecutiveSuccesses: number;
  phase: RecoveryPhase;
}
```

### 4. Configuration Model with Criticality Levels

```typescript
interface RateLimitConfig {
  version: string;
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
  cacheConfig: CacheConfig;
  replicaConfig?: ReplicaConfig;
}

interface LimitConfig {
  name: string;
  scope: 'read' | 'write';
  capacity: number;
  refillRate: number;
  windowSeconds: number;
  appliesTo?: string[];
  criticality?: 'normal' | 'critical'; // NEW: Endpoint criticality
  requiresPrimary?: boolean;           // NEW: Force primary checks
}

interface EndpointConfig {
  pattern: string;
  method?: string;
  cost: number;
  criticality?: 'normal' | 'critical'; // NEW: Per-endpoint criticality
}

const config: RateLimitConfig = {
  version: '1.0.0',
  cacheConfig: {
    baseTTL: 1500,
    maxEntries: 100000,
    maxMemoryBytes: 256 * 1024 * 1024
  },
  replicaConfig: {
    replicaHosts: ['replica-1.example.com', 'replica-2.example.com'],
    port: 6379,
    password: process.env.REDIS_PASSWORD || ''
  },
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete'],
          criticality: 'normal'
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        },
        {
          name: 'write',
          scope: 'write',
          capacity: 500,
          refillRate: 500 / 3600,
          windowSeconds: 3600,
          appliesTo: ['/api/create', '/api/update', '/api/delete'],
          criticality: 'normal'
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 300,
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          criticality: 'critical',
          requiresPrimary: true
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 100,
          refillRate: 100 / 300,
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          criticality: 'critical',
          requiresPrimary: true
        }
      ]
    }
  },
  endpoints: [
    { pattern: '/api/search', method: 'POST', cost: 3, criticality: 'normal' },
    { pattern: '/api/analyze', method: 'POST', cost: 5, criticality: 'normal' },
    { pattern: '/api/export', method: 'GET', cost: 10, criticality: 'normal' },
    { pattern: '/api/payment/*', method: 'POST', cost: 1, criticality: 'critical' }
  ]
};
```

### 5. Enhanced Circuit Breaker with Exponential Backoff

```typescript
class CircuitBreaker {
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private state: CircuitState = CircuitState.CLOSED;
  private openDuration = 10000; // Start with 10s backoff
  
  private readonly MIN_BACKOFF = 10000;    // 10s
  private readonly MAX_BACKOFF = 120000;   // 2min
  private readonly SUCCESS_THRESHOLD = 5;  // 5 successes to close
  private readonly FAILURE_THRESHOLD = 3;  // 3 failures to open
  private readonly OPERATION_TIMEOUT = 2000;
  
  constructor(
    private name: string,
    private onStateChange?: (healthy: boolean) => void,
    private degradationHandler?: DegradationHandler
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.OPEN) {
      const timeSinceFailure = Date.now() - this.lastFailureTime;
      
      if (timeSinceFailure > this.openDuration) {
        logger.info('Circuit breaker entering half-open state', { 
          name: this.name,
          backoff: this.openDuration
        });
        this.state = CircuitState.HALF_OPEN;
        this.successes = 0;
      } else {
        metrics.circuitBreakerRejections.inc({ breaker: this.name });
        throw new Error(`Circuit breaker OPEN for ${this.name}`);
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT);
      
      this.successes++;
      
      if (this.state === CircuitState.HALF_OPEN && 
          this.successes >= this.SUCCESS_THRESHOLD) {
        logger.info('Circuit breaker closed', { 
          name: this.name,
          consecutiveSuccesses: this.successes
        });
        this.state = CircuitState.CLOSED;
        this.failures = 0;
        this.openDuration = this.MIN_BACKOFF; // Reset backoff
        this.onStateChange?.(true);
      }
      
      metrics.circuitBreakerState.set({ breaker: this.name }, this.state);
      
      return result;
    } catch (error) {
      this.successes = 0;
      this.failures++;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD && 
          this.state !== CircuitState.OPEN) {
        // Exponential backoff with jitter
        this.openDuration = Math.min(
          this.MAX_BACKOFF,
          this.openDuration * 2 + Math.random() * 1000
        );
        
        this.state = CircuitState.OPEN;
        logger.error('Circuit breaker opened', { 
          name: this.name, 
          failures: this.failures,
          backoffMs: this.openDuration
        });
        metrics.circuitBreakerState.set({ breaker: this.name }, this.state);
        this.onStateChange?.(false);
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
  
  getState(): { state: string; failures: number; successes: number; backoff: number } {
    return {
      state: CircuitState[this.state],
      failures: this.failures,
      successes: this.successes,
      backoff: this.openDuration
    };
  }
}

enum CircuitState {
  CLOSED = 0,
  HALF_OPEN = 1,
  OPEN = 2
}
```

### 6. Deployment Architecture with Read Replicas

```typescript
const redis = new Redis({
  sentinels: [
    { host: 'sentinel-1', port: 26379 },
    { host: 'sentinel-2', port: 26379 },
    { host: 'sentinel-3', port: 26379 }
  ],
  name: 'ratelimit-primary',
  sentinelPassword: process.env.SENTINEL_PASSWORD,
  password: process.env.REDIS_PASSWORD,
  db: 0,
  connectTimeout: 2000,
  commandTimeout: 2000,
  maxRetriesPerRequest: 1,
  enableReadyCheck: true,
  enableOfflineQueue: false,
  lazyConnect: false,
  retryStrategy: (times) => {
    if (times > 3) return null;
    return Math.min(times * 50, 200);
  }
});

const l1Cache = new AdaptiveLRUCache({
  baseTTL: 1500,
  maxEntries: 100000,
  maxMemoryBytes: 256 * 1024 * 1024
});

const l2Strategy = new ReadReplicaStrategy(
  {
    replicaHosts: ['replica-1.local', 'replica-2.local'],
    port: 6379,
    password: process.env.REDIS_PASSWORD || ''
  },
  redis
);

const degradationHandler = new DegradationHandler();

const circuitBreaker = new CircuitBreaker(
  'redis-primary',
  (healthy) => {
    l1Cache.setHealthState(healthy);
    if (healthy) {
      logger.info('Redis primary healthy, cache state updated');
    } else {
      logger.warn('Redis primary unhealthy, relying on degradation');
    }
  },
  degradationHandler
);

// Health monitoring with recovery tracking
setInterval(async () => {
  try {
    await redis.ping();
    metrics.redisHealth.set(1);
    
    // Record success for all active degraded states
    // This allows recovery tracking to progress
    for (const [key, _] of degradationHandler['degradationState'].entries()) {
      const [_, type, idKey, limitName] = key.split(':');
      degradationHandler.recordSuccess(
        { type: type as any, key: idKey },
        { name: limitName } as any
      );
    }
  } catch (error) {
    metrics.redisHealth.set(0);
    logger.error('Redis health check failed', { error });
  }
}, 5000);

// Metrics dashboard
setInterval(() => {
  const cacheMetrics = l1Cache.getMetrics();
  const cbState = circuitBreaker.getState();
  const recoveryPhase = degradationHandler.getRecoveryPhase();
  
  logger.info('Rate limiter health', {
    cache: {
      size: cacheMetrics.size,
      memoryMB: (cacheMetrics.memoryUsage / (1024 * 1024)).toFixed(2),
      healthy: cacheMetrics.healthy
    },
    circuitBreaker: {
      state: cbState.state,
      backoffMs: cbState.backoff
    },
    degradation: {
      active: degradationHandler.isInDegradedMode(),
      recoveryPhase: RecoveryPhase[recoveryPhase]
    }
  });
}, 30000);
```

### 7. Enhanced Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Tiered cache metrics
  l1CacheHits: Counter;
  l1CacheMisses: Counter;
  l2CacheHits: Counter;
  l2CacheMisses: Counter;
  cacheSize: Gauge;
  cacheMemory: Gauge;
  
  // Redis metrics
  redisErrors: Counter;
  redisLatency: Histogram;
  redisHealth: Gauge;
  
  // Circuit breaker metrics
  circuitBreakerState: Gauge;
  circuitBreakerRejections: Counter;
  
  // Recovery metrics
  degradedRequests: Counter;
  degradedRequestsByTier: Counter;
  degradationRecoveries: Counter;
  recoveryPhaseTransitions: Counter;
  
  // Business metrics
  tokenBucketUtilization: Histogram;
  costDistribution: Histogram;
  tierRejections: Counter;
  endpointRejections: Counter;
}
```

## Rationale

### Key Design Decisions

1. **Tiered Cache Architecture (L1 + L2)**
   - L1 (in-memory LRU): Sub-millisecond reads for hot keys
   - L2 (read replicas): ~5-10ms reads for warm keys, offloads primary
   - Primary (Redis): Authoritative source for all writes and critical reads
   - **Why**: Provides 3-tier defense against Redis primary overload while maintaining accuracy guarantees where needed

2. **Policy-Based Cache Headroom**
   - Critical endpoints (payments): 1.0x headroom (exact), 500ms TTL, no L2
   - Pro/Enterprise: 1.2x headroom, 1s TTL, L2 enabled
   - Free tier: 1.5x headroom, 2s TTL, L2 enabled
   - **Why**: Balances accuracy requirements with load distribution. Critical operations get strict guarantees, bulk traffic gets aggressive caching

3. **Exponential Recovery with Phases**
   - TESTING: 5 consecutive successes required
   - PARTIAL: 15 consecutive successes required
   - STABILIZING: 30 successes + 95% success rate
   - NORMAL: Fully recovered
   - **Why**: Prevents flapping between degraded/normal modes. Each phase requires exponentially more proof of stability, with regression on any failure

4. **Circuit Breaker with Exponential Backoff**
   - Starts at 10s backoff, doubles on each failure (max 2min)
   - Adds jitter to prevent thundering herd
   - **Why**: Gives Redis time to recover without constant retry storms. Jitter prevents synchronized retries across instances

5. **Read Replicas for Non-Critical Checks**
   - Non-critical limits can read from replicas
   - Read-only checks via Lua script (no token consumption)
   - Falls back to primary if replica is unavailable
   - **Why**: Offloads ~70% of read traffic from primary during normal operation, critical path still uses primary

6. **Per-Limit Criticality Levels**
   - Normal: Standard caching, can use replicas
   - Critical: Minimal caching, primary only
   - **Why**: Allows fine-grained control over accuracy vs. performance trade-offs per endpoint type

## What I Changed

1. **Replaced Adaptive Cache TTL with Tiered Caching**
   - **Old**: Single-layer cache with TTL extending from 1.5s → 3s during outages
   - **New**: L1 (in-memory) + L2 (read replicas) + Primary, with policy-based TTLs
   - **Why**: Extending TTL to 3s increases overage risk. Tiered architecture provides better load distribution without sacrificing accuracy

2. **Replaced Binary Recovery with Exponential Phases**
   - **Old**: 90% success rate over 10 requests triggers recovery
   - **New**: 4-phase recovery (TESTING → PARTIAL → STABILIZING → NORMAL) with increasing thresholds
   - **Why**: 10 requests is too small a sample; 90% allows 1 failure per 10 requests which could indicate instability. Exponential phases require sustained stability before full recovery

3. **Added Read Replica Strategy**
   - **Old**: Single Redis primary for all operations
   - **New**: Read replicas for non-critical limit checks
   - **Why**: Reduces primary load by ~70% during normal operation, improves availability during primary degradation

4. **Changed Recovery State TTL from 5min → 3min**
   - **Why**: 5 minutes is too long; Redis stability usually resolves or persists within 1-2 minutes. Shorter TTL allows faster response to state changes

5. **Added Circuit Breaker Exponential Backoff**
   - **Old**: Fixed 30s timeout between retry attempts
   - **New**: 10s → 20s → 40s → 80s → 120s (max) with jitter
   - **Why**: Fixed timeout causes thundering herd; exponential backoff with jitter staggers retries and gives Redis more time to recover from sustained issues

6. **Changed Degradation State TTL from 1min → 2min**
   - **Why**: 1 minute is too aggressive for recovery tracking; extending to 2 minutes allows better signal accumulation during partial outages

7. **Removed bypassCache Flag**
   - **Old**: Boolean flag to force Redis check
   - **New**: Criticality-based policies with headroom/TTL tuning
   - **Why**: Binary bypass is too coarse; policy-based approach allows nuanced control (500ms TTL for critical vs 2s for free tier)

8. **Added HALF_OPEN Circuit State**
   - **Old**: Existing design had this
   - **Kept**: Essential for gradual recovery testing
   - **Enhanced**: Now requires 5 consecutive successes (up from 3) to close circuit

## What I Kept

1. **Token bucket with atomic Lua scripts** - Distributed correctness is non-negotiable
2. **Redis TIME for clock sync** - Prevents time-based exploits across distributed instances
3. **Multi-tier limiting (global + endpoint)** - Comprehensive protection model
4. **Tier-based degradation quotas** - Simple, predictable fallback behavior
5. **Cost multipliers in degradation** - Resource protection during outages
6. **Static cost configuration** - Predictable consumption model
7. **Read/write scope categorization** - Clear operational separation
8. **Async config reload** - Safe, non-disruptive updates
9. **Sentinel architecture** - Appropriate for initial scale (1-10M req/day)
10. **Non-blocking metrics/audit logging** - Performance over perfect observability
11. **Identifier resolution strategy** - Clean abstraction for user/IP/API key identification

## Open Questions

1. **L2 Replica Lag Tolerance**: Read replicas may lag primary by 100-500ms. For free-tier traffic with 1.5x headroom and 2s TTL, max overage could reach 2-3%. Is this acceptable?

2. **Recovery Phase Thresholds**: Are 5/15/30 consecutive successes the right progression, or should phases be time-based (e.g., "30 seconds of 95% success rate")?

3. **Memory Scaling**: With L1 cache holding 100K entries, peak memory ~200MB. Under Redis outage, this could grow. Should we add memory pressure eviction?

4. **Replica Failover**: If all replicas fail but primary is healthy, L2 strategy falls back to primary. Could this cause primary overload during replica-only outages?

5. **Critical Endpoint Definition**: Should "critical" be determined by endpoint pattern (payments) or by business impact? How do we guide operators to set this correctly?

6. **Cross-Region Consistency**: For multi-region deployments, should we use regional Redis primaries with cross-region replication, or single global primary? This design assumes single-region.

## Convergence Status

**ITERATING** - Second iteration introducing tiered caching and exponential recovery.

## PROMPT_FOR_CRITIC:

Focus your review on these architectural changes:

1. **Tiered Cache Strategy (L1 + L2 + Primary)**: Does the added complexity of read replicas justify the ~70% primary offload? Is the replica lag tolerance (100-500ms) acceptable given our caching headroom?

2. **Exponential Recovery Phases**: Is the 4-phase progression (5/15/30/∞ consecutive successes) better than the threshold-based approach (90% over 10 requests)? Does it effectively prevent flapping?

3. **Policy-Based Criticality**: Are the three policies (critical/pro/free) sufficient granularity, or do we need more fine-grained control? Should policies be per-endpoint or per-limit?

4. **Circuit Breaker Backoff**: Does exponential backoff (10s → 2min) with jitter adequately prevent thundering herd while allowing timely recovery?

5. **Replica Fallback Strategy**: When L2 (replicas) fails but primary is healthy, falling back to primary could overload it. Should we have a "replica-only" mode that rejects requests instead?

6. **Memory vs Accuracy Trade-off**: With tiered caching, we're using ~200MB memory (vs 128MB in your design) to achieve better availability. Is this trade-off worthwhile?

7. **Regional Deployment**: This design assumes single-region Redis. For multi-region, would regional primaries with cross-region sync be better, or should we use geo-distributed degradation quotas?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Rate Limiting System for REST API

## Architecture Overview

**Three-tier architecture with adaptive resilience and operational safeguards:**

```
┌─────────────────────────────────────────────────────────────┐
│                    API Gateway Layer                         │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────┐    │
│  │ Rate Limit     │→ │ Identifier   │→ │ Tier        │    │
│  │ Middleware     │  │ Resolver     │  │ Resolver    │    │
│  └────────────────┘  └──────────────┘  └─────────────┘    │
└──────────────┬──────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│                Rate Limiting Core                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Rate Limiter Service                                │   │
│  │  • Token bucket with atomic Redis operations         │   │
│  │  • Multi-tier limit checking (global + endpoint)     │   │
│  │  • Cost calculation per operation                    │   │
│  │  • Adaptive caching with health-based policy        │   │
│  └──────────────────────────────────────────────────────┘   │
│         ↓ (tiered cache)                ↓ (authoritative)   │
│  ┌──────────────────────┐      ┌─────────────────────┐     │
│  │  Tiered Cache        │      │  Redis Sentinel     │     │
│  │  • L1: In-memory     │      │  Primary + Replicas │     │
│  │  • L2: Read replicas │      │  • Replica lag      │     │
│  │    with lag check    │      │    monitoring       │     │
│  └──────────────────────┘      └─────────────────────┘     │
│         ↓ (on failure)                                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Degradation Handler with Hybrid Recovery            │   │
│  │  • Tier-based quotas with cost awareness            │   │
│  │  • Time + success count recovery gates              │   │
│  │  • Jittered retry windows                           │   │
│  │  • Memory pressure monitoring                       │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
               ↓
┌──────────────┴──────────────────────────────────────────────┐
│              Observability & Operations                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Metrics     │  │  Audit       │  │  Config      │     │
│  │  Collector   │  │  Logger      │  │  Manager     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Rate Limiter Service with Lag-Aware Tiered Caching

```typescript
class TokenBucketRateLimiter implements RateLimiter {
  constructor(
    private redis: RedisClient,
    private l1Cache: AdaptiveLRUCache,
    private l2Strategy: LagAwareReplicaStrategy,
    private config: RateLimitConfig,
    private circuitBreaker: CircuitBreaker,
    private degradationHandler: DegradationHandler
  ) {}

  async checkAndConsume(
    identifier: Identifier,
    tier: Tier,
    path: string,
    cost: number
  ): Promise<RateLimitResult> {
    const limits = this.config.getLimits(tier, path);
    
    const results = await Promise.all(
      limits.map(limit => this.checkSingleLimit(identifier, limit, cost, path, tier))
    );
    
    const blocked = results.find(r => !r.allowed);
    if (blocked) return blocked;
    
    return results.reduce((most, current) => 
      current.remaining < most.remaining ? current : most
    );
  }

  private async checkSingleLimit(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    path: string,
    tier: string
  ): Promise<RateLimitResult> {
    const cacheKey = this.buildCacheKey(identifier, limit);
    const policy = this.getCachePolicy(limit, tier);
    
    // L1: In-memory cache with policy-based headroom
    const cached = this.l1Cache.get(cacheKey);
    if (cached && cached.expiresAt > Date.now()) {
      if (cached.remaining >= cost * policy.headroom) {
        const updated = {
          ...cached,
          remaining: cached.remaining - cost,
          source: 'l1-cache' as const
        };
        this.l1Cache.set(cacheKey, updated, policy.l1TTL);
        return updated;
      }
    }
    
    // L2: Read replicas with lag awareness
    if (policy.allowL2 && !limit.requiresPrimary) {
      try {
        const l2Result = await this.l2Strategy.checkReplica(
          identifier, 
          limit, 
          cost,
          policy.maxReplicaLagMs
        );
        
        if (l2Result && l2Result.remaining >= cost * policy.l2SafetyMargin) {
          this.l1Cache.set(cacheKey, l2Result, policy.l1TTL);
          return { ...l2Result, source: 'l2-replica' };
        }
      } catch (error) {
        logger.debug('L2 cache miss or failure', { 
          error: error.message,
          identifier: this.maskIdentifier(identifier)
        });
      }
    }
    
    // Primary: Redis check (authoritative)
    try {
      return await this.circuitBreaker.execute(async () => {
        const result = await this.checkRedis(identifier, limit, cost, true);
        
        if (policy.l1TTL > 0) {
          this.l1Cache.set(cacheKey, result, policy.l1TTL);
        }
        
        // Record success for recovery tracking
        this.degradationHandler.recordSuccess(identifier, limit);
        
        return result;
      });
    } catch (error) {
      logger.error('Rate limit check failed', { 
        identifier: this.maskIdentifier(identifier),
        limit: limit.name, 
        error: error.message,
        path
      });
      
      // Record failure for recovery tracking
      this.degradationHandler.recordFailure(identifier, limit);
      
      return this.degradationHandler.handleFailure(
        identifier, 
        limit, 
        cost, 
        tier, 
        path
      );
    }
  }

  private getCachePolicy(limit: LimitConfig, tier: string): CachePolicy {
    // Critical endpoints: minimal caching, no replicas
    if (limit.criticality === 'critical') {
      return {
        l1TTL: 500,
        headroom: 1.0,
        allowL2: false,
        maxReplicaLagMs: 0,
        l2SafetyMargin: 1.0
      };
    }
    
    // High-value tiers: conservative caching
    if (tier === 'enterprise' || tier === 'pro') {
      return {
        l1TTL: 1000,
        headroom: 1.2,
        allowL2: true,
        maxReplicaLagMs: 200,    // Stricter lag tolerance
        l2SafetyMargin: 1.3      // 30% safety margin on replicas
      };
    }
    
    // Free tier: aggressive caching to reduce load
    return {
      l1TTL: 2000,
      headroom: 1.5,
      allowL2: true,
      maxReplicaLagMs: 500,      // More tolerant lag
      l2SafetyMargin: 1.5        // 50% safety margin
    };
  }

  private async checkRedis(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    isPrimary: boolean
  ): Promise<RateLimitResult> {
    const key = this.buildRedisKey(identifier, limit);
    const now = await this.getRedisTime(isPrimary);
    
    const script = `
      local key = KEYS[1]
      local capacity = tonumber(ARGV[1])
      local refill_rate = tonumber(ARGV[2])
      local cost = tonumber(ARGV[3])
      local now = tonumber(ARGV[4])
      local ttl = tonumber(ARGV[5])
      local is_primary = tonumber(ARGV[6])
      
      local state = redis.call('HMGET', key, 'tokens', 'last_refill')
      local tokens = tonumber(state[1]) or capacity
      local last_refill = tonumber(state[2]) or now
      
      local elapsed = math.max(0, now - last_refill)
      local tokens_to_add = elapsed * refill_rate
      tokens = math.min(capacity, tokens + tokens_to_add)
      
      -- Only consume on primary
      if is_primary == 1 and tokens >= cost then
        local new_tokens = tokens - cost
        redis.call('HSET', key, 'tokens', new_tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        local reset_time = now + ((capacity - new_tokens) / refill_rate)
        return {1, new_tokens, capacity, reset_time}
      elseif is_primary == 0 then
        -- Read-only check for replicas, no HSET
        return {tokens >= cost and 1 or 0, tokens, capacity, now}
      else
        -- Update timestamp even on rejection for accurate refill
        redis.call('HSET', key, 'tokens', tokens, 'last_refill', now)
        redis.call('EXPIRE', key, ttl)
        
        local deficit = cost - tokens
        local retry_after = math.ceil(deficit / refill_rate)
        
        return {0, tokens, capacity, now + retry_after, retry_after}
      }
    `;
    
    const result = await this.redis.eval(
      script,
      [key],
      [
        limit.capacity,
        limit.refillRate,
        cost,
        now,
        limit.windowSeconds + 60,
        isPrimary ? 1 : 0
      ]
    );
    
    return {
      allowed: result[0] === 1,
      remaining: result[1],
      limit: result[2],
      resetAt: result[3],
      retryAfter: result[4] || null,
      source: isPrimary ? 'redis-primary' : 'redis-replica',
      expiresAt: now + this.l1Cache.getBaseTTL()
    };
  }
  
  private async getRedisTime(isPrimary: boolean): Promise<number> {
    const client = isPrimary ? this.redis : this.l2Strategy.getReplicaClient();
    const [seconds, microseconds] = await client.time();
    return parseInt(seconds) * 1000 + Math.floor(parseInt(microseconds) / 1000);
  }
  
  private buildCacheKey(identifier: Identifier, limit: LimitConfig): string {
    return `rl:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private buildRedisKey(identifier: Identifier, limit: LimitConfig): string {
    return `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private maskIdentifier(identifier: Identifier): string {
    const masked = identifier.key.length <= 4 ? '****' : 
                   identifier.key.slice(0, 4) + '****';
    return `${identifier.type}:${masked}`;
  }
}
```

### 2. Lag-Aware Read Replica Strategy

```typescript
class LagAwareReplicaStrategy {
  private replicaClients: RedisClient[];
  private currentReplicaIndex = 0;
  private replicaLagCache = new Map<string, number>();
  private readonly LAG_CHECK_INTERVAL = 10000; // Check lag every 10s
  
  constructor(
    private config: ReplicaConfig,
    private primaryClient: RedisClient
  ) {
    this.replicaClients = config.replicaHosts.map(host =>
      new Redis({
        host,
        port: config.port,
        password: config.password,
        db: 0,
        connectTimeout: 1000,
        commandTimeout: 1000,
        maxRetriesPerRequest: 1,
        enableReadyCheck: false,
        lazyConnect: false,
        readOnly: true
      })
    );
    
    // Start lag monitoring
    this.startLagMonitoring();
  }
  
  private startLagMonitoring(): void {
    setInterval(async () => {
      for (let i = 0; i < this.replicaClients.length; i++) {
        try {
          const replica = this.replicaClients[i];
          const info = await replica.info('replication');
          
          // Parse master_last_io_seconds_ago from INFO output
          const match = info.match(/master_last_io_seconds_ago:(\d+)/);
          const lagSeconds = match ? parseInt(match[1]) : 0;
          const lagMs = lagSeconds * 1000;
          
          this.replicaLagCache.set(`replica-${i}`, lagMs);
          
          metrics.replicaLag.set({ replica: `replica-${i}` }, lagMs);
        } catch (error) {
          logger.warn('Failed to check replica lag', { 
            replica: i, 
            error: error.message 
          });
          this.replicaLagCache.set(`replica-${i}`, Infinity);
        }
      }
    }, this.LAG_CHECK_INTERVAL);
  }
  
  getReplicaClient(): RedisClient {
    if (this.replicaClients.length === 0) {
      return this.primaryClient;
    }
    
    // Round-robin replica selection
    const client = this.replicaClients[this.currentReplicaIndex];
    this.currentReplicaIndex = (this.currentReplicaIndex + 1) % this.replicaClients.length;
    return client;
  }
  
  async checkReplica(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    maxLagMs: number
  ): Promise<RateLimitResult | null> {
    const replicaIndex = this.currentReplicaIndex;
    const client = this.getReplicaClient();
    
    // Check if replica lag is acceptable
    const currentLag = this.replicaLagCache.get(`replica-${replicaIndex}`) || 0;
    if (currentLag > maxLagMs) {
      logger.debug('Replica lag too high, skipping', { 
        replicaIndex, 
        lagMs: currentLag, 
        maxLagMs 
      });
      metrics.replicaLagSkips.inc({ replica: `replica-${replicaIndex}` });
      return null;
    }
    
    const key = `ratelimit:${identifier.type}:${identifier.key}:${limit.name}`;
    
    try {
      const [seconds] = await client.time();
      const now = parseInt(seconds) * 1000;
      
      const state = await client.hmget(key, 'tokens', 'last_refill');
      const tokens = parseFloat(state[0]) || limit.capacity;
      const lastRefill = parseInt(state[1]) || now;
      
      const elapsed = Math.max(0, now - lastRefill);
      const tokensToAdd = elapsed * limit.refillRate;
      const currentTokens = Math.min(limit.capacity, tokens + tokensToAdd);
      
      return {
        allowed: currentTokens >= cost,
        remaining: currentTokens,
        limit: limit.capacity,
        resetAt: now + ((limit.capacity - currentTokens) / limit.refillRate),
        retryAfter: null,
        source: 'redis-replica',
        expiresAt: now + 1000
      };
    } catch (error) {
      logger.debug('Replica check failed', { 
        replica: replicaIndex, 
        error: error.message 
      });
      return null;
    }
  }
}

interface CachePolicy {
  l1TTL: number;           // L1 cache TTL in ms
  headroom: number;        // Token headroom multiplier for L1
  allowL2: boolean;        // Whether to use L2 read replicas
  maxReplicaLagMs: number; // Max acceptable replica lag
  l2SafetyMargin: number;  // Safety margin for L2 reads
}
```

### 3. Hybrid Recovery Degradation Handler

```typescript
class DegradationHandler {
  private readonly DEGRADATION_QUOTAS: Record<string, DegradationQuota> = {
    enterprise: { requestsPerMinute: 100, costMultiplier: 1.0 },
    pro: { requestsPerMinute: 50, costMultiplier: 1.0 },
    free: { requestsPerMinute: 10, costMultiplier: 1.5 },
    ip: { requestsPerMinute: 5, costMultiplier: 2.0 }
  };
  
  private degradationState = new LRUCache<string, DegradationState>({
    max: 10000,
    ttl: 90000, // 90s TTL (compromise between responsiveness and stability)
  });
  
  private recoveryTracker = new LRUCache<string, RecoveryState>({
    max: 10000,
    ttl: 150000, // 2.5min TTL
  });
  
  private memoryPressure = false;
  
  constructor() {
    this.startMemoryMonitoring();
  }
  
  private startMemoryMonitoring(): void {
    setInterval(() => {
      const used = process.memoryUsage();
      const heapUsedMB = used.heapUsed / 1024 / 1024;
      const heapTotalMB = used.heapTotal / 1024 / 1024;
      const usagePercent = (heapUsedMB / heapTotalMB) * 100;
      
      this.memoryPressure = usagePercent > 85;
      
      if (this.memoryPressure) {
        logger.warn('Memory pressure detected', { 
          heapUsedMB: heapUsedMB.toFixed(2),
          usagePercent: usagePercent.toFixed(1)
        });
        
        // Aggressive eviction under memory pressure
        const toEvict = Math.floor(this.degradationState.size * 0.3);
        let evicted = 0;
        for (const key of this.degradationState.keys()) {
          if (evicted >= toEvict) break;
          this.degradationState.delete(key);
          evicted++;
        }
      }
      
      metrics.memoryPressure.set(this.memoryPressure ? 1 : 0);
      metrics.degradationStateSize.set(this.degradationState.size);
    }, 5000);
  }
  
  handleFailure(
    identifier: Identifier,
    limit: LimitConfig,
    cost: number,
    tier: string,
    path: string
  ): RateLimitResult {
    const stateKey = this.buildStateKey(identifier, limit);
    const quota = this.DEGRADATION_QUOTAS[tier] || this.DEGRADATION_QUOTAS.ip;
    
    let state = this.degradationState.get(stateKey);
    const now = Date.now();
    
    if (!state || now - state.windowStart >= 60000) {
      state = {
        windowStart: now,
        tokensUsed: 0,
        requestCount: 0,
        failureTime: now
      };
    }
    
    const adjustedCost = cost * quota.costMultiplier;
    const capacityInWindow = quota.requestsPerMinute;
    const wouldExceed = (state.tokensUsed + adjustedCost) > capacityInWindow;
    
    if (!wouldExceed) {
      state.tokensUsed += adjustedCost;
      state.requestCount++;
      
      if (!this.memoryPressure) {
        this.degradationState.set(stateKey, state);
      }
      
      return {
        allowed: true,
        remaining: Math.max(0, capacityInWindow - state.tokensUsed),
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: null,
        source: 'degraded',
        expiresAt: now + 500 // Short cache during degradation
      };
    } else {
      const timeUntilReset = (state.windowStart + 60000) - now;
      
      return {
        allowed: false,
        remaining: 0,
        limit: capacityInWindow,
        resetAt: state.windowStart + 60000,
        retryAfter: Math.ceil(timeUntilReset / 1000),
        source: 'degraded',
        expiresAt: now + 500
      };
    }
  }
  
  recordSuccess(identifier: Identifier, limit: LimitConfig): void {
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now(),
        consecutiveSuccesses: 0,
        phase: RecoveryPhase.TESTING,
        phaseEntryTime: Date.now()
      };
    }
    
    recovery.successCount++;
    recovery.totalCount++;
    recovery.consecutiveSuccesses++;
    recovery.lastSuccessTime = Date.now();
    
    if (!this.memoryPressure) {
      this.recoveryTracker.set(recoveryKey, recovery);
    }
    
    // Hybrid recovery: time + success count gates
    const shouldProgress = this.shouldProgressRecovery(recovery);
    
    if (shouldProgress) {
      this.progressRecoveryPhase(identifier, limit, recovery);
    }
  }
  
  recordFailure(identifier: Identifier, limit: LimitConfig): void {
    const recoveryKey = this.buildStateKey(identifier, limit);
    let recovery = this.recoveryTracker.get(recoveryKey);
    
    if (!recovery) {
      recovery = {
        successCount: 0,
        totalCount: 0,
        lastSuccessTime: Date.now(),
        consecutiveSuccesses: 0,
        phase: RecoveryPhase.TESTING,
        phaseEntryTime: Date.now()
      };
    }
    
    recovery.totalCount++;
    recovery.consecutiveSuccesses = 0;
    
    if (!this.memoryPressure) {
      this.recoveryTracker.set(recoveryKey, recovery);
    }
    
    // Regression: move back a phase
    if (recovery.phase !== RecoveryPhase.TESTING) {
      recovery.phase = Math.max(RecoveryPhase.TESTING, recovery.phase - 1);
      recovery.phaseEntryTime = Date.now();
      
      logger.warn('Recovery regression', {
        identifier: this.maskIdentifier(identifier),
        limit: limit.name,
        phase: RecoveryPhase[recovery.phase]
      });
    }
  }
  
  private shouldProgressRecovery(recovery: RecoveryState): boolean {
    const now = Date.now();
    const timeInPhase = now - recovery.phaseEntryTime;
    
    switch (recovery.phase) {
      case RecoveryPhase.TESTING:
        // Need 5 consecutive successes AND 10 seconds in phase
        return recovery.consecutiveSuccesses >= 5 && timeInPhase >= 10000;
      
      case RecoveryPhase.PARTIAL:
        // Need 10 consecutive successes AND 20 seconds in phase
        return recovery.consecutiveSuccesses >= 10 && timeInPhase >= 20000;
      
      case RecoveryPhase.STABILIZING:
        // Need 20 consecutive successes AND 30 seconds AND 95% success rate
        return recovery.consecutiveSuccesses >= 20 && 
               timeInPhase >= 30000 &&
               (recovery.successCount / recovery.totalCount) >= 0.95;
      
      case RecoveryPhase.NORMAL:
        return false;
      
      default:
        return false;
    }
  }
  
  private progressRecoveryPhase(
    identifier: Identifier,
    limit: LimitConfig,
    recovery: RecoveryState
  ): void {
    const oldPhase = recovery.phase;
    recovery.phase = Math.min(RecoveryPhase.NORMAL, recovery.phase + 1);
    recovery.phaseEntryTime = Date.now();
    
    logger.info('Recovery phase progression', {
      identifier: this.maskIdentifier(identifier),
      limit: limit.name,
      oldPhase: RecoveryPhase[oldPhase],
      newPhase: RecoveryPhase[recovery.phase],
      consecutiveSuccesses: recovery.consecutiveSuccesses,
      successRate: (recovery.successCount / recovery.totalCount).toFixed(3)
    });
    
    if (recovery.phase === RecoveryPhase.NORMAL) {
      this.exitDegradedMode(identifier, limit);
    }
    
    metrics.recoveryPhaseTransitions.inc({
      tier: identifier.tier || 'unknown',
      limit: limit.name,
      phase: RecoveryPhase[recovery.phase]
    });
  }
  
  private exitDegradedMode(identifier: Identifier, limit: LimitConfig): void {
    const stateKey = this.buildStateKey(identifier, limit);
    
    this.degradationState.delete(stateKey);
    this.recoveryTracker.delete(stateKey);
    
    logger.info('Fully recovered from degraded mode', {
      identifier: this.maskIdentifier(identifier),
      limit: limit.name
    });
    
    metrics.degradationRecoveries.inc({
      tier: identifier.tier || 'unknown',
      limit: limit.name
    });
  }
  
  private buildStateKey(identifier: Identifier, limit: LimitConfig): string {
    return `degraded:${identifier.type}:${identifier.key}:${limit.name}`;
  }
  
  private maskIdentifier(identifier: Identifier): string {
    const masked = identifier.key.length <= 4 ? '****' : 
                   identifier.key.slice(0, 4) + '****';
    return `${identifier.type}:${masked}`;
  }
  
  isInDegradedMode(): boolean {
    return this.degradationState.size > 0;
  }
  
  getMetrics(): DegradationMetrics {
    return {
      degradedCount: this.degradationState.size,
      recoveryTrackerSize: this.recoveryTracker.size,
      memoryPressure: this.memoryPressure
    };
  }
}

enum RecoveryPhase {
  TESTING = 0,      // 5 successes + 10s
  PARTIAL = 1,      // 10 successes + 20s
  STABILIZING = 2,  // 20 successes + 30s + 95% rate
  NORMAL = 3
}

interface DegradationState {
  windowStart: number;
  tokensUsed: number;
  requestCount: number;
  failureTime: number;
}

interface RecoveryState {
  successCount: number;
  totalCount: number;
  lastSuccessTime: number;
  consecutiveSuccesses: number;
  phase: RecoveryPhase;
  phaseEntryTime: number; // NEW: Track time in current phase
}
```

### 4. Circuit Breaker with Adaptive Backoff

```typescript
class CircuitBreaker {
  private failures = 0;
  private successes = 0;
  private lastFailureTime = 0;
  private state: CircuitState = CircuitState.CLOSED;
  private openDuration = 5000; // Start with 5s (more aggressive)
  
  private readonly MIN_BACKOFF = 5000;     // 5s (reduced from 10s)
  private readonly MAX_BACKOFF = 60000;    // 1min (reduced from 2min)
  private readonly SUCCESS_THRESHOLD = 3;  // 3 successes to close (reduced from 5)
  private readonly FAILURE_THRESHOLD = 3;
  private readonly OPERATION_TIMEOUT = 2000;
  
  constructor(
    private name: string,
    private onStateChange?: (healthy: boolean) => void,
    private degradationHandler?: DegradationHandler
  ) {}
  
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === CircuitState.OPEN) {
      const timeSinceFailure = Date.now() - this.lastFailureTime;
      
      if (timeSinceFailure > this.openDuration) {
        logger.info('Circuit breaker entering half-open state', { 
          name: this.name,
          backoff: this.openDuration
        });
        this.state = CircuitState.HALF_OPEN;
        this.successes = 0;
      } else {
        metrics.circuitBreakerRejections.inc({ breaker: this.name });
        throw new Error(`Circuit breaker OPEN for ${this.name}`);
      }
    }
    
    try {
      const result = await this.withTimeout(fn(), this.OPERATION_TIMEOUT);
      
      this.successes++;
      
      if (this.state === CircuitState.HALF_OPEN && 
          this.successes >= this.SUCCESS_THRESHOLD) {
        logger.info('Circuit breaker closed', { 
          name: this.name,
          consecutiveSuccesses: this.successes
        });
        this.state = CircuitState.CLOSED;
        this.failures = 0;
        this.openDuration = this.MIN_BACKOFF; // Reset backoff
        this.onStateChange?.(true);
      }
      
      metrics.circuitBreakerState.set({ breaker: this.name }, this.state);
      
      return result;
    } catch (error) {
      this.successes = 0;
      this.failures++;
      this.lastFailureTime = Date.now();
      
      if (this.failures >= this.FAILURE_THRESHOLD && 
          this.state !== CircuitState.OPEN) {
        // Exponential backoff with jitter (max 10% jitter)
        const jitter = Math.random() * this.openDuration * 0.1;
        this.openDuration = Math.min(
          this.MAX_BACKOFF,
          this.openDuration * 2 + jitter
        );
        
        this.state = CircuitState.OPEN;
        logger.error('Circuit breaker opened', { 
          name: this.name, 
          failures: this.failures,
          backoffMs: this.openDuration
        });
        metrics.circuitBreakerState.set({ breaker: this.name }, this.state);
        this.onStateChange?.(false);
      }
      
      throw error;
    }
  }
  
  private withTimeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<T>((_, reject) => 
        setTimeout(() => reject(new Error('Operation timeout')), ms)
      )
    ]);
  }
  
  getState(): { state: string; failures: number; successes: number; backoff: number } {
    return {
      state: CircuitState[this.state],
      failures: this.failures,
      successes: this.successes,
      backoff: this.openDuration
    };
  }
}

enum CircuitState {
  CLOSED = 0,
  HALF_OPEN = 1,
  OPEN = 2
}
```

### 5. Enhanced Configuration with Per-Limit Policies

```typescript
interface RateLimitConfig {
  version: string;
  tiers: {
    [tier: string]: TierConfig;
  };
  endpoints: EndpointConfig[];
  cacheConfig: CacheConfig;
  replicaConfig?: ReplicaConfig;
  degradationConfig: DegradationConfig; // NEW
}

interface LimitConfig {
  name: string;
  scope: 'read' | 'write';
  capacity: number;
  refillRate: number;
  windowSeconds: number;
  appliesTo?: string[];
  criticality?: 'normal' | 'critical';
  requiresPrimary?: boolean;
}

interface DegradationConfig {
  enableMemoryPressureEviction: boolean;
  memoryPressureThresholdPercent: number;
  evictionRateUnderPressure: number; // 0.0 - 1.0
}

const config: RateLimitConfig = {
  version: '1.0.0',
  cacheConfig: {
    baseTTL: 1500,
    maxEntries: 100000,
    maxMemoryBytes: 256 * 1024 * 1024 // 256MB
  },
  replicaConfig: {
    replicaHosts: ['replica-1.example.com', 'replica-2.example.com'],
    port: 6379,
    password: process.env.REDIS_PASSWORD || ''
  },
  degradationConfig: {
    enableMemoryPressureEviction: true,
    memoryPressureThresholdPercent: 85,
    evictionRateUnderPressure: 0.3
  },
  tiers: {
    free: {
      name: 'free',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 100,
          refillRate: 100 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        }
      ]
    },
    pro: {
      name: 'pro',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 1000,
          refillRate: 1000 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 20,
          refillRate: 20 / 300,
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          criticality: 'critical',
          requiresPrimary: true
        }
      ]
    },
    enterprise: {
      name: 'enterprise',
      limits: [
        {
          name: 'global',
          scope: 'read',
          capacity: 10000,
          refillRate: 10000 / 3600,
          windowSeconds: 3600,
          criticality: 'normal'
        },
        {
          name: 'payment',
          scope: 'write',
          capacity: 100,
          refillRate: 100 / 300,
          windowSeconds: 300,
          appliesTo: ['/api/payment/*'],
          criticality: 'critical',
          requiresPrimary: true
        }
      ]
    }
  },
  endpoints: [
    { pattern: '/api/search', method: 'POST', cost: 3, criticality: 'normal' },
    { pattern: '/api/analyze', method: 'POST', cost: 5, criticality: 'normal' },
    { pattern: '/api/export', method: 'GET', cost: 10, criticality: 'normal' },
    { pattern: '/api/payment/*', method: 'POST', cost: 1, criticality: 'critical' }
  ]
};
```

### 6. Enhanced Metrics

```typescript
interface Metrics {
  // Core metrics
  requestsAllowed: Counter;
  requestsBlocked: Counter;
  rateLimitCheckDuration: Histogram;
  
  // Tiered cache metrics
  l1CacheHits: Counter;
  l1CacheMisses: Counter;
  l2CacheHits: Counter;
  l2CacheMisses: Counter;
  cacheSize: Gauge;
  cacheMemory: Gauge;
  
  // Replica metrics
  replicaLag: Gauge;           // Per-replica lag in ms
  replicaLagSkips: Counter;    // Skipped due to high lag
  
  // Redis metrics
  redisErrors: Counter;
  redisLatency: Histogram;
  redisHealth: Gauge;
  
  // Circuit breaker metrics
  circuitBreakerState: Gauge;
  circuitBreakerRejections: Counter;
  
  // Recovery metrics
  degradedRequests: Counter;
  degradedRequestsByTier: Counter;
  degradationRecoveries: Counter;
  recoveryPhaseTransitions: Counter;
  
  // Memory metrics
  memoryPressure: Gauge;
  degradationStateSize: Gauge;
  
  // Business metrics
  tokenBucketUtilization: Histogram;
  costDistribution: Histogram;
  tierRejections: Counter;
  endpointRejections: Counter;
}
```

## What I Improved

### 1. **Replica Lag Monitoring**
- **Problem**: L2 replicas can lag primary by 100-500ms, causing stale reads
- **Solution**: Added active lag monitoring via Redis INFO replication, with per-policy lag tolerance
- **Benefit**: Critical endpoints skip replicas entirely; free tier tolerates 500ms lag with 1.5x safety margin

### 2. **Hybrid Recovery Gates (Time + Success Count)**
- **Problem**: Pure success-count recovery can be gamed by rapid-fire requests during brief healthy windows
- **Solution**: Each phase requires BOTH success count AND minimum time-in-phase (10s → 20s → 30s)
- **Benefit**: Prevents premature recovery from transient blips; requires sustained stability

### 3. **Memory Pressure Monitoring**
- **Problem**: During prolonged Redis outages, degradation state could grow unbounded
- **Solution**: Active memory monitoring with aggressive eviction (30% of entries) at 85% heap usage
- **Benefit**: Prevents OOM crashes; degrades gracefully to rejecting requests vs crashing

### 4. **Reduced Circuit Breaker Thresholds**
- **Problem**: 10s → 2min backoff is too conservative; 5 successes to close is high
- **Solution**: 5s → 1min backoff with 3 successes to close (from 5)
- **Benefit**: Faster recovery from transient Redis issues (network blips, brief maintenance)

### 5. **L2 Safety Margin**
- **Problem**: Replica reads with exact token checks risk overage due to lag
- **Solution**: Added `l2SafetyMargin` (1.3x for pro, 1.5x for free) - only allow request if `remaining >= cost * margin`
- **Benefit**: Compensates for replication lag without overly restricting throughput

### 6. **Shortened L1 Cache Expiry During Degradation**
- **Problem**: 1-2s cache during degraded mode could compound inaccuracies
- **Solution**: 500ms cache during degraded mode vs 1-2s during normal
- **Benefit**: Tighter quota enforcement when system is already unreliable

### 7. **Adjusted TTLs for Recovery Tracking**
- **Problem**: 5min recovery TTL too long; 1min degradation TTL too short
- **Solution**: 2.5min recovery TTL (from 5min), 90s degradation TTL (from 60s)
- **Benefit**: Better balance between signal accumulation and responsiveness to state changes

## What I Kept

1. **Token bucket with atomic Lua scripts** - Core correctness guarantee
2. **Three-tier cache architecture (L1/L2/Primary)** - Sound load distribution strategy
3. **Policy-based cache configuration** - Flexible per-tier/per-criticality tuning
4. **Multi-phase exponential recovery** - Prevents flapping effectively
5. **Circuit breaker with exponential backoff** - Standard resilience pattern
6. **Tier-based degradation quotas** - Simple, predictable fallback
7. **Cost multipliers in degradation** - Resource protection during outages
8. **Redis Sentinel architecture** - Appropriate for target scale
9. **Non-blocking metrics/audit logging** - Performance-first observability
10. **Static endpoint cost configuration** - Predictable consumption model

## Remaining Concerns

### 1. **Replica Lag Monitoring Overhead**
- INFO replication calls every 10s across all replicas
- For 2 replicas: 12 calls/min per instance
- **Trade-off**: Accuracy vs monitoring overhead; could increase interval to 30s for high-scale deployments

### 2. **Memory Eviction During Prolonged Outages**
- 30% eviction under memory pressure means losing degradation state
- Could cause users to get re-admitted immediately after eviction, then re-throttled
- **Trade-off**: Fairness vs stability; alternative is OOM crash

### 3. **L2 Safety Margin Calibration**
- 1.3x-1.5x margins are conservative estimates
- Under worst-case lag (500ms) with high refill rate (10 tokens/sec), could over-restrict by 5-7 tokens
- **Trade-off**: Protection vs throughput; needs production data to tune

### 4. **Hybrid Recovery Complexity**
- Time-gated + count-gated recovery has 6 tunable parameters (2 per phase)
- Operators may struggle to reason about recovery behavior
- **Trade-off**: Robustness vs operational simplicity

### 5. **Cross-Region Replication Lag**
- Design assumes <500ms lag; cross-region replicas can lag 1-5 seconds
- L2 strategy would skip replicas entirely in multi-region deployments
- **Gap**: Need regional primaries or geo-aware degradation quotas

### 6. **Replica Failover Cascade**
- If all replicas lag beyond tolerance, all L2 attempts fall through to primary
- Could cause primary overload during replica-only issues (e.g., network partition)
- **Missing**: "Replica-only mode" that rejects requests instead of falling back

### 7. **Phase Entry Time Tracking**
- Added `phaseEntryTime` to recovery state (4 bytes per tracked identifier)
- With 10K tracked states: +40KB memory overhead
- **Trade-off**: Accuracy vs memory; negligible at current scale but worth monitoring

## Convergence Status

**ITERATING** - Third iteration addressing lag monitoring, hybrid recovery gates, and memory pressure safeguards.

## PROMPT_FOR_ARCHITECT:

Focus your review on these operational and safety improvements:

1. **Replica Lag Monitoring Strategy**: Is active INFO polling every 10s the right approach, or should we use Redis keyspace notifications, master_link_down_since, or passive lag detection based on read failures?

2. **Hybrid Recovery Gates**: Do time-based gates (10s/20s/30s) effectively prevent premature recovery, or do they just slow down recovery unnecessarily? Should gates be adaptive based on observed failure patterns?

3. **Memory Pressure Eviction**: Is 30% eviction at 85% heap usage the right threshold, or should we use LRU eviction continuously? Should we prioritize evicting certain tiers (free over enterprise)?

4. **L2 Safety Margin Calibration**: How should operators tune the 1.3x-1.5x safety margins? Should these be dynamic based on observed replica lag distribution?

5. **Circuit Breaker Aggressiveness**: Reducing min backoff to 5s and success threshold to 3 makes recovery faster but risks flapping. Is this the right balance, or should we keep 10s/5 successes?

6. **Replica-Only Failure Mode**: When L2 fails but primary is healthy, should we fall back to primary (current) or reject requests to prevent cascade? What's the failure mode priority?

7. **Cross-Region Strategy**: For multi-region deployments, should we abandon L2 replicas entirely and rely on regional primaries, or can we make lag-aware strategy work with higher tolerances (5s)?

**Convergence Signal:** ITERATING

---

