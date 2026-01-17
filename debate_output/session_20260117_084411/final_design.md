# Final Agreed Design

**Task:** Design a simple caching layer with TTL support

**Status:** consensus

---

## Design

# Simple Caching Layer with TTL Support

## Architecture

### Core Components

1. **Cache**: Main interface and orchestrator
2. **Storage Backend**: Key-value storage with metadata
3. **TTL Manager**: Handles expiration logic
4. **Eviction Policy**: Memory management strategy

### Component Diagram

```
┌─────────────────────────────────────┐
│           Cache Interface           │
│  get/set/delete/clear/has/keys      │
└──────────────┬──────────────────────┘
               │
       ┌───────┴────────┐
       │                │
┌──────▼──────┐  ┌─────▼────────┐
│   Storage   │  │ TTL Manager  │
│   Backend   │  │              │
└─────────────┘  └──────────────┘
       │                │
       └────────┬───────┘
                │
      ┌─────────▼─────────┐
      │ Eviction Strategy │
      │   (LRU/LFU/FIFO)  │
      └───────────────────┘
```

## Data Models

### Cache Entry Structure

```typescript
interface CacheEntry<T> {
  value: T;
  metadata: {
    createdAt: number;         // Unix timestamp (ms)
    expiresAt: number | null;  // Unix timestamp (ms), null = never expires
    lastAccessed: number;      // Unix timestamp (ms)
    accessCount: number;       // For LFU eviction
  };
}
```

### Cache Configuration

```typescript
interface CacheConfig {
  maxSize?: number;              // Maximum entries (default: 1000)
  defaultTTL?: number | null;    // Default TTL in ms (default: null = no expiry)
  evictionPolicy?: 'LRU' | 'LFU' | 'FIFO';  // Default: LRU
  cleanupInterval?: number;      // Auto-cleanup interval in ms (default: 60000, 0 = disabled)
  onEvict?: (key: string, value: any, reason: 'eviction' | 'expiration') => void;
  updateOnGet?: boolean;         // Update lastAccessed on get() (default: true)
  checkExpiryOnGet?: boolean;    // Check expiry lazily on get() (default: true)
  clone?: boolean;               // Clone values on get/set (default: false)
}
```

## Public API Interface

```typescript
class Cache<T = any> {
  constructor(config?: CacheConfig);
  
  // Core operations
  set(key: string, value: T, ttl?: number | null): void;
  get(key: string): T | undefined;
  has(key: string): boolean;
  delete(key: string): boolean;
  clear(): void;
  
  // Bulk operations
  setMany(entries: Array<[string, T, number | null?]>): void;
  getMany(keys: string[]): Map<string, T>;
  deleteMany(keys: string[]): number;
  deletePattern(pattern: RegExp): number;
  
  // Introspection
  size(): number;
  keys(): string[];
  values(): T[];
  entries(): Array<[string, T]>;
  
  // TTL management
  getTTL(key: string): number | null | undefined;
  setTTL(key: string, ttl: number | null): boolean;
  touch(key: string, ttl?: number | null): boolean;
  
  // Maintenance
  cleanup(): number;  // Manual cleanup, returns number removed
  
  // Statistics
  getStats(): CacheStats;
  resetStats(): void;
  
  // Lifecycle
  destroy(): void;
}

interface CacheStats {
  hits: number;
  misses: number;
  evictions: number;
  expirations: number;
  sets: number;
  deletes: number;
  currentSize: number;
  maxSize: number;
  hitRate: number;       // hits / (hits + misses)
}
```

## Implementation Details

### TTL Manager

```typescript
class TTLManager<T> {
  private cleanupTimer: NodeJS.Timeout | null = null;
  private expirationCount = 0;
  
  constructor(
    private storage: Map<string, CacheEntry<T>>,
    private cleanupInterval: number,
    private onExpire?: (key: string, value: T) => void
  ) {
    if (cleanupInterval > 0) {
      this.startCleanup();
    }
  }
  
  isExpired(entry: CacheEntry<T>): boolean {
    return entry.metadata.expiresAt !== null && Date.now() >= entry.metadata.expiresAt;
  }
  
  checkAndRemoveIfExpired(key: string): boolean {
    const entry = this.storage.get(key);
    if (!entry) return false;
    
    if (this.isExpired(entry)) {
      this.storage.delete(key);
      this.expirationCount++;
      this.onExpire?.(key, entry.value);
      return true;
    }
    return false;
  }
  
  private startCleanup(): void {
    this.cleanupTimer = setInterval(() => {
      this.removeExpired();
    }, this.cleanupInterval);
    
    if (typeof this.cleanupTimer === 'object' && 'unref' in this.cleanupTimer) {
      this.cleanupTimer.unref();
    }
  }
  
  removeExpired(): number {
    let removed = 0;
    const now = Date.now();
    
    for (const [key, entry] of this.storage.entries()) {
      if (entry.metadata.expiresAt !== null && now >= entry.metadata.expiresAt) {
        this.storage.delete(key);
        this.expirationCount++;
        this.onExpire?.(key, entry.value);
        removed++;
      }
    }
    return removed;
  }
  
  getExpirationCount(): number {
    return this.expirationCount;
  }
  
  destroy(): void {
    if (this.cleanupTimer !== null) {
      clearInterval(this.cleanupTimer);
      this.cleanupTimer = null;
    }
  }
}
```

### Eviction Policies

```typescript
interface EvictionPolicy<T> {
  evict(storage: Map<string, CacheEntry<T>>): string | null;
  onAccess?(entry: CacheEntry<T>): void;
}

class LRUEviction<T> implements EvictionPolicy<T> {
  evict(storage: Map<string, CacheEntry<T>>): string | null {
    if (storage.size === 0) return null;
    
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    
    for (const [key, entry] of storage.entries()) {
      if (entry.metadata.lastAccessed < oldestTime) {
        oldestTime = entry.metadata.lastAccessed;
        oldestKey = key;
      }
    }
    
    return oldestKey;
  }
  
  onAccess(entry: CacheEntry<T>): void {
    entry.metadata.lastAccessed = Date.now();
  }
}

class LFUEviction<T> implements EvictionPolicy<T> {
  evict(storage: Map<string, CacheEntry<T>>): string | null {
    if (storage.size === 0) return null;
    
    let leastUsedKey: string | null = null;
    let leastCount = Infinity;
    let oldestAccess = Infinity;
    
    for (const [key, entry] of storage.entries()) {
      const isLessFrequent = entry.metadata.accessCount < leastCount;
      const isSameFreqButOlder = entry.metadata.accessCount === leastCount && 
                                  entry.metadata.lastAccessed < oldestAccess;
      
      if (isLessFrequent || isSameFreqButOlder) {
        leastCount = entry.metadata.accessCount;
        oldestAccess = entry.metadata.lastAccessed;
        leastUsedKey = key;
      }
    }
    
    return leastUsedKey;
  }
  
  onAccess(entry: CacheEntry<T>): void {
    entry.metadata.accessCount++;
    entry.metadata.lastAccessed = Date.now();
  }
}

class FIFOEviction<T> implements EvictionPolicy<T> {
  evict(storage: Map<string, CacheEntry<T>>): string | null {
    if (storage.size === 0) return null;
    
    let oldestKey: string | null = null;
    let oldestTime = Infinity;
    
    for (const [key, entry] of storage.entries()) {
      if (entry.metadata.createdAt < oldestTime) {
        oldestTime = entry.metadata.createdAt;
        oldestKey = key;
      }
    }
    
    return oldestKey;
  }
}
```

### Core Cache Implementation

```typescript
class Cache<T = any> {
  private storage: Map<string, CacheEntry<T>> = new Map();
  private ttlManager: TTLManager<T>;
  private evictionPolicy: EvictionPolicy<T>;
  private config: Required<CacheConfig>;
  private stats = {
    hits: 0,
    misses: 0,
    evictions: 0,
    sets: 0,
    deletes: 0
  };
  
  constructor(config?: CacheConfig) {
    this.config = {
      maxSize: config?.maxSize ?? 1000,
      defaultTTL: config?.defaultTTL ?? null,
      evictionPolicy: config?.evictionPolicy ?? 'LRU',
      cleanupInterval: config?.cleanupInterval ?? 60000,
      onEvict: config?.onEvict ?? (() => {}),
      updateOnGet: config?.updateOnGet ?? true,
      checkExpiryOnGet: config?.checkExpiryOnGet ?? true,
      clone: config?.clone ?? false
    };
    
    this.evictionPolicy = this.createEvictionPolicy(this.config.evictionPolicy);
    this.ttlManager = new TTLManager<T>(
      this.storage,
      this.config.cleanupInterval,
      (key, value) => this.handleExpiration(key, value)
    );
  }
  
  set(key: string, value: T, ttl?: number | null): void {
    this.validateKey(key);
    if (ttl !== undefined) {
      this.validateTTL(ttl);
    }
    
    const now = Date.now();
    const effectiveTTL = ttl !== undefined ? ttl : this.config.defaultTTL;
    
    // Clone if configured
    const storedValue = this.config.clone ? this.cloneValue(value) : value;
    
    const entry: CacheEntry<T> = {
      value: storedValue,
      metadata: {
        createdAt: now,
        expiresAt: effectiveTTL === null ? null : now + effectiveTTL,
        lastAccessed: now,
        accessCount: 0
      }
    };
    
    const isUpdate = this.storage.has(key);
    
    if (!isUpdate && this.storage.size >= this.config.maxSize) {
      this.evictOne();
    }
    
    this.storage.set(key, entry);
    this.stats.sets++;
  }
  
  get(key: string): T | undefined {
    this.validateKey(key);
    
    if (this.config.checkExpiryOnGet && this.ttlManager.checkAndRemoveIfExpired(key)) {
      this.stats.misses++;
      return undefined;
    }
    
    const entry = this.storage.get(key);
    
    if (!entry) {
      this.stats.misses++;
      return undefined;
    }
    
    this.stats.hits++;
    
    if (this.config.updateOnGet && this.evictionPolicy.onAccess) {
      this.evictionPolicy.onAccess(entry);
    }
    
    return this.config.clone ? this.cloneValue(entry.value) : entry.value;
  }
  
  has(key: string): boolean {
    this.validateKey(key);
    
    if (this.config.checkExpiryOnGet && this.ttlManager.checkAndRemoveIfExpired(key)) {
      return false;
    }
    
    return this.storage.has(key);
  }
  
  delete(key: string): boolean {
    this.validateKey(key);
    const existed = this.storage.delete(key);
    if (existed) {
      this.stats.deletes++;
    }
    return existed;
  }
  
  clear(): void {
    this.storage.clear();
  }
  
  setMany(entries: Array<[string, T, number | null?]>): void {
    for (const entry of entries) {
      const [key, value, ttl] = entry;
      this.set(key, value, ttl);
    }
  }
  
  getMany(keys: string[]): Map<string, T> {
    const result = new Map<string, T>();
    for (const key of keys) {
      const value = this.get(key);
      if (value !== undefined) {
        result.set(key, value);
      }
    }
    return result;
  }
  
  deleteMany(keys: string[]): number {
    let deleted = 0;
    for (const key of keys) {
      if (this.delete(key)) {
        deleted++;
      }
    }
    return deleted;
  }
  
  deletePattern(pattern: RegExp): number {
    const keysToDelete: string[] = [];
    
    for (const key of this.storage.keys()) {
      if (pattern.test(key)) {
        keysToDelete.push(key);
      }
    }
    
    return this.deleteMany(keysToDelete);
  }
  
  size(): number {
    return this.storage.size;
  }
  
  keys(): string[] {
    return Array.from(this.storage.keys());
  }
  
  values(): T[] {
    const result: T[] = [];
    for (const [key, entry] of this.storage.entries()) {
      if (!this.config.checkExpiryOnGet || !this.ttlManager.checkAndRemoveIfExpired(key)) {
        result.push(this.config.clone ? this.cloneValue(entry.value) : entry.value);
      }
    }
    return result;
  }
  
  entries(): Array<[string, T]> {
    const result: Array<[string, T]> = [];
    for (const [key, entry] of this.storage.entries()) {
      if (!this.config.checkExpiryOnGet || !this.ttlManager.checkAndRemoveIfExpired(key)) {
        const value = this.config.clone ? this.cloneValue(entry.value) : entry.value;
        result.push([key, value]);
      }
    }
    return result;
  }
  
  getTTL(key: string): number | null | undefined {
    this.validateKey(key);
    
    const entry = this.storage.get(key);
    if (!entry) return undefined;
    
    if (entry.metadata.expiresAt === null) return null;
    
    const remaining = entry.metadata.expiresAt - Date.now();
    return remaining > 0 ? remaining : undefined;
  }
  
  setTTL(key: string, ttl: number | null): boolean {
    this.validateKey(key);
    this.validateTTL(ttl);
    
    const entry = this.storage.get(key);
    if (!entry) return false;
    
    entry.metadata.expiresAt = ttl === null ? null : Date.now() + ttl;
    return true;
  }
  
  touch(key: string, ttl?: number | null): boolean {
    this.validateKey(key);
    
    const entry = this.storage.get(key);
    if (!entry) return false;
    
    const effectiveTTL = ttl !== undefined ? ttl : this.config.defaultTTL;
    this.validateTTL(effectiveTTL);
    
    entry.metadata.expiresAt = effectiveTTL === null ? null : Date.now() + effectiveTTL;
    entry.metadata.lastAccessed = Date.now();
    
    return true;
  }
  
  cleanup(): number {
    return this.ttlManager.removeExpired();
  }
  
  getStats(): CacheStats {
    const total = this.stats.hits + this.stats.misses;
    return {
      hits: this.stats.hits,
      misses: this.stats.misses,
      evictions: this.stats.evictions,
      expirations: this.ttlManager.getExpirationCount(),
      sets: this.stats.sets,
      deletes: this.stats.deletes,
      currentSize: this.storage.size,
      maxSize: this.config.maxSize,
      hitRate: total > 0 ? this.stats.hits / total : 0
    };
  }
  
  resetStats(): void {
    this.stats.hits = 0;
    this.stats.misses = 0;
    this.stats.evictions = 0;
    this.stats.sets = 0;
    this.stats.deletes = 0;
  }
  
  destroy(): void {
    this.ttlManager.destroy();
    this.storage.clear();
  }
  
  private evictOne(): void {
    const keyToEvict = this.evictionPolicy.evict(this.storage);
    if (keyToEvict !== null) {
      const entry = this.storage.get(keyToEvict);
      this.storage.delete(keyToEvict);
      this.stats.evictions++;
      
      if (entry) {
        try {
          this.config.onEvict(keyToEvict, entry.value, 'eviction');
        } catch (error) {
          console.error('Error in onEvict callback:', error);
        }
      }
    }
  }
  
  private handleExpiration(key: string, value: T): void {
    try {
      this.config.onEvict(key, value, 'expiration');
    } catch (error) {
      console.error('Error in onEvict callback:', error);
    }
  }
  
  private createEvictionPolicy(policy: 'LRU' | 'LFU' | 'FIFO'): EvictionPolicy<T> {
    switch (policy) {
      case 'LRU': return new LRUEviction<T>();
      case 'LFU': return new LFUEviction<T>();
      case 'FIFO': return new FIFOEviction<T>();
    }
  }
  
  private validateKey(key: string): void {
    if (typeof key !== 'string' || key.length === 0) {
      throw new InvalidKeyError(key);
    }
  }
  
  private validateTTL(ttl: number | null | undefined): void {
    if (ttl !== undefined && ttl !== null && (typeof ttl !== 'number' || ttl <= 0 || !isFinite(ttl))) {
      throw new InvalidTTLError(ttl);
    }
  }
  
  private cloneValue(value: T): T {
    if (value === null || value === undefined) return value;
    if (typeof value !== 'object') return value;
    
    try {
      return JSON.parse(JSON.stringify(value));
    } catch {
      return value;
    }
  }
}
```

## Error Types

```typescript
class CacheError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'CacheError';
  }
}

class InvalidTTLError extends CacheError {
  constructor(ttl: any) {
    super(`Invalid TTL value: ${ttl}. Must be positive number or null.`);
    this.name = 'InvalidTTLError';
  }
}

class InvalidKeyError extends CacheError {
  constructor(key: any) {
    super(`Invalid key: ${key}. Must be non-empty string.`);
    this.name = 'InvalidKeyError';
  }
}
```

## Usage Examples

```typescript
// Basic usage with TTL
const cache = new Cache<string>({
  maxSize: 100,
  defaultTTL: 5 * 60 * 1000,  // 5 minutes default
  evictionPolicy: 'LRU'
});

cache.set('user:123', 'John Doe', 10000);  // 10 second TTL
cache.set('config:app', 'production', null);  // Never expires

// Bulk operations
cache.setMany([
  ['key1', 'value1', 1000],
  ['key2', 'value2', 2000],
  ['key3', 'value3', null]
]);

const values = cache.getMany(['key1', 'key2']);  // Map<string, string>

// Pattern deletion
cache.deletePattern(/^temp:/);  // Delete all keys starting with "temp:"

// Touch to refresh TTL and update lastAccessed
cache.touch('session:abc');  // Reset to default TTL

// Manual cleanup
const expired = cache.cleanup();  // Returns count of removed entries

// Clone mode for safety
const safeCache = new Cache<object>({
  clone: true  // Deep clone values on get/set
});

const obj = { count: 0 };
safeCache.set('data', obj);
obj.count = 99;  // Won't affect cached value
safeCache.get('data');  // Returns { count: 0 }

// Eviction callback with reason
const trackedCache = new Cache({
  onEvict: (key, value, reason) => {
    if (reason === 'eviction') {
      console.log(`Cache full, evicted: ${key}`);
    } else {
      console.log(`Expired: ${key}`);
    }
  }
});

// Disable automatic expiry checking
const manualCache = new Cache({
  checkExpiryOnGet: false,
  cleanupInterval: 0  // No automatic cleanup
});

// Manual cleanup only
setInterval(() => {
  manualCache.cleanup();
}, 120000);

// Statistics
const stats = cache.getStats();
console.log(`Hit rate: ${(stats.hitRate * 100).toFixed(2)}%`);
console.log(`Evictions: ${stats.evictions}, Expirations: ${stats.expirations}`);

cache.destroy();
```

## Performance Characteristics

| Operation | Time Complexity | Space Complexity | Notes |
|-----------|----------------|------------------|-------|
| get()     | O(1)           | O(1)             | Map lookup + optional expiry check |
| set()     | O(1) amortized | O(1)             | May trigger O(n) eviction scan |
| delete()  | O(1)           | O(1)             | Map delete |
| has()     | O(1)           | O(1)             | Map lookup + optional expiry check |
| clear()   | O(1)           | O(1)             | Map.clear() |
| setMany() | O(k)           | O(k)             | k = number of entries |
| getMany() | O(k)           | O(k)             | k = number of keys |
| deleteMany() | O(k)        | O(1)             | k = number of keys |
| deletePattern() | O(n)     | O(m)             | n = total keys, m = matched keys |
| keys()    | O(n)           | O(n)             | Creates array copy |
| values()  | O(n)           | O(n)             | Iterates + filters expired |
| entries() | O(n)           | O(n)             | Iterates + filters expired |
| cleanup() | O(n)           | O(1)             | Scans all entries |
| eviction  | O(n)           | O(1)             | Full scan to find victim |