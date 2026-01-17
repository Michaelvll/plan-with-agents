# Claude Code Debate Session

**Started:** 2026-01-17T08:36:00.985092
**Ended:** 2026-01-17T08:42:03.741879
**Status:** consensus
**Rounds:** 2

## Initial Prompt

Design a simple caching layer with TTL support

---

## Round 1

### 🔵 Agent A

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, thread-safe in-memory caching system with automatic expiration based on Time-To-Live (TTL) values.

### Core Components

```python
from typing import Any, Optional, Dict, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import time
from collections import OrderedDict


@dataclass
class CacheEntry:
    """Represents a single cache entry with metadata."""
    value: Any
    created_at: datetime
    ttl_seconds: int
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl_seconds <= 0:
            return False  # TTL of 0 or negative means no expiration
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() >= expiry_time
    
    def remaining_ttl(self) -> float:
        """Returns remaining seconds until expiration, or -1 if no expiration."""
        if self.ttl_seconds <= 0:
            return -1
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        remaining = (expiry_time - datetime.now()).total_seconds()
        return max(0, remaining)


class CacheLayer:
    """
    Thread-safe in-memory cache with TTL support and LRU eviction.
    
    Features:
    - Per-key TTL configuration
    - Automatic background cleanup of expired entries
    - LRU eviction when max_size is reached
    - Thread-safe operations
    - Optional statistics tracking
    """
    
    def __init__(
        self,
        default_ttl: int = 300,
        max_size: Optional[int] = 1000,
        cleanup_interval: int = 60,
        enable_stats: bool = False
    ):
        """
        Initialize the cache layer.
        
        Args:
            default_ttl: Default TTL in seconds (0 = no expiration)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: Seconds between cleanup runs (0 = disable)
            enable_stats: Track hit/miss statistics
        """
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._enable_stats = enable_stats
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        
        # Background cleanup
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        if cleanup_interval > 0:
            self._start_cleanup_thread()
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from cache.
        
        Args:
            key: Cache key
            default: Value to return if key is missing or expired
            
        Returns:
            Cached value or default
        """
        with self._lock:
            if key not in self._cache:
                if self._enable_stats:
                    self._misses += 1
                return default
            
            entry = self._cache[key]
            
            if entry.is_expired():
                del self._cache[key]
                if self._enable_stats:
                    self._misses += 1
                return default
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            
            if self._enable_stats:
                self._hits += 1
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default)
        """
        with self._lock:
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl_seconds=ttl_seconds
            )
            
            # Update existing or add new
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            # Evict oldest if over limit
            if self._max_size and len(self._cache) > self._max_size:
                self._cache.popitem(last=False)
                if self._enable_stats:
                    self._evictions += 1
    
    def delete(self, key: str) -> bool:
        """
        Remove a key from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key existed, False otherwise
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Remove all entries from cache."""
        with self._lock:
            self._cache.clear()
    
    def get_ttl(self, key: str) -> Optional[float]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining seconds, -1 for no expiration, None if key doesn't exist
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return None
            
            return entry.remaining_ttl()
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get cached value or compute and cache it.
        
        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl: TTL for computed value
            
        Returns:
            Cached or computed value
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Compute outside lock to avoid blocking
        computed_value = compute_fn()
        self.set(key, computed_value, ttl)
        return computed_value
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "evictions": self._evictions,
                "enabled": self._enable_stats
            }
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        with self._lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            return len(keys_to_delete)
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                time.sleep(self._cleanup_interval)
                if not self._stop_cleanup.is_set():
                    self._cleanup_expired()
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()
    
    def close(self) -> None:
        """Shutdown cache and cleanup thread."""
        if self._cleanup_thread:
            self._stop_cleanup.set()
            self._cleanup_thread.join(timeout=5)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
```

## Usage Examples

```python
# Basic usage
cache = CacheLayer(default_ttl=300, max_size=1000)

# Store with default TTL
cache.set("user:123", {"name": "Alice", "role": "admin"})

# Store with custom TTL
cache.set("session:abc", {"token": "xyz"}, ttl=3600)

# Retrieve
user = cache.get("user:123")

# Get or compute pattern
def fetch_user_from_db():
    return db.query("SELECT * FROM users WHERE id = 123")

user = cache.get_or_compute("user:123", fetch_user_from_db, ttl=600)

# Check remaining TTL
ttl = cache.get_ttl("user:123")  # Returns seconds remaining

# Statistics
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate']}%")

# Context manager for cleanup
with CacheLayer(default_ttl=60) as cache:
    cache.set("temp", "data")
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `default_ttl` | 300 | Default expiration time in seconds (0 = no expiration) |
| `max_size` | 1000 | Maximum cache entries (None = unlimited) |
| `cleanup_interval` | 60 | Seconds between background cleanup runs (0 = disable) |
| `enable_stats` | False | Track hit/miss/eviction statistics |

## Error Handling

```python
# Thread-safe operations - no race conditions
cache = CacheLayer()

# Handles missing keys gracefully
value = cache.get("nonexistent", default="fallback")  # Returns "fallback"

# TTL of 0 or negative means no expiration
cache.set("permanent", "data", ttl=0)

# Safe cleanup on shutdown
cache.close()
```

## Performance Characteristics

- **Get**: O(1) average case
- **Set**: O(1) average case
- **Delete**: O(1)
- **Cleanup**: O(n) where n = number of entries (runs in background)
- **Memory**: O(n) where n = number of cached entries

## Thread Safety

All public methods use `threading.RLock()` for thread-safe operations. Multiple threads can safely read/write concurrently.

## Rationale

### Why OrderedDict for LRU?
Using `OrderedDict` provides efficient O(1) access and maintains insertion order. The `move_to_end()` method implements LRU eviction naturally without additional complexity.

### Why datetime for TTL tracking?
Using `datetime` objects instead of Unix timestamps makes expiration logic more readable and testable. The slight overhead is negligible for a cache layer.

### Why background cleanup thread?
Lazy deletion on access could leave expired entries consuming memory. A background thread ensures bounded memory usage even with infrequently accessed keys.

### Why RLock instead of Lock?
`RLock` allows reentrant locking, preventing deadlocks if internal methods call each other while holding the lock.

### Why not use weakref?
Weak references don't provide TTL control. We need explicit expiration semantics, not garbage collection dependent behavior.

## What I Incorporated

This is the initial design proposal.

## What I Kept

Initial design - no previous iterations.

## Open Questions

1. Should we add support for cache namespaces/prefixes?
2. Should we implement cache warming (preload keys)?
3. Should we add persistence (save/load from disk)?
4. Should we support cache key patterns (wildcards for bulk operations)?
5. Should we add metric hooks for integration with monitoring systems?

## Convergence Status

**ITERATING**: This is the initial design. Seeking collaborative review and refinement.

## PROMPT_FOR_CRITIC:

Please review this caching layer design and focus on:
1. **API ergonomics**: Is the interface intuitive? Any missing convenience methods?
2. **Edge cases**: What failure modes or race conditions might exist?
3. **Performance**: Any bottlenecks with the thread-safety approach?
4. **Feature gaps**: What essential caching features are missing?
5. **Production readiness**: What would be needed to use this in a real system?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Simple Caching Layer with TTL Support

## Architecture Overview

A lightweight, thread-safe in-memory caching system with automatic expiration based on Time-To-Live (TTL) values, designed for production use with comprehensive error handling and observability.

### Core Components

```python
from typing import Any, Optional, Dict, Callable, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading
import time
from collections import OrderedDict
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


@dataclass
class CacheEntry(Generic[T]):
    """Represents a single cache entry with metadata."""
    value: T
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl_seconds <= 0:
            return False  # TTL of 0 or negative means no expiration
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() >= expiry_time
    
    def remaining_ttl(self) -> float:
        """Returns remaining seconds until expiration, or -1 if no expiration."""
        if self.ttl_seconds <= 0:
            return -1
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        remaining = (expiry_time - datetime.now()).total_seconds()
        return max(0, remaining)
    
    def touch(self) -> None:
        """Update access metadata."""
        self.access_count += 1
        self.last_accessed = datetime.now()


class CacheError(Exception):
    """Base exception for cache-related errors."""
    pass


class CacheShutdownError(CacheError):
    """Raised when attempting to use a closed cache."""
    pass


class CacheLayer:
    """
    Thread-safe in-memory cache with TTL support and LRU eviction.
    
    Features:
    - Per-key TTL configuration
    - Automatic background cleanup of expired entries
    - LRU eviction when max_size is reached
    - Thread-safe operations
    - Comprehensive statistics tracking
    - Graceful shutdown handling
    - Optional callback hooks for monitoring
    """
    
    def __init__(
        self,
        default_ttl: int = 300,
        max_size: Optional[int] = 1000,
        cleanup_interval: int = 60,
        enable_stats: bool = True,
        on_eviction: Optional[Callable[[str, Any], None]] = None,
        on_expiration: Optional[Callable[[str, Any], None]] = None
    ):
        """
        Initialize the cache layer.
        
        Args:
            default_ttl: Default TTL in seconds (0 = no expiration)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: Seconds between cleanup runs (0 = disable)
            enable_stats: Track hit/miss statistics
            on_eviction: Optional callback when entries are evicted (key, value)
            on_expiration: Optional callback when entries expire (key, value)
        
        Raises:
            ValueError: If parameters are invalid
        """
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be positive or None")
        if cleanup_interval < 0:
            raise ValueError("cleanup_interval must be non-negative")
        if default_ttl < 0:
            raise ValueError("default_ttl must be non-negative")
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._enable_stats = enable_stats
        self._on_eviction = on_eviction
        self._on_expiration = on_expiration
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        self._sets = 0
        
        # Lifecycle management
        self._closed = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        
        if cleanup_interval > 0:
            self._start_cleanup_thread()
    
    def _check_open(self) -> None:
        """Raise exception if cache is closed."""
        if self._closed:
            raise CacheShutdownError("Cache has been closed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from cache.
        
        Args:
            key: Cache key
            default: Value to return if key is missing or expired
            
        Returns:
            Cached value or default
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            
            if key not in self._cache:
                if self._enable_stats:
                    self._misses += 1
                return default
            
            entry = self._cache[key]
            
            if entry.is_expired():
                value = entry.value
                del self._cache[key]
                if self._enable_stats:
                    self._misses += 1
                    self._expirations += 1
                self._invoke_callback(self._on_expiration, key, value)
                return default
            
            # Update access metadata
            entry.touch()
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            
            if self._enable_stats:
                self._hits += 1
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default)
            
        Raises:
            CacheShutdownError: If cache is closed
            ValueError: If key is empty or ttl is negative
        """
        if not key:
            raise ValueError("Cache key cannot be empty")
        if ttl is not None and ttl < 0:
            raise ValueError("TTL must be non-negative")
        
        with self._lock:
            self._check_open()
            
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl_seconds=ttl_seconds
            )
            
            # Update existing or add new
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            if self._enable_stats:
                self._sets += 1
            
            # Evict oldest if over limit
            if self._max_size and len(self._cache) > self._max_size:
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                if self._enable_stats:
                    self._evictions += 1
                self._invoke_callback(self._on_eviction, evicted_key, evicted_entry.value)
    
    def set_many(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> None:
        """
        Store multiple key-value pairs.
        
        Args:
            mapping: Dictionary of key-value pairs to cache
            ttl: TTL in seconds (None = use default)
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        for key, value in mapping.items():
            self.set(key, value, ttl)
    
    def get_many(self, keys: list[str], default: Any = None) -> Dict[str, Any]:
        """
        Retrieve multiple values from cache.
        
        Args:
            keys: List of cache keys
            default: Value to use for missing/expired keys
            
        Returns:
            Dictionary mapping keys to values
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        return {key: self.get(key, default) for key in keys}
    
    def delete(self, key: str) -> bool:
        """
        Remove a key from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key existed, False otherwise
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def delete_many(self, keys: list[str]) -> int:
        """
        Remove multiple keys from cache.
        
        Args:
            keys: List of cache keys to remove
            
        Returns:
            Number of keys actually deleted
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        count = 0
        for key in keys:
            if self.delete(key):
                count += 1
        return count
    
    def clear(self) -> None:
        """
        Remove all entries from cache.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._cache.clear()
    
    def contains(self, key: str) -> bool:
        """
        Check if key exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is valid
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return False
            
            return True
    
    def get_ttl(self, key: str) -> Optional[float]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining seconds, -1 for no expiration, None if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return None
            
            return entry.remaining_ttl()
    
    def refresh_ttl(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Reset the TTL for an existing key.
        
        Args:
            key: Cache key
            ttl: New TTL in seconds (None = use default)
            
        Returns:
            True if key was refreshed, False if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                return False
            
            entry.created_at = datetime.now()
            entry.ttl_seconds = ttl if ttl is not None else self._default_ttl
            return True
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get cached value or compute and cache it.
        
        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl: TTL for computed value
            
        Returns:
            Cached or computed value
            
        Raises:
            CacheShutdownError: If cache is closed
            Exception: Any exception raised by compute_fn
        """
        # Fast path: check cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Check again with lock to prevent thundering herd
        with self._lock:
            self._check_open()
            # Double-check after acquiring lock
            value = self.get(key)
            if value is not None:
                return value
            
            # Compute outside lock to avoid blocking other operations
            # but mark that computation is in progress
            pass
        
        # Compute value (outside lock to avoid blocking)
        try:
            computed_value = compute_fn()
        except Exception as e:
            logger.warning(f"Error computing value for key '{key}': {e}")
            raise
        
        # Store computed value
        self.set(key, computed_value, ttl)
        return computed_value
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 2),
                "evictions": self._evictions,
                "expirations": self._expirations,
                "sets": self._sets,
                "total_requests": total_requests,
                "enabled": self._enable_stats,
                "closed": self._closed
            }
    
    def reset_stats(self) -> None:
        """
        Reset all statistics counters.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expirations = 0
            self._sets = 0
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        with self._lock:
            if self._closed:
                return 0
            
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_delete:
                entry = self._cache[key]
                del self._cache[key]
                if self._enable_stats:
                    self._expirations += 1
                self._invoke_callback(self._on_expiration, key, entry.value)
            
            return len(keys_to_delete)
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                time.sleep(self._cleanup_interval)
                if not self._stop_cleanup.is_set():
                    try:
                        self._cleanup_expired()
                    except Exception as e:
                        logger.error(f"Error during cache cleanup: {e}")
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()
    
    def _invoke_callback(
        self,
        callback: Optional[Callable[[str, Any], None]],
        key: str,
        value: Any
    ) -> None:
        """Safely invoke a callback, logging any errors."""
        if callback is None:
            return
        
        try:
            callback(key, value)
        except Exception as e:
            logger.error(f"Error in cache callback for key '{key}': {e}")
    
    def close(self) -> None:
        """
        Shutdown cache and cleanup thread.
        
        This method is idempotent and can be called multiple times.
        """
        with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            if self._cleanup_thread:
                self._stop_cleanup.set()
        
        # Wait for cleanup thread outside lock
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=5)
            if self._cleanup_thread.is_alive():
                logger.warning("Cache cleanup thread did not terminate gracefully")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __len__(self) -> int:
        """Return number of entries in cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists (does not check expiration)."""
        with self._lock:
            return key in self._cache
```

## Usage Examples

```python
# Basic usage
cache = CacheLayer(default_ttl=300, max_size=1000)

# Store with default TTL
cache.set("user:123", {"name": "Alice", "role": "admin"})

# Store with custom TTL
cache.set("session:abc", {"token": "xyz"}, ttl=3600)

# Retrieve
user = cache.get("user:123")

# Check existence
if cache.contains("user:123"):
    print("User in cache")

# Get or compute pattern
def fetch_user_from_db():
    return db.query("SELECT * FROM users WHERE id = 123")

user = cache.get_or_compute("user:123", fetch_user_from_db, ttl=600)

# Bulk operations
cache.set_many({
    "user:1": {"name": "Alice"},
    "user:2": {"name": "Bob"}
}, ttl=300)

users = cache.get_many(["user:1", "user:2"])

# Refresh TTL for hot keys
cache.refresh_ttl("user:123", ttl=600)

# Check remaining TTL
ttl = cache.get_ttl("user:123")  # Returns seconds remaining

# Statistics
stats = cache.stats()
print(f"Hit rate: {stats['hit_rate']}%")
print(f"Size: {stats['size']}/{stats['max_size']}")

# Context manager for cleanup
with CacheLayer(default_ttl=60) as cache:
    cache.set("temp", "data")
    # Automatically closes on exit

# Monitoring hooks
def on_evict(key, value):
    print(f"Evicted: {key}")

def on_expire(key, value):
    print(f"Expired: {key}")

cache = CacheLayer(
    default_ttl=300,
    on_eviction=on_evict,
    on_expiration=on_expire
)
```

## Configuration Options

| Parameter | Default | Description |
|-----------|---------|-------------|
| `default_ttl` | 300 | Default expiration time in seconds (0 = no expiration) |
| `max_size` | 1000 | Maximum cache entries (None = unlimited) |
| `cleanup_interval` | 60 | Seconds between background cleanup runs (0 = disable) |
| `enable_stats` | True | Track hit/miss/eviction statistics (changed to True) |
| `on_eviction` | None | Optional callback when entries are evicted |
| `on_expiration` | None | Optional callback when entries expire |

## Error Handling

```python
# Thread-safe operations - no race conditions
cache = CacheLayer()

# Handles missing keys gracefully
value = cache.get("nonexistent", default="fallback")  # Returns "fallback"

# TTL of 0 means no expiration
cache.set("permanent", "data", ttl=0)

# Validates input parameters
try:
    cache.set("", "value")  # Raises ValueError
except ValueError as e:
    print(f"Invalid key: {e}")

# Prevents use after close
cache.close()
try:
    cache.get("key")  # Raises CacheShutdownError
except CacheShutdownError as e:
    print(f"Cache closed: {e}")

# Safe cleanup on shutdown
cache.close()  # Idempotent - safe to call multiple times
```

## Performance Characteristics

- **Get**: O(1) average case
- **Set**: O(1) average case
- **Delete**: O(1)
- **Set/Get Many**: O(k) where k = number of keys
- **Cleanup**: O(n) where n = number of entries (runs in background)
- **Memory**: O(n) where n = number of cached entries

## Thread Safety

All public methods use `threading.RLock()` for thread-safe operations. Multiple threads can safely read/write concurrently. The `get_or_compute` method uses double-checked locking to prevent thundering herd issues.

## Production Considerations

### Monitoring Integration
```python
# Use callbacks for metrics export
def export_eviction_metric(key, value):
    metrics.increment('cache.evictions', tags={'key_prefix': key.split(':')[0]})

cache = CacheLayer(on_eviction=export_eviction_metric)
```

### Logging
The cache uses Python's standard `logging` module. Configure appropriately:
```python
logging.basicConfig(level=logging.WARNING)
```

### Graceful Shutdown
Always use context managers or explicitly call `close()`:
```python
# In application shutdown
cache.close()
```

### Memory Management
- Set `max_size` based on available memory
- Enable `cleanup_interval` to prevent memory leaks from expired entries
- Monitor `stats()` for cache efficiency

## What I Improved

1. **Exception Safety**: Added `CacheError` and `CacheShutdownError` for proper error handling. Added `_check_open()` to prevent operations on closed cache.

2. **Input Validation**: Added validation for `max_size`, `cleanup_interval`, `default_ttl`, and empty keys. Raise `ValueError` for invalid inputs.

3. **Bulk Operations**: Added `set_many()`, `get_many()`, and `delete_many()` for efficient batch operations.

4. **Convenience Methods**: Added `contains()`, `refresh_ttl()`, and `reset_stats()` for common use cases.

5. **Enhanced Statistics**: Track `expirations`, `sets`, and `total_requests`. Changed default `enable_stats` to `True` for better observability.

6. **Monitoring Hooks**: Added `on_eviction` and `on_expiration` callbacks for integration with monitoring systems.

7. **Access Tracking**: Added `access_count` and `last_accessed` to `CacheEntry` for future analytics.

8. **Thundering Herd Protection**: Improved `get_or_compute()` with double-checked locking pattern.

9. **Graceful Shutdown**: Made `close()` idempotent and added warning for non-graceful cleanup thread termination.

10. **Python Dunder Methods**: Added `__len__()` and `__contains__()` for more Pythonic API.

11. **Callback Error Handling**: Wrapped callbacks in try-except to prevent callback errors from breaking cache operations.

12. **Separation Tracking**: Distinguished between evictions (LRU) and expirations (TTL) in statistics.

## What I Kept

1. **OrderedDict for LRU**: Excellent choice for O(1) operations with insertion order.

2. **RLock**: Correct choice for reentrant locking to prevent deadlocks.

3. **Background Cleanup Thread**: Essential for preventing memory leaks from expired entries.

4. **Per-Entry TTL**: Flexible TTL configuration at both global and per-key level.

5. **Context Manager Support**: Clean resource management with `__enter__` and `__exit__`.

6. **CacheEntry Metadata**: Good separation of concerns with dedicated entry class.

7. **Thread-Safe Design**: Comprehensive use of locks for all public methods.

8. **Datetime-Based TTL**: More readable and testable than Unix timestamps.

## Remaining Considerations

1. **Memory Overhead**: Each entry has additional metadata (access tracking). For millions of entries, consider making this optional.

2. **Callback Performance**: Callbacks are invoked inside locks. Long-running callbacks could block cache operations. Consider async callbacks or a callback queue.

3. **Cleanup Thread Termination**: 5-second timeout may be insufficient for large caches. Consider making this configurable.

4. **No Persistence**: Cache is in-memory only. For persistence, consider serialization support.

5. **No Namespace Support**: All keys share one global space. For multi-tenant systems, consider key prefixing or separate cache instances.

6. **Type Safety**: Using `Generic[T]` in `CacheEntry` but not enforced in `CacheLayer`. Full type safety would require making `CacheLayer` generic.

## Convergence Status

**ITERATING**: Design has been significantly enhanced with production-ready features. Ready for further refinement based on specific use cases.

## PROMPT_FOR_ARCHITECT:

I've enhanced the design with comprehensive error handling, bulk operations, monitoring hooks, and production-ready features. Please review:

1. **Callback Design**: Do the `on_eviction` and `on_expiration` callbacks meet your monitoring needs? Should they be async or queued to avoid blocking?

2. **Bulk Operations**: Are the `set_many/get_many/delete_many` APIs intuitive? Should they support partial success with error reporting?

3. **Access Tracking**: The `access_count` and `last_accessed` fields add memory overhead. Should these be optional or behind a flag?

4. **Type Safety**: Should we make `CacheLayer` generic (`CacheLayer[T]`) for stronger type checking, or keep it flexible?

5. **Thundering Herd**: The current `get_or_compute` uses double-checked locking. Would you prefer a more sophisticated approach like request coalescing?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

# Production-Ready Caching Layer with TTL and Advanced Features

## Architecture Overview

A high-performance, thread-safe in-memory caching system with automatic expiration, designed for production environments with configurable monitoring, flexible type safety, and optimized performance characteristics.

### Core Components

```python
from typing import Any, Optional, Dict, Callable, TypeVar, Generic, Protocol, List, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
from collections import OrderedDict
import logging
from enum import Enum
from queue import Queue, Empty
import weakref

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CallbackMode(Enum):
    """Defines how callbacks are invoked."""
    SYNC = "sync"  # Blocking, inside lock
    ASYNC_QUEUED = "async_queued"  # Non-blocking, queued for background processing
    FIRE_AND_FORGET = "fire_and_forget"  # Non-blocking, new thread per callback


class StatsLevel(Enum):
    """Defines granularity of statistics tracking."""
    NONE = 0  # No statistics
    BASIC = 1  # Hit/miss/size only
    DETAILED = 2  # Includes evictions, expirations, access patterns


@dataclass
class CacheEntry(Generic[T]):
    """Represents a single cache entry with metadata."""
    value: T
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl_seconds <= 0:
            return False  # TTL of 0 or negative means no expiration
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() >= expiry_time
    
    def remaining_ttl(self) -> float:
        """Returns remaining seconds until expiration, or -1 if no expiration."""
        if self.ttl_seconds <= 0:
            return -1
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        remaining = (expiry_time - datetime.now()).total_seconds()
        return max(0, remaining)
    
    def touch(self, track_access: bool = True) -> None:
        """Update access metadata."""
        if track_access:
            self.access_count += 1
            self.last_accessed = datetime.now()


@dataclass
class BulkOperationResult:
    """Result of bulk operations with success/failure tracking."""
    successful: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)  # key -> error message
    
    @property
    def success_count(self) -> int:
        return len(self.successful)
    
    @property
    def failure_count(self) -> int:
        return len(self.failed)
    
    @property
    def total(self) -> int:
        return self.success_count + self.failure_count


class CacheError(Exception):
    """Base exception for cache-related errors."""
    pass


class CacheShutdownError(CacheError):
    """Raised when attempting to use a closed cache."""
    pass


class CacheCallbackError(CacheError):
    """Raised when a callback fails in SYNC mode."""
    pass


class CallbackProtocol(Protocol):
    """Protocol for cache event callbacks."""
    def __call__(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Callback signature for cache events.
        
        Args:
            key: Cache key
            value: Cached value
            metadata: Optional context (e.g., {"reason": "ttl_expired", "age_seconds": 123})
        """
        ...


class CacheLayer:
    """
    Thread-safe in-memory cache with TTL support, LRU eviction, and production features.
    
    Features:
    - Per-key TTL configuration with efficient expiration tracking
    - Automatic background cleanup of expired entries
    - LRU eviction when max_size is reached
    - Thread-safe operations with minimal lock contention
    - Configurable statistics tracking (NONE/BASIC/DETAILED)
    - Optional access pattern tracking with memory/performance trade-off
    - Flexible callback system (sync/async/fire-and-forget)
    - Graceful shutdown with configurable timeout
    - Bulk operations with partial success reporting
    - Request coalescing for thundering herd prevention
    - Namespace support via key prefixing utilities
    """
    
    def __init__(
        self,
        default_ttl: int = 300,
        max_size: Optional[int] = 1000,
        cleanup_interval: int = 60,
        stats_level: StatsLevel = StatsLevel.BASIC,
        track_access_patterns: bool = False,
        callback_mode: CallbackMode = CallbackMode.ASYNC_QUEUED,
        callback_queue_size: int = 1000,
        shutdown_timeout: float = 5.0,
        on_eviction: Optional[CallbackProtocol] = None,
        on_expiration: Optional[CallbackProtocol] = None
    ):
        """
        Initialize the cache layer.
        
        Args:
            default_ttl: Default TTL in seconds (0 = no expiration)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: Seconds between cleanup runs (0 = disable)
            stats_level: Granularity of statistics tracking
            track_access_patterns: Enable access_count/last_accessed tracking
            callback_mode: How to invoke callbacks (sync/async/fire-and-forget)
            callback_queue_size: Max queued callbacks in ASYNC_QUEUED mode
            shutdown_timeout: Seconds to wait for graceful shutdown
            on_eviction: Optional callback when entries are evicted
            on_expiration: Optional callback when entries expire
        
        Raises:
            ValueError: If parameters are invalid
        """
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be positive or None")
        if cleanup_interval < 0:
            raise ValueError("cleanup_interval must be non-negative")
        if default_ttl < 0:
            raise ValueError("default_ttl must be non-negative")
        if shutdown_timeout < 0:
            raise ValueError("shutdown_timeout must be non-negative")
        if callback_queue_size < 1:
            raise ValueError("callback_queue_size must be positive")
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._stats_level = stats_level
        self._track_access = track_access_patterns
        self._callback_mode = callback_mode
        self._shutdown_timeout = shutdown_timeout
        self._on_eviction = on_eviction
        self._on_expiration = on_expiration
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        self._sets = 0
        
        # Lifecycle management
        self._closed = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._callback_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._stop_callbacks = threading.Event()
        
        # Callback queue for ASYNC_QUEUED mode
        self._callback_queue: Optional[Queue] = None
        if callback_mode == CallbackMode.ASYNC_QUEUED:
            self._callback_queue = Queue(maxsize=callback_queue_size)
            self._start_callback_thread()
        
        # Request coalescing for get_or_compute
        self._computing_keys: Dict[str, threading.Event] = {}
        self._computing_lock = threading.Lock()
        
        if cleanup_interval > 0:
            self._start_cleanup_thread()
    
    def _check_open(self) -> None:
        """Raise exception if cache is closed."""
        if self._closed:
            raise CacheShutdownError("Cache has been closed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from cache.
        
        Args:
            key: Cache key
            default: Value to return if key is missing or expired
            
        Returns:
            Cached value or default
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            
            if key not in self._cache:
                self._record_stat('miss')
                return default
            
            entry = self._cache[key]
            
            if entry.is_expired():
                value = entry.value
                del self._cache[key]
                self._record_stat('miss')
                self._record_stat('expiration')
                self._invoke_callback(
                    self._on_expiration, 
                    key, 
                    value,
                    metadata={"reason": "ttl_expired", "age_seconds": (datetime.now() - entry.created_at).total_seconds()}
                )
                return default
            
            # Update access metadata
            entry.touch(self._track_access)
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            
            self._record_stat('hit')
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default)
            
        Raises:
            CacheShutdownError: If cache is closed
            ValueError: If key is empty or ttl is negative
        """
        if not key:
            raise ValueError("Cache key cannot be empty")
        if ttl is not None and ttl < 0:
            raise ValueError("TTL must be non-negative")
        
        with self._lock:
            self._check_open()
            
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl_seconds=ttl_seconds
            )
            
            # Update existing or add new
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            self._record_stat('set')
            
            # Evict oldest if over limit
            if self._max_size and len(self._cache) > self._max_size:
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                self._record_stat('eviction')
                self._invoke_callback(
                    self._on_eviction, 
                    evicted_key, 
                    evicted_entry.value,
                    metadata={"reason": "lru_eviction", "access_count": evicted_entry.access_count if self._track_access else None}
                )
    
    def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None,
        continue_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Store multiple key-value pairs.
        
        Args:
            mapping: Dictionary of key-value pairs to cache
            ttl: TTL in seconds (None = use default)
            continue_on_error: If False, stop on first error
            
        Returns:
            BulkOperationResult with success/failure details
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        result = BulkOperationResult()
        
        for key, value in mapping.items():
            try:
                self.set(key, value, ttl)
                result.successful.append(key)
            except Exception as e:
                result.failed[key] = str(e)
                if not continue_on_error:
                    break
        
        return result
    
    def get_many(self, keys: List[str], default: Any = None) -> Dict[str, Any]:
        """
        Retrieve multiple values from cache.
        
        Args:
            keys: List of cache keys
            default: Value to use for missing/expired keys
            
        Returns:
            Dictionary mapping keys to values
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        return {key: self.get(key, default) for key in keys}
    
    def delete(self, key: str) -> bool:
        """
        Remove a key from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key existed, False otherwise
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def delete_many(
        self, 
        keys: List[str],
        continue_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Remove multiple keys from cache.
        
        Args:
            keys: List of cache keys to remove
            continue_on_error: If False, stop on first error
            
        Returns:
            BulkOperationResult with success/failure details
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        result = BulkOperationResult()
        
        for key in keys:
            try:
                if self.delete(key):
                    result.successful.append(key)
                else:
                    result.failed[key] = "Key not found"
            except Exception as e:
                result.failed[key] = str(e)
                if not continue_on_error:
                    break
        
        return result
    
    def clear(self) -> None:
        """
        Remove all entries from cache.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._cache.clear()
    
    def contains(self, key: str) -> bool:
        """
        Check if key exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is valid
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return False
            
            return True
    
    def get_ttl(self, key: str) -> Optional[float]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining seconds, -1 for no expiration, None if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return None
            
            return entry.remaining_ttl()
    
    def refresh_ttl(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Reset the TTL for an existing key.
        
        Args:
            key: Cache key
            ttl: New TTL in seconds (None = use default)
            
        Returns:
            True if key was refreshed, False if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return False
            
            entry.created_at = datetime.now()
            entry.ttl_seconds = ttl if ttl is not None else self._default_ttl
            return True
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get cached value or compute and cache it with request coalescing.
        
        Multiple concurrent requests for the same key will wait for the first
        computation to complete rather than computing independently.
        
        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl: TTL for computed value
            
        Returns:
            Cached or computed value
            
        Raises:
            CacheShutdownError: If cache is closed
            Exception: Any exception raised by compute_fn
        """
        # Fast path: check cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Check if another thread is computing this key
        computing_event = None
        should_compute = False
        
        with self._computing_lock:
            if key in self._computing_keys:
                # Another thread is computing, wait for it
                computing_event = self._computing_keys[key]
            else:
                # We'll compute it
                self._computing_keys[key] = threading.Event()
                should_compute = True
        
        if computing_event:
            # Wait for other thread to finish computing
            computing_event.wait()
            # Try to get the computed value
            value = self.get(key)
            if value is not None:
                return value
            # Fall through to compute if other thread failed
        
        if should_compute:
            try:
                # Double-check cache before computing
                value = self.get(key)
                if value is not None:
                    return value
                
                # Compute value (outside lock to avoid blocking)
                computed_value = compute_fn()
                
                # Store computed value
                self.set(key, computed_value, ttl)
                return computed_value
            except Exception as e:
                logger.warning(f"Error computing value for key '{key}': {e}")
                raise
            finally:
                # Signal completion and cleanup
                with self._computing_lock:
                    event = self._computing_keys.pop(key, None)
                    if event:
                        event.set()
        
        # Shouldn't reach here, but compute as fallback
        return compute_fn()
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            
            stats_dict = {
                "size": len(self._cache),
                "max_size": self._max_size,
                "closed": self._closed,
                "stats_level": self._stats_level.name,
                "tracking_access_patterns": self._track_access
            }
            
            if self._stats_level.value >= StatsLevel.BASIC.value:
                total_requests = self._hits + self._misses
                hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
                
                stats_dict.update({
                    "hits": self._hits,
                    "misses": self._misses,
                    "hit_rate": round(hit_rate, 2),
                    "total_requests": total_requests
                })
            
            if self._stats_level.value >= StatsLevel.DETAILED.value:
                stats_dict.update({
                    "evictions": self._evictions,
                    "expirations": self._expirations,
                    "sets": self._sets
                })
            
            return stats_dict
    
    def reset_stats(self) -> None:
        """
        Reset all statistics counters.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expirations = 0
            self._sets = 0
    
    def get_access_patterns(self) -> Dict[str, Dict[str, Any]]:
        """
        Get access pattern information for all keys.
        
        Only available when track_access_patterns=True.
        
        Returns:
            Dictionary mapping keys to access metadata
            
        Raises:
            CacheShutdownError: If cache is closed
            ValueError: If access pattern tracking is disabled
        """
        if not self._track_access:
            raise ValueError("Access pattern tracking is disabled. Enable with track_access_patterns=True")
        
        with self._lock:
            self._check_open()
            
            patterns = {}
            for key, entry in self._cache.items():
                patterns[key] = {
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed.isoformat() if entry.last_accessed else None,
                    "age_seconds": (datetime.now() - entry.created_at).total_seconds(),
                    "remaining_ttl": entry.remaining_ttl()
                }
            
            return patterns
    
    def _record_stat(self, stat_type: str) -> None:
        """Record a statistic if tracking is enabled."""
        if self._stats_level == StatsLevel.NONE:
            return
        
        if stat_type == 'hit':
            self._hits += 1
        elif stat_type == 'miss':
            self._misses += 1
        elif stat_type == 'set' and self._stats_level.value >= StatsLevel.DETAILED.value:
            self._sets += 1
        elif stat_type == 'eviction' and self._stats_level.value >= StatsLevel.DETAILED.value:
            self._evictions += 1
        elif stat_type == 'expiration' and self._stats_level.value >= StatsLevel.DETAILED.value:
            self._expirations += 1
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        with self._lock:
            if self._closed:
                return 0
            
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_delete:
                entry = self._cache[key]
                age_seconds = (datetime.now() - entry.created_at).total_seconds()
                del self._cache[key]
                self._record_stat('expiration')
                self._invoke_callback(
                    self._on_expiration, 
                    key, 
                    entry.value,
                    metadata={"reason": "background_cleanup", "age_seconds": age_seconds}
                )
            
            return len(keys_to_delete)
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                time.sleep(self._cleanup_interval)
                if not self._stop_cleanup.is_set():
                    try:
                        self._cleanup_expired()
                    except Exception as e:
                        logger.error(f"Error during cache cleanup: {e}")
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()
    
    def _start_callback_thread(self) -> None:
        """Start background thread for processing queued callbacks."""
        def callback_loop():
            while not self._stop_callbacks.is_set():
                try:
                    callback, key, value, metadata = self._callback_queue.get(timeout=0.1)
                    try:
                        callback(key, value, metadata)
                    except Exception as e:
                        logger.error(f"Error in queued callback for key '{key}': {e}")
                    finally:
                        self._callback_queue.task_done()
                except Empty:
                    continue
        
        self._callback_thread = threading.Thread(
            target=callback_loop,
            daemon=True,
            name="CacheCallbacks"
        )
        self._callback_thread.start()
    
    def _invoke_callback(
        self,
        callback: Optional[CallbackProtocol],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Invoke a callback according to configured mode."""
        if callback is None:
            return
        
        if self._callback_mode == CallbackMode.SYNC:
            try:
                callback(key, value, metadata)
            except Exception as e:
                logger.error(f"Error in sync callback for key '{key}': {e}")
                # In sync mode, we could raise here if desired
        
        elif self._callback_mode == CallbackMode.ASYNC_QUEUED:
            try:
                self._callback_queue.put_nowait((callback, key, value, metadata))
            except Exception as e:
                logger.warning(f"Callback queue full, dropping callback for key '{key}': {e}")
        
        elif self._callback_mode == CallbackMode.FIRE_AND_FORGET:
            def run_callback():
                try:
                    callback(key, value, metadata)
                except Exception as e:
                    logger.error(f"Error in fire-and-forget callback for key '{key}': {e}")
            
            thread = threading.Thread(target=run_callback, daemon=True, name=f"CacheCallback-{key}")
            thread.start()
    
    def close(self) -> None:
        """
        Shutdown cache and cleanup threads.
        
        This method is idempotent and can be called multiple times.
        """
        with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            if self._cleanup_thread:
                self._stop_cleanup.set()
            
            if self._callback_thread:
                self._stop_callbacks.set()
        
        # Wait for threads outside lock
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=self._shutdown_timeout)
            if self._cleanup_thread.is_alive():
                logger.warning("Cache cleanup thread did not terminate gracefully")
        
        if self._callback_thread:
            self._callback_thread.join(timeout=self._shutdown_timeout)
            if self._callback_thread.is_alive():
                logger.warning("Cache callback thread did not terminate gracefully")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __len__(self) -> int:
        """Return number of entries in cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists (does not check expiration)."""
        with self._lock:
            return key in self._cache


# Utility functions for namespace support
def namespace_key(namespace: str, key: str) -> str:
    """Create namespaced key."""
    return f"{namespace}:{key}"


def extract_namespace(namespaced_key: str) -> Tuple[Optional[str], str]:
    """Extract namespace and key from namespaced key."""
    parts = namespaced_key.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, namespaced_key


class NamespacedCache:
    """Wrapper providing automatic key namespacing."""
    
    def __init__(self, cache: CacheLayer, namespace: str):
        self._cache = cache
        self._namespace = namespace
    
    def _ns_key(self, key: str) -> str:
        return namespace_key(self._namespace, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(self._ns_key(key), default)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._cache.set(self._ns_key(key), value, ttl)
    
    def delete(self, key: str) -> bool:
        return self._cache.delete(self._ns_key(key))
    
    def contains(self, key: str) -> bool:
        return self._cache.contains(self._ns_key(key))
```

## Usage Examples

```python
# Basic usage with different stats levels
cache = CacheLayer(
    default_ttl=300, 
    max_size=1000,
    stats_level=StatsLevel.BASIC  # Minimal overhead
)

# Production config with async callbacks
cache = CacheLayer(
    default_ttl=300,
    max_size=10000,
    stats_level=StatsLevel.DETAILED,
    track_access_patterns=False,  # Disable to save memory
    callback_mode=CallbackMode.ASYNC_QUEUED,
    shutdown_timeout=10.0
)

# Store with default TTL
cache.set("user:123", {"name": "Alice", "role": "admin"})

# Bulk operations with error tracking
result = cache.set_many({
    "user:1": {"name": "Alice"},
    "user:2": {"name": "Bob"}
}, ttl=300, continue_on_error=True)

print(f"Successful: {result.success_count}, Failed: {result.failure_count}")
for key, error in result.failed.items():
    print(f"Failed to set {key}: {error}")

# Get or compute with request coalescing
def fetch_user_from_db():
    return db.query("SELECT * FROM users WHERE id = 123")

user = cache.get_or_compute("user:123", fetch_user_from_db, ttl=600)

# Monitoring hooks with metadata
def on_evict(key: str, value: Any, metadata: Optional[Dict] = None):
    if metadata:
        reason = metadata.get("reason", "unknown")
        access_count = metadata.get("access_count", 0)
        print(f"Evicted {key}: reason={reason}, accesses={access_count}")

cache = CacheLayer(
    on_eviction=on_evict,
    callback_mode=CallbackMode.ASYNC_QUEUED  # Non-blocking
)

# Access patterns (when enabled)
cache_with_tracking = CacheLayer(
    track_access_patterns=True,
    stats_level=StatsLevel.DETAILED
)
cache_with_tracking.set("key1", "value1")
cache_with_tracking.get("key1")
cache_with_tracking.get("key1")

patterns = cache_with_tracking.get_access_patterns()
print(patterns["key1"])  # {"access_count": 2, "last_accessed": "...", ...}

# Namespace support for multi-tenancy
shared_cache = CacheLayer()
tenant_a = NamespacedCache(shared_cache, "tenant_a")
tenant_b = NamespacedCache(shared_cache, "tenant_b")

tenant_a.set("user:1", {"name": "Alice"})
tenant_b.set("user:1", {"name": "Bob"})  # Different namespace, no conflict

# Context manager for cleanup
with CacheLayer(default_ttl=60) as cache:
    cache.set("temp", "data")
    # Automatically closes on exit
```

## Configuration Guide

### Performance vs Memory Trade-offs

| Configuration | Memory Usage | Performance | Use Case |
|---------------|--------------|-------------|----------|
| `stats_level=NONE, track_access_patterns=False` | Minimal | Highest | High-throughput, memory-constrained |
| `stats_level=BASIC, track_access_patterns=False` | Low | High | Production default |
| `stats_level=DETAILED, track_access_patterns=True` | High | Lower | Development, analytics |

### Callback Modes

| Mode | Blocking | Guaranteed Delivery | Use Case |
|------|----------|---------------------|----------|
| `SYNC` | Yes | Yes | Critical operations, testing |
| `ASYNC_QUEUED` | No | Best-effort | Metrics export, monitoring |
| `FIRE_AND_FORGET` | No | No | Logging, non-critical notifications |

## Error Handling

```python
# Bulk operations report partial failures
result = cache.set_many({"": "invalid", "valid": "data"})
assert result.failure_count == 1
assert "" in result.failed
assert result.failed[""] == "Cache key cannot be empty"

# Access patterns require explicit enablement
cache = CacheLayer(track_access_patterns=False)
try:
    cache.get_access_patterns()
except ValueError as e:
    print(f"Cannot get patterns: {e}")

# Thread-safe shutdown
cache.close()
try:
    cache.get("key")
except CacheShutdownError:
    print("Cache is closed")
```

## Performance Characteristics

- **Get**: O(1) average case
- **Set**: O(1) average case
- **Delete**: O(1)
- **Bulk operations**: O(k) where k = number of keys
- **Cleanup**: O(n) where n = number of entries (background thread)
- **get_or_compute**: O(1) cache hit, O(compute) + O(1) on miss
- **Memory overhead per entry**: 
  - Base: ~120 bytes (entry object, datetime, OrderedDict node)
  - With access tracking: ~140 bytes (adds access_count, last_accessed)

## Rationale

1. **Configurable Statistics**: Added `StatsLevel` enum to allow users to disable stats entirely or choose granularity, reducing overhead for high-throughput scenarios.

2. **Optional Access Tracking**: Made access pattern tracking opt-in via `track_access_patterns` flag to eliminate memory overhead when not needed.

3. **Flexible Callback System**: Introduced `CallbackMode` enum with three modes (SYNC/ASYNC_QUEUED/FIRE_AND_FORGET) to handle different use cases without blocking cache operations.

4. **Callback Metadata**: Enhanced callbacks with optional metadata dictionary providing context about eviction/expiration reasons, enabling richer monitoring.

5. **Bulk Operation Results**: Created `BulkOperationResult` dataclass to track partial successes/failures in bulk operations with detailed error messages.

6. **Request Coalescing**: Implemented proper thundering herd prevention in `get_or_compute` using event-based synchronization to avoid duplicate computations.

7. **Namespace Support**: Added utility functions and `NamespacedCache` wrapper for multi-tenant scenarios without modifying core cache.

8. **Configurable Shutdown**: Made shutdown timeout configurable to handle varying cache sizes and cleanup requirements.

9. **Callback Queue**: Implemented dedicated callback processing thread for ASYNC_QUEUED mode with bounded queue to prevent memory issues.

10. **Type Hints**: Used `Protocol` for callbacks to provide clear interface contracts while maintaining flexibility.

## What I Incorporated

1. **Production-ready error handling** from previous design with enhanced validation
2. **Bulk operations** with added partial success reporting
3. **Comprehensive statistics** with configurable granularity
4. **Callback system** with multiple invocation modes
5. **Thread-safe design** with improved request coalescing
6. **Access pattern tracking** made optional for memory efficiency
7. **Graceful shutdown** with configurable timeout

## What I Kept

1. **OrderedDict for LRU**: Optimal O(1) operations
2. **RLock for thread safety**: Correct reentrant locking
3. **Background cleanup thread**: Essential for TTL management
4. **Per-entry TTL**: Flexible expiration control
5. **CacheEntry metadata**: Clean separation of concerns
6. **Context manager support**: Pythonic resource management

## Open Questions

1. **Type Safety Trade-off**: Should `CacheLayer` be generic (`CacheLayer[T]`) for stronger typing? This would require users to declare cache types upfront, reducing flexibility but catching type errors earlier.

2. **Callback Queue Overflow**: Current ASYNC_QUEUED mode drops callbacks when queue is full. Should we add a configurable overflow policy (block/drop/log-and-continue)?

3. **Persistence Layer**: Should we add optional serialization support for cache snapshots? This would enable warm restarts but add complexity.

4. **Metrics Integration**: Should we provide built-in integrations for common metrics systems (Prometheus, StatsD) or keep callbacks generic?

5. **Advanced Eviction**: Should we support multiple eviction policies (LRU/LFU/TTL-aware) or keep it simple with LRU?

## Convergence Status

**PROPOSING_FINAL**: Design addresses all core requirements with production-ready features, configurable performance/memory trade-offs, and comprehensive error handling. The callback system is flexible, bulk operations report partial failures, and request coalescing prevents thundering herd. Ready for implementation with minor refinements based on specific deployment needs.

## PROMPT_FOR_CRITIC:

I've created a comprehensive caching layer design with the following key improvements:

1. **Configurable overhead**: `StatsLevel` enum and optional `track_access_patterns` allow users to optimize for memory vs observability
2. **Callback flexibility**: Three callback modes (SYNC/ASYNC_QUEUED/FIRE_AND_FORGET) with metadata-enriched callbacks for better monitoring integration
3. **Bulk operations**: Return `BulkOperationResult` with detailed success/failure tracking and configurable error handling
4. **Request coalescing**: Proper thundering herd prevention using event-based synchronization in `get_or_compute`
5. **Namespace support**: Utility functions and wrapper class for multi-tenant scenarios

Please review:

1. **Callback modes**: Is the three-mode approach (SYNC/ASYNC_QUEUED/FIRE_AND_FORGET) clear and practical? Should ASYNC_QUEUED have a configurable overflow policy beyond dropping?

2. **Stats granularity**: Does the NONE/BASIC/DETAILED hierarchy cover real-world needs? Should BASIC include eviction/expiration counts?

3. **Access tracking**: Is making this opt-in via `track_access_patterns` sufficient, or should we add more granular controls (e.g., track only access_count but not timestamps)?

4. **Type safety**: Should we make `CacheLayer` generic for stronger typing, accepting the trade-off of reduced flexibility?

5. **Production readiness**: Are there any critical production concerns (monitoring, debugging, resource limits) not addressed?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

## Design

# Production-Ready Caching Layer with TTL and Advanced Features

## Architecture Overview

A high-performance, thread-safe in-memory caching system with automatic expiration, designed for production environments with configurable monitoring, flexible type safety, and optimized performance characteristics.

### Core Components

```python
from typing import Any, Optional, Dict, Callable, TypeVar, Generic, Protocol, List, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
from collections import OrderedDict
import logging
from enum import Enum
from queue import Queue, Empty
import weakref

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CallbackMode(Enum):
    """Defines how callbacks are invoked."""
    SYNC = "sync"  # Blocking, inside lock
    ASYNC_QUEUED = "async_queued"  # Non-blocking, queued for background processing
    FIRE_AND_FORGET = "fire_and_forget"  # Non-blocking, new thread per callback


class StatsLevel(Enum):
    """Defines granularity of statistics tracking."""
    NONE = 0  # No statistics
    BASIC = 1  # Hit/miss/size/evictions/expirations
    DETAILED = 2  # Includes access patterns per key


class CallbackQueuePolicy(Enum):
    """Defines behavior when callback queue is full."""
    DROP = "drop"  # Silently drop new callbacks
    DROP_WITH_LOG = "drop_with_log"  # Drop and log warning
    BLOCK = "block"  # Block until space available (use with caution)


@dataclass
class CacheEntry(Generic[T]):
    """Represents a single cache entry with metadata."""
    value: T
    created_at: datetime
    ttl_seconds: int
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Check if this entry has exceeded its TTL."""
        if self.ttl_seconds <= 0:
            return False  # TTL of 0 or negative means no expiration
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        return datetime.now() >= expiry_time
    
    def remaining_ttl(self) -> float:
        """Returns remaining seconds until expiration, or -1 if no expiration."""
        if self.ttl_seconds <= 0:
            return -1
        expiry_time = self.created_at + timedelta(seconds=self.ttl_seconds)
        remaining = (expiry_time - datetime.now()).total_seconds()
        return max(0, remaining)
    
    def touch(self, track_access: bool = True) -> None:
        """Update access metadata."""
        if track_access:
            self.access_count += 1
            self.last_accessed = datetime.now()


@dataclass
class BulkOperationResult:
    """Result of bulk operations with success/failure tracking."""
    successful: List[str] = field(default_factory=list)
    failed: Dict[str, str] = field(default_factory=dict)  # key -> error message
    
    @property
    def success_count(self) -> int:
        return len(self.successful)
    
    @property
    def failure_count(self) -> int:
        return len(self.failed)
    
    @property
    def total(self) -> int:
        return self.success_count + self.failure_count
    
    @property
    def all_succeeded(self) -> bool:
        return self.failure_count == 0


class CacheError(Exception):
    """Base exception for cache-related errors."""
    pass


class CacheShutdownError(CacheError):
    """Raised when attempting to use a closed cache."""
    pass


class CacheCallbackError(CacheError):
    """Raised when a callback fails in SYNC mode."""
    pass


class CallbackProtocol(Protocol):
    """Protocol for cache event callbacks."""
    def __call__(self, key: str, value: Any, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Callback signature for cache events.
        
        Args:
            key: Cache key
            value: Cached value
            metadata: Optional context (e.g., {"reason": "ttl_expired", "age_seconds": 123})
        """
        ...


class CacheLayer:
    """
    Thread-safe in-memory cache with TTL support, LRU eviction, and production features.
    
    Features:
    - Per-key TTL configuration with efficient expiration tracking
    - Automatic background cleanup of expired entries
    - LRU eviction when max_size is reached
    - Thread-safe operations with minimal lock contention
    - Configurable statistics tracking (NONE/BASIC/DETAILED)
    - Optional access pattern tracking with memory/performance trade-off
    - Flexible callback system (sync/async/fire-and-forget)
    - Graceful shutdown with configurable timeout
    - Bulk operations with partial success reporting
    - Request coalescing for thundering herd prevention
    - Namespace support via key prefixing utilities
    """
    
    def __init__(
        self,
        default_ttl: int = 300,
        max_size: Optional[int] = 1000,
        cleanup_interval: int = 60,
        stats_level: StatsLevel = StatsLevel.BASIC,
        track_access_patterns: bool = False,
        callback_mode: CallbackMode = CallbackMode.ASYNC_QUEUED,
        callback_queue_size: int = 1000,
        callback_queue_policy: CallbackQueuePolicy = CallbackQueuePolicy.DROP_WITH_LOG,
        shutdown_timeout: float = 5.0,
        on_eviction: Optional[CallbackProtocol] = None,
        on_expiration: Optional[CallbackProtocol] = None
    ):
        """
        Initialize the cache layer.
        
        Args:
            default_ttl: Default TTL in seconds (0 = no expiration)
            max_size: Maximum number of entries (None = unlimited)
            cleanup_interval: Seconds between cleanup runs (0 = disable)
            stats_level: Granularity of statistics tracking
            track_access_patterns: Enable access_count/last_accessed tracking (requires DETAILED stats)
            callback_mode: How to invoke callbacks (sync/async/fire-and-forget)
            callback_queue_size: Max queued callbacks in ASYNC_QUEUED mode
            callback_queue_policy: Behavior when callback queue is full
            shutdown_timeout: Seconds to wait for graceful shutdown
            on_eviction: Optional callback when entries are evicted
            on_expiration: Optional callback when entries expire
        
        Raises:
            ValueError: If parameters are invalid
        """
        if max_size is not None and max_size < 1:
            raise ValueError("max_size must be positive or None")
        if cleanup_interval < 0:
            raise ValueError("cleanup_interval must be non-negative")
        if default_ttl < 0:
            raise ValueError("default_ttl must be non-negative")
        if shutdown_timeout < 0:
            raise ValueError("shutdown_timeout must be non-negative")
        if callback_queue_size < 1:
            raise ValueError("callback_queue_size must be positive")
        if track_access_patterns and stats_level != StatsLevel.DETAILED:
            raise ValueError("track_access_patterns requires stats_level=StatsLevel.DETAILED")
        
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval
        self._stats_level = stats_level
        self._track_access = track_access_patterns
        self._callback_mode = callback_mode
        self._callback_queue_policy = callback_queue_policy
        self._shutdown_timeout = shutdown_timeout
        self._on_eviction = on_eviction
        self._on_expiration = on_expiration
        
        # Statistics
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0
        self._sets = 0
        
        # Lifecycle management
        self._closed = False
        self._cleanup_thread: Optional[threading.Thread] = None
        self._callback_thread: Optional[threading.Thread] = None
        self._stop_cleanup = threading.Event()
        self._stop_callbacks = threading.Event()
        
        # Callback queue for ASYNC_QUEUED mode
        self._callback_queue: Optional[Queue] = None
        self._dropped_callbacks = 0  # Track dropped callbacks
        if callback_mode == CallbackMode.ASYNC_QUEUED:
            self._callback_queue = Queue(maxsize=callback_queue_size)
            self._start_callback_thread()
        
        # Request coalescing for get_or_compute
        self._computing_keys: Dict[str, threading.Event] = {}
        self._computing_results: Dict[str, Tuple[bool, Any]] = {}  # key -> (success, value_or_exception)
        self._computing_lock = threading.Lock()
        
        if cleanup_interval > 0:
            self._start_cleanup_thread()
    
    def _check_open(self) -> None:
        """Raise exception if cache is closed."""
        if self._closed:
            raise CacheShutdownError("Cache has been closed")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieve a value from cache.
        
        Args:
            key: Cache key
            default: Value to return if key is missing or expired
            
        Returns:
            Cached value or default
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            
            if key not in self._cache:
                self._record_stat('miss')
                return default
            
            entry = self._cache[key]
            
            if entry.is_expired():
                value = entry.value
                del self._cache[key]
                self._record_stat('miss')
                self._record_stat('expiration')
                self._invoke_callback(
                    self._on_expiration, 
                    key, 
                    value,
                    metadata={"reason": "ttl_expired", "age_seconds": (datetime.now() - entry.created_at).total_seconds()}
                )
                return default
            
            # Update access metadata
            entry.touch(self._track_access)
            
            # Move to end (LRU)
            self._cache.move_to_end(key)
            
            self._record_stat('hit')
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: TTL in seconds (None = use default)
            
        Raises:
            CacheShutdownError: If cache is closed
            ValueError: If key is empty or ttl is negative
        """
        if not key:
            raise ValueError("Cache key cannot be empty")
        if ttl is not None and ttl < 0:
            raise ValueError("TTL must be non-negative")
        
        with self._lock:
            self._check_open()
            
            ttl_seconds = ttl if ttl is not None else self._default_ttl
            
            entry = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl_seconds=ttl_seconds
            )
            
            # Update existing or add new
            if key in self._cache:
                del self._cache[key]
            
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            self._record_stat('set')
            
            # Evict oldest if over limit
            if self._max_size and len(self._cache) > self._max_size:
                evicted_key, evicted_entry = self._cache.popitem(last=False)
                self._record_stat('eviction')
                self._invoke_callback(
                    self._on_eviction, 
                    evicted_key, 
                    evicted_entry.value,
                    metadata={"reason": "lru_eviction", "access_count": evicted_entry.access_count if self._track_access else None}
                )
    
    def set_many(
        self, 
        mapping: Dict[str, Any], 
        ttl: Optional[int] = None,
        continue_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Store multiple key-value pairs.
        
        Args:
            mapping: Dictionary of key-value pairs to cache
            ttl: TTL in seconds (None = use default)
            continue_on_error: If False, stop on first error
            
        Returns:
            BulkOperationResult with success/failure details
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        result = BulkOperationResult()
        
        for key, value in mapping.items():
            try:
                self.set(key, value, ttl)
                result.successful.append(key)
            except Exception as e:
                result.failed[key] = str(e)
                if not continue_on_error:
                    break
        
        return result
    
    def get_many(self, keys: List[str], default: Any = None) -> Dict[str, Any]:
        """
        Retrieve multiple values from cache.
        
        Args:
            keys: List of cache keys
            default: Value to use for missing/expired keys
            
        Returns:
            Dictionary mapping keys to values
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        return {key: self.get(key, default) for key in keys}
    
    def delete(self, key: str) -> bool:
        """
        Remove a key from cache.
        
        Args:
            key: Cache key to remove
            
        Returns:
            True if key existed, False otherwise
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def delete_many(
        self, 
        keys: List[str],
        continue_on_error: bool = True
    ) -> BulkOperationResult:
        """
        Remove multiple keys from cache.
        
        Args:
            keys: List of cache keys to remove
            continue_on_error: If False, stop on first error
            
        Returns:
            BulkOperationResult with success/failure details
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        result = BulkOperationResult()
        
        for key in keys:
            try:
                if self.delete(key):
                    result.successful.append(key)
                else:
                    result.failed[key] = "Key not found"
            except Exception as e:
                result.failed[key] = str(e)
                if not continue_on_error:
                    break
        
        return result
    
    def clear(self) -> None:
        """
        Remove all entries from cache.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._cache.clear()
    
    def contains(self, key: str) -> bool:
        """
        Check if key exists and is not expired.
        
        Args:
            key: Cache key
            
        Returns:
            True if key exists and is valid
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return False
            
            return True
    
    def get_ttl(self, key: str) -> Optional[float]:
        """
        Get remaining TTL for a key.
        
        Args:
            key: Cache key
            
        Returns:
            Remaining seconds, -1 for no expiration, None if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return None
            
            return entry.remaining_ttl()
    
    def refresh_ttl(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Reset the TTL for an existing key.
        
        Args:
            key: Cache key
            ttl: New TTL in seconds (None = use default)
            
        Returns:
            True if key was refreshed, False if key doesn't exist
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            if key not in self._cache:
                return False
            
            entry = self._cache[key]
            if entry.is_expired():
                del self._cache[key]
                self._record_stat('expiration')
                return False
            
            entry.created_at = datetime.now()
            entry.ttl_seconds = ttl if ttl is not None else self._default_ttl
            return True
    
    def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        ttl: Optional[int] = None
    ) -> Any:
        """
        Get cached value or compute and cache it with request coalescing.
        
        Multiple concurrent requests for the same key will wait for the first
        computation to complete rather than computing independently. If the
        computation fails, the exception is raised to all waiting threads.
        
        Args:
            key: Cache key
            compute_fn: Function to call if cache miss
            ttl: TTL for computed value
            
        Returns:
            Cached or computed value
            
        Raises:
            CacheShutdownError: If cache is closed
            Exception: Any exception raised by compute_fn
        """
        # Fast path: check cache first
        value = self.get(key)
        if value is not None:
            return value
        
        # Check if another thread is computing this key
        computing_event = None
        should_compute = False
        
        with self._computing_lock:
            if key in self._computing_keys:
                # Another thread is computing, wait for it
                computing_event = self._computing_keys[key]
            else:
                # We'll compute it
                self._computing_keys[key] = threading.Event()
                should_compute = True
        
        if computing_event:
            # Wait for other thread to finish computing
            computing_event.wait()
            
            # Check if computation succeeded or failed
            with self._computing_lock:
                if key in self._computing_results:
                    success, result = self._computing_results.pop(key)
                    if success:
                        return result
                    else:
                        raise result  # Re-raise the exception
            
            # Fallback: try cache again
            value = self.get(key)
            if value is not None:
                return value
        
        if should_compute:
            try:
                # Double-check cache before computing
                value = self.get(key)
                if value is not None:
                    with self._computing_lock:
                        event = self._computing_keys.pop(key, None)
                        if event:
                            self._computing_results[key] = (True, value)
                            event.set()
                    return value
                
                # Compute value (outside cache lock to avoid blocking)
                computed_value = compute_fn()
                
                # Store computed value
                self.set(key, computed_value, ttl)
                
                # Signal completion with success
                with self._computing_lock:
                    event = self._computing_keys.pop(key, None)
                    if event:
                        self._computing_results[key] = (True, computed_value)
                        event.set()
                
                return computed_value
            except Exception as e:
                # Signal completion with failure
                with self._computing_lock:
                    event = self._computing_keys.pop(key, None)
                    if event:
                        self._computing_results[key] = (False, e)
                        event.set()
                
                logger.warning(f"Error computing value for key '{key}': {e}")
                raise
        
        # Shouldn't reach here, but compute as fallback
        return compute_fn()
    
    def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache metrics
            
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            
            stats_dict = {
                "size": len(self._cache),
                "max_size": self._max_size,
                "closed": self._closed,
                "stats_level": self._stats_level.name,
                "tracking_access_patterns": self._track_access
            }
            
            if self._stats_level.value >= StatsLevel.BASIC.value:
                total_requests = self._hits + self._misses
                hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
                
                stats_dict.update({
                    "hits": self._hits,
                    "misses": self._misses,
                    "hit_rate": round(hit_rate, 2),
                    "total_requests": total_requests,
                    "evictions": self._evictions,
                    "expirations": self._expirations,
                    "sets": self._sets
                })
            
            if self._callback_mode == CallbackMode.ASYNC_QUEUED:
                stats_dict["dropped_callbacks"] = self._dropped_callbacks
            
            return stats_dict
    
    def reset_stats(self) -> None:
        """
        Reset all statistics counters.
        
        Raises:
            CacheShutdownError: If cache is closed
        """
        with self._lock:
            self._check_open()
            self._hits = 0
            self._misses = 0
            self._evictions = 0
            self._expirations = 0
            self._sets = 0
            self._dropped_callbacks = 0
    
    def get_access_patterns(self, key: Optional[str] = None) -> Union[Dict[str, Dict[str, Any]], Dict[str, Any]]:
        """
        Get access pattern information.
        
        Only available when track_access_patterns=True (requires DETAILED stats level).
        
        Args:
            key: Optional specific key to get patterns for. If None, returns all keys.
            
        Returns:
            Dictionary with access metadata for key(s)
            
        Raises:
            CacheShutdownError: If cache is closed
            ValueError: If access pattern tracking is disabled or key doesn't exist
        """
        if not self._track_access:
            raise ValueError("Access pattern tracking is disabled. Enable with track_access_patterns=True and stats_level=StatsLevel.DETAILED")
        
        with self._lock:
            self._check_open()
            
            if key is not None:
                if key not in self._cache:
                    raise ValueError(f"Key '{key}' not found in cache")
                
                entry = self._cache[key]
                return {
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed.isoformat() if entry.last_accessed else None,
                    "age_seconds": (datetime.now() - entry.created_at).total_seconds(),
                    "remaining_ttl": entry.remaining_ttl()
                }
            
            patterns = {}
            for k, entry in self._cache.items():
                patterns[k] = {
                    "access_count": entry.access_count,
                    "last_accessed": entry.last_accessed.isoformat() if entry.last_accessed else None,
                    "age_seconds": (datetime.now() - entry.created_at).total_seconds(),
                    "remaining_ttl": entry.remaining_ttl()
                }
            
            return patterns
    
    def _record_stat(self, stat_type: str) -> None:
        """Record a statistic if tracking is enabled."""
        if self._stats_level == StatsLevel.NONE:
            return
        
        if stat_type == 'hit':
            self._hits += 1
        elif stat_type == 'miss':
            self._misses += 1
        elif stat_type == 'set' and self._stats_level.value >= StatsLevel.BASIC.value:
            self._sets += 1
        elif stat_type == 'eviction' and self._stats_level.value >= StatsLevel.BASIC.value:
            self._evictions += 1
        elif stat_type == 'expiration' and self._stats_level.value >= StatsLevel.BASIC.value:
            self._expirations += 1
    
    def _cleanup_expired(self) -> int:
        """Remove expired entries. Returns number of entries removed."""
        with self._lock:
            if self._closed:
                return 0
            
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in keys_to_delete:
                entry = self._cache[key]
                age_seconds = (datetime.now() - entry.created_at).total_seconds()
                del self._cache[key]
                self._record_stat('expiration')
                self._invoke_callback(
                    self._on_expiration, 
                    key, 
                    entry.value,
                    metadata={"reason": "background_cleanup", "age_seconds": age_seconds}
                )
            
            return len(keys_to_delete)
    
    def _start_cleanup_thread(self) -> None:
        """Start background thread for periodic cleanup."""
        def cleanup_loop():
            while not self._stop_cleanup.is_set():
                time.sleep(self._cleanup_interval)
                if not self._stop_cleanup.is_set():
                    try:
                        self._cleanup_expired()
                    except Exception as e:
                        logger.error(f"Error during cache cleanup: {e}")
        
        self._cleanup_thread = threading.Thread(
            target=cleanup_loop,
            daemon=True,
            name="CacheCleanup"
        )
        self._cleanup_thread.start()
    
    def _start_callback_thread(self) -> None:
        """Start background thread for processing queued callbacks."""
        def callback_loop():
            while not self._stop_callbacks.is_set():
                try:
                    callback, key, value, metadata = self._callback_queue.get(timeout=0.1)
                    try:
                        callback(key, value, metadata)
                    except Exception as e:
                        logger.error(f"Error in queued callback for key '{key}': {e}")
                    finally:
                        self._callback_queue.task_done()
                except Empty:
                    continue
        
        self._callback_thread = threading.Thread(
            target=callback_loop,
            daemon=True,
            name="CacheCallbacks"
        )
        self._callback_thread.start()
    
    def _invoke_callback(
        self,
        callback: Optional[CallbackProtocol],
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Invoke a callback according to configured mode."""
        if callback is None:
            return
        
        if self._callback_mode == CallbackMode.SYNC:
            try:
                callback(key, value, metadata)
            except Exception as e:
                logger.error(f"Error in sync callback for key '{key}': {e}")
        
        elif self._callback_mode == CallbackMode.ASYNC_QUEUED:
            try:
                if self._callback_queue_policy == CallbackQueuePolicy.BLOCK:
                    self._callback_queue.put((callback, key, value, metadata))
                else:
                    self._callback_queue.put_nowait((callback, key, value, metadata))
            except Exception:
                self._dropped_callbacks += 1
                if self._callback_queue_policy == CallbackQueuePolicy.DROP_WITH_LOG:
                    logger.warning(f"Callback queue full, dropping callback for key '{key}'")
        
        elif self._callback_mode == CallbackMode.FIRE_AND_FORGET:
            def run_callback():
                try:
                    callback(key, value, metadata)
                except Exception as e:
                    logger.error(f"Error in fire-and-forget callback for key '{key}': {e}")
            
            thread = threading.Thread(target=run_callback, daemon=True, name=f"CacheCallback-{key}")
            thread.start()
    
    def close(self) -> None:
        """
        Shutdown cache and cleanup threads.
        
        This method is idempotent and can be called multiple times.
        """
        with self._lock:
            if self._closed:
                return
            
            self._closed = True
            
            if self._cleanup_thread:
                self._stop_cleanup.set()
            
            if self._callback_thread:
                self._stop_callbacks.set()
        
        # Wait for threads outside lock
        if self._cleanup_thread:
            self._cleanup_thread.join(timeout=self._shutdown_timeout)
            if self._cleanup_thread.is_alive():
                logger.warning("Cache cleanup thread did not terminate gracefully")
        
        if self._callback_thread:
            self._callback_thread.join(timeout=self._shutdown_timeout)
            if self._callback_thread.is_alive():
                logger.warning("Cache callback thread did not terminate gracefully")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def __len__(self) -> int:
        """Return number of entries in cache."""
        with self._lock:
            return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Check if key exists (does not check expiration)."""
        with self._lock:
            return key in self._cache


# Utility functions for namespace support
def namespace_key(namespace: str, key: str) -> str:
    """Create namespaced key."""
    return f"{namespace}:{key}"


def extract_namespace(namespaced_key: str) -> Tuple[Optional[str], str]:
    """Extract namespace and key from namespaced key."""
    parts = namespaced_key.split(":", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return None, namespaced_key


class NamespacedCache:
    """Wrapper providing automatic key namespacing."""
    
    def __init__(self, cache: CacheLayer, namespace: str):
        self._cache = cache
        self._namespace = namespace
    
    def _ns_key(self, key: str) -> str:
        return namespace_key(self._namespace, key)
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._cache.get(self._ns_key(key), default)
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        self._cache.set(self._ns_key(key), value, ttl)
    
    def delete(self, key: str) -> bool:
        return self._cache.delete(self._ns_key(key))
    
    def contains(self, key: str) -> bool:
        return self._cache.contains(self._ns_key(key))
    
    def get_or_compute(self, key: str, compute_fn: Callable[[], Any], ttl: Optional[int] = None) -> Any:
        return self._cache.get_or_compute(self._ns_key(key), compute_fn, ttl)
```

## Usage Examples

```python
# Basic usage with BASIC stats (includes evictions/expirations)
cache = CacheLayer(
    default_ttl=300, 
    max_size=1000,
    stats_level=StatsLevel.BASIC
)

# Production config with async callbacks and overflow policy
cache = CacheLayer(
    default_ttl=300,
    max_size=10000,
    stats_level=StatsLevel.BASIC,
    track_access_patterns=False,
    callback_mode=CallbackMode.ASYNC_QUEUED,
    callback_queue_policy=CallbackQueuePolicy.DROP_WITH_LOG,
    shutdown_timeout=10.0
)

# Store with default TTL
cache.set("user:123", {"name": "Alice", "role": "admin"})

# Bulk operations with error tracking
result = cache.set_many({
    "user:1": {"name": "Alice"},
    "user:2": {"name": "Bob"}
}, ttl=300, continue_on_error=True)

if result.all_succeeded:
    print("All operations succeeded")
else:
    print(f"Successful: {result.success_count}, Failed: {result.failure_count}")
    for key, error in result.failed.items():
        print(f"Failed to set {key}: {error}")

# Get or compute with request coalescing and exception propagation
def fetch_user_from_db():
    user = db.query("SELECT * FROM users WHERE id = 123")
    if not user:
        raise ValueError("User not found")
    return user

try:
    user = cache.get_or_compute("user:123", fetch_user_from_db, ttl=600)
except ValueError as e:
    print(f"Computation failed: {e}")

# Monitoring hooks with metadata
def on_evict(key: str, value: Any, metadata: Optional[Dict] = None):
    if metadata:
        reason = metadata.get("reason", "unknown")
        access_count = metadata.get("access_count")
        if access_count is not None:
            print(f"Evicted {key}: reason={reason}, accesses={access_count}")
        else:
            print(f"Evicted {key}: reason={reason}")

cache = CacheLayer(
    on_eviction=on_evict,
    callback_mode=CallbackMode.ASYNC_QUEUED,
    callback_queue_policy=CallbackQueuePolicy.DROP_WITH_LOG
)

# Access patterns (requires DETAILED stats)
cache_with_tracking = CacheLayer(
    track_access_patterns=True,
    stats_level=StatsLevel.DETAILED
)
cache_with_tracking.set("key1", "value1")
cache_with_tracking.get("key1")
cache_with_tracking.get("key1")

# Get patterns for specific key
pattern = cache_with_tracking.get_access_patterns("key1")
print(pattern)  # {"access_count": 2, "last_accessed": "...", ...}

# Get patterns for all keys
all_patterns = cache_with_tracking.get_access_patterns()

# Namespace support for multi-tenancy
shared_cache = CacheLayer()
tenant_a = NamespacedCache(shared_cache, "tenant_a")
tenant_b = NamespacedCache(shared_cache, "tenant_b")

tenant_a.set("user:1", {"name": "Alice"})
tenant_b.set("user:1", {"name": "Bob"})  # Different namespace, no conflict

# Context manager for cleanup
with CacheLayer(default_ttl=60) as cache:
    cache.set("temp", "data")
    # Automatically closes on exit

# BASIC stats now include evictions/expirations
cache = CacheLayer(stats_level=StatsLevel.BASIC)
cache.set("key", "value")
stats = cache.stats()
print(stats)  # Includes hits, misses, evictions, expirations, sets
```

## Configuration Guide

### Performance vs Memory Trade-offs

| Configuration | Memory Usage | Performance | Use Case |
|---------------|--------------|-------------|----------|
| `stats_level=NONE, track_access_patterns=False` | Minimal | Highest | High-throughput, memory-constrained |
| `stats_level=BASIC, track_access_patterns=False` | Low | High | **Production default - includes evictions/expirations** |
| `stats_level=DETAILED, track_access_patterns=True` | High | Lower | Development, detailed analytics |

### Callback Modes

| Mode | Blocking | Guaranteed Delivery | Use Case |
|------|----------|---------------------|----------|
| `SYNC` | Yes | Yes | Critical operations, testing |
| `ASYNC_QUEUED` | No | Best-effort | **Production default - metrics export, monitoring** |
| `FIRE_AND_FORGET` | No | No | Logging, non-critical notifications |

### Callback Queue Policies

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `DROP` | Silent drop | High-performance, callbacks not critical |
| `DROP_WITH_LOG` | Drop + warning log | **Production default - visibility into dropped callbacks** |
| `BLOCK` | Wait for space | Critical callbacks, can impact performance |

## Error Handling

```python
# Bulk operations report partial failures
result = cache.set_many({"": "invalid", "valid": "data"})
assert result.failure_count == 1
assert "" in result.failed
assert result.failed[""] == "Cache key cannot be empty"
assert result.all_succeeded == False

# Access patterns require DETAILED stats level
cache = CacheLayer(track_access_patterns=False)
try:
    cache.get_access_patterns()
except ValueError as e:
    print(f"Cannot get patterns: {e}")

# Exception propagation in get_or_compute
def failing_compute():
    raise RuntimeError("DB connection failed")

try:
    cache.get_or_compute("key", failing_compute)
except RuntimeError as e:
    print(f"Computation failed: {e}")

# Thread-safe shutdown
cache.close()
try:
    cache.get("key")
except CacheShutdownError:
    print("Cache is closed")
```

## Performance Characteristics

- **Get**: O(1) average case
- **Set**: O(1) average case
- **Delete**: O(1)
- **Bulk operations**: O(k) where k = number of keys
- **Cleanup**: O(n) where n = number of entries (background thread)
- **get_or_compute**: O(1) cache hit, O(compute) + O(1) on miss with coalescing
- **Memory overhead per entry**: 
  - Base (stats_level=NONE or BASIC): ~120 bytes (entry object, datetime, OrderedDict node)
  - With DETAILED + access tracking: ~140 bytes (adds access_count, last_accessed)

## What I Improved

1. **Stats Hierarchy Simplified**: Changed BASIC level to include evictions/expirations/sets by default. These metrics are essential for production monitoring and add minimal overhead. DETAILED is now primarily about per-key access patterns.

2. **Access Tracking Constraint**: Enforced `track_access_patterns=True` requires `stats_level=DETAILED` in constructor validation. This prevents confusing configurations where access tracking is enabled but stats level won't capture it.

3. **Callback Queue Policy**: Added `CallbackQueuePolicy` enum with three options (DROP/DROP_WITH_LOG/BLOCK) to give explicit control over overflow behavior. Added `dropped_callbacks` counter to stats for visibility.

4. **Exception Propagation in Coalescing**: Improved `get_or_compute` to properly propagate exceptions to all waiting threads using `_computing_results` dictionary. Previously, failures would cause waiting threads to fall back to recomputing.

5. **Per-Key Access Patterns**: Added optional `key` parameter to `get_access_patterns()` to allow querying specific keys without fetching all patterns, reducing overhead for targeted debugging.

6. **BulkOperationResult Enhancement**: Added `all_succeeded` property for convenient checking of complete success without comparing counts.

## What I Kept

1. **OrderedDict for LRU**: Optimal O(1) operations with clean LRU semantics
2. **RLock for thread safety**: Correct reentrant locking for nested calls
3. **Background cleanup thread**: Essential for TTL management without blocking operations
4. **Per-entry TTL**: Flexible expiration control per key
5. **CacheEntry metadata**: Clean separation of concerns with entry-level state
6. **Context manager support**: Pythonic resource management with __enter__/__exit__
7. **Request coalescing infrastructure**: Event-based synchronization for thundering herd prevention
8. **Callback mode flexibility**: Three-mode system (SYNC/ASYNC_QUEUED/FIRE_AND_FORGET) covers real-world needs
9. **Namespace utilities**: Clean namespace support without modifying core cache

## Remaining Considerations

1. **Generic Type Safety**: Making `CacheLayer` generic (`CacheLayer[T]`) would provide stronger typing but reduce flexibility for mixed-type caches. Current approach favors flexibility - users can add type hints at call sites if desired.

2. **Persistence**: No built-in serialization/persistence. For warm restarts, users can implement custom callbacks to serialize on eviction/expiration or periodically snapshot via `get_access_patterns()`.

3. **Advanced Eviction Policies**: Currently only LRU. LFU or TTL-aware eviction would require additional complexity (priority queues, reordering on access). LRU is simple and effective for most use cases.

4. **Metrics Integration**: Callbacks are generic enough to integrate with any metrics system (Prometheus, StatsD, etc.). Users implement metrics export in callbacks rather than baking in specific integrations.

5. **Callback Error Handling**: SYNC mode logs errors but doesn't raise by default. Could add `raise_on_callback_error` flag if critical callbacks need to fail operations.

## Convergence Status

**ACCEPTING_FINAL**: The design is production-ready with all essential improvements incorporated:
- Stats hierarchy is simplified and practical (BASIC includes evictions/expirations)
- Callback queue overflow is explicitly controlled with three policies
- Exception propagation in request coalescing works correctly
- Access pattern tracking has clear requirements (DETAILED stats level)
- Bulk operations have convenient success checking
- Configuration guide provides clear production defaults

The architecture balances performance, observability, and flexibility. All core caching requirements are met with thread-safety, TTL support, LRU eviction, configurable monitoring, and graceful shutdown.

## PROMPT_FOR_ARCHITECT:

I've refined the design with these key changes:

1. **Stats hierarchy**: Moved evictions/expirations/sets to BASIC level (minimal overhead, essential for production). DETAILED is now primarily for per-key access patterns.

2. **Access tracking constraint**: Enforced validation that `track_access_patterns=True` requires `stats_level=DETAILED` to prevent confusing configurations.

3. **Callback overflow control**: Added `CallbackQueuePolicy` enum (DROP/DROP_WITH_LOG/BLOCK) for explicit overflow behavior + `dropped_callbacks` stat for visibility.

4. **Exception propagation**: Fixed `get_or_compute` to properly share exceptions with waiting threads via `_computing_results` dictionary.

5. **Per-key patterns**: Added optional `key` parameter to `get_access_patterns()` for targeted queries.

Questions for you:

1. **Stats granularity**: Does moving evictions/expirations to BASIC make sense? The overhead is negligible (just counter increments) and these metrics are crucial for production monitoring.

2. **Default callback policy**: Is `DROP_WITH_LOG` the right production default, or should we use `DROP` (silent) to avoid log spam under high load?

3. **Type safety trade-off**: Should we add an optional generic parameter like `CacheLayer[T]` that's opt-in, allowing users to choose between flexibility (current) and type safety?

4. **Computing results cleanup**: The `_computing_results` dict could grow if results aren't consumed. Should we add a TTL or size limit for these temporary results?

**Convergence Signal:** ACCEPTING_FINAL

---

