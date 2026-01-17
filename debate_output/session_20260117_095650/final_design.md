# Final Agreed Design

**Task:** Design a rate limiting system for a REST API

Requirements:
- Multiple rate limit tiers (free, pro, enterprise)
- Support both user-level and IP-level limiting
- Handle burst traffic gracefully
- Provide clear feedback in headers
- Support distributed deployment
- Consider Redis-based implementation

**Status:** debating

---

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