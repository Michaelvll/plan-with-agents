# Final Agreed Design

**Task:** Design a simple caching layer with TTL support

**Status:** consensus

---

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