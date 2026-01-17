# Final Agreed Design

**Task:** Design a rate limiting system

**Status:** debating

---

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