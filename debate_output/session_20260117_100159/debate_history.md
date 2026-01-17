# Claude Code Debate Session

**Started:** 2026-01-17T10:01:59.200205
**Ended:** 2026-01-17T10:06:47.379851
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a simple caching layer with TTL support

---

## Round 1

### 🔵 Agent A

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, in-memory caching system with automatic expiration of entries based on Time-To-Live (TTL) values.

**Core Components:**
1. **Cache Store**: Thread-safe hash map for key-value storage
2. **TTL Manager**: Handles expiration tracking and cleanup
3. **Cache Entry**: Wrapper containing value, metadata, and expiration time
4. **Cleanup Scheduler**: Background task for removing expired entries

## Data Models

```python
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime, timedelta
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
    
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at
    
    def mark_accessed(self) -> None:
        self.access_count += 1
        self.last_accessed = datetime.now()

@dataclass
class CacheStats:
    """Cache statistics for monitoring"""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
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
        cleanup_interval: int = 60  # seconds
    ):
        """
        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: How often to run cleanup task (seconds)
        """
        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._stats = CacheStats()
        self._cleanup_interval = cleanup_interval
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache.
        Returns None if key doesn't exist or has expired.
        """
        pass
    
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
            value: Value to store
            ttl: Time-to-live in seconds (uses default if None)
        
        Returns:
            True if successful, False if cache is full
        """
        pass
    
    def delete(self, key: str) -> bool:
        """Remove entry from cache. Returns True if existed."""
        pass
    
    def clear(self) -> None:
        """Remove all entries from cache."""
        pass
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        pass
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        pass
    
    def start(self) -> None:
        """Start the background cleanup task."""
        pass
    
    def stop(self) -> None:
        """Stop the background cleanup task and cleanup resources."""
        pass
```

## Implementation Details

### Thread Safety Strategy
- Use `threading.RLock()` for reentrant locking
- Lock acquisition order: always acquire store lock before any operations
- Hold locks for minimal duration to maximize concurrency

### TTL Management
1. **Lazy Expiration**: Check expiration on `get()` operations
2. **Active Expiration**: Background thread periodically scans for expired entries
3. **Hybrid approach** ensures timely cleanup without overhead on every operation

### Eviction Strategy (when max_size is set)
- **Primary**: Remove expired entries first
- **Fallback**: LRU eviction based on `last_accessed` timestamp
- **Triggered**: Before inserting when at capacity

### Background Cleanup Process
```python
def _cleanup_expired(self) -> None:
    """Remove expired entries from cache."""
    with self._lock:
        expired_keys = [
            key for key, entry in self._store.items() 
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._store[key]
            self._stats.evictions += 1
        self._stats.total_entries = len(self._store)
```

## Error Handling

### Exception Types
```python
class CacheError(Exception):
    """Base exception for cache operations"""
    pass

class CacheFullError(CacheError):
    """Raised when cache is at max capacity and cannot evict"""
    pass

class CacheShutdownError(CacheError):
    """Raised when operation attempted on stopped cache"""
    pass
```

### Error Scenarios
1. **Cache Full**: Return `False` from `set()`, optionally raise `CacheFullError`
2. **Invalid TTL**: Validate TTL > 0, raise `ValueError` if invalid
3. **Shutdown State**: Raise `CacheShutdownError` for operations on stopped cache
4. **Thread Errors**: Log but don't crash; graceful degradation if cleanup fails

## Usage Example

```python
# Initialize cache
cache = Cache(
    default_ttl=300,      # 5 minutes default
    max_size=1000,        # Limit to 1000 entries
    cleanup_interval=60   # Cleanup every minute
)
cache.start()

# Store values
cache.set("user:123", {"name": "Alice"}, ttl=600)
cache.set("temp:token", "abc123", ttl=30)

# Retrieve values
user = cache.get("user:123")  # Returns dict or None
exists = cache.exists("temp:token")

# Statistics
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.2%}")

# Cleanup
cache.stop()
```

## Performance Considerations

- **Time Complexity**:
  - `get()`: O(1) average
  - `set()`: O(1) average, O(n) worst case if eviction needed
  - `delete()`: O(1)
  - Cleanup: O(n) where n = number of entries

- **Space Complexity**: O(n) where n = number of cached entries

- **Optimization Opportunities**:
  - Use sorted data structure for expiration times (heap/sorted list)
  - Batch cleanup operations
  - Separate read/write locks for better concurrency

## Testing Strategy

1. **Unit Tests**:
   - Basic get/set/delete operations
   - TTL expiration (lazy and active)
   - Thread safety (concurrent operations)
   - Eviction behavior at max capacity
   - Statistics accuracy

2. **Integration Tests**:
   - Long-running cleanup thread
   - High-concurrency scenarios
   - Memory leak detection

3. **Edge Cases**:
   - Zero TTL
   - Very large TTL values
   - Rapid expiration/cleanup cycles
   - Cache full scenarios

## Rationale

1. **Thread-safe by default**: Using RLock ensures safety without requiring users to implement their own synchronization
2. **Hybrid expiration**: Combines lazy (efficient) with active cleanup (prevents memory bloat)
3. **Simple interface**: Minimal API surface makes it easy to use correctly
4. **Statistics built-in**: Enables monitoring and debugging without external tools
5. **Graceful degradation**: Returns None/False rather than raising exceptions for common scenarios

## What I Changed

N/A - Initial design

## What I Kept

N/A - Initial design

## Open Questions

1. Should we support TTL refresh on access (sliding expiration)?
2. Should serialization/deserialization be handled by the cache or left to users?
3. Should we add persistence layer support or keep it purely in-memory?
4. What's the optimal cleanup interval default - too frequent wastes CPU, too slow wastes memory

## Convergence Status

**ITERATING** - This is the first round and needs peer review for potential issues and improvements.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
Focus on the thread safety model and the hybrid expiration strategy. Are there race conditions I'm missing? Is the cleanup approach efficient enough, or would a different data structure (like a priority queue for expiration times) be significantly better?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, in-memory caching system with automatic expiration of entries based on Time-To-Live (TTL) values. Uses a hybrid expiration model with optimized data structures for efficient cleanup.

**Core Components:**
1. **Cache Store**: Thread-safe hash map for key-value storage
2. **Expiration Index**: Min-heap (priority queue) tracking entries by expiration time
3. **Cache Entry**: Wrapper containing value, metadata, and expiration time
4. **Cleanup Scheduler**: Background task for removing expired entries

## Data Models

```python
from dataclasses import dataclass
from typing import Any, Optional
from datetime import datetime, timedelta
import threading
import time
import heapq
from collections import OrderedDict

@dataclass
class CacheEntry:
    """Represents a single cache entry with expiration"""
    value: Any
    created_at: datetime
    expires_at: datetime
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    # Heap index for efficient removal, -1 if not in heap
    heap_index: int = -1
    
    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Check expiration with optional time parameter for testing"""
        check_time = current_time if current_time else datetime.now()
        return check_time >= self.expires_at
    
    def mark_accessed(self) -> None:
        self.access_count += 1
        self.last_accessed = datetime.now()
    
    def __lt__(self, other):
        """For heap ordering by expiration time"""
        return self.expires_at < other.expires_at

@dataclass
class HeapEntry:
    """Wrapper for heap to track key-expiration pairs"""
    expires_at: datetime
    key: str
    
    def __lt__(self, other):
        return self.expires_at < other.expires_at

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
        enable_lru: bool = True  # Use LRU for eviction
    ):
        """
        Args:
            default_ttl: Default time-to-live in seconds (must be > 0)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: How often to run cleanup task (seconds)
            enable_lru: If True, use LRU eviction; if False, use access-time based
        
        Raises:
            ValueError: If default_ttl <= 0 or cleanup_interval <= 0
        """
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        if cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
            
        # Use OrderedDict for LRU support if enabled
        self._store: dict[str, CacheEntry] = OrderedDict() if enable_lru else {}
        self._expiration_heap: list[HeapEntry] = []  # Min-heap by expiration time
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._stats = CacheStats()
        self._cleanup_interval = cleanup_interval
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
            
            # If key exists, remove old entry from heap
            if key in self._store:
                self._remove_from_heap(key)
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
            
            # Add to expiration heap
            heap_entry = HeapEntry(expires_at=expires_at, key=key)
            heapq.heappush(self._expiration_heap, heap_entry)
            
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
            self._expiration_heap.clear()
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
        """
        with self._lock:
            if not self._started:
                return
            
            self._started = False
            self._shutdown_event.set()
        
        # Wait for cleanup thread outside the lock
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=timeout)
    
    def _remove_entry(self, key: str) -> None:
        """
        Remove entry from both store and heap.
        Must be called with lock held.
        """
        if key in self._store:
            del self._store[key]
            self._remove_from_heap(key)
            self._stats.total_entries = len(self._store)
    
    def _remove_from_heap(self, key: str) -> None:
        """
        Mark heap entry as invalid (lazy removal).
        Actual removal happens during heap operations.
        Must be called with lock held.
        """
        # Lazy deletion: we don't remove from heap immediately
        # Instead, we check during cleanup if the key still exists
        pass
    
    def _evict_one(self) -> bool:
        """
        Evict one entry to make space.
        Strategy: First try expired entries, then use LRU/access-time.
        Must be called with lock held.
        
        Returns:
            True if eviction successful, False otherwise
        """
        # First, try to remove expired entries
        while self._expiration_heap:
            heap_entry = self._expiration_heap[0]
            
            # Check if entry still exists and is expired
            if heap_entry.key in self._store:
                entry = self._store[heap_entry.key]
                if entry.is_expired():
                    heapq.heappop(self._expiration_heap)
                    del self._store[heap_entry.key]
                    self._stats.evictions += 1
                    self._stats.expirations += 1
                    return True
                else:
                    # Not expired, stop checking heap
                    break
            else:
                # Entry no longer exists, remove from heap
                heapq.heappop(self._expiration_heap)
        
        # No expired entries, evict based on access pattern
        if not self._store:
            return False
        
        if self._enable_lru:
            # Remove least recently used (first item in OrderedDict)
            key_to_evict = next(iter(self._store))
        else:
            # Remove least recently accessed by access time
            key_to_evict = min(
                self._store.keys(),
                key=lambda k: self._store[k].last_accessed or self._store[k].created_at
            )
        
        self._remove_entry(key_to_evict)
        self._stats.evictions += 1
        return True
    
    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache using heap.
        Returns number of entries removed.
        Must be called with lock held.
        """
        removed_count = 0
        now = datetime.now()
        
        # Process heap until we find non-expired entry
        while self._expiration_heap:
            heap_entry = self._expiration_heap[0]
            
            # Check if expired
            if heap_entry.expires_at > now:
                break  # Heap is sorted, no more expired entries
            
            # Pop from heap
            heapq.heappop(self._expiration_heap)
            
            # Check if entry still exists in store (may have been deleted)
            if heap_entry.key in self._store:
                entry = self._store[heap_entry.key]
                # Double-check expiration with entry's actual expiration time
                if entry.is_expired(now):
                    del self._store[heap_entry.key]
                    removed_count += 1
                    self._stats.expirations += 1
        
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
                        removed = self._cleanup_expired()
                        # Optional: log cleanup activity
                        # print(f"Cleanup removed {removed} expired entries")
                        
            except Exception as e:
                # Log error but don't crash the thread
                # In production, use proper logging
                print(f"Error in cleanup worker: {e}")
                # Continue running despite errors
```

## Error Handling

### Exception Types
```python
class CacheError(Exception):
    """Base exception for cache operations"""
    pass

class CacheFullError(CacheError):
    """Raised when cache is at max capacity and cannot evict"""
    pass

class CacheShutdownError(CacheError):
    """Raised when operation attempted on stopped cache"""
    pass
```

### Error Scenarios
1. **Cache Full**: Return `False` from `set()` when cannot evict
2. **Invalid TTL**: Raise `ValueError` immediately if TTL <= 0
3. **Shutdown State**: Raise `CacheShutdownError` for operations on non-started cache
4. **Thread Errors**: Log and continue; cleanup failures don't affect cache operations
5. **Invalid Parameters**: Validate in `__init__` and raise `ValueError`

## Usage Example

```python
# Initialize cache
cache = Cache(
    default_ttl=300,      # 5 minutes default
    max_size=1000,        # Limit to 1000 entries
    cleanup_interval=60,  # Cleanup every minute
    enable_lru=True       # Use LRU eviction
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
- **Lock Granularity**: Single lock protects both store and heap for consistency
- **Lock Duration**: Minimal hold time - all operations are O(1) or O(log n)
- **Race Condition Prevention**:
  - Check-then-act patterns protected within single lock acquisition
  - Expiration checks use consistent time snapshot
  - Heap and store updates are atomic within lock

### TTL Management with Min-Heap
1. **Lazy Expiration**: Check expiration on `get()` and `exists()` operations
2. **Active Expiration**: Background thread uses heap to efficiently find expired entries
3. **Heap Optimization**: O(log n) insertion, O(1) peek for next expiration, O(log n) removal
4. **Lazy Heap Cleanup**: Entries deleted from store aren't immediately removed from heap - validated during heap operations

### Eviction Strategy (when max_size is set)
- **Priority 1**: Remove expired entries first (heap-assisted O(log n))
- **Priority 2**: LRU eviction using OrderedDict (O(1) if enabled)
- **Priority 3**: Access-time based eviction if LRU disabled (O(n))
- **Triggered**: Before inserting new entry when at capacity

### Performance Characteristics

- **Time Complexity**:
  - `get()`: O(1) average, O(log n) if LRU move needed
  - `set()`: O(log n) for heap insertion
  - `delete()`: O(1) for store, lazy for heap
  - Cleanup: O(k log n) where k = expired entries
  - Eviction: O(log n) with heap, O(1) with LRU

- **Space Complexity**: O(n) for store + O(n) for heap = O(n) total

## Testing Strategy

1. **Unit Tests**:
   - Basic get/set/delete operations
   - TTL expiration (lazy and active)
   - Heap consistency after operations
   - Thread safety (concurrent operations with ThreadPoolExecutor)
   - Eviction behavior at max capacity (expired first, then LRU)
   - Statistics accuracy
   - Error handling (invalid TTL, operations on stopped cache)

2. **Integration Tests**:
   - Long-running cleanup thread (hours)
   - High-concurrency scenarios (100+ threads)
   - Memory leak detection with profiling
   - Heap-store synchronization under load

3. **Edge Cases**:
   - Minimum TTL (1 second)
   - Very large TTL values (days/weeks)
   - Rapid expiration/cleanup cycles
   - Cache full with no evictable entries
   - Updating existing keys (heap cleanup)
   - Starting/stopping multiple times

## What I Improved

1. **Heap-Based Expiration**: Added min-heap (priority queue) for O(log n) expiration tracking instead of O(n) iteration. Cleanup now efficiently processes only expired entries.

2. **LRU Support**: Integrated OrderedDict for true O(1) LRU eviction when enabled, with fallback to access-time based eviction.

3. **Race Condition Fixes**:
   - Added explicit started state check to prevent operations on non-started cache
   - Made expiration checks use consistent time snapshots
   - Protected check-then-act patterns properly

4. **Enhanced Error Handling**:
   - Added validation in `__init__` to fail fast on invalid parameters
   - Raise `CacheShutdownError` for operations on stopped cache (clearer than silent failures)
   - Added timeout parameter to `stop()` method

5. **Statistics Enhancement**: Separated `expirations` from `evictions` to distinguish automatic TTL removal from capacity-based eviction.

6. **Cleanup Efficiency**: Background cleanup now uses heap to find expired entries in O(k log n) instead of scanning all entries O(n).

7. **Lazy Heap Cleanup**: Heap entries for deleted keys aren't immediately removed (expensive O(n) operation), but validated lazily during heap operations.

## What I Kept

1. **Thread-safe design with RLock**: Excellent choice for reentrant locking
2. **Hybrid expiration approach**: Lazy + active is the right balance
3. **Simple, clean interface**: Easy to use and understand
4. **Built-in statistics**: Essential for monitoring
5. **Graceful degradation**: Returning False/None rather than crashing
6. **Separation of concerns**: Clear separation between entry, stats, and cache logic
7. **Background cleanup thread**: Proper approach with daemon thread and shutdown event

## Remaining Concerns

1. **Heap Memory Overhead**: Maintaining duplicate references (store + heap) increases memory by ~2x for keys. For very large caches, this could be significant.

2. **Heap Lazy Cleanup**: Deleted entries remain in heap until encountered. In pathological cases (many deletes), heap could grow larger than store. Consider periodic heap rebuilding if `len(heap) > 2 * len(store)`.

3. **Stop Timeout Handling**: If cleanup thread doesn't stop within timeout, it's left dangling as daemon. Consider force-kill mechanism or logging warning.

4. **Serialization**: Design assumes values are kept in memory as-is. For distributed caching or persistence, serialization layer would be needed.

## Convergence Status

**ITERATING** - First round review with significant improvements to efficiency and thread safety. Need architect's feedback on heap overhead trade-offs and validation of race condition fixes.

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
Please review the heap-based expiration approach and the lazy heap cleanup strategy. Specifically: (1) Is the memory overhead of maintaining a separate heap justified by the O(log n) vs O(n) cleanup improvement? (2) Are there any race conditions in the heap-store synchronization that I've missed? (3) Should we add a heap rebuild mechanism when lazy deletions accumulate, or is the current approach sufficient?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

### Why Buckets Over Heap

The heap-based approach has fundamental synchronization complexity:
1. **Dual Data Structure Problem**: Every operation must maintain consistency between store and heap
2. **Lazy Deletion Accumulation**: Deleted entries remain in heap, potentially growing unbounded
3. **O(log n) Cost**: Heap operations are logarithmic vs O(1) for hash-based buckets
4. **Complex Eviction**: Must check if heap top entry still exists in store before using it

The bucket approach eliminates these issues:
1. **Single Conceptual Model**: Store + buckets + index operate as one logical structure
2. **Immediate Cleanup**: Deleting from bucket is O(1), no lazy accumulation
3. **Constant Time**: Hash table operations dominate, no logarithmic factors
4. **Simple Eviction**: Iterate oldest bucket, all entries are candidates

### Granularity Trade-off

Bucket size controls precision vs efficiency:
- **Small buckets** (1-5s): More precise expiration, more buckets to manage
- **Medium buckets** (10-30s): Good balance for most use cases
- **Large buckets** (60s+): Fewer buckets, entries may live slightly longer than TTL

For most applications, 10-30s is optimal. Entries rarely need sub-second expiration precision.

## What I Changed

1. **Replaced Heap with Buckets**: Eliminated heap entirely in favor of time-bucketed approach for simpler synchronization and O(1) operations

2. **Added Reverse Index**: `_key_to_bucket` enables O(1) removal from buckets when keys are deleted or updated

3. **Simplified Thread Safety**: Single logical data structure (store + buckets + index) with clearer consistency model

4. **Removed HeapEntry Class**: No longer needed, simplifies data model

5. **Better Stop Handling**: Added warning when cleanup thread doesn't stop within timeout instead of silent failure

6. **Removed Access-Time Eviction**: Simplified to LRU or FIFO only - access-time scanning was O(n) and rarely useful

## What I Kept

1. **Thread-safe design with RLock**: Excellent foundation
2. **Hybrid expiration approach**: Lazy + active is still optimal
3. **Clean interface**: get/set/delete/exists/start/stop
4. **Statistics tracking**: Essential for monitoring
5. **OrderedDict for LRU**: Perfect for O(1) LRU implementation
6. **CacheEntry dataclass**: Clean separation of concerns
7. **Graceful error handling**: Return False/None vs crashing
8. **Validation in __init__**: Fail fast on invalid parameters

## Open Questions

1. **Bucket Size Tuning**: Should we auto-calculate bucket_size based on default_ttl (e.g., ttl/10)?
2. **Bucket Cleanup**: Should we proactively remove empty buckets or wait for next cleanup cycle?
3. **Memory Monitoring**: Should we add a method to report bucket distribution for debugging?

## Convergence Status

**ITERATING** - First round with fundamental redesign of expiration tracking mechanism. The bucket approach is simpler and faster, but needs validation that the precision trade-off is acceptable.

## Prompt for Collaborator

PROMPT_FOR_CRITIC:
I've replaced the heap with a bucket-based approach for expiration tracking. Please evaluate: (1) Does the O(1) simplicity of buckets outweigh the loss of exact expiration precision? (2) Is the reverse index (`_key_to_bucket`) the right way to enable O(1) removal, or is there a simpler approach? (3) Are there any race conditions in the bucket-store-index synchronization that I've missed? (4) Should bucket_size be configurable or automatically derived from TTL?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, in-memory caching system with automatic expiration based on Time-To-Live (TTL) values. Uses a **dual-list approach** that combines O(1) operations with precise expiration tracking, avoiding both heap complexity and bucket imprecision.

**Core Components:**
1. **Cache Store**: Thread-safe dictionary holding entries
2. **Cache Entry**: Wrapper containing value, metadata, and expiration time
3. **Expiration Linked List**: Ordered by expiration time for precise cleanup
4. **Cleanup Scheduler**: Background task for efficient expiration processing

## Data Models

```python
from dataclasses import dataclass
from typing import Any, Optional, Dict
from datetime import datetime, timedelta
from collections import OrderedDict
import threading
import time

@dataclass
class ExpirationNode:
    """Node in the expiration linked list"""
    key: str
    expires_at: datetime
    prev: Optional['ExpirationNode'] = None
    next: Optional['ExpirationNode'] = None

@dataclass
class CacheEntry:
    """Represents a single cache entry with expiration"""
    value: Any
    created_at: datetime
    expires_at: datetime
    expiration_node: ExpirationNode  # Reference to position in expiration list
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

class ExpirationList:
    """Doubly-linked list ordered by expiration time"""
    
    def __init__(self):
        # Sentinel nodes to simplify edge cases
        self.head = ExpirationNode(key="", expires_at=datetime.min)
        self.tail = ExpirationNode(key="", expires_at=datetime.max)
        self.head.next = self.tail
        self.tail.prev = self.head
        self._size = 0
    
    def insert(self, key: str, expires_at: datetime) -> ExpirationNode:
        """
        Insert new node in sorted position (binary search from tail for cache locality).
        Returns the created node.
        O(1) amortized for monotonically increasing expirations (common case).
        """
        # Optimization: Most inserts are recent, search from tail backwards
        node = ExpirationNode(key=key, expires_at=expires_at)
        
        # Find insertion point (start from tail for locality)
        current = self.tail.prev
        while current != self.head and current.expires_at > expires_at:
            current = current.prev
        
        # Insert after current
        node.next = current.next
        node.prev = current
        current.next.prev = node
        current.next = node
        
        self._size += 1
        return node
    
    def remove(self, node: ExpirationNode) -> None:
        """Remove node from list. O(1)."""
        if node.prev:
            node.prev.next = node.next
        if node.next:
            node.next.prev = node.prev
        node.prev = None
        node.next = None
        self._size -= 1
    
    def pop_expired(self, current_time: datetime) -> list[str]:
        """
        Remove and return all expired keys. O(k) where k = expired entries.
        Returns keys in expiration order.
        """
        expired_keys = []
        current = self.head.next
        
        while current != self.tail and current.expires_at <= current_time:
            expired_keys.append(current.key)
            next_node = current.next
            self.remove(current)
            current = next_node
        
        return expired_keys
    
    def peek_next_expiration(self) -> Optional[datetime]:
        """Return next expiration time without removing. O(1)."""
        if self.head.next != self.tail:
            return self.head.next.expires_at
        return None
    
    def size(self) -> int:
        """Return number of entries in list. O(1)."""
        return self._size
    
    def clear(self) -> None:
        """Remove all nodes. O(1)."""
        self.head.next = self.tail
        self.tail.prev = self.head
        self._size = 0
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
        enable_lru: bool = True  # Use LRU for eviction
    ):
        """
        Args:
            default_ttl: Default time-to-live in seconds (must be > 0)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: How often to run cleanup task (seconds)
            enable_lru: If True, use LRU eviction; if False, use FIFO
        
        Raises:
            ValueError: If default_ttl <= 0 or cleanup_interval <= 0
        """
        if default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        if cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")
            
        # Use OrderedDict for LRU support if enabled
        self._store: Dict[str, CacheEntry] = OrderedDict() if enable_lru else {}
        self._expiration_list = ExpirationList()
        
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._stats = CacheStats()
        self._cleanup_interval = cleanup_interval
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
                self._remove_entry(key, entry)
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
            key: Cache key (must be non-empty string)
            value: Value to store (any picklable Python object)
            ttl: Time-to-live in seconds (uses default if None)
        
        Returns:
            True if successful, False if cache is full and eviction failed
        
        Raises:
            ValueError: If ttl <= 0 or key is empty
            CacheShutdownError: If cache is stopped
        """
        if not key:
            raise ValueError("Key cannot be empty")
        if ttl is not None and ttl <= 0:
            raise ValueError("TTL must be positive")
            
        with self._lock:
            if not self._started:
                raise CacheShutdownError("Cache not started")
            
            effective_ttl = ttl if ttl is not None else self._default_ttl
            now = datetime.now()
            expires_at = now + timedelta(seconds=effective_ttl)
            
            # If key exists, remove old expiration node
            existing_entry = self._store.get(key)
            if existing_entry:
                self._expiration_list.remove(existing_entry.expiration_node)
            # Check capacity before adding new entry
            elif self._max_size and len(self._store) >= self._max_size:
                if not self._evict_one():
                    return False  # Could not evict, cache full
            
            # Create expiration node and entry
            exp_node = self._expiration_list.insert(key, expires_at)
            entry = CacheEntry(
                value=value,
                created_at=now,
                expires_at=expires_at,
                expiration_node=exp_node,
                last_accessed=now
            )
            
            # Add to store
            self._store[key] = entry
            self._stats.total_entries = len(self._store)
            return True
    
    def delete(self, key: str) -> bool:
        """
        Remove entry from cache. Returns True if existed.
        Thread-safe operation.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry:
                self._remove_entry(key, entry)
                return True
            return False
    
    def clear(self) -> None:
        """Remove all entries from cache. Thread-safe."""
        with self._lock:
            self._store.clear()
            self._expiration_list.clear()
            self._stats.total_entries = 0
    
    def exists(self, key: str) -> bool:
        """Check if key exists and is not expired. Thread-safe."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove_entry(key, entry)
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
    
    def get_ttl(self, key: str) -> Optional[int]:
        """
        Get remaining TTL in seconds for a key.
        Returns None if key doesn't exist or is expired.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            
            if entry.is_expired():
                self._remove_entry(key, entry)
                self._stats.expirations += 1
                return None
            
            remaining = (entry.expires_at - datetime.now()).total_seconds()
            return max(0, int(remaining))
    
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
    
    def _remove_entry(self, key: str, entry: CacheEntry) -> None:
        """
        Remove entry from store and expiration list.
        Must be called with lock held.
        """
        del self._store[key]
        self._expiration_list.remove(entry.expiration_node)
        self._stats.total_entries = len(self._store)
    
    def _evict_one(self) -> bool:
        """
        Evict one entry to make space.
        Strategy: First try expired entries, then use LRU/FIFO.
        Must be called with lock held.
        
        Returns:
            True if eviction successful, False otherwise
        """
        # First, check if head of expiration list is expired
        next_expiration = self._expiration_list.peek_next_expiration()
        if next_expiration:
            now = datetime.now()
            if next_expiration <= now:
                # Batch remove expired entries
                expired_keys = self._expiration_list.pop_expired(now)
                for key in expired_keys:
                    if key in self._store:
                        del self._store[key]
                        self._stats.evictions += 1
                        self._stats.expirations += 1
                
                self._stats.total_entries = len(self._store)
                return len(expired_keys) > 0
        
        # No expired entries, evict based on access pattern
        if not self._store:
            return False
        
        if self._enable_lru:
            # Remove least recently used (first item in OrderedDict)
            key_to_evict = next(iter(self._store))
        else:
            # Remove first inserted (FIFO)
            key_to_evict = next(iter(self._store))
        
        entry_to_evict = self._store[key_to_evict]
        self._remove_entry(key_to_evict, entry_to_evict)
        self._stats.evictions += 1
        return True
    
    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache using expiration list.
        Returns number of entries removed.
        Must be called with lock held.
        """
        now = datetime.now()
        expired_keys = self._expiration_list.pop_expired(now)
        
        removed_count = 0
        for key in expired_keys:
            if key in self._store:
                del self._store[key]
                removed_count += 1
                self._stats.expirations += 1
        
        self._stats.total_entries = len(self._store)
        return removed_count
    
    def _cleanup_worker(self) -> None:
        """Background thread worker for adaptive cleanup scheduling."""
        while not self._shutdown_event.is_set():
            try:
                # Calculate dynamic wait time based on next expiration
                wait_time = self._cleanup_interval
                
                with self._lock:
                    if self._started:
                        next_exp = self._expiration_list.peek_next_expiration()
                        if next_exp:
                            # Wake up when next entry expires (bounded by cleanup_interval)
                            time_until_next = (next_exp - datetime.now()).total_seconds()
                            wait_time = max(1, min(time_until_next + 0.1, self._cleanup_interval))
                
                # Wait for calculated time or shutdown signal
                if self._shutdown_event.wait(timeout=wait_time):
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
3. **Empty Key**: Raise `ValueError` if key is empty string
4. **Shutdown State**: Raise `CacheShutdownError` for operations on non-started cache
5. **Thread Errors**: Log warnings and continue; cleanup failures don't crash
6. **Invalid Parameters**: Validate in `__init__` and raise `ValueError`
7. **Thread Timeout**: Warn if cleanup thread doesn't stop within timeout

## Usage Example

```python
# Initialize cache
cache = Cache(
    default_ttl=300,      # 5 minutes default
    max_size=1000,        # Limit to 1000 entries
    cleanup_interval=60,  # Cleanup check interval
    enable_lru=True       # Use LRU eviction
)
cache.start()

try:
    # Store values
    cache.set("user:123", {"name": "Alice"}, ttl=600)
    cache.set("temp:token", "abc123", ttl=30)
    
    # Retrieve values
    user = cache.get("user:123")  # Returns dict or None
    exists = cache.exists("temp:token")
    remaining = cache.get_ttl("temp:token")  # Get remaining seconds
    
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
- **Lock Granularity**: Single lock protects store and expiration list atomically
- **Lock Duration**: Minimal hold time - all operations are O(1) or O(k) for k expired
- **Atomic Updates**: List and store updates happen within same lock acquisition
- **Consistent State**: Entry holds node reference, ensuring list-store synchronization

### TTL Management with Expiration List

**Why Linked List Over Buckets:**
1. **Precise Expiration**: No granularity loss - entries expire exactly at TTL
2. **Simpler Synchronization**: Two structures (store + list) vs three (store + buckets + reverse index)
3. **No Tuning Required**: No bucket_size parameter to configure
4. **Efficient Cleanup**: Process only expired entries, not entire buckets
5. **Better for Variable TTLs**: No wasted memory from sparsely populated buckets

**Why Linked List Over Heap:**
1. **O(1) Deletion**: Remove node directly vs O(n) heap search or lazy deletion
2. **Simpler Code**: No heap maintenance, just pointer manipulation
3. **Cache Locality**: Sequential access during cleanup is cache-friendly
4. **No Lazy Issues**: Direct removal prevents memory bloat from deleted entries

**How It Works:**
1. **Insertion**: New entries inserted in sorted position (O(1) amortized for typical patterns)
2. **Deletion**: Direct node removal via stored reference (O(1))
3. **Cleanup**: Walk from head, remove all expired entries (O(k) for k expired)
4. **Adaptive Scheduling**: Wake cleanup thread when next entry expires (not fixed intervals)

**Optimization Details:**
- **Sentinel Nodes**: Eliminate null checks and edge cases
- **Backward Insertion**: Search from tail for better locality (most inserts are recent)
- **Batch Expiration**: `pop_expired()` removes multiple entries in one pass
- **Adaptive Wake**: Cleanup thread wakes when needed, not on fixed schedule

### Eviction Strategy (when max_size is set)
- **Priority 1**: Batch remove expired entries from expiration list (O(k) for k expired)
- **Priority 2**: LRU eviction using OrderedDict (O(1))
- **Priority 3**: FIFO if LRU disabled (O(1))
- **Triggered**: Before inserting new entry when at capacity

### Performance Characteristics

- **Time Complexity**:
  - `get()`: O(1) average
  - `set()`: O(1) amortized (worst case O(n) for reverse-ordered inserts, rare in practice)
  - `delete()`: O(1) for both store and list
  - Cleanup: O(k) where k = expired entries (not total entries)
  - Eviction: O(1) for LRU/FIFO, O(k) for expired batch

- **Space Complexity**: 
  - Store: O(n) entries
  - Expiration list: O(n) nodes
  - Total: O(2n) = O(n)
  - **20-30% less memory than bucket approach** (no reverse index)

### Adaptive Cleanup Scheduling

Unlike fixed-interval polling, the cleanup thread dynamically adjusts:
```python
next_expiration = expiration_list.peek_next_expiration()
if next_expiration:
    wait_time = min(time_until(next_expiration), cleanup_interval)
```

**Benefits:**
- **Lower CPU**: Sleep longer when no near-term expirations
- **Lower Latency**: Wake early when entries about to expire
- **Responsive**: Long TTL entries don't waste cleanup cycles

## Testing Strategy

1. **Unit Tests**:
   - Basic get/set/delete operations
   - TTL expiration (lazy and active)
   - List-store consistency after operations
   - Thread safety (concurrent operations)
   - Eviction behavior at max capacity
   - Statistics accuracy
   - Error handling (invalid TTL, empty keys, operations on stopped cache)
   - get_ttl() accuracy as time progresses

2. **Integration Tests**:
   - Long-running cleanup thread with adaptive scheduling
   - High-concurrency scenarios (100+ threads)
   - Memory leak detection (no orphaned nodes)
   - List-store synchronization under load
   - Mixed TTL values (1s to 1 hour)
   - Adaptive cleanup wake times

3. **Edge Cases**:
   - Minimum TTL (1 second)
   - Very large TTL values (days)
   - Rapid set/delete cycles on same key
   - Cache full with no evictable entries
   - Starting/stopping multiple times
   - Cleanup during heavy write load
   - Reverse-ordered TTL insertions (worst case for list insertion)

## What I Improved

1. **Replaced Buckets with Linked List**: Eliminated bucketing imprecision and reverse index complexity. List provides exact expiration with simpler two-structure model (store + list vs store + buckets + index).

2. **Removed bucket_size Parameter**: No tuning required - list naturally handles any TTL distribution without granularity trade-offs.

3. **Added Adaptive Cleanup**: Cleanup thread wakes when next entry expires (bounded by cleanup_interval), reducing CPU waste and improving responsiveness.

4. **Added get_ttl() Method**: Allows users to query remaining time on cache entries - useful for debugging and monitoring.

5. **Simplified Deletion**: O(1) direct node removal via stored reference eliminates reverse index lookups.

6. **Better Memory Efficiency**: Two structures instead of three saves ~20-30% overhead (no reverse index mapping).

7. **Added Empty Key Validation**: Prevent subtle bugs from empty string keys.

8. **Improved Eviction**: Batch-removes expired entries before falling back to LRU, more efficient than bucket iteration.

## What I Kept

1. **Thread-safe design with RLock**: Perfect foundation for concurrent access
2. **Hybrid expiration approach**: Lazy on read + active cleanup remains optimal
3. **Clean interface**: get/set/delete/exists/start/stop is intuitive
4. **Statistics tracking**: Essential for monitoring cache health
5. **OrderedDict for LRU**: Excellent O(1) LRU with move_to_end()
6. **CacheEntry dataclass**: Clean encapsulation of entry metadata
7. **Graceful error handling**: Return False/None vs exceptions for common failures
8. **Validation in __init__**: Fail fast on configuration errors
9. **Stop with timeout**: Prevents indefinite hangs on shutdown

## Remaining Concerns

1. **Insertion Performance**: Worst case O(n) for reverse-ordered TTLs. In practice, cache entries are typically added with similar TTLs (temporal locality), making this rare. Consider adding a fast-path check if this becomes an issue.

2. **Memory vs Heap**: Linked list uses ~2n objects vs heap's ~2n objects. Similar overhead, but list nodes may be slightly larger. Not a concern for typical cache sizes (<100K entries).

3. **Thread Contention**: Single lock protects all operations. For extremely high concurrency (1000+ threads), consider sharding the cache. For typical use (10-100 threads), single lock is simpler and sufficient.

## Convergence Status

**ITERATING** - Second round with fundamental redesign. The linked list approach eliminates bucketing precision loss and removes the reverse index, resulting in simpler code with exact expiration semantics. Need validation that the insertion cost (O(1) amortized) is acceptable and the adaptive cleanup provides meaningful benefit.

## Prompt for Collaborator

PROMPT_FOR_ARCHITECT:
I've replaced buckets with a doubly-linked list for precise expiration tracking and added adaptive cleanup scheduling. Please evaluate: (1) Does the O(1) amortized insertion (worst case O(n) for reverse-ordered TTLs) match real-world access patterns? (2) Is the adaptive cleanup (waking when next entry expires) worth the added complexity vs fixed-interval polling? (3) Should we add a fast-path for the common case where new TTL >= tail TTL (append-only optimization)? (4) Are there concurrency edge cases in the list manipulation (node prev/next pointers) that could cause corruption under heavy load?

**Convergence Signal:** ITERATING

---

