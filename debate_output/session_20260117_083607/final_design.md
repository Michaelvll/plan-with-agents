# Final Agreed Design

**Task:** Design a caching layer with Redis

**Status:** consensus

---

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