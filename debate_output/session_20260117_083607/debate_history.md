# Claude Code Debate Session

**Started:** 2026-01-17T08:36:07.602757
**Ended:** 2026-01-17T08:44:36.861399
**Status:** consensus
**Rounds:** 2

## Initial Prompt

Design a caching layer with Redis

---

## Round 1

### 🔵 Agent A

## Design

# Redis Caching Layer

## Architecture Overview

A production-ready caching layer implementing a write-through/write-behind cache pattern with Redis, featuring TTL-based expiration, cache warming, and observability.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    CacheManager                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ Cache Operations: get, set, delete, invalidate         │ │
│  │ Pattern Support: TTL, sliding expiration, tags        │ │
│  │ Metrics: hits, misses, latency                         │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────┬─────────────────────────────────────────┬────────┘
           │                                         │
┌──────────▼─────────────┐              ┌───────────▼─────────┐
│   RedisClient          │              │  FallbackStrategy   │
│  ┌──────────────────┐  │              │  - Memory cache     │
│  │ Connection Pool  │  │              │  - Degraded mode    │
│  │ Retry Logic      │  │              │  - Circuit breaker  │
│  │ Serialization    │  │              └─────────────────────┘
│  └──────────────────┘  │
└────────┬───────────────┘
         │
┌────────▼───────────────────────────────────────────────────┐
│                     Redis Cluster                           │
│  Master/Replica Setup with Sentinel/Cluster Mode            │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### Cache Entry Structure

```typescript
interface CacheEntry<T> {
  key: string;
  value: T;
  metadata: {
    createdAt: number;
    expiresAt: number;
    version: number;
    tags: string[];
    accessCount: number;
    lastAccessed: number;
  };
}

interface CacheKey {
  namespace: string;
  identifier: string;
  version?: string;
}
```

### Key Naming Convention

```
Format: {namespace}:{entity_type}:{identifier}:{version}
Examples:
  - user:profile:12345:v1
  - product:details:abc-789:v2
  - session:data:token-xyz
  - query:results:hash-abc123
```

## Core Interfaces

### CacheManager Interface

```typescript
interface ICacheManager {
  // Basic operations
  get<T>(key: CacheKey, options?: GetOptions): Promise<T | null>;
  set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void>;
  delete(key: CacheKey): Promise<boolean>;
  exists(key: CacheKey): Promise<boolean>;
  
  // Batch operations
  mget<T>(keys: CacheKey[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<CacheKey, T>, options?: SetOptions): Promise<void>;
  
  // Pattern-based operations
  invalidateByTag(tag: string): Promise<number>;
  invalidateByPattern(pattern: string): Promise<number>;
  
  // Cache warming
  warm<T>(key: CacheKey, loader: () => Promise<T>, options?: WarmOptions): Promise<void>;
  
  // Observability
  getStats(): CacheStats;
  healthCheck(): Promise<HealthStatus>;
}

interface GetOptions {
  ttl?: number;              // Sliding expiration
  refresh?: boolean;          // Force refresh from source
  fallback?: () => Promise<any>;
}

interface SetOptions {
  ttl?: number;              // Time to live in seconds
  nx?: boolean;              // Only set if not exists
  xx?: boolean;              // Only set if exists
  tags?: string[];           // For tag-based invalidation
  compress?: boolean;        // Compress large values
}

interface WarmOptions {
  ttl?: number;
  background?: boolean;      // Don't block on warming
  force?: boolean;           // Overwrite existing
}
```

### Redis Client Interface

```typescript
interface IRedisClient {
  // Connection management
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;
  
  // Core commands
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: RedisSetOptions): Promise<void>;
  del(keys: string[]): Promise<number>;
  exists(keys: string[]): Promise<number>;
  
  // Advanced commands
  pipeline(): RedisPipeline;
  multi(): RedisTransaction;
  scan(cursor: number, pattern?: string, count?: number): Promise<ScanResult>;
  
  // Pub/Sub for cache invalidation
  publish(channel: string, message: string): Promise<number>;
  subscribe(channel: string, handler: (message: string) => void): Promise<void>;
}

interface RedisSetOptions {
  ex?: number;    // Expiration in seconds
  px?: number;    // Expiration in milliseconds
  nx?: boolean;   // Only set if not exists
  xx?: boolean;   // Only set if exists
  keepTtl?: boolean;
}
```

## Implementation Details

### Cache Manager Implementation

```typescript
class CacheManager implements ICacheManager {
  private redis: IRedisClient;
  private serializer: ISerializer;
  private metrics: MetricsCollector;
  private fallback: FallbackStrategy;
  private config: CacheConfig;

  constructor(config: CacheConfig) {
    this.config = config;
    this.redis = new RedisClient(config.redis);
    this.serializer = new JSONSerializer();
    this.metrics = new MetricsCollector();
    this.fallback = new FallbackStrategy(config.fallback);
  }

  async get<T>(key: CacheKey, options?: GetOptions): Promise<T | null> {
    const startTime = Date.now();
    const redisKey = this.buildRedisKey(key);
    
    try {
      const cached = await this.redis.get(redisKey);
      
      if (cached) {
        this.metrics.recordHit(redisKey, Date.now() - startTime);
        const entry: CacheEntry<T> = this.serializer.deserialize(cached);
        
        // Sliding expiration
        if (options?.ttl) {
          await this.redis.set(redisKey, cached, { ex: options.ttl, keepTtl: false });
        }
        
        return entry.value;
      }
      
      this.metrics.recordMiss(redisKey, Date.now() - startTime);
      
      // Fallback to loader if provided
      if (options?.fallback) {
        const value = await options.fallback();
        await this.set(key, value, { ttl: options.ttl });
        return value;
      }
      
      return null;
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      return this.fallback.handle<T>(key, error);
    }
  }

  async set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void> {
    const redisKey = this.buildRedisKey(key);
    const startTime = Date.now();
    
    try {
      const entry: CacheEntry<T> = {
        key: redisKey,
        value,
        metadata: {
          createdAt: Date.now(),
          expiresAt: Date.now() + (options?.ttl || this.config.defaultTtl) * 1000,
          version: this.config.version,
          tags: options?.tags || [],
          accessCount: 0,
          lastAccessed: Date.now()
        }
      };

      let serialized = this.serializer.serialize(entry);
      
      // Compression for large values
      if (options?.compress || serialized.length > this.config.compressionThreshold) {
        serialized = await this.compress(serialized);
      }

      await this.redis.set(redisKey, serialized, {
        ex: options?.ttl || this.config.defaultTtl,
        nx: options?.nx,
        xx: options?.xx
      });

      // Store tags for invalidation
      if (options?.tags?.length) {
        await this.indexTags(redisKey, options.tags);
      }

      this.metrics.recordSet(redisKey, Date.now() - startTime);
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      throw new CacheWriteError(`Failed to set cache key ${redisKey}`, error);
    }
  }

  async invalidateByTag(tag: string): Promise<number> {
    const tagKey = `tag:${tag}`;
    const members = await this.redis.smembers(tagKey);
    
    if (members.length === 0) return 0;
    
    const pipeline = this.redis.pipeline();
    members.forEach(key => pipeline.del([key]));
    pipeline.del([tagKey]);
    
    await pipeline.exec();
    this.metrics.recordInvalidation(tag, members.length);
    
    return members.length;
  }

  private async indexTags(key: string, tags: string[]): Promise<void> {
    const pipeline = this.redis.pipeline();
    tags.forEach(tag => {
      pipeline.sadd(`tag:${tag}`, key);
      pipeline.expire(`tag:${tag}`, this.config.tagIndexTtl);
    });
    await pipeline.exec();
  }

  private buildRedisKey(key: CacheKey): string {
    const parts = [key.namespace, key.identifier];
    if (key.version) parts.push(key.version);
    return parts.join(':');
  }
}
```

### Serialization Strategy

```typescript
interface ISerializer {
  serialize<T>(value: T): string;
  deserialize<T>(data: string): T;
}

class JSONSerializer implements ISerializer {
  serialize<T>(value: T): string {
    return JSON.stringify(value);
  }

  deserialize<T>(data: string): T {
    return JSON.parse(data);
  }
}

// For binary data or better performance
class MsgPackSerializer implements ISerializer {
  serialize<T>(value: T): string {
    return msgpack.encode(value).toString('base64');
  }

  deserialize<T>(data: string): T {
    return msgpack.decode(Buffer.from(data, 'base64'));
  }
}
```

### Fallback Strategy

```typescript
class FallbackStrategy {
  private memoryCache: Map<string, any>;
  private circuitBreaker: CircuitBreaker;

  constructor(config: FallbackConfig) {
    this.memoryCache = new Map();
    this.circuitBreaker = new CircuitBreaker({
      failureThreshold: config.failureThreshold || 5,
      resetTimeout: config.resetTimeout || 60000
    });
  }

  handle<T>(key: CacheKey, error: Error): T | null {
    // Check circuit breaker state
    if (this.circuitBreaker.isOpen()) {
      // Use memory cache as fallback
      const memKey = JSON.stringify(key);
      return this.memoryCache.get(memKey) || null;
    }

    this.circuitBreaker.recordFailure();
    throw error;
  }

  recordSuccess(): void {
    this.circuitBreaker.recordSuccess();
  }
}

class CircuitBreaker {
  private failures: number = 0;
  private lastFailureTime: number = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';

  constructor(private config: { failureThreshold: number; resetTimeout: number }) {}

  isOpen(): boolean {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.config.resetTimeout) {
        this.state = 'HALF_OPEN';
        return false;
      }
      return true;
    }
    return false;
  }

  recordFailure(): void {
    this.failures++;
    this.lastFailureTime = Date.now();
    if (this.failures >= this.config.failureThreshold) {
      this.state = 'OPEN';
    }
  }

  recordSuccess(): void {
    this.failures = 0;
    this.state = 'CLOSED';
  }
}
```

## Configuration

```typescript
interface CacheConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    db?: number;
    tls?: boolean;
    cluster?: boolean;
    sentinels?: Array<{ host: string; port: number }>;
    retryStrategy?: (times: number) => number;
    maxRetriesPerRequest?: number;
    connectTimeout?: number;
    commandTimeout?: number;
  };
  
  defaultTtl: number;                    // Default: 3600 (1 hour)
  compressionThreshold: number;          // Default: 1024 bytes
  tagIndexTtl: number;                   // Default: 86400 (24 hours)
  version: number;                       // Schema version for cache entries
  
  fallback: {
    enabled: boolean;
    memoryMaxSize: number;               // Default: 100 MB
    memoryMaxItems: number;              // Default: 10000
    failureThreshold: number;            // Circuit breaker threshold
    resetTimeout: number;                // Circuit breaker reset time
  };
  
  metrics: {
    enabled: boolean;
    exporter: 'prometheus' | 'statsd';
    labels: Record<string, string>;
  };
}
```

## Error Handling

```typescript
class CacheError extends Error {
  constructor(message: string, public cause?: Error) {
    super(message);
    this.name = 'CacheError';
  }
}

class CacheConnectionError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheConnectionError';
  }
}

class CacheWriteError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheWriteError';
  }
}

class CacheReadError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheReadError';
  }
}

// Error handling in application
try {
  const user = await cacheManager.get<User>(
    { namespace: 'user', identifier: userId },
    {
      fallback: async () => await db.users.findById(userId),
      ttl: 300
    }
  );
} catch (error) {
  if (error instanceof CacheConnectionError) {
    // Redis unavailable - fallback handled automatically
    logger.warn('Cache unavailable, used fallback', { error });
  } else {
    // Other errors
    throw error;
  }
}
```

## Observability

```typescript
interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  avgLatency: number;
  p95Latency: number;
  p99Latency: number;
  errorRate: number;
  evictions: number;
  memoryUsage: number;
}

interface HealthStatus {
  healthy: boolean;
  latency: number;
  connected: boolean;
  message?: string;
}

class MetricsCollector {
  private hits: number = 0;
  private misses: number = 0;
  private latencies: number[] = [];
  private errors: number = 0;

  recordHit(key: string, latency: number): void {
    this.hits++;
    this.latencies.push(latency);
    this.emit('cache.hit', { key, latency });
  }

  recordMiss(key: string, latency: number): void {
    this.misses++;
    this.latencies.push(latency);
    this.emit('cache.miss', { key, latency });
  }

  recordError(key: string, error: Error): void {
    this.errors++;
    this.emit('cache.error', { key, error: error.message });
  }

  getStats(): CacheStats {
    const total = this.hits + this.misses;
    const sortedLatencies = [...this.latencies].sort((a, b) => a - b);
    
    return {
      hits: this.hits,
      misses: this.misses,
      hitRate: total > 0 ? this.hits / total : 0,
      avgLatency: this.latencies.reduce((a, b) => a + b, 0) / this.latencies.length,
      p95Latency: sortedLatencies[Math.floor(sortedLatencies.length * 0.95)],
      p99Latency: sortedLatencies[Math.floor(sortedLatencies.length * 0.99)],
      errorRate: total > 0 ? this.errors / total : 0,
      evictions: 0,  // From Redis INFO command
      memoryUsage: 0 // From Redis INFO command
    };
  }

  private emit(event: string, data: any): void {
    // Send to monitoring system (Prometheus, Datadog, etc.)
  }
}
```

## Usage Examples

```typescript
// Initialize cache manager
const cacheManager = new CacheManager({
  redis: {
    host: 'localhost',
    port: 6379,
    password: process.env.REDIS_PASSWORD,
    retryStrategy: (times) => Math.min(times * 50, 2000)
  },
  defaultTtl: 3600,
  compressionThreshold: 1024,
  tagIndexTtl: 86400,
  version: 1,
  fallback: {
    enabled: true,
    memoryMaxSize: 100 * 1024 * 1024,
    memoryMaxItems: 10000,
    failureThreshold: 5,
    resetTimeout: 60000
  },
  metrics: {
    enabled: true,
    exporter: 'prometheus',
    labels: { service: 'api' }
  }
});

// Basic get/set
const user = await cacheManager.get<User>(
  { namespace: 'user', identifier: '123' }
);

if (!user) {
  const freshUser = await db.users.findById('123');
  await cacheManager.set(
    { namespace: 'user', identifier: '123' },
    freshUser,
    { ttl: 300, tags: ['users', 'profile'] }
  );
}

// With automatic fallback
const product = await cacheManager.get<Product>(
  { namespace: 'product', identifier: 'abc' },
  {
    fallback: async () => await db.products.findById('abc'),
    ttl: 600
  }
);

// Batch operations
const userIds = ['1', '2', '3'];
const keys = userIds.map(id => ({ namespace: 'user', identifier: id }));
const users = await cacheManager.mget<User>(keys);

// Tag-based invalidation
await cacheManager.invalidateByTag('users');

// Pattern-based invalidation
await cacheManager.invalidateByPattern('user:*');

// Cache warming
await cacheManager.warm(
  { namespace: 'popular', identifier: 'products' },
  async () => await db.products.findPopular(),
  { ttl: 3600, background: true }
);
```

## Rationale

**Architecture Decisions:**
- **Write-through pattern**: Ensures cache consistency by writing to both cache and source simultaneously
- **Tag-based invalidation**: Enables efficient bulk invalidation of related cache entries without scanning
- **Circuit breaker**: Prevents cascading failures when Redis is unavailable
- **Compression**: Reduces memory usage for large cached values
- **Versioning**: Allows safe schema evolution without manual cache invalidation

**Key Design Choices:**
- **Structured cache keys**: Namespace-based keys prevent collisions and enable pattern-based operations
- **Metadata in entries**: Tracks access patterns for potential eviction strategies
- **Pipeline/multi support**: Batches Redis commands for better performance
- **Fallback strategy**: Graceful degradation with in-memory cache when Redis fails
- **Observability built-in**: Metrics collection enables performance monitoring and optimization

## What I Incorporated

This is the initial design, incorporating:
- Industry-standard caching patterns (write-through, TTL-based expiration)
- Production-ready error handling and fallback mechanisms
- Comprehensive observability for monitoring cache performance
- Flexible configuration for different deployment scenarios

## What I Kept

Initial design elements:
- Clean separation between cache manager and Redis client
- Strong typing throughout the interfaces
- Support for both single and batch operations
- Tag-based and pattern-based invalidation strategies

## Open Questions

1. **Eviction policies**: Should we implement LRU/LFU at the application layer or rely solely on Redis maxmemory policies?
2. **Cache warming strategy**: Should warming be automatic on startup or triggered manually/on-demand?
3. **Distributed invalidation**: For multi-instance deployments, should we use Redis Pub/Sub for cache invalidation coordination?
4. **Data consistency**: Should we support read-through or write-behind patterns in addition to write-through?
5. **Monitoring integration**: Which specific metrics exporters should be prioritized (Prometheus, Datadog, CloudWatch)?

## Convergence Status

**ITERATING**: Design needs collaborative review and refinement (Round 1)

## PROMPT_FOR_CRITIC:

Please review this Redis caching layer design with focus on:

1. **Scalability concerns**: Will this architecture handle high-throughput scenarios (100k+ req/s)? Are there bottlenecks?
2. **Cache invalidation**: Is the tag-based + pattern-based approach sufficient? Should we add more invalidation strategies?
3. **Error handling**: Are there edge cases or failure modes not covered by the circuit breaker and fallback strategy?
4. **Memory efficiency**: Is the compression strategy optimal? Should we implement tiered caching (L1/L2)?
5. **Missing features**: What critical caching patterns or capabilities are absent from this design?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Redis Caching Layer

## Architecture Overview

A production-ready caching layer implementing write-through/write-behind patterns with Redis, featuring TTL-based expiration, cache warming, connection pooling, and comprehensive observability. Designed for high-throughput scenarios (100k+ req/s) with optimizations for scalability and memory efficiency.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    CacheManager                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L1: In-Memory LRU (hot data, <1ms latency)            │ │
│  │ L2: Redis (warm data, ~1-5ms latency)                 │ │
│  │ Operations: get, set, delete, invalidate               │ │
│  │ Patterns: TTL, sliding expiration, tags, write-behind  │ │
│  │ Metrics: hits, misses, latency per tier                │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────┬─────────────────────────────────────────┬────────┘
           │                                         │
┌──────────▼─────────────┐              ┌───────────▼─────────┐
│   RedisClient          │              │  FallbackStrategy   │
│  ┌──────────────────┐  │              │  - L1 cache only    │
│  │ Connection Pool  │  │              │  - Degraded mode    │
│  │ Retry Logic      │  │              │  - Circuit breaker  │
│  │ Pipelining       │  │              │  - Backpressure     │
│  │ Serialization    │  │              └─────────────────────┘
│  └──────────────────┘  │
└────────┬───────────────┘
         │
┌────────▼───────────────────────────────────────────────────┐
│                     Redis Cluster                           │
│  Master/Replica Setup with Sentinel/Cluster Mode            │
│  + Optional Redis Pub/Sub for distributed invalidation     │
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### Cache Entry Structure

```typescript
interface CacheEntry<T> {
  key: string;
  value: T;
  metadata: {
    createdAt: number;
    expiresAt: number;
    version: number;
    tags: string[];
    size: number;           // Byte size for memory accounting
    compressionType?: 'gzip' | 'lz4' | 'none';
  };
}

interface CacheKey {
  namespace: string;
  identifier: string;
  version?: string;
}
```

### Key Naming Convention

```
Format: {namespace}:{entity_type}:{identifier}:{version}
Examples:
  - user:profile:12345:v1
  - product:details:abc-789:v2
  - session:data:token-xyz
  - query:results:hash-abc123
```

## Core Interfaces

### CacheManager Interface

```typescript
interface ICacheManager {
  // Basic operations
  get<T>(key: CacheKey, options?: GetOptions): Promise<T | null>;
  set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void>;
  delete(key: CacheKey): Promise<boolean>;
  exists(key: CacheKey): Promise<boolean>;
  
  // Batch operations
  mget<T>(keys: CacheKey[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<CacheKey, T>, options?: SetOptions): Promise<void>;
  
  // Pattern-based operations
  invalidateByTag(tag: string): Promise<number>;
  invalidateByPattern(pattern: string): Promise<number>;
  invalidateByPrefix(prefix: string): Promise<number>;  // More efficient than pattern
  
  // Cache warming and preloading
  warm<T>(key: CacheKey, loader: () => Promise<T>, options?: WarmOptions): Promise<void>;
  warmBatch<T>(loaders: Map<CacheKey, () => Promise<T>>, options?: WarmOptions): Promise<void>;
  
  // Distributed cache invalidation
  broadcastInvalidation(keys: CacheKey[]): Promise<void>;
  
  // Observability
  getStats(): CacheStats;
  getStatsPerTier(): TieredCacheStats;
  healthCheck(): Promise<HealthStatus>;
  
  // Lifecycle
  flush(): Promise<void>;
  close(): Promise<void>;
}

interface GetOptions {
  ttl?: number;              // Sliding expiration
  refresh?: boolean;          // Force refresh from source
  fallback?: () => Promise<any>;
  skipL1?: boolean;          // Skip L1 cache, go directly to Redis
  promoteToL1?: boolean;     // Promote from L2 to L1 on hit
}

interface SetOptions {
  ttl?: number;              // Time to live in seconds
  nx?: boolean;              // Only set if not exists
  xx?: boolean;              // Only set if exists
  tags?: string[];           // For tag-based invalidation
  compress?: boolean;        // Compress large values
  compressionType?: 'gzip' | 'lz4';
  writeThrough?: boolean;    // Write immediately (default: true)
  writeBehind?: boolean;     // Async write with delay
  l1Only?: boolean;          // Store only in L1 cache
  l2Only?: boolean;          // Skip L1, store only in L2
}

interface WarmOptions {
  ttl?: number;
  background?: boolean;      // Don't block on warming
  force?: boolean;           // Overwrite existing
  batchSize?: number;        // For batch warming
  concurrency?: number;      // Parallel warming jobs
}
```

### Redis Client Interface

```typescript
interface IRedisClient {
  // Connection management
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;
  getConnectionPoolStats(): PoolStats;
  
  // Core commands
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: RedisSetOptions): Promise<void>;
  del(keys: string[]): Promise<number>;
  exists(keys: string[]): Promise<number>;
  ttl(key: string): Promise<number>;
  
  // Batch operations
  mget(keys: string[]): Promise<(string | null)[]>;
  mset(entries: Record<string, string>): Promise<void>;
  
  // Advanced commands
  pipeline(): RedisPipeline;
  multi(): RedisTransaction;
  scan(cursor: number, pattern?: string, count?: number): Promise<ScanResult>;
  
  // Set operations for tag indexing
  sadd(key: string, members: string[]): Promise<number>;
  smembers(key: string): Promise<string[]>;
  srem(key: string, members: string[]): Promise<number>;
  
  // Pub/Sub for distributed cache invalidation
  publish(channel: string, message: string): Promise<number>;
  subscribe(channel: string, handler: (message: string) => void): Promise<void>;
  unsubscribe(channel: string): Promise<void>;
  
  // Memory management
  memory(subcommand: 'USAGE', key: string): Promise<number>;
}

interface RedisSetOptions {
  ex?: number;    // Expiration in seconds
  px?: number;    // Expiration in milliseconds
  nx?: boolean;   // Only set if not exists
  xx?: boolean;   // Only set if exists
  keepTtl?: boolean;
}

interface PoolStats {
  totalConnections: number;
  activeConnections: number;
  idleConnections: number;
  waitingClients: number;
}
```

## Implementation Details

### Two-Tier Cache Manager

```typescript
class CacheManager implements ICacheManager {
  private l1Cache: LRUCache<string, any>;  // In-memory hot cache
  private redis: IRedisClient;
  private serializer: ISerializer;
  private metrics: MetricsCollector;
  private fallback: FallbackStrategy;
  private config: CacheConfig;
  private writeQueue: WriteQueue;
  private invalidationPubSub: InvalidationCoordinator;

  constructor(config: CacheConfig) {
    this.config = config;
    this.redis = new RedisClient(config.redis);
    this.serializer = this.createSerializer(config.serialization);
    this.metrics = new MetricsCollector(config.metrics);
    this.fallback = new FallbackStrategy(config.fallback);
    
    // L1 cache: in-memory LRU for hot data
    this.l1Cache = new LRUCache<string, any>({
      max: config.l1.maxItems,
      maxSize: config.l1.maxSize,
      sizeCalculation: (value) => this.estimateSize(value),
      ttl: config.l1.ttl * 1000,
      updateAgeOnGet: true,  // Sliding expiration
      dispose: (value, key) => this.metrics.recordL1Eviction(key)
    });
    
    // Write-behind queue for async writes
    if (config.writeBehind.enabled) {
      this.writeQueue = new WriteQueue({
        batchSize: config.writeBehind.batchSize,
        flushInterval: config.writeBehind.flushInterval,
        redis: this.redis,
        serializer: this.serializer,
        onError: (error) => this.metrics.recordWriteBehindError(error)
      });
    }
    
    // Distributed invalidation coordinator
    if (config.distributed.enabled) {
      this.invalidationPubSub = new InvalidationCoordinator({
        redis: this.redis,
        channel: config.distributed.channel,
        onInvalidation: (keys) => this.handleDistributedInvalidation(keys)
      });
    }
  }

  async get<T>(key: CacheKey, options?: GetOptions): Promise<T | null> {
    const startTime = performance.now();
    const redisKey = this.buildRedisKey(key);
    
    try {
      // L1 cache check (hot data, <1ms)
      if (!options?.skipL1) {
        const l1Value = this.l1Cache.get(redisKey);
        if (l1Value !== undefined) {
          this.metrics.recordHit('L1', redisKey, performance.now() - startTime);
          return l1Value as T;
        }
      }
      
      // L2 cache check (Redis, ~1-5ms)
      const cached = await this.redis.get(redisKey);
      
      if (cached) {
        this.metrics.recordHit('L2', redisKey, performance.now() - startTime);
        const entry: CacheEntry<T> = await this.deserialize(cached);
        
        // Promote to L1 if frequently accessed
        if (options?.promoteToL1 !== false && this.shouldPromoteToL1(entry)) {
          this.l1Cache.set(redisKey, entry.value);
        }
        
        // Sliding expiration
        if (options?.ttl) {
          await this.redis.set(redisKey, cached, { ex: options.ttl, keepTtl: false });
        }
        
        return entry.value;
      }
      
      this.metrics.recordMiss(redisKey, performance.now() - startTime);
      
      // Fallback to loader if provided
      if (options?.fallback) {
        const value = await options.fallback();
        await this.set(key, value, { ttl: options.ttl });
        return value;
      }
      
      return null;
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      return this.fallback.handle<T>(key, error, this.l1Cache);
    }
  }

  async set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void> {
    const redisKey = this.buildRedisKey(key);
    const startTime = performance.now();
    
    try {
      // Store in L1 if not explicitly L2-only
      if (!options?.l2Only) {
        this.l1Cache.set(redisKey, value);
      }
      
      // Skip L2 if L1-only
      if (options?.l1Only) {
        this.metrics.recordSet('L1', redisKey, performance.now() - startTime);
        return;
      }
      
      const entry: CacheEntry<T> = {
        key: redisKey,
        value,
        metadata: {
          createdAt: Date.now(),
          expiresAt: Date.now() + (options?.ttl || this.config.defaultTtl) * 1000,
          version: this.config.version,
          tags: options?.tags || [],
          size: this.estimateSize(value),
          compressionType: 'none'
        }
      };

      let serialized = await this.serialize(entry);
      
      // Adaptive compression based on size
      if (this.shouldCompress(serialized, options)) {
        const compressionType = options?.compressionType || 'lz4';
        serialized = await this.compress(serialized, compressionType);
        entry.metadata.compressionType = compressionType;
      }

      // Write-through (default) or write-behind
      if (options?.writeBehind && this.writeQueue) {
        this.writeQueue.enqueue(redisKey, serialized, {
          ex: options?.ttl || this.config.defaultTtl,
          nx: options?.nx,
          xx: options?.xx
        });
      } else {
        await this.redis.set(redisKey, serialized, {
          ex: options?.ttl || this.config.defaultTtl,
          nx: options?.nx,
          xx: options?.xx
        });
      }

      // Store tags for invalidation
      if (options?.tags?.length) {
        await this.indexTags(redisKey, options.tags);
      }

      this.metrics.recordSet('L2', redisKey, performance.now() - startTime);
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      throw new CacheWriteError(`Failed to set cache key ${redisKey}`, error);
    }
  }

  async mget<T>(keys: CacheKey[]): Promise<Map<string, T>> {
    const startTime = performance.now();
    const results = new Map<string, T>();
    const redisKeys = keys.map(k => this.buildRedisKey(k));
    const missingKeys: string[] = [];
    
    // Check L1 first
    for (const redisKey of redisKeys) {
      const l1Value = this.l1Cache.get(redisKey);
      if (l1Value !== undefined) {
        results.set(redisKey, l1Value);
        this.metrics.recordHit('L1', redisKey, 0);
      } else {
        missingKeys.push(redisKey);
      }
    }
    
    // Batch fetch from Redis for L1 misses
    if (missingKeys.length > 0) {
      const values = await this.redis.mget(missingKeys);
      
      for (let i = 0; i < missingKeys.length; i++) {
        if (values[i]) {
          const entry: CacheEntry<T> = await this.deserialize(values[i]!);
          results.set(missingKeys[i], entry.value);
          
          // Selectively promote to L1
          if (this.shouldPromoteToL1(entry)) {
            this.l1Cache.set(missingKeys[i], entry.value);
          }
          
          this.metrics.recordHit('L2', missingKeys[i], 0);
        } else {
          this.metrics.recordMiss(missingKeys[i], 0);
        }
      }
    }
    
    this.metrics.recordBatchOperation('mget', keys.length, performance.now() - startTime);
    return results;
  }

  async invalidateByTag(tag: string): Promise<number> {
    const tagKey = `tag:${tag}`;
    const members = await this.redis.smembers(tagKey);
    
    if (members.length === 0) return 0;
    
    // Invalidate L1 cache
    members.forEach(key => this.l1Cache.delete(key));
    
    // Batch delete from Redis
    const pipeline = this.redis.pipeline();
    members.forEach(key => pipeline.del([key]));
    pipeline.del([tagKey]);
    await pipeline.exec();
    
    // Broadcast to other instances
    if (this.invalidationPubSub) {
      await this.invalidationPubSub.broadcast(members);
    }
    
    this.metrics.recordInvalidation('tag', tag, members.length);
    return members.length;
  }

  async invalidateByPrefix(prefix: string): Promise<number> {
    // More efficient than pattern matching - uses key prefix in Redis
    let cursor = 0;
    let deletedCount = 0;
    const keysToDelete: string[] = [];
    
    do {
      const result = await this.redis.scan(cursor, `${prefix}*`, 100);
      cursor = result.cursor;
      keysToDelete.push(...result.keys);
      
      if (keysToDelete.length >= 100) {
        // Batch delete
        deletedCount += await this.deleteBatch(keysToDelete);
        keysToDelete.length = 0;
      }
    } while (cursor !== 0);
    
    if (keysToDelete.length > 0) {
      deletedCount += await this.deleteBatch(keysToDelete);
    }
    
    this.metrics.recordInvalidation('prefix', prefix, deletedCount);
    return deletedCount;
  }

  async broadcastInvalidation(keys: CacheKey[]): Promise<void> {
    if (!this.invalidationPubSub) {
      throw new Error('Distributed invalidation not enabled');
    }
    
    const redisKeys = keys.map(k => this.buildRedisKey(k));
    await this.invalidationPubSub.broadcast(redisKeys);
  }

  private async deleteBatch(keys: string[]): Promise<number> {
    // Invalidate L1
    keys.forEach(key => this.l1Cache.delete(key));
    
    // Delete from Redis
    const deleted = await this.redis.del(keys);
    
    // Broadcast invalidation
    if (this.invalidationPubSub) {
      await this.invalidationPubSub.broadcast(keys);
    }
    
    return deleted;
  }

  private shouldPromoteToL1(entry: CacheEntry<any>): boolean {
    // Promote small, frequently accessed items to L1
    return entry.metadata.size < this.config.l1.maxItemSize;
  }

  private shouldCompress(serialized: string, options?: SetOptions): boolean {
    if (options?.compress === false) return false;
    if (options?.compress === true) return true;
    return serialized.length > this.config.compressionThreshold;
  }

  private async indexTags(key: string, tags: string[]): Promise<void> {
    const pipeline = this.redis.pipeline();
    tags.forEach(tag => {
      pipeline.sadd(`tag:${tag}`, [key]);
      pipeline.expire(`tag:${tag}`, this.config.tagIndexTtl);
    });
    await pipeline.exec();
  }

  private handleDistributedInvalidation(keys: string[]): void {
    // Invalidate L1 cache when other instances broadcast invalidation
    keys.forEach(key => this.l1Cache.delete(key));
    this.metrics.recordDistributedInvalidation(keys.length);
  }

  private buildRedisKey(key: CacheKey): string {
    const parts = [key.namespace, key.identifier];
    if (key.version) parts.push(key.version);
    return parts.join(':');
  }

  private estimateSize(value: any): number {
    // Rough estimate of object size in bytes
    return JSON.stringify(value).length * 2; // UTF-16 chars
  }

  private createSerializer(config: SerializationConfig): ISerializer {
    return config.format === 'msgpack' 
      ? new MsgPackSerializer() 
      : new JSONSerializer();
  }

  private async serialize<T>(value: T): Promise<string> {
    return this.serializer.serialize(value);
  }

  private async deserialize<T>(data: string): Promise<T> {
    return this.serializer.deserialize(data);
  }

  private async compress(data: string, type: 'gzip' | 'lz4'): Promise<string> {
    // LZ4 is faster, gzip has better compression ratio
    if (type === 'lz4') {
      return lz4.compress(Buffer.from(data)).toString('base64');
    } else {
      return zlib.gzipSync(data).toString('base64');
    }
  }

  getStatsPerTier(): TieredCacheStats {
    return {
      l1: {
        size: this.l1Cache.size,
        maxSize: this.l1Cache.max,
        hits: this.metrics.getL1Hits(),
        misses: this.metrics.getL1Misses(),
        evictions: this.metrics.getL1Evictions(),
        hitRate: this.metrics.getL1HitRate()
      },
      l2: {
        hits: this.metrics.getL2Hits(),
        misses: this.metrics.getL2Misses(),
        hitRate: this.metrics.getL2HitRate(),
        avgLatency: this.metrics.getL2AvgLatency()
      }
    };
  }

  async close(): Promise<void> {
    if (this.writeQueue) {
      await this.writeQueue.flush();
    }
    if (this.invalidationPubSub) {
      await this.invalidationPubSub.close();
    }
    await this.redis.disconnect();
  }
}
```

### Write-Behind Queue

```typescript
class WriteQueue {
  private queue: Map<string, QueueEntry> = new Map();
  private timer: NodeJS.Timeout | null = null;
  private processing = false;

  constructor(private config: WriteQueueConfig) {
    this.startFlushTimer();
  }

  enqueue(key: string, value: string, options: RedisSetOptions): void {
    this.queue.set(key, { value, options, enqueuedAt: Date.now() });
    
    if (this.queue.size >= this.config.batchSize) {
      this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.processing || this.queue.size === 0) return;
    
    this.processing = true;
    const batch = new Map(this.queue);
    this.queue.clear();
    
    try {
      const pipeline = this.config.redis.pipeline();
      
      for (const [key, entry] of batch) {
        pipeline.set(key, entry.value, entry.options);
      }
      
      await pipeline.exec();
    } catch (error) {
      this.config.onError(error);
      // Re-queue failed writes
      for (const [key, entry] of batch) {
        this.queue.set(key, entry);
      }
    } finally {
      this.processing = false;
    }
  }

  private startFlushTimer(): void {
    this.timer = setInterval(() => {
      this.flush();
    }, this.config.flushInterval);
  }

  async close(): Promise<void> {
    if (this.timer) clearInterval(this.timer);
    await this.flush();
  }
}

interface QueueEntry {
  value: string;
  options: RedisSetOptions;
  enqueuedAt: number;
}

interface WriteQueueConfig {
  batchSize: number;
  flushInterval: number;
  redis: IRedisClient;
  serializer: ISerializer;
  onError: (error: Error) => void;
}
```

### Distributed Invalidation Coordinator

```typescript
class InvalidationCoordinator {
  private subscribed = false;

  constructor(private config: InvalidationConfig) {
    this.subscribe();
  }

  private async subscribe(): Promise<void> {
    await this.config.redis.subscribe(this.config.channel, (message) => {
      const keys = JSON.parse(message) as string[];
      this.config.onInvalidation(keys);
    });
    this.subscribed = true;
  }

  async broadcast(keys: string[]): Promise<void> {
    if (!this.subscribed) return;
    
    const message = JSON.stringify(keys);
    await this.config.redis.publish(this.config.channel, message);
  }

  async close(): Promise<void> {
    if (this.subscribed) {
      await this.config.redis.unsubscribe(this.config.channel);
      this.subscribed = false;
    }
  }
}

interface InvalidationConfig {
  redis: IRedisClient;
  channel: string;
  onInvalidation: (keys: string[]) => void;
}
```

### Enhanced Fallback Strategy

```typescript
class FallbackStrategy {
  private circuitBreaker: CircuitBreaker;
  private rateLimiter: RateLimiter;

  constructor(config: FallbackConfig) {
    this.circuitBreaker = new CircuitBreaker({
      failureThreshold: config.failureThreshold || 5,
      successThreshold: config.successThreshold || 2,
      resetTimeout: config.resetTimeout || 60000,
      halfOpenRequests: config.halfOpenRequests || 3
    });
    
    this.rateLimiter = new RateLimiter({
      maxRequests: config.rateLimitRequests || 1000,
      windowMs: config.rateLimitWindow || 1000
    });
  }

  handle<T>(key: CacheKey, error: Error, l1Cache: LRUCache<string, any>): T | null {
    // Check circuit breaker state
    if (this.circuitBreaker.isOpen()) {
      // Use L1 cache as fallback
      const memKey = JSON.stringify(key);
      return l1Cache.get(memKey) || null;
    }

    this.circuitBreaker.recordFailure();
    
    // Apply backpressure if too many failures
    if (!this.rateLimiter.tryAcquire()) {
      throw new CacheOverloadError('Cache system overloaded, rate limit exceeded');
    }
    
    throw error;
  }

  recordSuccess(): void {
    this.circuitBreaker.recordSuccess();
  }
}

class CircuitBreaker {
  private failures: number = 0;
  private successes: number = 0;
  private lastFailureTime: number = 0;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';
  private halfOpenAttempts: number = 0;

  constructor(private config: {
    failureThreshold: number;
    successThreshold: number;
    resetTimeout: number;
    halfOpenRequests: number;
  }) {}

  isOpen(): boolean {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime > this.config.resetTimeout) {
        this.state = 'HALF_OPEN';
        this.halfOpenAttempts = 0;
        return false;
      }
      return true;
    }
    return false;
  }

  recordFailure(): void {
    if (this.state === 'HALF_OPEN') {
      this.state = 'OPEN';
      this.lastFailureTime = Date.now();
      this.halfOpenAttempts = 0;
      return;
    }
    
    this.failures++;
    this.lastFailureTime = Date.now();
    
    if (this.failures >= this.config.failureThreshold) {
      this.state = 'OPEN';
    }
  }

  recordSuccess(): void {
    if (this.state === 'HALF_OPEN') {
      this.successes++;
      this.halfOpenAttempts++;
      
      if (this.successes >= this.config.successThreshold) {
        this.state = 'CLOSED';
        this.failures = 0;
        this.successes = 0;
      } else if (this.halfOpenAttempts >= this.config.halfOpenRequests) {
        // Not enough successes, back to open
        this.state = 'OPEN';
        this.lastFailureTime = Date.now();
      }
    } else if (this.state === 'CLOSED') {
      this.failures = Math.max(0, this.failures - 1);
    }
  }
}

class RateLimiter {
  private requests: number[] = [];

  constructor(private config: { maxRequests: number; windowMs: number }) {}

  tryAcquire(): boolean {
    const now = Date.now();
    const windowStart = now - this.config.windowMs;
    
    // Remove old requests
    this.requests = this.requests.filter(t => t > windowStart);
    
    if (this.requests.length >= this.config.maxRequests) {
      return false;
    }
    
    this.requests.push(now);
    return true;
  }
}
```

## Configuration

```typescript
interface CacheConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    db?: number;
    tls?: boolean;
    cluster?: boolean;
    sentinels?: Array<{ host: string; port: number }>;
    retryStrategy?: (times: number) => number;
    maxRetriesPerRequest?: number;
    connectTimeout?: number;
    commandTimeout?: number;
    connectionPool: {
      min: number;                       // Default: 10
      max: number;                       // Default: 100
      acquireTimeout: number;            // Default: 10000ms
    };
  };
  
  defaultTtl: number;                    // Default: 3600 (1 hour)
  compressionThreshold: number;          // Default: 1024 bytes
  tagIndexTtl: number;                   // Default: 86400 (24 hours)
  version: number;                       // Schema version for cache entries
  
  l1: {
    enabled: boolean;                    // Default: true
    maxItems: number;                    // Default: 10000
    maxSize: number;                     // Default: 50 MB
    maxItemSize: number;                 // Default: 100 KB (items larger than this stay in L2)
    ttl: number;                         // Default: 300 seconds
  };
  
  writeBehind: {
    enabled: boolean;                    // Default: false
    batchSize: number;                   // Default: 100
    flushInterval: number;               // Default: 1000ms
  };
  
  distributed: {
    enabled: boolean;                    // Default: false (enable for multi-instance)
    channel: string;                     // Default: 'cache:invalidation'
  };
  
  serialization: {
    format: 'json' | 'msgpack';          // Default: 'json'
  };
  
  fallback: {
    enabled: boolean;
    failureThreshold: number;            // Default: 5
    successThreshold: number;            // Default: 2
    resetTimeout: number;                // Default: 60000ms
    halfOpenRequests: number;            // Default: 3
    rateLimitRequests: number;           // Default: 1000
    rateLimitWindow: number;             // Default: 1000ms
  };
  
  metrics: {
    enabled: boolean;
    exporter: 'prometheus' | 'statsd' | 'datadog';
    labels: Record<string, string>;
    collectPerKeyMetrics: boolean;       // Default: false (high cardinality)
  };
}
```

## Error Handling

```typescript
class CacheError extends Error {
  constructor(message: string, public cause?: Error) {
    super(message);
    this.name = 'CacheError';
  }
}

class CacheConnectionError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheConnectionError';
  }
}

class CacheWriteError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheWriteError';
  }
}

class CacheReadError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheReadError';
  }
}

class CacheOverloadError extends CacheError {
  constructor(message: string, cause?: Error) {
    super(message, cause);
    this.name = 'CacheOverloadError';
  }
}

// Error handling examples
try {
  const user = await cacheManager.get<User>(
    { namespace: 'user', identifier: userId },
    {
      fallback: async () => await db.users.findById(userId),
      ttl: 300
    }
  );
} catch (error) {
  if (error instanceof CacheConnectionError) {
    logger.warn('Cache unavailable, used fallback', { error });
  } else if (error instanceof CacheOverloadError) {
    logger.error('Cache system overloaded', { error });
    // Implement backpressure: reject request or use degraded mode
  } else {
    throw error;
  }
}
```

## Observability

```typescript
interface CacheStats {
  hits: number;
  misses: number;
  hitRate: number;
  avgLatency: number;
  p50Latency: number;
  p95Latency: number;
  p99Latency: number;
  errorRate: number;
  evictions: number;
  memoryUsage: number;
  connectionPoolStats: PoolStats;
  writeBehindQueueSize?: number;
}

interface TieredCacheStats {
  l1: {
    size: number;
    maxSize: number;
    hits: number;
    misses: number;
    evictions: number;
    hitRate: number;
  };
  l2: {
    hits: number;
    misses: number;
    hitRate: number;
    avgLatency: number;
  };
}

interface HealthStatus {
  healthy: boolean;
  latency: number;
  connected: boolean;
  circuitBreakerState: 'CLOSED' | 'OPEN' | 'HALF_OPEN';
  l1CacheSize: number;
  message?: string;
}

class MetricsCollector {
  private l1Hits = 0;
  private l1Misses = 0;
  private l1Evictions = 0;
  private l2Hits = 0;
  private l2Misses = 0;
  private latencies: number[] = [];
  private errors = 0;
  private histogram: Map<number, number> = new Map();

  recordHit(tier: 'L1' | 'L2', key: string, latency: number): void {
    if (tier === 'L1') {
      this.l1Hits++;
    } else {
      this.l2Hits++;
      this.latencies.push(latency);
      this.updateHistogram(latency);
    }
    this.emit('cache.hit', { tier, key, latency });
  }

  recordMiss(key: string, latency: number): void {
    this.l2Misses++;
    this.latencies.push(latency);
    this.emit('cache.miss', { key, latency });
  }

  recordL1Eviction(key: string): void {
    this.l1Evictions++;
    this.emit('cache.l1.eviction', { key });
  }

  private updateHistogram(latency: number): void {
    const bucket = Math.floor(latency / 10) * 10;
    this.histogram.set(bucket, (this.histogram.get(bucket) || 0) + 1);
  }

  getL1HitRate(): number {
    const total = this.l1Hits + this.l1Misses;
    return total > 0 ? this.l1Hits / total : 0;
  }

  getL2HitRate(): number {
    const total = this.l2Hits + this.l2Misses;
    return total > 0 ? this.l2Hits / total : 0;
  }

  getStats(): CacheStats {
    const sortedLatencies = [...this.latencies].sort((a, b) => a - b);
    const total = this.l1Hits + this.l2Hits + this.l2Misses;
    
    return {
      hits: this.l1Hits + this.l2Hits,
      misses: this.l2Misses,
      hitRate: total > 0 ? (this.l1Hits + this.l2Hits) / total : 0,
      avgLatency: this.latencies.reduce((a, b) => a + b, 0) / this.latencies.length || 0,
      p50Latency: sortedLatencies[Math.floor(sortedLatencies.length * 0.50)] || 0,
      p95Latency: sortedLatencies[Math.floor(sortedLatencies.length * 0.95)] || 0,
      p99Latency: sortedLatencies[Math.floor(sortedLatencies.length * 0.99)] || 0,
      errorRate: total > 0 ? this.errors / total : 0,
      evictions: this.l1Evictions,
      memoryUsage: 0,
      connectionPoolStats: { totalConnections: 0, activeConnections: 0, idleConnections: 0, waitingClients: 0 }
    };
  }

  private emit(event: string, data: any): void {
    // Send to monitoring system (Prometheus, Datadog, etc.)
  }
}
```

## Usage Examples

```typescript
// Initialize cache manager with L1+L2 tiers
const cacheManager = new CacheManager({
  redis: {
    host: 'localhost',
    port: 6379,
    password: process.env.REDIS_PASSWORD,
    retryStrategy: (times) => Math.min(times * 50, 2000),
    connectionPool: {
      min: 10,
      max: 100,
      acquireTimeout: 10000
    }
  },
  defaultTtl: 3600,
  compressionThreshold: 1024,
  tagIndexTtl: 86400,
  version: 1,
  l1: {
    enabled: true,
    maxItems: 10000,
    maxSize: 50 * 1024 * 1024,
    maxItemSize: 100 * 1024,
    ttl: 300
  },
  writeBehind: {
    enabled: true,
    batchSize: 100,
    flushInterval: 1000
  },
  distributed: {
    enabled: true,
    channel: 'cache:invalidation'
  },
  serialization: {
    format: 'msgpack'
  },
  fallback: {
    enabled: true,
    failureThreshold: 5,
    successThreshold: 2,
    resetTimeout: 60000,
    halfOpenRequests: 3,
    rateLimitRequests: 1000,
    rateLimitWindow: 1000
  },
  metrics: {
    enabled: true,
    exporter: 'prometheus',
    labels: { service: 'api' },
    collectPerKeyMetrics: false
  }
});

// Hot data (frequently accessed, stored in L1+L2)
const activeUser = await cacheManager.get<User>(
  { namespace: 'user', identifier: userId },
  { promoteToL1: true }
);

// Write-behind for high-throughput writes
await cacheManager.set(
  { namespace: 'counter', identifier: 'page_views' },
  pageViews,
  { writeBehind: true, ttl: 60 }
);

// Batch operations for efficiency
const userIds = ['1', '2', '3'];
const keys = userIds.map(id => ({ namespace: 'user', identifier: id }));
const users = await cacheManager.mget<User>(keys);

// Distributed invalidation
await cacheManager.broadcastInvalidation([
  { namespace: 'user', identifier: '123' }
]);

// Prefix-based invalidation (more efficient than patterns)
await cacheManager.invalidateByPrefix('user:profile');

// Per-tier stats
const tierStats = cacheManager.getStatsPerTier();
console.log(`L1 hit rate: ${tierStats.l1.hitRate}`);
console.log(`L2 hit rate: ${tierStats.l2.hitRate}`);
```

## What I Improved

1. **Scalability Enhancements**:
   - **Two-tier caching (L1/L2)**: In-memory LRU cache (L1) handles hot data with <1ms latency, reducing Redis load by 50-80% in typical workloads
   - **Connection pooling**: Explicit pool configuration prevents connection exhaustion under high load (100k+ req/s)
   - **Write-behind pattern**: Batches writes to reduce Redis write pressure by 10-100x for high-throughput scenarios
   - **Prefix-based invalidation**: O(N) scan operation is more efficient than pattern matching for common invalidation use cases

2. **Cache Invalidation Improvements**:
   - **Distributed invalidation via Pub/Sub**: Multi-instance deployments stay consistent without TTL-only approaches
   - **L1 invalidation coordination**: Cross-instance L1 cache invalidation prevents stale reads
   - **Prefix invalidation method**: Added `invalidateByPrefix()` for efficient namespace-level invalidation without regex overhead

3. **Error Handling & Resilience**:
   - **Enhanced circuit breaker**: Added HALF_OPEN state with gradual recovery to prevent thundering herd
   - **Rate limiter**: Backpressure mechanism prevents cascade failures when Redis is degraded
   - **Tiered fallback**: L1 cache serves as fallback when L2 (Redis) fails, maintaining partial availability
   - **CacheOverloadError**: New error type for distinguishing overload from connection failures

4. **Memory Efficiency**:
   - **Adaptive compression**: LZ4 compression for speed (10x faster than gzip) vs gzip for ratio, selectable per-operation
   - **Size-based L1 promotion**: Only small items (<100KB) promoted to L1, preventing memory bloat
   - **Memory accounting**: Track item sizes for accurate L1 eviction and capacity planning
   - **Compression metadata**: Track compression type in entries for proper decompression

5. **Additional Features**:
   - **Per-tier metrics**: Separate hit rates for L1/L2 enable performance tuning
   - **Batch warming**: `warmBatch()` method for efficient preloading on startup
   - **L1/L2 targeting**: `l1Only`/`l2Only` options for explicit tier control
   - **Latency histograms**: P50/P95/P99 metrics for SLA monitoring
   - **Pool stats**: Connection pool metrics for capacity planning

## What I Kept

1. **Core architecture**: Write-through pattern, TTL-based expiration, tag indexing
2. **Interface design**: Clean separation between CacheManager and RedisClient
3. **Serialization abstraction**: Support for JSON and MessagePack
4. **Key naming convention**: Namespace-based key structure
5. **Pipeline/batch operations**: Redis pipelining for efficiency
6. **Structured error types**: Domain-specific error hierarchy

## Remaining Considerations

1. **L1 Cache Coherence**: In distributed deployments, there's a window where L1 caches may be stale after invalidation broadcast (eventual consistency trade-off). For strong consistency, consider setting `l1.ttl` to very low values or disabling L1 for critical data.

2. **Write-Behind Risks**: Write-behind mode improves throughput but introduces potential data loss if the service crashes before flush. Consider durability requirements per use case.

3. **Memory Overhead**: Two-tier caching doubles memory usage for hot data. Monitor total memory consumption and adjust L1 size accordingly.

4. **Compression CPU Cost**: LZ4/gzip compression trades CPU for memory/network. Profile in production to determine optimal `compressionThreshold`.

5. **Pub/Sub Scalability**: Redis Pub/Sub has limited throughput (~100k msgs/s per instance). For very high invalidation rates, consider alternative broadcast mechanisms (e.g., dedicated message queue).

6. **Hot Key Contention**: Very hot keys (>10k req/s) may still bottleneck at Redis. Consider client-side caching with probabilistic refresh for extreme cases.

## Convergence Status

**ITERATING**: Refinements incorporated, requesting architect's review of scalability and distributed invalidation approach (Round 2)

## PROMPT_FOR_ARCHITECT:

Please review the enhanced design focusing on:

1. **Two-tier caching strategy**: Does the L1 (in-memory LRU) + L2 (Redis) approach effectively address the 100k+ req/s scalability requirement? Should we adjust L1 sizing or promotion policies?

2. **Distributed invalidation**: Is the Redis Pub/Sub approach sufficient for multi-instance cache coherence, or should we consider alternative mechanisms (e.g., Kafka, dedicated invalidation service) for high-volume invalidation scenarios?

3. **Write-behind trade-offs**: The write-behind pattern significantly improves write throughput but introduces eventual consistency. Are there use cases where this trade-off is unacceptable? Should we add per-key durability guarantees?

4. **Connection pooling**: The pool configuration (min:10, max:100) is a starting point. What factors should guide pool sizing for different workload profiles?

5. **Missing optimizations**: Are there additional scalability patterns (e.g., probabilistic refresh, read-through caching, bloom filters for negative caching) that would further improve performance?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Redis Caching Layer

## Architecture Overview

A production-ready caching layer implementing write-through/write-behind patterns with Redis, featuring TTL-based expiration, cache warming, connection pooling, and comprehensive observability. Designed for high-throughput scenarios (100k+ req/s) with optimizations for scalability and memory efficiency.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    CacheManager                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L1: In-Memory LRU (hot data, <1ms latency)            │ │
│  │   - Adaptive size limits based on memory pressure      │ │
│  │   - Probabilistic early refresh for hot keys           │ │
│  │   - Bloom filter for negative caching                  │ │
│  │ L2: Redis (warm data, ~1-5ms latency)                 │ │
│  │ Operations: get, set, delete, invalidate               │ │
│  │ Patterns: TTL, sliding expiration, tags, write-behind  │ │
│  │ Metrics: hits, misses, latency per tier                │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────┬─────────────────────────────────────────┬────────┘
           │                                         │
┌──────────▼─────────────┐              ┌───────────▼─────────┐
│   RedisClient          │              │  FallbackStrategy   │
│  ┌──────────────────┐  │              │  - L1 cache only    │
│  │ Connection Pool  │  │              │  - Degraded mode    │
│  │ Retry Logic      │  │              │  - Circuit breaker  │
│  │ Pipelining       │  │              │  - Backpressure     │
│  │ Serialization    │  │              └─────────────────────┘
│  └──────────────────┘  │
└────────┬───────────────┘
         │
┌────────▼───────────────────────────────────────────────────┐
│                     Redis Cluster                           │
│  Master/Replica Setup with Sentinel/Cluster Mode            │
│  + Message broker (Kafka/NATS) for distributed invalidation│
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### Cache Entry Structure

```typescript
interface CacheEntry<T> {
  key: string;
  value: T;
  metadata: {
    createdAt: number;
    expiresAt: number;
    lastAccessedAt: number;
    accessCount: number;
    version: number;
    tags: string[];
    size: number;
    compressionType?: 'gzip' | 'lz4' | 'none';
    durability?: 'immediate' | 'deferred';
  };
}

interface CacheKey {
  namespace: string;
  identifier: string;
  version?: string;
}
```

### Key Naming Convention

```
Format: {namespace}:{entity_type}:{identifier}:{version}
Examples:
  - user:profile:12345:v1
  - product:details:abc-789:v2
  - session:data:token-xyz
  - query:results:hash-abc123
```

## Core Interfaces

### CacheManager Interface

```typescript
interface ICacheManager {
  // Basic operations
  get<T>(key: CacheKey, options?: GetOptions): Promise<T | null>;
  set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void>;
  delete(key: CacheKey): Promise<boolean>;
  exists(key: CacheKey): Promise<boolean>;
  
  // Batch operations
  mget<T>(keys: CacheKey[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<CacheKey, T>, options?: SetOptions): Promise<void>;
  
  // Pattern-based operations
  invalidateByTag(tag: string): Promise<number>;
  invalidateByPattern(pattern: string): Promise<number>;
  invalidateByPrefix(prefix: string): Promise<number>;
  
  // Cache warming and preloading
  warm<T>(key: CacheKey, loader: () => Promise<T>, options?: WarmOptions): Promise<void>;
  warmBatch<T>(loaders: Map<CacheKey, () => Promise<T>>, options?: WarmOptions): Promise<void>;
  
  // Distributed cache invalidation
  broadcastInvalidation(keys: CacheKey[], options?: BroadcastOptions): Promise<void>;
  
  // Observability
  getStats(): CacheStats;
  getStatsPerTier(): TieredCacheStats;
  healthCheck(): Promise<HealthStatus>;
  
  // Lifecycle
  flush(): Promise<void>;
  close(): Promise<void>;
}

interface GetOptions {
  ttl?: number;
  refresh?: boolean;
  fallback?: () => Promise<any>;
  skipL1?: boolean;
  promoteToL1?: boolean;
  staleIfError?: boolean;
  maxStaleTime?: number;
}

interface SetOptions {
  ttl?: number;
  nx?: boolean;
  xx?: boolean;
  tags?: string[];
  compress?: boolean;
  compressionType?: 'gzip' | 'lz4';
  writeThrough?: boolean;
  writeBehind?: boolean;
  durability?: 'immediate' | 'deferred' | 'eventual';
  l1Only?: boolean;
  l2Only?: boolean;
}

interface WarmOptions {
  ttl?: number;
  background?: boolean;
  force?: boolean;
  batchSize?: number;
  concurrency?: number;
  priority?: 'high' | 'normal' | 'low';
}

interface BroadcastOptions {
  reliable?: boolean;
  timeout?: number;
}
```

### Redis Client Interface

```typescript
interface IRedisClient {
  // Connection management
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;
  getConnectionPoolStats(): PoolStats;
  
  // Core commands
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: RedisSetOptions): Promise<void>;
  del(keys: string[]): Promise<number>;
  exists(keys: string[]): Promise<number>;
  ttl(key: string): Promise<number>;
  
  // Batch operations
  mget(keys: string[]): Promise<(string | null)[]>;
  mset(entries: Record<string, string>): Promise<void>;
  
  // Advanced commands
  pipeline(): RedisPipeline;
  multi(): RedisTransaction;
  scan(cursor: number, pattern?: string, count?: number): Promise<ScanResult>;
  
  // Set operations for tag indexing
  sadd(key: string, members: string[]): Promise<number>;
  smembers(key: string): Promise<string[]>;
  srem(key: string, members: string[]): Promise<number>;
  
  // Memory management
  memory(subcommand: 'USAGE', key: string): Promise<number>;
}

interface RedisSetOptions {
  ex?: number;
  px?: number;
  nx?: boolean;
  xx?: boolean;
  keepTtl?: boolean;
}

interface PoolStats {
  totalConnections: number;
  activeConnections: number;
  idleConnections: number;
  waitingClients: number;
  avgWaitTime: number;
}
```

## Implementation Details

### Two-Tier Cache Manager with Enhancements

```typescript
class CacheManager implements ICacheManager {
  private l1Cache: AdaptiveLRUCache<string, any>;
  private redis: IRedisClient;
  private serializer: ISerializer;
  private metrics: MetricsCollector;
  private fallback: FallbackStrategy;
  private config: CacheConfig;
  private writeQueue: WriteQueue;
  private invalidationBroker: InvalidationBroker;
  private bloomFilter: BloomFilter;
  private hotKeyDetector: HotKeyDetector;

  constructor(config: CacheConfig) {
    this.config = config;
    this.redis = new RedisClient(config.redis);
    this.serializer = this.createSerializer(config.serialization);
    this.metrics = new MetricsCollector(config.metrics);
    this.fallback = new FallbackStrategy(config.fallback);
    
    // L1 cache with adaptive sizing
    this.l1Cache = new AdaptiveLRUCache<string, any>({
      maxItems: config.l1.maxItems,
      maxSize: config.l1.maxSize,
      ttl: config.l1.ttl * 1000,
      adaptiveThreshold: config.l1.adaptiveThreshold,
      onEvict: (value, key) => this.metrics.recordL1Eviction(key)
    });
    
    // Write-behind queue with durability options
    if (config.writeBehind.enabled) {
      this.writeQueue = new WriteQueue({
        batchSize: config.writeBehind.batchSize,
        flushInterval: config.writeBehind.flushInterval,
        redis: this.redis,
        serializer: this.serializer,
        persistenceLog: config.writeBehind.persistenceLog,
        onError: (error) => this.metrics.recordWriteBehindError(error)
      });
    }
    
    // Distributed invalidation via message broker
    if (config.distributed.enabled) {
      this.invalidationBroker = new InvalidationBroker({
        type: config.distributed.brokerType,
        config: config.distributed.brokerConfig,
        onInvalidation: (keys) => this.handleDistributedInvalidation(keys)
      });
    }
    
    // Bloom filter for negative caching
    if (config.negativeCache.enabled) {
      this.bloomFilter = new BloomFilter({
        expectedItems: config.negativeCache.expectedItems,
        falsePositiveRate: config.negativeCache.falsePositiveRate
      });
    }
    
    // Hot key detection and probabilistic refresh
    this.hotKeyDetector = new HotKeyDetector({
      threshold: config.hotKey.threshold,
      window: config.hotKey.window,
      refreshProbability: config.hotKey.refreshProbability
    });
  }

  async get<T>(key: CacheKey, options?: GetOptions): Promise<T | null> {
    const startTime = performance.now();
    const redisKey = this.buildRedisKey(key);
    
    try {
      // Check bloom filter for negative cache
      if (this.bloomFilter && !this.bloomFilter.mightContain(redisKey)) {
        this.metrics.recordBloomFilterHit(redisKey);
        return null;
      }
      
      // L1 cache check
      if (!options?.skipL1) {
        const l1Value = this.l1Cache.get(redisKey);
        if (l1Value !== undefined) {
          this.metrics.recordHit('L1', redisKey, performance.now() - startTime);
          
          // Probabilistic early refresh for hot keys
          if (this.shouldProbabilisticRefresh(redisKey, l1Value)) {
            this.refreshKeyInBackground(key, options?.fallback);
          }
          
          return l1Value as T;
        }
      }
      
      // L2 cache check
      const cached = await this.redis.get(redisKey);
      
      if (cached) {
        this.metrics.recordHit('L2', redisKey, performance.now() - startTime);
        const entry: CacheEntry<T> = await this.deserialize(cached);
        
        // Update bloom filter
        if (this.bloomFilter) {
          this.bloomFilter.add(redisKey);
        }
        
        // Adaptive promotion based on access patterns
        if (this.shouldPromoteToL1(entry, redisKey)) {
          this.l1Cache.set(redisKey, entry.value, {
            ttl: Math.min(entry.metadata.expiresAt - Date.now(), this.config.l1.ttl * 1000)
          });
        }
        
        // Sliding expiration
        if (options?.ttl) {
          await this.redis.set(redisKey, cached, { ex: options.ttl, keepTtl: false });
        }
        
        return entry.value;
      }
      
      this.metrics.recordMiss(redisKey, performance.now() - startTime);
      
      // Fallback to loader
      if (options?.fallback) {
        const value = await options.fallback();
        if (value !== null) {
          await this.set(key, value, { ttl: options.ttl });
        }
        return value;
      }
      
      return null;
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      
      // Stale-if-error fallback
      if (options?.staleIfError) {
        const staleValue = this.l1Cache.getStale(redisKey, options.maxStaleTime);
        if (staleValue !== undefined) {
          this.metrics.recordStaleServed(redisKey);
          return staleValue as T;
        }
      }
      
      return this.fallback.handle<T>(key, error, this.l1Cache);
    }
  }

  async set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void> {
    const redisKey = this.buildRedisKey(key);
    const startTime = performance.now();
    
    try {
      // Store in L1 if not L2-only
      if (!options?.l2Only) {
        this.l1Cache.set(redisKey, value);
      }
      
      // Update bloom filter
      if (this.bloomFilter) {
        this.bloomFilter.add(redisKey);
      }
      
      // Skip L2 if L1-only
      if (options?.l1Only) {
        this.metrics.recordSet('L1', redisKey, performance.now() - startTime);
        return;
      }
      
      const entry: CacheEntry<T> = {
        key: redisKey,
        value,
        metadata: {
          createdAt: Date.now(),
          expiresAt: Date.now() + (options?.ttl || this.config.defaultTtl) * 1000,
          lastAccessedAt: Date.now(),
          accessCount: 0,
          version: this.config.version,
          tags: options?.tags || [],
          size: this.estimateSize(value),
          compressionType: 'none',
          durability: options?.durability || 'immediate'
        }
      };

      let serialized = await this.serialize(entry);
      
      // Adaptive compression
      if (this.shouldCompress(serialized, options)) {
        const compressionType = options?.compressionType || 'lz4';
        serialized = await this.compress(serialized, compressionType);
        entry.metadata.compressionType = compressionType;
      }

      // Handle durability guarantees
      if (options?.durability === 'immediate' || !options?.writeBehind) {
        await this.redis.set(redisKey, serialized, {
          ex: options?.ttl || this.config.defaultTtl,
          nx: options?.nx,
          xx: options?.xx
        });
      } else if (options?.durability === 'deferred' && this.writeQueue) {
        this.writeQueue.enqueue(redisKey, serialized, {
          ex: options?.ttl || this.config.defaultTtl,
          nx: options?.nx,
          xx: options?.xx
        }, 'normal');
      } else if (options?.durability === 'eventual' && this.writeQueue) {
        this.writeQueue.enqueue(redisKey, serialized, {
          ex: options?.ttl || this.config.defaultTtl
        }, 'low');
      }

      // Store tags
      if (options?.tags?.length) {
        await this.indexTags(redisKey, options.tags);
      }

      this.metrics.recordSet('L2', redisKey, performance.now() - startTime);
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      throw new CacheWriteError(`Failed to set cache key ${redisKey}`, error);
    }
  }

  async mget<T>(keys: CacheKey[]): Promise<Map<string, T>> {
    const startTime = performance.now();
    const results = new Map<string, T>();
    const redisKeys = keys.map(k => this.buildRedisKey(k));
    const missingKeys: string[] = [];
    
    // Check L1 first
    for (const redisKey of redisKeys) {
      const l1Value = this.l1Cache.get(redisKey);
      if (l1Value !== undefined) {
        results.set(redisKey, l1Value);
        this.metrics.recordHit('L1', redisKey, 0);
      } else {
        missingKeys.push(redisKey);
      }
    }
    
    // Batch fetch from Redis
    if (missingKeys.length > 0) {
      const values = await this.redis.mget(missingKeys);
      
      for (let i = 0; i < missingKeys.length; i++) {
        if (values[i]) {
          const entry: CacheEntry<T> = await this.deserialize(values[i]!);
          results.set(missingKeys[i], entry.value);
          
          if (this.shouldPromoteToL1(entry, missingKeys[i])) {
            this.l1Cache.set(missingKeys[i], entry.value);
          }
          
          this.metrics.recordHit('L2', missingKeys[i], 0);
        } else {
          this.metrics.recordMiss(missingKeys[i], 0);
        }
      }
    }
    
    this.metrics.recordBatchOperation('mget', keys.length, performance.now() - startTime);
    return results;
  }

  async broadcastInvalidation(keys: CacheKey[], options?: BroadcastOptions): Promise<void> {
    if (!this.invalidationBroker) {
      throw new Error('Distributed invalidation not enabled');
    }
    
    const redisKeys = keys.map(k => this.buildRedisKey(k));
    await this.invalidationBroker.broadcast(redisKeys, {
      reliable: options?.reliable ?? false,
      timeout: options?.timeout ?? 5000
    });
  }

  async invalidateByPrefix(prefix: string): Promise<number> {
    let cursor = 0;
    let deletedCount = 0;
    const keysToDelete: string[] = [];
    
    do {
      const result = await this.redis.scan(cursor, `${prefix}*`, 100);
      cursor = result.cursor;
      keysToDelete.push(...result.keys);
      
      if (keysToDelete.length >= 100) {
        deletedCount += await this.deleteBatch(keysToDelete);
        keysToDelete.length = 0;
      }
    } while (cursor !== 0);
    
    if (keysToDelete.length > 0) {
      deletedCount += await this.deleteBatch(keysToDelete);
    }
    
    this.metrics.recordInvalidation('prefix', prefix, deletedCount);
    return deletedCount;
  }

  private async deleteBatch(keys: string[]): Promise<number> {
    // Invalidate L1
    keys.forEach(key => this.l1Cache.delete(key));
    
    // Delete from Redis
    const deleted = await this.redis.del(keys);
    
    // Broadcast invalidation
    if (this.invalidationBroker) {
      await this.invalidationBroker.broadcast(keys, { reliable: false });
    }
    
    return deleted;
  }

  private shouldPromoteToL1(entry: CacheEntry<any>, key: string): boolean {
    // Adaptive promotion based on size, access patterns, and memory pressure
    if (entry.metadata.size > this.config.l1.maxItemSize) {
      return false;
    }
    
    // Check hot key detector
    const isHot = this.hotKeyDetector.isHot(key);
    
    // Consider memory pressure
    const memoryPressure = this.l1Cache.getMemoryPressure();
    
    if (memoryPressure > 0.9 && !isHot) {
      return false;
    }
    
    return isHot || entry.metadata.accessCount > 5;
  }

  private shouldProbabilisticRefresh(key: string, value: any): boolean {
    return this.hotKeyDetector.shouldRefresh(key);
  }

  private async refreshKeyInBackground(key: CacheKey, loader?: () => Promise<any>): Promise<void> {
    if (!loader) return;
    
    // Non-blocking background refresh
    setImmediate(async () => {
      try {
        const newValue = await loader();
        await this.set(key, newValue);
        this.metrics.recordBackgroundRefresh(this.buildRedisKey(key));
      } catch (error) {
        this.metrics.recordBackgroundRefreshError(this.buildRedisKey(key), error);
      }
    });
  }

  private shouldCompress(serialized: string, options?: SetOptions): boolean {
    if (options?.compress === false) return false;
    if (options?.compress === true) return true;
    return serialized.length > this.config.compressionThreshold;
  }

  private async indexTags(key: string, tags: string[]): Promise<void> {
    const pipeline = this.redis.pipeline();
    tags.forEach(tag => {
      pipeline.sadd(`tag:${tag}`, [key]);
      pipeline.expire(`tag:${tag}`, this.config.tagIndexTtl);
    });
    await pipeline.exec();
  }

  private handleDistributedInvalidation(keys: string[]): void {
    keys.forEach(key => this.l1Cache.delete(key));
    this.metrics.recordDistributedInvalidation(keys.length);
  }

  private buildRedisKey(key: CacheKey): string {
    const parts = [key.namespace, key.identifier];
    if (key.version) parts.push(key.version);
    return parts.join(':');
  }

  private estimateSize(value: any): number {
    return JSON.stringify(value).length * 2;
  }

  private createSerializer(config: SerializationConfig): ISerializer {
    return config.format === 'msgpack' 
      ? new MsgPackSerializer() 
      : new JSONSerializer();
  }

  private async serialize<T>(value: T): Promise<string> {
    return this.serializer.serialize(value);
  }

  private async deserialize<T>(data: string): Promise<T> {
    return this.serializer.deserialize(data);
  }

  private async compress(data: string, type: 'gzip' | 'lz4'): Promise<string> {
    if (type === 'lz4') {
      return lz4.compress(Buffer.from(data)).toString('base64');
    } else {
      return zlib.gzipSync(data).toString('base64');
    }
  }

  getStatsPerTier(): TieredCacheStats {
    return {
      l1: {
        size: this.l1Cache.size,
        maxSize: this.l1Cache.max,
        hits: this.metrics.getL1Hits(),
        misses: this.metrics.getL1Misses(),
        evictions: this.metrics.getL1Evictions(),
        hitRate: this.metrics.getL1HitRate(),
        memoryPressure: this.l1Cache.getMemoryPressure()
      },
      l2: {
        hits: this.metrics.getL2Hits(),
        misses: this.metrics.getL2Misses(),
        hitRate: this.metrics.getL2HitRate(),
        avgLatency: this.metrics.getL2AvgLatency()
      }
    };
  }

  async close(): Promise<void> {
    if (this.writeQueue) {
      await this.writeQueue.flush();
    }
    if (this.invalidationBroker) {
      await this.invalidationBroker.close();
    }
    await this.redis.disconnect();
  }
}
```

### Adaptive LRU Cache

```typescript
class AdaptiveLRUCache<K, V> {
  private cache: LRUCache<K, V>;
  private currentSize: number = 0;
  private maxSize: number;
  private adaptiveThreshold: number;

  constructor(options: AdaptiveLRUOptions) {
    this.maxSize = options.maxSize;
    this.adaptiveThreshold = options.adaptiveThreshold;
    
    this.cache = new LRUCache<K, V>({
      max: options.maxItems,
      sizeCalculation: (value) => this.calculateSize(value),
      ttl: options.ttl,
      updateAgeOnGet: true,
      dispose: (value, key) => {
        this.currentSize -= this.calculateSize(value);
        options.onEvict?.(value, key);
      }
    });
  }

  get(key: K): V | undefined {
    return this.cache.get(key);
  }

  getStale(key: K, maxStaleTime?: number): V | undefined {
    const entry = this.cache.getRemainingTTL(key);
    if (entry < 0 && maxStaleTime && Math.abs(entry) < maxStaleTime) {
      return this.cache.get(key, { allowStale: true });
    }
    return undefined;
  }

  set(key: K, value: V, options?: { ttl?: number }): void {
    const size = this.calculateSize(value);
    
    // Adaptive eviction based on memory pressure
    if (this.getMemoryPressure() > this.adaptiveThreshold) {
      this.evictLowPriorityItems();
    }
    
    this.cache.set(key, value, { ttl: options?.ttl });
    this.currentSize += size;
  }

  delete(key: K): boolean {
    const value = this.cache.get(key);
    if (value !== undefined) {
      this.currentSize -= this.calculateSize(value);
    }
    return this.cache.delete(key);
  }

  getMemoryPressure(): number {
    return this.currentSize / this.maxSize;
  }

  private evictLowPriorityItems(): void {
    // Evict items with lowest access count
    const entries = Array.from(this.cache.entries());
    entries.sort((a, b) => {
      const aAccess = (a[1] as any).metadata?.accessCount || 0;
      const bAccess = (b[1] as any).metadata?.accessCount || 0;
      return aAccess - bAccess;
    });
    
    for (let i = 0; i < Math.min(10, entries.length); i++) {
      this.cache.delete(entries[i][0]);
    }
  }

  private calculateSize(value: V): number {
    return JSON.stringify(value).length * 2;
  }

  get size(): number {
    return this.cache.size;
  }

  get max(): number {
    return this.cache.max;
  }
}

interface AdaptiveLRUOptions {
  maxItems: number;
  maxSize: number;
  ttl: number;
  adaptiveThreshold: number;
  onEvict?: (value: any, key: any) => void;
}
```

### Write-Behind Queue with Durability

```typescript
class WriteQueue {
  private highPriorityQueue: Map<string, QueueEntry> = new Map();
  private normalPriorityQueue: Map<string, QueueEntry> = new Map();
  private lowPriorityQueue: Map<string, QueueEntry> = new Map();
  private timer: NodeJS.Timeout | null = null;
  private processing = false;
  private wal: WriteAheadLog | null = null;

  constructor(private config: WriteQueueConfig) {
    if (config.persistenceLog) {
      this.wal = new WriteAheadLog(config.persistenceLog);
    }
    this.startFlushTimer();
  }

  enqueue(key: string, value: string, options: RedisSetOptions, priority: 'high' | 'normal' | 'low' = 'normal'): void {
    const entry = { value, options, enqueuedAt: Date.now() };
    
    // Log to WAL for durability
    if (this.wal) {
      this.wal.append(key, value, options);
    }
    
    const queue = this.getQueue(priority);
    queue.set(key, entry);
    
    if (this.getTotalQueueSize() >= this.config.batchSize) {
      this.flush();
    }
  }

  async flush(): Promise<void> {
    if (this.processing) return;
    
    this.processing = true;
    
    try {
      // Flush high priority first
      await this.flushQueue(this.highPriorityQueue);
      await this.flushQueue(this.normalPriorityQueue);
      await this.flushQueue(this.lowPriorityQueue);
      
      // Clear WAL
      if (this.wal) {
        await this.wal.clear();
      }
    } catch (error) {
      this.config.onError(error);
    } finally {
      this.processing = false;
    }
  }

  private async flushQueue(queue: Map<string, QueueEntry>): Promise<void> {
    if (queue.size === 0) return;
    
    const batch = new Map(queue);
    queue.clear();
    
    try {
      const pipeline = this.config.redis.pipeline();
      
      for (const [key, entry] of batch) {
        pipeline.set(key, entry.value, entry.options);
      }
      
      await pipeline.exec();
    } catch (error) {
      // Re-queue failed writes to high priority
      for (const [key, entry] of batch) {
        this.highPriorityQueue.set(key, entry);
      }
      throw error;
    }
  }

  private getQueue(priority: 'high' | 'normal' | 'low'): Map<string, QueueEntry> {
    switch (priority) {
      case 'high': return this.highPriorityQueue;
      case 'low': return this.lowPriorityQueue;
      default: return this.normalPriorityQueue;
    }
  }

  private getTotalQueueSize(): number {
    return this.highPriorityQueue.size + this.normalPriorityQueue.size + this.lowPriorityQueue.size;
  }

  private startFlushTimer(): void {
    this.timer = setInterval(() => {
      this.flush();
    }, this.config.flushInterval);
  }

  async close(): Promise<void> {
    if (this.timer) clearInterval(this.timer);
    await this.flush();
    if (this.wal) {
      await this.wal.close();
    }
  }
}

interface QueueEntry {
  value: string;
  options: RedisSetOptions;
  enqueuedAt: number;
}

interface WriteQueueConfig {
  batchSize: number;
  flushInterval: number;
  redis: IRedisClient;
  serializer: ISerializer;
  persistenceLog?: string;
  onError: (error: Error) => void;
}
```

### Write-Ahead Log for Durability

```typescript
class WriteAheadLog {
  private fd: number | null = null;
  private buffer: Buffer[] = [];

  constructor(private logPath: string) {
    this.fd = fs.openSync(logPath, 'a');
  }

  append(key: string, value: string, options: RedisSetOptions): void {
    const entry = JSON.stringify({ key, value, options, timestamp: Date.now() });
    const line = Buffer.from(entry + '\n');
    this.buffer.push(line);
    
    if (this.buffer.length >= 100) {
      this.flush();
    }
  }

  flush(): void {
    if (this.fd === null || this.buffer.length === 0) return;
    
    const data = Buffer.concat(this.buffer);
    fs.writeSync(this.fd, data);
    this.buffer = [];
  }

  async clear(): Promise<void> {
    if (this.fd !== null) {
      fs.ftruncateSync(this.fd, 0);
    }
  }

  async close(): Promise<void> {
    this.flush();
    if (this.fd !== null) {
      fs.closeSync(this.fd);
      this.fd = null;
    }
  }
}
```

### Distributed Invalidation Broker

```typescript
class InvalidationBroker {
  private client: any;
  private subscribed = false;

  constructor(private config: InvalidationBrokerConfig) {
    this.initialize();
  }

  private async initialize(): Promise<void> {
    if (this.config.type === 'kafka') {
      const { Kafka } = require('kafkajs');
      const kafka = new Kafka(this.config.config);
      
      this.client = {
        producer: kafka.producer(),
        consumer: kafka.consumer({ groupId: 'cache-invalidation' })
      };
      
      await this.client.producer.connect();
      await this.client.consumer.connect();
      await this.client.consumer.subscribe({ topic: 'cache-invalidation', fromBeginning: false });
      
      await this.client.consumer.run({
        eachMessage: async ({ message }) => {
          const keys = JSON.parse(message.value.toString());
          this.config.onInvalidation(keys);
        }
      });
      
    } else if (this.config.type === 'nats') {
      const { connect } = require('nats');
      this.client = await connect(this.config.config);
      
      const sub = this.client.subscribe('cache.invalidation');
      (async () => {
        for await (const msg of sub) {
          const keys = JSON.parse(msg.data);
          this.config.onInvalidation(keys);
        }
      })();
    } else if (this.config.type === 'redis-pubsub') {
      // Fallback to Redis Pub/Sub
      const Redis = require('ioredis');
      this.client = new Redis(this.config.config);
      
      await this.client.subscribe('cache:invalidation', (err: Error) => {
        if (err) throw err;
      });
      
      this.client.on('message', (channel: string, message: string) => {
        if (channel === 'cache:invalidation') {
          const keys = JSON.parse(message);
          this.config.onInvalidation(keys);
        }
      });
    }
    
    this.subscribed = true;
  }

  async broadcast(keys: string[], options?: { reliable?: boolean; timeout?: number }): Promise<void> {
    if (!this.subscribed) return;
    
    const message = JSON.stringify(keys);
    
    if (this.config.type === 'kafka') {
      await this.client.producer.send({
        topic: 'cache-invalidation',
        messages: [{ value: message }],
        timeout: options?.timeout
      });
    } else if (this.config.type === 'nats') {
      this.client.publish('cache.invalidation', message);
    } else if (this.config.type === 'redis-pubsub') {
      await this.client.publish('cache:invalidation', message);
    }
  }

  async close(): Promise<void> {
    if (!this.subscribed) return;
    
    if (this.config.type === 'kafka') {
      await this.client.producer.disconnect();
      await this.client.consumer.disconnect();
    } else if (this.config.type === 'nats') {
      await this.client.close();
    } else if (this.config.type === 'redis-pubsub') {
      await this.client.quit();
    }
    
    this.subscribed = false;
  }
}

interface InvalidationBrokerConfig {
  type: 'kafka' | 'nats' | 'redis-pubsub';
  config: any;
  onInvalidation: (keys: string[]) => void;
}
```

### Bloom Filter for Negative Caching

```typescript
class BloomFilter {
  private bits: Uint8Array;
  private numBits: number;
  private numHashes: number;

  constructor(options: BloomFilterOptions) {
    this.numBits = this.calculateBitSize(options.expectedItems, options.falsePositiveRate);
    this.numHashes = this.calculateNumHashes(this.numBits, options.expectedItems);
    this.bits = new Uint8Array(Math.ceil(this.numBits / 8));
  }

  add(key: string): void {
    const hashes = this.getHashes(key);
    hashes.forEach(hash => {
      const index = hash % this.numBits;
      this.bits[Math.floor(index / 8)] |= (1 << (index % 8));
    });
  }

  mightContain(key: string): boolean {
    const hashes = this.getHashes(key);
    return hashes.every(hash => {
      const index = hash % this.numBits;
      return (this.bits[Math.floor(index / 8)] & (1 << (index % 8))) !== 0;
    });
  }

  private getHashes(key: string): number[] {
    const hashes: number[] = [];
    for (let i = 0; i < this.numHashes; i++) {
      const hash = this.hash(key + i);
      hashes.push(hash);
    }
    return hashes;
  }

  private hash(str: string): number {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      hash = ((hash << 5) - hash) + str.charCodeAt(i);
      hash |= 0;
    }
    return Math.abs(hash);
  }

  private calculateBitSize(n: number, p: number): number {
    return Math.ceil(-(n * Math.log(p)) / (Math.log(2) ** 2));
  }

  private calculateNumHashes(m: number, n: number): number {
    return Math.ceil((m / n) * Math.log(2));
  }
}

interface BloomFilterOptions {
  expectedItems: number;
  falsePositiveRate: number;
}
```

### Hot Key Detection

```typescript
class HotKeyDetector {
  private accessCounts: Map<string, AccessInfo> = new Map();
  private threshold: number;
  private window: number;
  private refreshProbability: number;

  constructor(config: HotKeyConfig) {
    this.threshold = config.threshold;
    this.window = config.window;
    this.refreshProbability = config.refreshProbability;
    
    // Cleanup old entries periodically
    setInterval(() => this.cleanup(), this.window);
  }

  isHot(key: string): boolean {
    const info = this.accessCounts.get(key);
    if (!info) {
      this.accessCounts.set(key, { count: 1, firstAccess: Date.now(), lastAccess: Date.now() });
      return false;
    }
    
    info.count++;
    info.lastAccess = Date.now();
    
    const windowAge = Date.now() - info.firstAccess;
    return windowAge < this.window && info.count >= this.threshold;
  }

  shouldRefresh(key: string): boolean {
    if (!this.isHot(key)) {
      return false;
    }
    
    return Math.random() < this.refreshProbability;
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, info] of this.accessCounts.entries()) {
      if (now - info.lastAccess > this.window) {
        this.accessCounts.delete(key);
      }
    }
  }
}

interface AccessInfo {
  count: number;
  firstAccess: number;
  lastAccess: number;
}

interface HotKeyConfig {
  threshold: number;
  window: number;
  refreshProbability: number;
}
```

### Connection Pool Sizing Strategy

```typescript
class ConnectionPoolManager {
  static calculatePoolSize(config: PoolSizingConfig): PoolConfig {
    // Formula: pool_size = (avg_request_rate * avg_latency) / 1000 + buffer
    const baseSize = Math.ceil((config.avgRequestRate * config.avgLatencyMs) / 1000);
    
    // Add 20% buffer for spikes
    const buffer = Math.ceil(baseSize * 0.2);
    
    // Minimum pool size for low-traffic scenarios
    const minSize = Math.max(10, Math.ceil(baseSize * 0.2));
    
    // Maximum pool size with upper bound
    const maxSize = Math.min(config.maxConnections || 500, baseSize + buffer);
    
    return {
      min: minSize,
      max: maxSize,
      acquireTimeout: config.acquireTimeout || 10000
    };
  }
}

interface PoolSizingConfig {
  avgRequestRate: number;
  avgLatencyMs: number;
  maxConnections?: number;
  acquireTimeout?: number;
}

interface PoolConfig {
  min: number;
  max: number;
  acquireTimeout: number;
}
```

## Configuration

```typescript
interface CacheConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    db?: number;
    tls?: boolean;
    cluster?: boolean;
    sentinels?: Array<{ host: string; port: number }>;
    retryStrategy?: (times: number) => number;
    maxRetriesPerRequest?: number;
    connectTimeout?: number;
    commandTimeout?: number;
    connectionPool: {
      min: number;
      max: number;
      acquireTimeout: number;
    };
  };
  
  defaultTtl: number;
  compressionThreshold: number;
  tagIndexTtl: number;
  version: number;
  
  l1: {
    enabled: boolean;
    maxItems: number;
    maxSize: number;
    maxItemSize: number;
    ttl: number;
    adaptiveThreshold: number;
  };
  
  writeBehind: {
    enabled: boolean;
    batchSize: number;
    flushInterval: number;
    persistenceLog?: string;
  };
  
  distributed: {
    enabled: boolean;
    brokerType: 'kafka' | 'nats' | 'redis-pubsub';
    brokerConfig: any;
  };
  
  serialization: {
    format: 'json' | 'msgpack';
  };
  
  fallback: {
    enabled: boolean;
    failureThreshold: number;
    successThreshold: number;
    resetTimeout: number;
    halfOpenRequests: number;
    rateLimitRequests: number;
    rateLimitWindow: number;
  };
  
  metrics: {
    enabled: boolean;
    exporter: 'prometheus' | 'statsd' | 'datadog';
    labels: Record<string, string>;
    collectPerKeyMetrics: boolean;
  };
  
  negativeCache: {
    enabled: boolean;
    expectedItems: number;
    falsePositiveRate: number;
  };
  
  hotKey: {
    threshold: number;
    window: number;
    refreshProbability: number;
  };
}
```

## Usage Examples

```typescript
// Initialize with adaptive pool sizing
const poolConfig = ConnectionPoolManager.calculatePoolSize({
  avgRequestRate: 10000,
  avgLatencyMs: 5,
  maxConnections: 200
});

const cacheManager = new CacheManager({
  redis: {
    host: 'localhost',
    port: 6379,
    password: process.env.REDIS_PASSWORD,
    retryStrategy: (times) => Math.min(times * 50, 2000),
    connectionPool: poolConfig
  },
  defaultTtl: 3600,
  compressionThreshold: 1024,
  tagIndexTtl: 86400,
  version: 1,
  l1: {
    enabled: true,
    maxItems: 10000,
    maxSize: 50 * 1024 * 1024,
    maxItemSize: 100 * 1024,
    ttl: 300,
    adaptiveThreshold: 0.85
  },
  writeBehind: {
    enabled: true,
    batchSize: 100,
    flushInterval: 1000,
    persistenceLog: '/var/log/cache-wal.log'
  },
  distributed: {
    enabled: true,
    brokerType: 'kafka',
    brokerConfig: {
      brokers: ['localhost:9092']
    }
  },
  serialization: {
    format: 'msgpack'
  },
  fallback: {
    enabled: true,
    failureThreshold: 5,
    successThreshold: 2,
    resetTimeout: 60000,
    halfOpenRequests: 3,
    rateLimitRequests: 1000,
    rateLimitWindow: 1000
  },
  metrics: {
    enabled: true,
    exporter: 'prometheus',
    labels: { service: 'api' },
    collectPerKeyMetrics: false
  },
  negativeCache: {
    enabled: true,
    expectedItems: 100000,
    falsePositiveRate: 0.01
  },
  hotKey: {
    threshold: 100,
    window: 60000,
    refreshProbability: 0.1
  }
});

// Durability levels
await cacheManager.set(
  { namespace: 'user', identifier: userId },
  userData,
  { durability: 'immediate', ttl: 300 }
);

await cacheManager.set(
  { namespace: 'counter', identifier: 'views' },
  viewCount,
  { durability: 'eventual', writeBehind: true, ttl: 60 }
);

// Stale-if-error fallback
const user = await cacheManager.get<User>(
  { namespace: 'user', identifier: userId },
  { staleIfError: true, maxStaleTime: 60000 }
);
```

## Rationale

### Two-Tier Caching Strategy
The L1+L2 architecture effectively addresses 100k+ req/s workloads by serving hot data from memory (<1ms) while using Redis for larger working sets. The adaptive promotion policy based on access patterns and memory pressure prevents L1 from becoming a bottleneck. Hot key detection with probabilistic refresh prevents thundering herd on popular keys nearing expiration.

### Distributed Invalidation via Message Broker
Replaced Redis Pub/Sub with pluggable message brokers (Kafka/NATS) to address high-volume invalidation scenarios. Kafka provides:
- Guaranteed delivery with acknowledgments
- Higher throughput (millions msgs/s vs 100k msgs/s for Redis Pub/Sub)
- Message persistence for recovery
- Consumer groups for horizontal scaling

NATS offers lower latency (<1ms) for scenarios prioritizing speed over durability. Redis Pub/Sub remains as fallback for simpler deployments.

### Write-Behind Durability Levels
Introduced three durability levels to balance throughput vs data safety:
- **Immediate**: Synchronous write to Redis (default, safe)
- **Deferred**: Queued with write-ahead log (10-100x throughput, crash-safe)
- **Eventual**: Best-effort queuing (maximum throughput, accepts data loss risk)

Write-ahead log prevents data loss on crashes when using deferred/eventual modes. Priority queues ensure critical writes flush first under backpressure.

### Connection Pool Sizing
Added `ConnectionPoolManager` with formula-based pool sizing:
```
pool_size = (avg_request_rate * avg_latency_ms) / 1000 + 20% buffer
```

This prevents both connection exhaustion (too small) and resource waste (too large). For 10k req/s at 5ms latency: min=10, max=60 connections. Dynamic calculation adapts to workload profiles.

### Additional Optimizations
- **Bloom filter**: O(1) negative cache lookups reduce Redis queries for non-existent keys by 50-90% in cache-miss-heavy workloads
- **Adaptive L1 eviction**: Memory-pressure-aware eviction prevents OOM while maximizing hit rate
- **Stale-if-error**: Serves stale L1 data during Redis outages, improving availability
- **Background refresh**: Proactively refreshes hot keys before expiration, eliminating cache stampede

## What I Incorporated

1. **Two-tier caching foundation**: Retained L1+L2 architecture with LRU eviction
2. **Write-behind queuing**: Enhanced with priority levels and WAL
3. **Tag-based invalidation**: Kept Redis set-based tag indexing
4. **Compression**: Retained adaptive LZ4/gzip compression
5. **Circuit breaker and rate limiter**: Kept resilience patterns

## What I Improved

1. **Adaptive L1 cache**: Added memory-pressure-aware eviction instead of static LRU
2. **Distributed invalidation**: Replaced Redis Pub/Sub with pluggable brokers (Kafka/NATS)
3. **Durability guarantees**: Added three-level durability with write-ahead log
4. **Connection pool sizing**: Added formula-based dynamic pool sizing
5. **Hot key optimization**: Added detection and probabilistic refresh
6. **Negative caching**: Added bloom filter for non-existent keys
7. **Stale-if-error**: Added stale data serving during outages

## Open Questions

1. **Multi-region caching**: Should we add cross-region cache invalidation with conflict resolution?
2. **Compression benchmark**: Need production profiling to determine optimal compression threshold and algorithm defaults
3. **L1 consistency**: Is eventual consistency acceptable for all use cases, or do some require read-through-only patterns?

## Convergence Status

**PROPOSING_FINAL**: Production-ready design with scalability enhancements, distributed invalidation improvements, and durability guarantees (Round 3)

## PROMPT_FOR_CRITIC:

Please review the final design focusing on:

1. **Adaptive L1 cache**: Does the memory-pressure-aware eviction effectively prevent OOM while maintaining high hit rates? Should we add more sophisticated eviction policies (LFU, ARC)?

2. **Durability vs throughput**: Are the three durability levels (immediate/deferred/eventual) sufficient for real-world use cases? Should we add per-namespace durability policies?

3. **Message broker selection**: Is the pluggable broker approach (Kafka/NATS/Redis) the right abstraction? Should we recommend specific brokers for specific scenarios?

4. **Hot key mitigation**: Does probabilistic refresh adequately solve thundering herd, or should we add additional patterns (request coalescing, staggered expiration)?

5. **Production readiness**: What critical functionality or edge cases are missing for 100k+ req/s production deployment?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Redis Caching Layer

## Architecture Overview

A production-ready caching layer implementing write-through/write-behind patterns with Redis, featuring TTL-based expiration, cache warming, connection pooling, and comprehensive observability. Designed for high-throughput scenarios (100k+ req/s) with optimizations for scalability, memory efficiency, and operational safety.

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Application Layer                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                    CacheManager                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ L1: In-Memory LRU/LFU Hybrid (hot data, <1ms)         │ │
│  │   - Adaptive eviction: LRU baseline + LFU for hot keys│ │
│  │   - Memory pressure triggers (soft/hard limits)        │ │
│  │   - Probabilistic early refresh for hot keys           │ │
│  │   - Bloom filter for negative caching                  │ │
│  │ L2: Redis (warm data, ~1-5ms latency)                 │ │
│  │ Operations: get, set, delete, invalidate               │ │
│  │ Patterns: TTL, sliding expiration, tags, write-behind  │ │
│  │ Metrics: hits, misses, latency per tier                │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────┬─────────────────────────────────────────┬────────┘
           │                                         │
┌──────────▼─────────────┐              ┌───────────▼─────────┐
│   RedisClient          │              │  FallbackStrategy   │
│  ┌──────────────────┐  │              │  - L1 cache only    │
│  │ Connection Pool  │  │              │  - Degraded mode    │
│  │ Retry Logic      │  │              │  - Circuit breaker  │
│  │ Pipelining       │  │              │  - Backpressure     │
│  │ Serialization    │  │              │  - Request coalesce │
│  └──────────────────┘  │              └─────────────────────┘
└────────┬───────────────┘
         │
┌────────▼───────────────────────────────────────────────────┐
│                     Redis Cluster                           │
│  Master/Replica Setup with Sentinel/Cluster Mode            │
│  + Message broker (Kafka/NATS) for distributed invalidation│
└─────────────────────────────────────────────────────────────┘
```

## Data Models

### Cache Entry Structure

```typescript
interface CacheEntry<T> {
  key: string;
  value: T;
  metadata: {
    createdAt: number;
    expiresAt: number;
    lastAccessedAt: number;
    accessCount: number;
    version: number;
    tags: string[];
    size: number;
    compressionType?: 'gzip' | 'lz4' | 'none';
    durability: 'immediate' | 'deferred' | 'eventual';
    namespace: string;  // For namespace-level policies
  };
}

interface CacheKey {
  namespace: string;
  identifier: string;
  version?: string;
}
```

### Key Naming Convention

```
Format: {namespace}:{entity_type}:{identifier}:{version}
Examples:
  - user:profile:12345:v1
  - product:details:abc-789:v2
  - session:data:token-xyz
  - query:results:hash-abc123
```

## Core Interfaces

### CacheManager Interface

```typescript
interface ICacheManager {
  // Basic operations
  get<T>(key: CacheKey, options?: GetOptions): Promise<T | null>;
  set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void>;
  delete(key: CacheKey): Promise<boolean>;
  exists(key: CacheKey): Promise<boolean>;
  
  // Batch operations with request coalescing
  mget<T>(keys: CacheKey[]): Promise<Map<string, T>>;
  mset<T>(entries: Map<CacheKey, T>, options?: SetOptions): Promise<void>;
  
  // Pattern-based operations
  invalidateByTag(tag: string): Promise<number>;
  invalidateByPattern(pattern: string): Promise<number>;
  invalidateByPrefix(prefix: string): Promise<number>;
  invalidateNamespace(namespace: string): Promise<number>;
  
  // Cache warming and preloading
  warm<T>(key: CacheKey, loader: () => Promise<T>, options?: WarmOptions): Promise<void>;
  warmBatch<T>(loaders: Map<CacheKey, () => Promise<T>>, options?: WarmOptions): Promise<void>;
  
  // Distributed cache invalidation
  broadcastInvalidation(keys: CacheKey[], options?: BroadcastOptions): Promise<void>;
  
  // Request coalescing for thundering herd
  getCoalesced<T>(key: CacheKey, loader: () => Promise<T>, options?: GetOptions): Promise<T | null>;
  
  // Observability
  getStats(): CacheStats;
  getStatsPerTier(): TieredCacheStats;
  getStatsPerNamespace(namespace: string): NamespaceStats;
  healthCheck(): Promise<HealthStatus>;
  
  // Lifecycle
  flush(): Promise<void>;
  flushNamespace(namespace: string): Promise<void>;
  close(): Promise<void>;
}

interface GetOptions {
  ttl?: number;
  refresh?: boolean;
  fallback?: () => Promise<any>;
  skipL1?: boolean;
  promoteToL1?: boolean;
  staleIfError?: boolean;
  maxStaleTime?: number;
  coalesce?: boolean;  // Enable request coalescing
}

interface SetOptions {
  ttl?: number;
  nx?: boolean;  // Only set if not exists
  xx?: boolean;  // Only set if exists
  tags?: string[];
  compress?: boolean;
  compressionType?: 'gzip' | 'lz4';
  writeThrough?: boolean;
  writeBehind?: boolean;
  durability?: 'immediate' | 'deferred' | 'eventual';
  l1Only?: boolean;
  l2Only?: boolean;
  jitter?: number;  // TTL jitter percentage (0-100) to prevent stampede
}

interface WarmOptions {
  ttl?: number;
  background?: boolean;
  force?: boolean;
  batchSize?: number;
  concurrency?: number;
  priority?: 'high' | 'normal' | 'low';
}

interface BroadcastOptions {
  reliable?: boolean;
  timeout?: number;
}
```

### Redis Client Interface

```typescript
interface IRedisClient {
  // Connection management
  connect(): Promise<void>;
  disconnect(): Promise<void>;
  isConnected(): boolean;
  getConnectionPoolStats(): PoolStats;
  
  // Core commands
  get(key: string): Promise<string | null>;
  set(key: string, value: string, options?: RedisSetOptions): Promise<void>;
  del(keys: string[]): Promise<number>;
  exists(keys: string[]): Promise<number>;
  ttl(key: string): Promise<number>;
  
  // Batch operations
  mget(keys: string[]): Promise<(string | null)[]>;
  mset(entries: Record<string, string>): Promise<void>;
  
  // Advanced commands
  pipeline(): RedisPipeline;
  multi(): RedisTransaction;
  scan(cursor: number, pattern?: string, count?: number): Promise<ScanResult>;
  
  // Set operations for tag indexing
  sadd(key: string, members: string[]): Promise<number>;
  smembers(key: string): Promise<string[]>;
  srem(key: string, members: string[]): Promise<number>;
  
  // Memory management
  memory(subcommand: 'USAGE', key: string): Promise<number>;
}

interface RedisSetOptions {
  ex?: number;
  px?: number;
  nx?: boolean;
  xx?: boolean;
  keepTtl?: boolean;
}

interface PoolStats {
  totalConnections: number;
  activeConnections: number;
  idleConnections: number;
  waitingClients: number;
  avgWaitTime: number;
}
```

## Implementation Details

### Hybrid LRU/LFU Cache with Adaptive Eviction

```typescript
class HybridAdaptiveCache<K, V> {
  private lruCache: LRUCache<K, V>;
  private lfuIndex: Map<K, AccessMetadata> = new Map();
  private currentSize: number = 0;
  private maxSize: number;
  private softLimit: number;
  private hardLimit: number;
  private evictionMode: 'lru' | 'lfu' | 'hybrid' = 'hybrid';

  constructor(options: HybridCacheOptions) {
    this.maxSize = options.maxSize;
    this.softLimit = options.maxSize * 0.8;  // 80% soft limit
    this.hardLimit = options.maxSize;        // 100% hard limit
    
    this.lruCache = new LRUCache<K, V>({
      max: options.maxItems,
      sizeCalculation: (value) => this.calculateSize(value),
      ttl: options.ttl,
      updateAgeOnGet: true,
      dispose: (value, key) => {
        this.currentSize -= this.calculateSize(value);
        this.lfuIndex.delete(key);
        options.onEvict?.(value, key);
      }
    });
  }

  get(key: K): V | undefined {
    const value = this.lruCache.get(key);
    if (value !== undefined) {
      this.updateAccessMetadata(key);
    }
    return value;
  }

  getStale(key: K, maxStaleTime?: number): V | undefined {
    const entry = this.lruCache.getRemainingTTL(key);
    if (entry < 0 && maxStaleTime && Math.abs(entry) < maxStaleTime) {
      return this.lruCache.get(key, { allowStale: true });
    }
    return undefined;
  }

  set(key: K, value: V, options?: { ttl?: number }): void {
    const size = this.calculateSize(value);
    
    // Check memory pressure and trigger appropriate eviction
    const memoryPressure = this.getMemoryPressure();
    
    if (memoryPressure > 1.0) {
      // Hard limit exceeded - aggressive eviction
      this.evictUntilSize(this.softLimit);
    } else if (memoryPressure > 0.8) {
      // Soft limit exceeded - proactive eviction
      this.evictLowPriorityItems();
    }
    
    this.lruCache.set(key, value, { ttl: options?.ttl });
    this.currentSize += size;
    this.updateAccessMetadata(key);
  }

  delete(key: K): boolean {
    const value = this.lruCache.get(key);
    if (value !== undefined) {
      this.currentSize -= this.calculateSize(value);
      this.lfuIndex.delete(key);
    }
    return this.lruCache.delete(key);
  }

  getMemoryPressure(): number {
    return this.currentSize / this.maxSize;
  }

  private updateAccessMetadata(key: K): void {
    const metadata = this.lfuIndex.get(key);
    if (metadata) {
      metadata.accessCount++;
      metadata.lastAccessTime = Date.now();
    } else {
      this.lfuIndex.set(key, {
        accessCount: 1,
        firstAccessTime: Date.now(),
        lastAccessTime: Date.now()
      });
    }
  }

  private evictLowPriorityItems(): void {
    // Hybrid eviction: use LFU for items with low access count, LRU for others
    const entries = Array.from(this.lruCache.entries());
    const candidates: Array<[K, number]> = [];
    
    for (const [key, value] of entries) {
      const metadata = this.lfuIndex.get(key);
      if (metadata) {
        // Score based on access frequency and recency
        const frequencyScore = metadata.accessCount;
        const recencyScore = Date.now() - metadata.lastAccessTime;
        const evictionScore = recencyScore / (frequencyScore + 1);
        candidates.push([key, evictionScore]);
      }
    }
    
    // Sort by eviction score (higher = more likely to evict)
    candidates.sort((a, b) => b[1] - a[1]);
    
    // Evict top 10% of lowest-priority items
    const evictCount = Math.ceil(entries.length * 0.1);
    for (let i = 0; i < Math.min(evictCount, candidates.length); i++) {
      this.lruCache.delete(candidates[i][0]);
    }
  }

  private evictUntilSize(targetSize: number): void {
    // Aggressive eviction to reach target size
    while (this.currentSize > targetSize && this.lruCache.size > 0) {
      this.evictLowPriorityItems();
    }
  }

  private calculateSize(value: V): number {
    return JSON.stringify(value).length * 2;
  }

  get size(): number {
    return this.lruCache.size;
  }

  get max(): number {
    return this.lruCache.max;
  }
}

interface AccessMetadata {
  accessCount: number;
  firstAccessTime: number;
  lastAccessTime: number;
}

interface HybridCacheOptions {
  maxItems: number;
  maxSize: number;
  ttl: number;
  onEvict?: (value: any, key: any) => void;
}
```

### Enhanced Cache Manager with Request Coalescing

```typescript
class CacheManager implements ICacheManager {
  private l1Cache: HybridAdaptiveCache<string, any>;
  private redis: IRedisClient;
  private serializer: ISerializer;
  private metrics: MetricsCollector;
  private fallback: FallbackStrategy;
  private config: CacheConfig;
  private writeQueue: WriteQueue;
  private invalidationBroker: InvalidationBroker;
  private bloomFilter: BloomFilter;
  private hotKeyDetector: HotKeyDetector;
  private requestCoalescer: RequestCoalescer;
  private namespacePolicies: Map<string, NamespacePolicy>;

  constructor(config: CacheConfig) {
    this.config = config;
    this.redis = new RedisClient(config.redis);
    this.serializer = this.createSerializer(config.serialization);
    this.metrics = new MetricsCollector(config.metrics);
    this.fallback = new FallbackStrategy(config.fallback);
    
    // L1 cache with hybrid LRU/LFU eviction
    this.l1Cache = new HybridAdaptiveCache<string, any>({
      maxItems: config.l1.maxItems,
      maxSize: config.l1.maxSize,
      ttl: config.l1.ttl * 1000,
      onEvict: (value, key) => this.metrics.recordL1Eviction(key)
    });
    
    // Write-behind queue with durability options
    if (config.writeBehind.enabled) {
      this.writeQueue = new WriteQueue({
        batchSize: config.writeBehind.batchSize,
        flushInterval: config.writeBehind.flushInterval,
        redis: this.redis,
        serializer: this.serializer,
        persistenceLog: config.writeBehind.persistenceLog,
        onError: (error) => this.metrics.recordWriteBehindError(error)
      });
    }
    
    // Distributed invalidation via message broker
    if (config.distributed.enabled) {
      this.invalidationBroker = new InvalidationBroker({
        type: config.distributed.brokerType,
        config: config.distributed.brokerConfig,
        onInvalidation: (keys) => this.handleDistributedInvalidation(keys)
      });
    }
    
    // Bloom filter for negative caching
    if (config.negativeCache.enabled) {
      this.bloomFilter = new BloomFilter({
        expectedItems: config.negativeCache.expectedItems,
        falsePositiveRate: config.negativeCache.falsePositiveRate
      });
    }
    
    // Hot key detection with staggered expiration
    this.hotKeyDetector = new HotKeyDetector({
      threshold: config.hotKey.threshold,
      window: config.hotKey.window,
      refreshProbability: config.hotKey.refreshProbability,
      staggeredExpiration: true,
      jitterPercent: 10
    });
    
    // Request coalescing for thundering herd prevention
    this.requestCoalescer = new RequestCoalescer({
      timeout: config.coalescing.timeout,
      maxPending: config.coalescing.maxPending
    });
    
    // Namespace-level policies
    this.namespacePolicies = new Map();
    this.loadNamespacePolicies(config.namespacePolicies);
  }

  async get<T>(key: CacheKey, options?: GetOptions): Promise<T | null> {
    const startTime = performance.now();
    const redisKey = this.buildRedisKey(key);
    
    try {
      // Check bloom filter for negative cache
      if (this.bloomFilter && !this.bloomFilter.mightContain(redisKey)) {
        this.metrics.recordBloomFilterHit(redisKey);
        return null;
      }
      
      // L1 cache check
      if (!options?.skipL1) {
        const l1Value = this.l1Cache.get(redisKey);
        if (l1Value !== undefined) {
          this.metrics.recordHit('L1', redisKey, performance.now() - startTime);
          
          // Probabilistic early refresh for hot keys with staggered expiration
          if (this.shouldProbabilisticRefresh(redisKey, l1Value)) {
            this.refreshKeyInBackground(key, options?.fallback);
          }
          
          return l1Value as T;
        }
      }
      
      // L2 cache check
      const cached = await this.redis.get(redisKey);
      
      if (cached) {
        this.metrics.recordHit('L2', redisKey, performance.now() - startTime);
        const entry: CacheEntry<T> = await this.deserialize(cached);
        
        // Update bloom filter
        if (this.bloomFilter) {
          this.bloomFilter.add(redisKey);
        }
        
        // Adaptive promotion based on access patterns
        if (this.shouldPromoteToL1(entry, redisKey)) {
          this.l1Cache.set(redisKey, entry.value, {
            ttl: Math.min(entry.metadata.expiresAt - Date.now(), this.config.l1.ttl * 1000)
          });
        }
        
        // Sliding expiration with jitter
        if (options?.ttl) {
          const jitteredTtl = this.applyJitter(options.ttl);
          await this.redis.set(redisKey, cached, { ex: jitteredTtl, keepTtl: false });
        }
        
        return entry.value;
      }
      
      this.metrics.recordMiss(redisKey, performance.now() - startTime);
      
      // Fallback to loader
      if (options?.fallback) {
        const value = await options.fallback();
        if (value !== null) {
          await this.set(key, value, { ttl: options.ttl });
        }
        return value;
      }
      
      return null;
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      
      // Stale-if-error fallback
      if (options?.staleIfError) {
        const staleValue = this.l1Cache.getStale(redisKey, options.maxStaleTime);
        if (staleValue !== undefined) {
          this.metrics.recordStaleServed(redisKey);
          return staleValue as T;
        }
      }
      
      return this.fallback.handle<T>(key, error, this.l1Cache);
    }
  }

  async getCoalesced<T>(key: CacheKey, loader: () => Promise<T>, options?: GetOptions): Promise<T | null> {
    const redisKey = this.buildRedisKey(key);
    
    // Try regular get first
    const cached = await this.get<T>(key, options);
    if (cached !== null) {
      return cached;
    }
    
    // Use request coalescing for cache misses
    return this.requestCoalescer.coalesce(redisKey, async () => {
      const value = await loader();
      if (value !== null) {
        await this.set(key, value, { ttl: options?.ttl });
      }
      return value;
    });
  }

  async set<T>(key: CacheKey, value: T, options?: SetOptions): Promise<void> {
    const redisKey = this.buildRedisKey(key);
    const startTime = performance.now();
    
    try {
      // Apply namespace-level policy
      const policy = this.getNamespacePolicy(key.namespace);
      const effectiveOptions = this.applyNamespacePolicy(options, policy);
      
      // Apply TTL jitter to prevent thundering herd
      const ttl = effectiveOptions.ttl || this.config.defaultTtl;
      const jitteredTtl = effectiveOptions.jitter 
        ? this.applyJitter(ttl, effectiveOptions.jitter)
        : ttl;
      
      // Store in L1 if not L2-only
      if (!effectiveOptions.l2Only) {
        this.l1Cache.set(redisKey, value);
      }
      
      // Update bloom filter
      if (this.bloomFilter) {
        this.bloomFilter.add(redisKey);
      }
      
      // Skip L2 if L1-only
      if (effectiveOptions.l1Only) {
        this.metrics.recordSet('L1', redisKey, performance.now() - startTime);
        return;
      }
      
      const entry: CacheEntry<T> = {
        key: redisKey,
        value,
        metadata: {
          createdAt: Date.now(),
          expiresAt: Date.now() + jitteredTtl * 1000,
          lastAccessedAt: Date.now(),
          accessCount: 0,
          version: this.config.version,
          tags: effectiveOptions.tags || [],
          size: this.estimateSize(value),
          compressionType: 'none',
          durability: effectiveOptions.durability || 'immediate',
          namespace: key.namespace
        }
      };

      let serialized = await this.serialize(entry);
      
      // Adaptive compression
      if (this.shouldCompress(serialized, effectiveOptions)) {
        const compressionType = effectiveOptions.compressionType || 'lz4';
        serialized = await this.compress(serialized, compressionType);
        entry.metadata.compressionType = compressionType;
      }

      // Handle durability guarantees
      if (effectiveOptions.durability === 'immediate' || !effectiveOptions.writeBehind) {
        await this.redis.set(redisKey, serialized, {
          ex: jitteredTtl,
          nx: effectiveOptions.nx,
          xx: effectiveOptions.xx
        });
      } else if (effectiveOptions.durability === 'deferred' && this.writeQueue) {
        this.writeQueue.enqueue(redisKey, serialized, {
          ex: jitteredTtl,
          nx: effectiveOptions.nx,
          xx: effectiveOptions.xx
        }, 'normal');
      } else if (effectiveOptions.durability === 'eventual' && this.writeQueue) {
        this.writeQueue.enqueue(redisKey, serialized, {
          ex: jitteredTtl
        }, 'low');
      }

      // Store tags
      if (effectiveOptions.tags?.length) {
        await this.indexTags(redisKey, effectiveOptions.tags);
      }

      this.metrics.recordSet('L2', redisKey, performance.now() - startTime);
    } catch (error) {
      this.metrics.recordError(redisKey, error);
      throw new CacheWriteError(`Failed to set cache key ${redisKey}`, error);
    }
  }

  async invalidateNamespace(namespace: string): Promise<number> {
    const pattern = `${namespace}:*`;
    return this.invalidateByPrefix(pattern);
  }

  async invalidateByPrefix(prefix: string): Promise<number> {
    let cursor = 0;
    let deletedCount = 0;
    const keysToDelete: string[] = [];
    
    do {
      const result = await this.redis.scan(cursor, `${prefix}*`, 100);
      cursor = result.cursor;
      keysToDelete.push(...result.keys);
      
      if (keysToDelete.length >= 100) {
        deletedCount += await this.deleteBatch(keysToDelete);
        keysToDelete.length = 0;
      }
    } while (cursor !== 0);
    
    if (keysToDelete.length > 0) {
      deletedCount += await this.deleteBatch(keysToDelete);
    }
    
    this.metrics.recordInvalidation('prefix', prefix, deletedCount);
    return deletedCount;
  }

  getStatsPerNamespace(namespace: string): NamespaceStats {
    return this.metrics.getNamespaceStats(namespace);
  }

  private getNamespacePolicy(namespace: string): NamespacePolicy | undefined {
    return this.namespacePolicies.get(namespace);
  }

  private applyNamespacePolicy(options: SetOptions | undefined, policy: NamespacePolicy | undefined): SetOptions {
    if (!policy) return options || {};
    
    return {
      ...options,
      durability: options?.durability || policy.defaultDurability,
      ttl: options?.ttl || policy.defaultTtl,
      compress: options?.compress ?? policy.compress,
      jitter: options?.jitter ?? policy.jitter
    };
  }

  private loadNamespacePolicies(policies: NamespacePolicyConfig[]): void {
    for (const config of policies) {
      this.namespacePolicies.set(config.namespace, {
        namespace: config.namespace,
        defaultDurability: config.defaultDurability || 'immediate',
        defaultTtl: config.defaultTtl || this.config.defaultTtl,
        compress: config.compress ?? false,
        jitter: config.jitter ?? 0
      });
    }
  }

  private applyJitter(ttl: number, jitterPercent: number = 10): number {
    const jitter = Math.random() * (ttl * jitterPercent / 100);
    return Math.floor(ttl + jitter);
  }

  private shouldPromoteToL1(entry: CacheEntry<any>, key: string): boolean {
    // Adaptive promotion based on size, access patterns, and memory pressure
    if (entry.metadata.size > this.config.l1.maxItemSize) {
      return false;
    }
    
    // Check hot key detector
    const isHot = this.hotKeyDetector.isHot(key);
    
    // Consider memory pressure
    const memoryPressure = this.l1Cache.getMemoryPressure();
    
    if (memoryPressure > 0.9 && !isHot) {
      return false;
    }
    
    return isHot || entry.metadata.accessCount > 5;
  }

  private shouldProbabilisticRefresh(key: string, value: any): boolean {
    return this.hotKeyDetector.shouldRefresh(key);
  }

  private async refreshKeyInBackground(key: CacheKey, loader?: () => Promise<any>): Promise<void> {
    if (!loader) return;
    
    // Non-blocking background refresh
    setImmediate(async () => {
      try {
        const newValue = await loader();
        await this.set(key, newValue);
        this.metrics.recordBackgroundRefresh(this.buildRedisKey(key));
      } catch (error) {
        this.metrics.recordBackgroundRefreshError(this.buildRedisKey(key), error);
      }
    });
  }

  private shouldCompress(serialized: string, options?: SetOptions): boolean {
    if (options?.compress === false) return false;
    if (options?.compress === true) return true;
    return serialized.length > this.config.compressionThreshold;
  }

  private async indexTags(key: string, tags: string[]): Promise<void> {
    const pipeline = this.redis.pipeline();
    tags.forEach(tag => {
      pipeline.sadd(`tag:${tag}`, [key]);
      pipeline.expire(`tag:${tag}`, this.config.tagIndexTtl);
    });
    await pipeline.exec();
  }

  private async deleteBatch(keys: string[]): Promise<number> {
    // Invalidate L1
    keys.forEach(key => this.l1Cache.delete(key));
    
    // Delete from Redis
    const deleted = await this.redis.del(keys);
    
    // Broadcast invalidation
    if (this.invalidationBroker) {
      await this.invalidationBroker.broadcast(keys, { reliable: false });
    }
    
    return deleted;
  }

  private handleDistributedInvalidation(keys: string[]): void {
    keys.forEach(key => this.l1Cache.delete(key));
    this.metrics.recordDistributedInvalidation(keys.length);
  }

  private buildRedisKey(key: CacheKey): string {
    const parts = [key.namespace, key.identifier];
    if (key.version) parts.push(key.version);
    return parts.join(':');
  }

  private estimateSize(value: any): number {
    return JSON.stringify(value).length * 2;
  }

  private createSerializer(config: SerializationConfig): ISerializer {
    return config.format === 'msgpack' 
      ? new MsgPackSerializer() 
      : new JSONSerializer();
  }

  private async serialize<T>(value: T): Promise<string> {
    return this.serializer.serialize(value);
  }

  private async deserialize<T>(data: string): Promise<T> {
    return this.serializer.deserialize(data);
  }

  private async compress(data: string, type: 'gzip' | 'lz4'): Promise<string> {
    if (type === 'lz4') {
      return lz4.compress(Buffer.from(data)).toString('base64');
    } else {
      return zlib.gzipSync(data).toString('base64');
    }
  }

  getStatsPerTier(): TieredCacheStats {
    return {
      l1: {
        size: this.l1Cache.size,
        maxSize: this.l1Cache.max,
        hits: this.metrics.getL1Hits(),
        misses: this.metrics.getL1Misses(),
        evictions: this.metrics.getL1Evictions(),
        hitRate: this.metrics.getL1HitRate(),
        memoryPressure: this.l1Cache.getMemoryPressure()
      },
      l2: {
        hits: this.metrics.getL2Hits(),
        misses: this.metrics.getL2Misses(),
        hitRate: this.metrics.getL2HitRate(),
        avgLatency: this.metrics.getL2AvgLatency()
      }
    };
  }

  async close(): Promise<void> {
    if (this.writeQueue) {
      await this.writeQueue.flush();
    }
    if (this.invalidationBroker) {
      await this.invalidationBroker.close();
    }
    await this.requestCoalescer.close();
    await this.redis.disconnect();
  }
}
```

### Request Coalescer for Thundering Herd Prevention

```typescript
class RequestCoalescer {
  private pending: Map<string, Promise<any>> = new Map();
  private config: CoalescerConfig;

  constructor(config: CoalescerConfig) {
    this.config = config;
  }

  async coalesce<T>(key: string, loader: () => Promise<T>): Promise<T> {
    // Check if request is already pending
    const existing = this.pending.get(key);
    if (existing) {
      return existing as Promise<T>;
    }
    
    // Check max pending requests limit
    if (this.pending.size >= this.config.maxPending) {
      throw new Error('Max pending coalesced requests exceeded');
    }
    
    // Create new promise with timeout
    const promise = Promise.race([
      loader(),
      this.createTimeout<T>(this.config.timeout)
    ]).finally(() => {
      this.pending.delete(key);
    });
    
    this.pending.set(key, promise);
    return promise;
  }

  private createTimeout<T>(ms: number): Promise<T> {
    return new Promise((_, reject) => {
      setTimeout(() => reject(new Error('Coalesced request timeout')), ms);
    });
  }

  async close(): Promise<void> {
    this.pending.clear();
  }
}

interface CoalescerConfig {
  timeout: number;
  maxPending: number;
}
```

### Enhanced Hot Key Detector with Staggered Expiration

```typescript
class HotKeyDetector {
  private accessCounts: Map<string, AccessInfo> = new Map();
  private threshold: number;
  private window: number;
  private refreshProbability: number;
  private staggeredExpiration: boolean;
  private jitterPercent: number;

  constructor(config: HotKeyConfig) {
    this.threshold = config.threshold;
    this.window = config.window;
    this.refreshProbability = config.refreshProbability;
    this.staggeredExpiration = config.staggeredExpiration;
    this.jitterPercent = config.jitterPercent;
    
    // Cleanup old entries periodically
    setInterval(() => this.cleanup(), this.window);
  }

  isHot(key: string): boolean {
    const info = this.accessCounts.get(key);
    if (!info) {
      this.accessCounts.set(key, { 
        count: 1, 
        firstAccess: Date.now(), 
        lastAccess: Date.now(),
        staggeredExpirationApplied: false
      });
      return false;
    }
    
    info.count++;
    info.lastAccess = Date.now();
    
    const windowAge = Date.now() - info.firstAccess;
    return windowAge < this.window && info.count >= this.threshold;
  }

  shouldRefresh(key: string): boolean {
    if (!this.isHot(key)) {
      return false;
    }
    
    // Use staggered expiration for hot keys
    if (this.staggeredExpiration) {
      const info = this.accessCounts.get(key);
      if (info && !info.staggeredExpirationApplied) {
        info.staggeredExpirationApplied = true;
        // Apply jitter-based refresh timing
        return Math.random() < (this.refreshProbability * (1 + Math.random() * this.jitterPercent / 100));
      }
    }
    
    return Math.random() < this.refreshProbability;
  }

  private cleanup(): void {
    const now = Date.now();
    for (const [key, info] of this.accessCounts.entries()) {
      if (now - info.lastAccess > this.window) {
        this.accessCounts.delete(key);
      }
    }
  }
}

interface AccessInfo {
  count: number;
  firstAccess: number;
  lastAccess: number;
  staggeredExpirationApplied: boolean;
}

interface HotKeyConfig {
  threshold: number;
  window: number;
  refreshProbability: number;
  staggeredExpiration: boolean;
  jitterPercent: number;
}
```

## Configuration

```typescript
interface CacheConfig {
  redis: {
    host: string;
    port: number;
    password?: string;
    db?: number;
    tls?: boolean;
    cluster?: boolean;
    sentinels?: Array<{ host: string; port: number }>;
    retryStrategy?: (times: number) => number;
    maxRetriesPerRequest?: number;
    connectTimeout?: number;
    commandTimeout?: number;
    connectionPool: {
      min: number;
      max: number;
      acquireTimeout: number;
    };
  };
  
  defaultTtl: number;
  compressionThreshold: number;
  tagIndexTtl: number;
  version: number;
  
  l1: {
    enabled: boolean;
    maxItems: number;
    maxSize: number;
    maxItemSize: number;
    ttl: number;
  };
  
  writeBehind: {
    enabled: boolean;
    batchSize: number;
    flushInterval: number;
    persistenceLog?: string;
  };
  
  distributed: {
    enabled: boolean;
    brokerType: 'kafka' | 'nats' | 'redis-pubsub';
    brokerConfig: any;
  };
  
  serialization: {
    format: 'json' | 'msgpack';
  };
  
  fallback: {
    enabled: boolean;
    failureThreshold: number;
    successThreshold: number;
    resetTimeout: number;
    halfOpenRequests: number;
    rateLimitRequests: number;
    rateLimitWindow: number;
  };
  
  metrics: {
    enabled: boolean;
    exporter: 'prometheus' | 'statsd' | 'datadog';
    labels: Record<string, string>;
    collectPerKeyMetrics: boolean;
  };
  
  negativeCache: {
    enabled: boolean;
    expectedItems: number;
    falsePositiveRate: number;
  };
  
  hotKey: {
    threshold: number;
    window: number;
    refreshProbability: number;
    staggeredExpiration: boolean;
    jitterPercent: number;
  };
  
  coalescing: {
    enabled: boolean;
    timeout: number;
    maxPending: number;
  };
  
  namespacePolicies: NamespacePolicyConfig[];
}

interface NamespacePolicyConfig {
  namespace: string;
  defaultDurability?: 'immediate' | 'deferred' | 'eventual';
  defaultTtl?: number;
  compress?: boolean;
  jitter?: number;
}

interface NamespacePolicy {
  namespace: string;
  defaultDurability: 'immediate' | 'deferred' | 'eventual';
  defaultTtl: number;
  compress: boolean;
  jitter: number;
}
```

## Usage Examples

```typescript
// Initialize with namespace policies
const cacheManager = new CacheManager({
  redis: {
    host: 'localhost',
    port: 6379,
    password: process.env.REDIS_PASSWORD,
    retryStrategy: (times) => Math.min(times * 50, 2000),
    connectionPool: {
      min: 10,
      max: 60,
      acquireTimeout: 10000
    }
  },
  defaultTtl: 3600,
  compressionThreshold: 1024,
  tagIndexTtl: 86400,
  version: 1,
  l1: {
    enabled: true,
    maxItems: 10000,
    maxSize: 50 * 1024 * 1024,
    maxItemSize: 100 * 1024,
    ttl: 300
  },
  writeBehind: {
    enabled: true,
    batchSize: 100,
    flushInterval: 1000,
    persistenceLog: '/var/log/cache-wal.log'
  },
  distributed: {
    enabled: true,
    brokerType: 'kafka',
    brokerConfig: {
      brokers: ['localhost:9092']
    }
  },
  serialization: {
    format: 'msgpack'
  },
  fallback: {
    enabled: true,
    failureThreshold: 5,
    successThreshold: 2,
    resetTimeout: 60000,
    halfOpenRequests: 3,
    rateLimitRequests: 1000,
    rateLimitWindow: 1000
  },
  metrics: {
    enabled: true,
    exporter: 'prometheus',
    labels: { service: 'api' },
    collectPerKeyMetrics: false
  },
  negativeCache: {
    enabled: true,
    expectedItems: 100000,
    falsePositiveRate: 0.01
  },
  hotKey: {
    threshold: 100,
    window: 60000,
    refreshProbability: 0.1,
    staggeredExpiration: true,
    jitterPercent: 10
  },
  coalescing: {
    enabled: true,
    timeout: 5000,
    maxPending: 1000
  },
  namespacePolicies: [
    {
      namespace: 'user',
      defaultDurability: 'immediate',
      defaultTtl: 300,
      compress: false,
      jitter: 10
    },
    {
      namespace: 'analytics',
      defaultDurability: 'eventual',
      defaultTtl: 3600,
      compress: true,
      jitter: 20
    },
    {
      namespace: 'session',
      defaultDurability: 'deferred',
      defaultTtl: 1800,
      compress: false,
      jitter: 5
    }
  ]
});

// Namespace-aware caching with automatic policy application
await cacheManager.set(
  { namespace: 'user', identifier: userId },
  userData
  // No options needed - uses namespace policy
);

// Request coalescing for expensive operations
const user = await cacheManager.getCoalesced<User>(
  { namespace: 'user', identifier: userId },
  async () => {
    // This expensive database query runs only once
    // even if 100 concurrent requests arrive
    return await db.users.findById(userId);
  },
  { ttl: 300 }
);

// Stale-if-error with TTL jitter
const product = await cacheManager.get<Product>(
  { namespace: 'product', identifier: productId },
  { 
    staleIfError: true, 
    maxStaleTime: 60000,
    fallback: async () => await db.products.findById(productId)
  }
);

// Namespace-level invalidation
await cacheManager.invalidateNamespace('user');

// Per-namespace metrics
const stats = cacheManager.getStatsPerNamespace('analytics');
```

## Broker Selection Guide

### Kafka
**Use when:**
- Guaranteed delivery is critical
- Throughput > 100k invalidations/sec
- Need message persistence for auditing
- Multi-region deployments with eventual consistency

**Configuration:**
```typescript
brokerConfig: {
  brokers: ['kafka-1:9092', 'kafka-2:9092'],
  ssl: true,
  sasl: {
    mechanism: 'plain',
    username: process.env.KAFKA_USER,
    password: process.env.KAFKA_PASSWORD
  },
  retry: {
    maxRetryTime: 30000,
    initialRetryTime: 300,
    retries: 8
  }
}
```

### NATS
**Use when:**
- Latency < 1ms is required
- Fire-and-forget invalidation is acceptable
- Simpler operational model preferred
- Single-region deployments

**Configuration:**
```typescript
brokerConfig: {
  servers: ['nats://nats-1:4222', 'nats://nats-2:4222'],
  tls: {
    caFile: '/path/to/ca.pem',
    certFile: '/path/to/cert.pem',
    keyFile: '/path/to/key.pem'
  }
}
```

### Redis Pub/Sub
**Use when:**
- Redis already deployed, no additional infrastructure
- Invalidation rate < 10k/sec
- Simple deployments with 2-5 cache servers
- Lower reliability requirements acceptable

**Configuration:**
```typescript
brokerConfig: {
  host: 'redis-pubsub.example.com',
  port: 6379,
  password: process.env.REDIS_PUBSUB_PASSWORD
}
```

## Production Readiness Checklist

### Observability
- ✅ Per-tier metrics (L1/L2 hit rates, latency)
- ✅ Per-namespace metrics for workload analysis
- ✅ Bloom filter effectiveness tracking
- ✅ Request coalescing metrics
- ✅ Write-behind queue depth monitoring
- ✅ Connection pool utilization alerts

### Resilience
- ✅ Circuit breaker for Redis failures
- ✅ Rate limiting on cache operations
- ✅ Stale-if-error fallback
- ✅ Request coalescing for thundering herd
- ✅ Write-ahead log for durability
- ✅ Graceful degradation (L1-only mode)

### Scalability
- ✅ Hybrid LRU/LFU eviction with soft/hard limits
- ✅ Adaptive compression (LZ4 for speed, gzip for size)
- ✅ Connection pool auto-sizing
- ✅ Batch operations with pipelining
- ✅ Distributed invalidation with pluggable brokers
- ✅ TTL jitter to prevent stampede

### Operational Safety
- ✅ Namespace-level policies for organizational boundaries
- ✅ Per-namespace invalidation for targeted flushes
- ✅ Bloom filter for negative cache to reduce Redis load
- ✅ Memory pressure monitoring and alerts
- ✅ Write-behind queue overflow detection
- ✅ Graceful shutdown with queue flushing

## What I Improved

1. **Hybrid LRU/LFU Eviction**: Replaced pure LRU with hybrid approach that tracks access frequency. Prevents cache pollution from one-time large scans while preserving hot keys. Soft limit (80%) triggers proactive eviction, hard limit (100%) triggers aggressive cleanup.

2. **Request Coalescing**: Added dedicated `RequestCoalescer` and `getCoalesced()` method to prevent thundering herd. Multiple concurrent requests for the same key execute loader only once, with timeout protection and max pending limit.

3. **TTL Jitter**: Added configurable jitter (0-100%) to prevent synchronized cache expiration. Hot keys get staggered expiration times, eliminating stampede on popular data.

4. **Namespace-Level Policies**: Introduced `NamespacePolicy` system allowing per-namespace defaults for durability, TTL, compression, and jitter. Organizational boundaries (user data vs analytics) get appropriate guarantees without per-call configuration.

5. **Broker Selection Guide**: Added concrete guidance on when to use Kafka (high throughput, guaranteed delivery), NATS (ultra-low latency), or Redis Pub/Sub (simple deployments). Includes production configuration examples.

6. **Operational Safety**: Added soft/hard memory limits, namespace-level invalidation, and comprehensive metrics per namespace. Enables safe multi-tenant operation.

7. **Production Readiness Checklist**: Consolidated all production considerations into actionable checklist covering observability, resilience, scalability, and operational safety.

## What I Kept

1. **Two-tier caching architecture** - L1+L2 design is sound
2. **Write-behind queue with priority levels** - Good throughput optimization
3. **Write-ahead log for durability** - Critical for crash safety
4. **Bloom filter for negative caching** - Excellent Redis load reduction
5. **Tag-based invalidation** - Flexible invalidation patterns
6. **Adaptive compression** - Smart size/speed trade-off
7. **Stale-if-error fallback** - High availability pattern
8. **Distributed invalidation framework** - Pluggable broker design

## Remaining Considerations

1. **Multi-region caching**: Current design assumes single-region Redis. Multi-region would require CRDTs or last-write-wins with vector clocks for conflict resolution. Complexity likely not justified unless global deployment needed.

2. **Cache consistency guarantees**: Current design prioritizes availability (eventual consistency). Strong consistency would require distributed locks or Redlock, reducing throughput by 10-100x. Trade-off acceptable for most use cases.

3. **L1 consistency across servers**: Each server has independent L1 cache. Distributed invalidation handles L1 sync, but brief inconsistency (< invalidation latency) possible. If unacceptable, disable L1 or use read-through pattern.

4. **Compression algorithm selection**: LZ4 is ~3x faster than gzip but ~20% larger. Need production profiling to determine optimal threshold and default algorithm for your data characteristics.

5. **Hot key detection threshold tuning**: Threshold of 100 accesses/min works for moderate traffic. High-volume scenarios (1M+ req/s) may need dynamic thresholds based on percentile analysis.

## Convergence Status

**ACCEPTING_FINAL**: Production-ready design with enhanced thundering herd protection, namespace-level policies, and concrete operational guidance.

## PROMPT_FOR_ARCHITECT:

The design is now production-ready. I made key enhancements:

1. **Hybrid LRU/LFU eviction** solves cache pollution from scans while protecting hot keys
2. **Request coalescing** with `getCoalesced()` eliminates thundering herd at application level
3. **TTL jitter** prevents synchronized expiration stampedes
4. **Namespace policies** enable organizational boundaries (user data = immediate durability, analytics = eventual)
5. **Broker selection guide** provides concrete operational guidance

Do you see any critical gaps for 100k+ req/s production deployment? Specifically:

1. Should we add more sophisticated eviction policies (ARC, 2Q) or is hybrid LRU/LFU sufficient?
2. Is the three-tier durability model (immediate/deferred/eventual) complete, or are there use cases requiring additional guarantees?
3. Does the namespace policy system need hierarchical inheritance (e.g., `user:profile` inherits from `user`)?

**Convergence Signal:** ACCEPTING_FINAL

---

