# Final Agreed Design

**Task:** Design a simple caching layer with TTL support

**Status:** debating

---

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, in-memory caching system with automatic expiration based on Time-To-Live (TTL) values. Uses a **single-data-structure approach** that eliminates heap synchronization complexity while maintaining efficient cleanup.

**Core Components:**
1. **Cache Store**: Thread-safe dictionary with integrated expiration tracking
2. **Cache Entry**: Wrapper containing value, metadata, and expiration time
3. **Expiration Buckets**: Time-based buckets for O(1) expiration tracking
4. **Cleanup Scheduler**: Background task for bucket-based cleanup

## Data Models

```python
from dataclasses import dataclass
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import time

@dataclass
class CacheEntry:
    """Represents a single cache entry with expiration"""
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check expiration with optional time parameter for testing"""
        check_time = current_time if current_time else datetime.now()
        return check_time >= self.expires_at
    
    def mark_accessed(self) -> None:
        self.access_count += 1
        self.last_accessed = datetime.now()

@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    total_entries: int = 0
    
    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0
```

## Core Interface

```python
class Cache:
    """Thread-safe caching layer with TTL support"""
    
    def __init__(
        self, 
        default_ttl: int = 300,  # seconds
        max_size: Optional[int] = None,
        cleanup_interval: int = 60,  # seconds
        enable_lru: bool = True,  # Use LRU for eviction
        bucket_size: int = 10  # Expiration bucket size in seconds
    ):
        """
        Args:
            default_ttl: Default time-to-live in seconds (must be > 0)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: How often to run cleanup task (seconds)
            enable_lru: If True, use LRU eviction; if False, use FIFO
            bucket_size: Granularity of expiration buckets (seconds)
        
        Raises:
            ValueError: If default_ttl <= 0 or cleanup_interval <= 0
        """
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        if cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
        if bucket_size <= 0:
            raise ValueError("bucket_size must be positive")
            
        # Use OrderedDict for LRU support if enabled
        self._store: Dict[str, CacheEntry] = OrderedDict() if enable_lru else {}
        # Expiration buckets: {bucket_timestamp: set of keys}
        self._expiration_buckets: Dict[int, set] = {}
        # Reverse index: {key: bucket_timestamp}
        self._key_to_bucket: Dict[str, int] = {}
        
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._stats = CacheStats()
        self._cleanup_interval = cleanup_interval
        self._bucket_size = bucket_size
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._enable_lru = enable_lru
        self._started = False
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        Returns None if key doesn't exist or has expired.
        Thread-safe and updates LRU order if enabled.
        """
        with self._lock:
            if not self._started:
                raise CacheShutdownError("Cache not started")
                
            entry = self._store.get(key)
            if entry is None:
                self._stats.misses += 1
                return None
            
            # Check expiration (lazy)
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.misses += 1
                self._stats.expirations += 1
                return None
            
            # Update access metadata
            entry.mark_accessed()
            self._stats.hits += 1
            
            # Move to end for LRU (OrderedDict optimization)
            if self._enable_lru:
                self._store.move_to_end(key)
            
            return entry.value
    
    def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """
        Store value in cache with specified TTL.
        
        Args:
            key: Cache key
            value: Value to store (any picklable Python object)
            ttl: Time-to-live in seconds (uses default if None)
        
        Returns:
            True if successful, False if cache is full and eviction failed
        
        Raises:
            ValueError: If ttl <= 0
            CacheShutdownError: If cache is stopped
        """
        if ttl is not None and ttl <= 0:
            raise ValueError("TTL must be positive")
            
        with self._lock:
            if not self._started:
                raise CacheShutdownError("Cache not started")
            
            effective_ttl = ttl if ttl is not None else self._default_ttl
            now = datetime.now()
            expires_at = now + timedelta(seconds=effective_ttl)
            
            # If key exists, remove from old bucket
            if key in self._store:
                self._remove_from_bucket(key)
            # Check capacity before adding new entry
            elif self._max_size and len(self._store) >= self._max_size:
                if not self._evict_one():
                    return False  # Could not evict, cache full
            
            # Create new entry
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=expires_at,
                last_accessed=now
            )
            
            # Add to store
            self._store[key] = entry
            
            # Add to expiration bucket
            self._add_to_bucket(key, expires_at)
            
            self._stats.total_entries = len(self._store)
            return True
    
    def delete(self, key: str) -> bool:
        """
        Remove entry from cache. Returns True if existed.
        Thread-safe operation.
        """
        with self._lock:
            if key in self._store:
                self._remove_entry(key)
                return True
            return False
    
    def clear(self) -> None:
        """Remove all entries from cache. Thread-safe."""
        with self._lock:
            self._store.clear()
            self._expiration_buckets.clear()
            self._key_to_bucket.clear()
            self._stats.total_entries = 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired. Thread-safe."""
        with self._lock:
            if key not in self._store:
                return False
            entry = self._store[key]
            if entry.is_expired():
                self._remove_entry(key)
                self._stats.expirations += 1
                return False
            return True
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics. Returns a copy for thread safety."""
        with self._lock:
            return CacheStats(
                hits=self._stats.hits,
                misses=self._stats.misses,
                evictions=self._stats.evictions,
                expirations=self._stats.expirations,
                total_entries=self._stats.total_entries
            )
    
    def start(self) -> None:
        """
        Start the background cleanup task.
        
        Raises:
            RuntimeError: If already started
        """
        with self._lock:
            if self._started:
                raise RuntimeError("Cache already started")
            
            self._started = True
            self._shutdown_event.clear()
            self._cleanup_thread = threading.Thread(
                target=self._cleanup_worker,
                daemon=True,
                name="CacheCleanup"
            )
            self._cleanup_thread.start()
    
    def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the background cleanup task and cleanup resources.
        
        Args:
            timeout: Maximum seconds to wait for cleanup thread to stop
        
        Raises:
            RuntimeWarning: If cleanup thread doesn't stop within timeout
        """
        with self._lock:
            if not self._started:
                return
            
            self._started = False
            self._shutdown_event.set()
        
        # Wait for cleanup thread outside the lock
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=timeout)
            if self._cleanup_thread.is_alive():
                import warnings
                warnings.warn(
                    f"Cleanup thread did not stop within {timeout}s timeout",
                    RuntimeWarning
                )
    
    def _add_to_bucket(self, key: str, expires_at: datetime) -> None:
        """
        Add key to appropriate expiration bucket.
        Must be called with lock held.
        """
        # Calculate bucket timestamp (round down to bucket_size)
        bucket_ts = int(expires_at.timestamp() / self._bucket_size) * self._bucket_size
        
        # Add to bucket
        if bucket_ts not in self._expiration_buckets:
            self._expiration_buckets[bucket_ts] = set()
        self._expiration_buckets[bucket_ts].add(key)
        
        # Update reverse index
        self._key_to_bucket[key] = bucket_ts
    
    def _remove_from_bucket(self, key: str) -> None:
        """
        Remove key from its expiration bucket.
        Must be called with lock held.
        """
        if key not in self._key_to_bucket:
            return
        
        bucket_ts = self._key_to_bucket[key]
        
        # Remove from bucket
        if bucket_ts in self._expiration_buckets:
            self._expiration_buckets[bucket_ts].discard(key)
            # Clean up empty bucket
            if not self._expiration_buckets[bucket_ts]:
                del self._expiration_buckets[bucket_ts]
        
        # Remove from reverse index
        del self._key_to_bucket[key]
    
    def _remove_entry(self, key: str) -> None:
        """
        Remove entry from store and bucket.
        Must be called with lock held.
        """
        if key in self._store:
            del self._store[key]
            self._remove_from_bucket(key)
            self._stats.total_entries = len(self._store)
    
    def _evict_one(self) -> bool:
        """
        Evict one entry to make space.
        Strategy: First try expired entries, then use LRU/FIFO.
        Must be called with lock held.
        
        Returns:
            True if eviction successful, False otherwise
        """
        # First, try to remove expired entries from oldest buckets
        now = datetime.now()
        current_ts = int(now.timestamp() / self._bucket_size) * self._bucket_size
        
        # Check buckets up to current time
        for bucket_ts in sorted(self._expiration_buckets.keys()):
            if bucket_ts > current_ts:
                break
            
            # Try to evict from this bucket
            bucket = self._expiration_buckets[bucket_ts]
            for key in list(bucket):  # Copy to avoid modification during iteration
                if key in self._store:
                    entry = self._store[key]
                    if entry.is_expired(now):
                        self._remove_entry(key)
                        self._stats.evictions += 1
                        self._stats.expirations += 1
                        return True
        
        # No expired entries, evict based on access pattern
        if not self._store:
            return False
        
        if self._enable_lru:
            # Remove least recently used (first item in OrderedDict)
            key_to_evict = next(iter(self._store))
        else:
            # Remove first inserted (FIFO)
            key_to_evict = next(iter(self._store))
        
        self._remove_entry(key_to_evict)
        self._stats.evictions += 1
        return True
    
    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache using bucket approach.
        Returns number of entries removed.
        Must be called with lock held.
        """
        removed_count = 0
        now = datetime.now()
        current_ts = int(now.timestamp() / self._bucket_size) * self._bucket_size
        
        # Process all buckets up to current time
        expired_buckets = [
            bucket_ts for bucket_ts in self._expiration_buckets.keys()
            if bucket_ts <= current_ts
        ]
        
        for bucket_ts in expired_buckets:
            bucket = self._expiration_buckets[bucket_ts]
            
            # Process all keys in bucket
            for key in list(bucket):  # Copy to avoid modification during iteration
                if key in self._store:
                    entry = self._store[key]
                    if entry.is_expired(now):
                        del self._store[key]
                        removed_count += 1
                        self._stats.expirations += 1
                
                # Remove from bucket (whether expired or not, for consistency)
                bucket.discard(key)
                self._key_to_bucket.pop(key, None)
            
            # Remove empty bucket
            if not bucket:
                del self._expiration_buckets[bucket_ts]
        
        self._stats.total_entries = len(self._store)
        return removed_count
    
    def _cleanup_worker(self) -> None:
        """Background thread worker for periodic cleanup."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for cleanup interval or shutdown signal
                if self._shutdown_event.wait(timeout=self._cleanup_interval):
                    break  # Shutdown requested
                
                # Perform cleanup
                with self._lock:
                    if self._started:
                        self._cleanup_expired()
                        
            except Exception as e:
                # Log error but don't crash the thread
                import warnings
                warnings.warn(f"Error in cleanup worker: {e}", RuntimeWarning)
```

## Error Handling

### Exception Types
```python
class CacheError(Exception):
    """Base exception for cache operations"""
    pass

class CacheShutdownError(CacheError):
    """Raised when operation attempted on stopped cache"""
    pass
```

### Error Scenarios
1. **Cache Full**: Return `False` from `set()` when cannot evict
2. **Invalid TTL**: Raise `ValueError` immediately if TTL <= 0
3. **Shutdown State**: Raise `CacheShutdownError` for operations on non-started cache
4. **Thread Errors**: Log warnings and continue; cleanup failures don't crash
5. **Invalid Parameters**: Validate in `__init__` and raise `ValueError`
6. **Thread Timeout**: Warn if cleanup thread doesn't stop within timeout

## Usage Example

```python
# Initialize cache
cache = Cache(
    default_ttl=300,      # 5 minutes default
    max_size=1000,        # Limit to 1000 entries
    cleanup_interval=60,  # Cleanup every minute
    enable_lru=True,      # Use LRU eviction
    bucket_size=10        # 10-second bucket granularity
)
cache.start()

try:
    # Store values
    cache.set("user:123", {"name": "Alice"}, ttl=600)
    cache.set("temp:token", "abc123", ttl=30)
    
    # Retrieve values
    user = cache.get("user:123")  # Returns dict or None
    exists = cache.exists("temp:token")
    
    # Statistics
    stats = cache.get_stats()
    print(f"Hit rate: {stats.hit_rate:.2%}")
    print(f"Expirations: {stats.expirations}")
    
finally:
    # Cleanup
    cache.stop(timeout=5.0)
```

## Implementation Details

### Thread Safety Strategy
- **RLock Usage**: Reentrant lock allows same thread to acquire multiple times
- **Lock Granularity**: Single lock protects store, buckets, and reverse index
- **Lock Duration**: Minimal hold time - all operations are O(1) average case
- **Atomic Updates**: Bucket and store updates happen within same lock acquisition
- **Consistent State**: Reverse index ensures bucket-store synchronization

### TTL Management with Expiration Buckets

**Why Buckets Instead of Heap:**
1. **No Synchronization Overhead**: Single data structure group (store + buckets + index) vs separate heap requiring careful sync
2. **O(1) Insertion**: Adding to bucket is O(1) vs O(log n) heap insertion
3. **O(1) Deletion**: Removing from bucket is O(1) vs O(n) heap search or lazy accumulation
4. **Predictable Memory**: 3 structures with 1:1 key relationships vs heap with potential lazy deletion bloat
5. **Batch Cleanup**: Process entire expired buckets at once, more cache-friendly

**How It Works:**
1. **Bucketing**: Round expiration times down to bucket_size (e.g., 10s)
   - Entry expiring at 13:45:37 → bucket 13:45:30
   - Entry expiring at 13:45:42 → bucket 13:45:40
2. **Cleanup**: Every cleanup_interval, process all buckets <= current time
3. **Granularity Trade-off**: Larger bucket_size = fewer buckets but less precise expiration

### Eviction Strategy (when max_size is set)
- **Priority 1**: Remove expired entries from oldest buckets (O(1) per entry)
- **Priority 2**: LRU eviction using OrderedDict (O(1))
- **Priority 3**: FIFO if LRU disabled (O(1))
- **Triggered**: Before inserting new entry when at capacity

### Performance Characteristics

- **Time Complexity**:
  - `get()`: O(1) average (OrderedDict move_to_end is O(1))
  - `set()`: O(1) for bucket insertion
  - `delete()`: O(1) for both store and bucket
  - Cleanup: O(k) where k = entries in expired buckets
  - Eviction: O(1) with LRU/FIFO

- **Space Complexity**: 
  - Store: O(n)
  - Buckets: O(n) keys across all buckets
  - Reverse index: O(n) 
  - Total: O(3n) = O(n)

**Memory Comparison:**
- Heap approach: Store (n entries) + Heap (n entries) = ~2n objects
- Bucket approach: Store (n entries) + Buckets (n keys) + Index (n mappings) = ~3n references
- **But**: Bucket approach has simpler objects (sets/ints vs heap nodes), often smaller in practice

## Testing Strategy

1. **Unit Tests**:
   - Basic get/set/delete operations
   - TTL expiration (lazy and active)
   - Bucket consistency after operations
   - Thread safety (concurrent operations)
   - Eviction behavior at max capacity
   - Statistics accuracy
   - Error handling (invalid TTL, operations on stopped cache)
   - Bucket boundary cases (entries at exact bucket boundaries)

2. **Integration Tests**:
   - Long-running cleanup thread
   - High-concurrency scenarios (100+ threads)
   - Memory leak detection
   - Bucket-store synchronization under load
   - Mixed TTL values (short and long)

3. **Edge Cases**:
   - Minimum TTL (1 second)
   - TTL smaller than bucket_size
   - Very large TTL values
   - Rapid set/delete cycles on same key
   - Cache full with no evictable entries
   - Starting/stopping multiple times
   - Cleanup during heavy write load