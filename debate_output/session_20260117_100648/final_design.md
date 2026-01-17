# Final Agreed Design

**Task:** Design a rate limiting system using token bucket algorithm

**Status:** debating

---

## Design

# Production-Grade Rate Limiting System Using Token Bucket Algorithm

## Architecture Overview

A distributed rate limiting system with three tiers optimized for accuracy, performance, and operational simplicity:
1. **Client Library Layer**: Lightweight SDK with intelligent retry and header parsing
2. **Rate Limiter Service Layer**: Stateless service with Redis-backed atomic operations
3. **Storage Layer**: Redis (standalone or cluster) with carefully tuned consistency guarantees

## Core Components

### 1. Simplified Token Bucket with Redis-Only State

```python
class TokenBucketState:
    """
    Immutable representation of bucket state returned from Redis.
    No local state management - Redis is the single source of truth.
    """
    def __init__(
        self,
        tokens_available: float,
        capacity: int,
        refill_rate: float,
        last_refill_time: float,
        reset_time: float
    ):
        self.tokens_available = tokens_available
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.last_refill_time = last_refill_time
        self.reset_time = reset_time
    
    def calculate_retry_after(self, tokens_requested: int) -> Optional[float]:
        """Calculate retry delay for denied requests."""
        if self.tokens_available >= tokens_requested:
            return None
        
        tokens_needed = tokens_requested - self.tokens_available
        return tokens_needed / self.refill_rate if self.refill_rate > 0 else None

@dataclass
class BucketConfig:
    """Immutable bucket configuration with validation."""
    capacity: int
    refill_rate: float  # tokens per second
    min_refill_interval_ms: int = 10
    
    def __post_init__(self):
        if self.capacity <= 0:
            raise ConfigurationError("Capacity must be positive")
        if self.refill_rate < 0:
            raise ConfigurationError("Refill rate cannot be negative")
        # Allow high refill rates - precision issues handled in Lua
        if self.refill_rate > self.capacity * 1000:
            raise ConfigurationError(
                f"Refill rate {self.refill_rate} exceeds capacity*1000 safety limit"
            )
```

### 2. Rate Limiter Service with Selective Caching

```python
class RateLimiterService:
    """
    Main service handling rate limit requests.
    Uses selective caching only for reads (check without consume).
    """
    def __init__(
        self,
        storage: StorageBackend,
        config_provider: ConfigProvider,
        fail_open: bool = True,
        enable_read_cache: bool = True,
        read_cache_ttl_ms: int = 50
    ):
        self.storage = storage
        self.config_provider = config_provider
        self.metrics = MetricsCollector()
        self.fail_open = fail_open
        
        # Selective caching: ONLY for read-only checks (preview mode)
        self.enable_read_cache = enable_read_cache
        self.read_cache_ttl_ms = read_cache_ttl_ms
        self.read_cache = TTLCache(maxsize=5000, ttl=read_cache_ttl_ms / 1000.0)
        
        # Simplified circuit breaker (per-instance is correct)
        self.redis_healthy = True
        self.last_health_check = time.time()
        self.consecutive_failures = 0
        self.failure_threshold = 5
    
    async def check_rate_limit(
        self,
        request: RateLimitRequest,
        consume: bool = True  # False = preview mode (check only)
    ) -> RateLimitResponse:
        """
        Primary endpoint: check and optionally consume tokens.
        
        Args:
            request: Rate limit request
            consume: If False, only check limits without consuming (cacheable)
        """
        start_time = time.time()
        bucket_key = self._generate_key(request)
        config = self.config_provider.get_config(request.scope, request.resource)
        
        # Check cache only for non-consuming reads
        if not consume and self.enable_read_cache:
            cached = self.read_cache.get(bucket_key)
            if cached and cached['config_hash'] == self._hash_config(config):
                self.metrics.cache_hit.inc()
                return self._build_response_from_cache(cached, request)
        
        try:
            # Check circuit breaker
            if not self._is_redis_healthy():
                return self._handle_storage_unavailable(request, config)
            
            # Execute atomic operation in Redis
            result = await self.storage.refill_and_consume(
                key=bucket_key,
                config=config,
                tokens_requested=request.tokens if consume else 0,
                current_time=time.time()
            )
            
            self._record_success()
            
            # Update cache only for non-consuming reads
            if not consume and self.enable_read_cache:
                self._update_read_cache(bucket_key, result, config)
            
            response = self._build_response(result, request, consume)
            self.metrics.record_request(request, response, time.time() - start_time)
            
            return response
            
        except StorageError as e:
            self._record_failure()
            self.metrics.record_error(request, e)
            return self._handle_storage_unavailable(request, config)
    
    async def check_hierarchical_limits(
        self,
        request: RateLimitRequest,
        limit_hierarchy: List[Tuple[str, str]]  # [(scope, resource), ...]
    ) -> HierarchicalRateLimitResponse:
        """
        Check multiple rate limits in parallel, consume only if all pass.
        
        Example:
            limit_hierarchy = [
                ('user', 'api.search'),
                ('ip', 'global'),
                ('global', 'api.search')
            ]
        
        This enables:
        - User-specific limit: 1000 req/hour
        - IP-based limit: 100 req/minute (DDoS protection)
        - Global API limit: 1M req/hour (system protection)
        """
        # Phase 1: Check all limits in parallel (no consumption)
        check_tasks = []
        for scope, resource in limit_hierarchy:
            check_request = RateLimitRequest(
                identifier=self._get_identifier_for_scope(request, scope),
                resource=resource,
                tokens=request.tokens,
                scope=scope,
                metadata=request.metadata
            )
            check_tasks.append(
                self.check_rate_limit(check_request, consume=False)
            )
        
        check_results = await asyncio.gather(*check_tasks)
        
        # Find first blocking limit
        blocking_limit = None
        for i, result in enumerate(check_results):
            if not result.allowed:
                blocking_limit = (limit_hierarchy[i], result)
                break
        
        # Phase 2: If all pass, consume from all limits in parallel
        if not blocking_limit:
            consume_tasks = []
            for scope, resource in limit_hierarchy:
                consume_request = RateLimitRequest(
                    identifier=self._get_identifier_for_scope(request, scope),
                    resource=resource,
                    tokens=request.tokens,
                    scope=scope,
                    metadata=request.metadata
                )
                consume_tasks.append(
                    self.check_rate_limit(consume_request, consume=True)
                )
            
            consume_results = await asyncio.gather(*consume_tasks)
            
            # Return most restrictive limit info
            most_restrictive = min(
                consume_results,
                key=lambda r: r.tokens_remaining / r.tokens_capacity
            )
            
            return HierarchicalRateLimitResponse(
                allowed=True,
                limit_results=dict(zip(limit_hierarchy, consume_results)),
                blocking_limit=None,
                most_restrictive_limit=most_restrictive
            )
        else:
            return HierarchicalRateLimitResponse(
                allowed=False,
                limit_results=dict(zip(limit_hierarchy, check_results)),
                blocking_limit=blocking_limit,
                most_restrictive_limit=blocking_limit[1]
            )
    
    def _is_redis_healthy(self) -> bool:
        """Simple per-instance health tracking."""
        # Fast path: check cached health status
        if time.time() - self.last_health_check < 5.0:
            return self.redis_healthy
        
        # Periodic health check (every 5 seconds)
        self.last_health_check = time.time()
        return self.redis_healthy
    
    def _record_success(self):
        """Record successful Redis operation."""
        self.consecutive_failures = 0
        if not self.redis_healthy:
            self.redis_healthy = True
            self.metrics.redis_recovered.inc()
    
    def _record_failure(self):
        """Record failed Redis operation."""
        self.consecutive_failures += 1
        if self.consecutive_failures >= self.failure_threshold:
            if self.redis_healthy:
                self.redis_healthy = False
                self.metrics.redis_unhealthy.inc()
    
    def _handle_storage_unavailable(
        self,
        request: RateLimitRequest,
        config: BucketConfig
    ) -> RateLimitResponse:
        """Fallback when Redis is unavailable."""
        self.metrics.storage_fallback.inc()
        
        if self.fail_open:
            return RateLimitResponse(
                allowed=True,
                tokens_remaining=config.capacity,
                tokens_capacity=config.capacity,
                retry_after_seconds=None,
                reset_at=datetime.now() + timedelta(seconds=60),
                degraded=True,
                degraded_reason="storage_unavailable"
            )
        else:
            return RateLimitResponse(
                allowed=False,
                tokens_remaining=0,
                tokens_capacity=config.capacity,
                retry_after_seconds=60.0,
                reset_at=datetime.now() + timedelta(seconds=60),
                degraded=True,
                degraded_reason="storage_unavailable"
            )
    
    def _hash_config(self, config: BucketConfig) -> str:
        """Generate stable hash of bucket configuration."""
        return hashlib.sha256(
            f"{config.capacity}:{config.refill_rate}".encode()
        ).hexdigest()[:16]
    
    def _update_read_cache(
        self,
        bucket_key: str,
        result: TokenBucketState,
        config: BucketConfig
    ):
        """Update read-only cache."""
        self.read_cache[bucket_key] = {
            'tokens_available': result.tokens_available,
            'capacity': result.capacity,
            'reset_time': result.reset_time,
            'config_hash': self._hash_config(config),
            'cached_at': time.time()
        }
```

### 3. Enhanced Redis Storage with Separate Config Keys

```python
class RedisStorageBackend:
    """
    Redis storage backend using Lua scripts for atomicity.
    Stores configuration separately from bucket state.
    """
    
    REFILL_AND_CONSUME_SCRIPT = """
    local bucket_key = KEYS[1]
    local config_key = KEYS[2]
    local tokens_requested = tonumber(ARGV[1])
    local capacity = tonumber(ARGV[2])
    local refill_rate = tonumber(ARGV[3])
    local current_time = tonumber(ARGV[4])
    local min_refill_interval_ms = tonumber(ARGV[5]) / 1000.0
    local config_hash = ARGV[6]
    
    -- Get or initialize configuration
    local stored_config_hash = redis.call('GET', config_key)
    
    if stored_config_hash and stored_config_hash ~= config_hash then
        -- Config changed - reset bucket
        redis.call('DEL', bucket_key)
        stored_config_hash = nil
    end
    
    if not stored_config_hash then
        redis.call('SET', config_key, config_hash)
        redis.call('EXPIRE', config_key, 86400)  -- 24 hours
    end
    
    -- Get bucket state
    local bucket = redis.call('HMGET', bucket_key, 'tokens', 'last_refill')
    local tokens = tonumber(bucket[1])
    local last_refill = tonumber(bucket[2])
    
    -- Initialize if bucket doesn't exist
    if not tokens or not last_refill then
        tokens = capacity
        last_refill = current_time
    end
    
    -- Clock skew protection
    local time_elapsed = current_time - last_refill
    if time_elapsed < -60 then
        return redis.error_reply("CLOCK_SKEW:" .. time_elapsed)
    end
    
    -- Cap forward time leaps (prevent exploitation)
    if time_elapsed > 3600 then
        time_elapsed = 3600
    end
    
    -- Refill tokens
    local new_tokens = tokens
    local new_last_refill = last_refill
    
    if time_elapsed >= min_refill_interval_ms then
        local tokens_to_add = time_elapsed * refill_rate
        new_tokens = math.min(capacity, tokens + tokens_to_add)
        new_last_refill = current_time
    end
    
    -- Consume tokens
    local success = 0
    local remaining_tokens = new_tokens
    
    if tokens_requested > 0 then
        if new_tokens >= tokens_requested then
            remaining_tokens = new_tokens - tokens_requested
            success = 1
        end
    else
        -- Read-only check (tokens_requested = 0)
        success = 1
    end
    
    -- Update state only if consuming
    if tokens_requested > 0 then
        redis.call('HMSET', bucket_key, 
            'tokens', remaining_tokens,
            'last_refill', new_last_refill
        )
        
        -- Dynamic TTL: time to refill to capacity + buffer
        local ttl
        if refill_rate > 0 then
            local time_to_full = (capacity - remaining_tokens) / refill_rate
            ttl = math.ceil(math.max(time_to_full * 2, 300))
        else
            ttl = 3600
        end
        redis.call('EXPIRE', bucket_key, ttl)
    end
    
    -- Calculate retry_after
    local retry_after = 0
    if success == 0 and refill_rate > 0 then
        local tokens_needed = tokens_requested - new_tokens
        retry_after = math.ceil(tokens_needed / refill_rate * 1000) / 1000
    end
    
    -- Calculate reset time
    local reset_time = new_last_refill
    if refill_rate > 0 then
        reset_time = new_last_refill + (capacity - remaining_tokens) / refill_rate
    else
        reset_time = new_last_refill + 3600
    end
    
    return {success, remaining_tokens, retry_after, capacity, new_last_refill, reset_time}
    """
    
    def __init__(self, redis_client: Redis):
        self.redis = redis_client
        self.script_sha = None
    
    async def refill_and_consume(
        self,
        key: str,
        config: BucketConfig,
        tokens_requested: int,
        current_time: float
    ) -> TokenBucketState:
        """Execute atomic refill and consume operation."""
        if not self.script_sha:
            self.script_sha = await self.redis.script_load(
                self.REFILL_AND_CONSUME_SCRIPT
            )
        
        config_key = f"{key}:config"
        config_hash = hashlib.sha256(
            f"{config.capacity}:{config.refill_rate}".encode()
        ).hexdigest()[:16]
        
        try:
            result = await self.redis.evalsha(
                self.script_sha,
                2,  # number of keys
                key,
                config_key,
                tokens_requested,
                config.capacity,
                config.refill_rate,
                current_time,
                config.min_refill_interval_ms,
                config_hash
            )
            
            success, tokens_remaining, retry_after, capacity, last_refill, reset_time = result
            
            return TokenBucketState(
                tokens_available=tokens_remaining,
                capacity=capacity,
                refill_rate=config.refill_rate,
                last_refill_time=last_refill,
                reset_time=reset_time
            )
            
        except redis.exceptions.ResponseError as e:
            if "CLOCK_SKEW" in str(e):
                raise ClockSkewError(f"Clock skew detected: {e}")
            raise StorageError(f"Redis script error: {e}")
        except redis.exceptions.RedisError as e:
            raise StorageError(f"Redis connection error: {e}")
```

### 4. Configuration Provider with Hot Reload

```python
class ConfigProvider:
    """
    Provides rate limit configurations with hot reload support.
    Configurations stored separately from runtime state.
    """
    def __init__(self, config_source: str = "config/rate_limits.yaml"):
        self.config_source = config_source
        self.configs: Dict[Tuple[str, str], BucketConfig] = {}
        self.last_reload = 0
        self.reload_interval = 60  # seconds
        self._load_configs()
    
    def get_config(self, scope: str, resource: str) -> BucketConfig:
        """Get configuration for scope and resource."""
        # Periodic reload
        if time.time() - self.last_reload > self.reload_interval:
            self._load_configs()
        
        key = (scope, resource)
        if key not in self.configs:
            # Fallback to default config
            return BucketConfig(
                capacity=1000,
                refill_rate=10.0,
                min_refill_interval_ms=10
            )
        
        return self.configs[key]
    
    def _load_configs(self):
        """Load configurations from YAML file."""
        try:
            with open(self.config_source) as f:
                data = yaml.safe_load(f)
            
            new_configs = {}
            for limit_config in data.get('rate_limits', []):
                scope = limit_config['scope']
                resource = limit_config.get('resource', 'default')
                
                config = BucketConfig(
                    capacity=limit_config['capacity'],
                    refill_rate=limit_config['refill_rate'],
                    min_refill_interval_ms=limit_config.get('min_refill_interval_ms', 10)
                )
                
                new_configs[(scope, resource)] = config
            
            self.configs = new_configs
            self.last_reload = time.time()
            
        except Exception as e:
            # Keep existing configs on error
            logging.error(f"Failed to reload configs: {e}")
```

## Data Models

```python
@dataclass
class RateLimitRequest:
    identifier: str  # user_id, ip_address, api_key
    resource: str  # API endpoint or resource name
    tokens: int = 1
    scope: str = "user"  # user, ip, api_key, global
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.tokens <= 0:
            raise InvalidRequestError("Tokens must be positive")
        if self.tokens > 100000:
            raise InvalidRequestError("Token request too large (max 100k)")

@dataclass
class RateLimitResponse:
    allowed: bool
    tokens_remaining: float
    tokens_capacity: int
    retry_after_seconds: Optional[float]
    reset_at: datetime
    degraded: bool = False
    degraded_reason: Optional[str] = None
    
    def to_headers(self) -> Dict[str, str]:
        """Generate RFC 6585 compliant headers."""
        headers = {
            "X-RateLimit-Limit": str(self.tokens_capacity),
            "X-RateLimit-Remaining": str(int(self.tokens_remaining)),
            "X-RateLimit-Reset": str(int(self.reset_at.timestamp())),
        }
        
        if self.retry_after_seconds:
            headers["Retry-After"] = str(max(1, int(math.ceil(self.retry_after_seconds))))
        
        if self.degraded:
            headers["X-RateLimit-Degraded"] = "true"
            if self.degraded_reason:
                headers["X-RateLimit-Degraded-Reason"] = self.degraded_reason
        
        return headers

@dataclass
class HierarchicalRateLimitResponse:
    """Response for hierarchical rate limit checks."""
    allowed: bool
    limit_results: Dict[Tuple[str, str], RateLimitResponse]
    blocking_limit: Optional[Tuple[Tuple[str, str], RateLimitResponse]]
    most_restrictive_limit: RateLimitResponse
    
    def to_headers(self) -> Dict[str, str]:
        """Return headers from most restrictive limit."""
        return self.most_restrictive_limit.to_headers()
```

## Storage Schema

**Bucket State Keys:**
```
Key: ratelimit:{scope}:{identifier}:{resource}
Type: Hash
Fields:
  - tokens: <float>         # Current available tokens
  - last_refill: <float>    # Unix timestamp with decimals
TTL: Dynamic (2x time_to_full, min 300s)
```

**Configuration Keys (Separate):**
```
Key: ratelimit:{scope}:{identifier}:{resource}:config
Type: String
Value: <config_hash>        # SHA256 of capacity:refill_rate
TTL: 86400 (24 hours)
```

## Deployment Architecture

```
┌─────────────────┐
│  Client Apps    │
│  (SDK with      │
│   retry logic)  │
└────────┬────────┘
         │
    HTTP/gRPC + TLS
         │
         ▼
┌─────────────────┐
│  Load Balancer  │
│  (L7 - Envoy)   │
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌─────────┐
│RateLimit│ │RateLimit│  (Stateless pods)
│Service  │ │Service  │  (Selective read cache)
│  Pod 1  │ │  Pod 2  │  (Per-instance health tracking)
└────┬────┘ └────┬────┘
     │           │
     └─────┬─────┘
           │
           ▼
   ┌───────────────┐
   │ Redis         │  (Standalone or Cluster)
   │ (AOF enabled) │  (Strong consistency)
   │ (No Sentinel) │  (Simple ops)
   └───────────────┘
           │
           ▼
   ┌───────────────┐
   │  Prometheus   │  (Metrics)
   │  + Grafana    │  (Dashboards)
   │  + Alerts     │  (On-call)
   └───────────────┘
```

**Deployment Decisions:**

1. **Standalone Redis First**: Start with standalone Redis (AOF persistence)
   - Simpler operations, fewer failure modes
   - 99.9% uptime with proper monitoring
   - Scale to Redis Cluster only when needed (multi-region, >100k RPS)

2. **Per-Instance Circuit Breaking**: Each pod tracks Redis health independently
   - Simpler than shared circuit breaker (no Redis dependency)
   - Fast local decisions (no network hop)
   - Acceptable: different pods may disagree briefly

3. **Selective Caching**: Only cache read-only checks (preview mode)
   - 50ms TTL (tighter than 100ms)
   - Never cache consuming operations
   - Bounded inaccuracy: max 50ms stale data

4. **Stateless Services**: Zero local state except read cache
   - Easy horizontal scaling
   - No state synchronization needed
   - Clean pod restarts

## Configuration Example

```yaml
# rate_limits.yaml
rate_limits:
  # User-level limits
  - name: api_standard_user
    scope: user
    resource: api.search
    capacity: 1000
    refill_rate: 10.0  # 10/sec = 36k/hour
    min_refill_interval_ms: 10
    
  - name: api_premium_user
    scope: user
    resource: api.search
    capacity: 10000
    refill_rate: 100.0
    min_refill_interval_ms: 10
    
  # IP-based limits (DDoS protection)
  - name: ip_global_limit
    scope: ip
    resource: global
    capacity: 100
    refill_rate: 5.0  # 5/sec = 300/min
    min_refill_interval_ms: 50
    
  # Global system limits
  - name: global_api_limit
    scope: global
    resource: api.search
    capacity: 1000000
    refill_rate: 10000.0  # 10k/sec = 36M/hour
    min_refill_interval_ms: 10

# Runtime configuration
runtime:
  fail_open: true
  enable_read_cache: true
  read_cache_ttl_ms: 50
  redis:
    mode: standalone  # Start simple
    host: redis.default.svc.cluster.local
    port: 6379
    db: 0
    connection_pool_size: 50
    socket_timeout_ms: 1000
    socket_connect_timeout_ms: 1000
  health_check:
    failure_threshold: 5
    check_interval_seconds: 5
```

## API Usage Example

### Hierarchical Rate Limiting

```python
# Example: Check user + IP + global limits
response = await rate_limiter.check_hierarchical_limits(
    request=RateLimitRequest(
        identifier="user_12345",
        resource="api.search",
        tokens=1,
        scope="user",
        metadata={"ip_address": "203.0.113.42"}
    ),
    limit_hierarchy=[
        ('user', 'api.search'),      # User-specific: 1000/hour
        ('ip', 'global'),             # IP-based: 100/min
        ('global', 'api.search')      # Global: 1M/hour
    ]
)

if response.allowed:
    # Process request
    return response.most_restrictive_limit.to_headers()
else:
    # Deny request with info about blocking limit
    scope, resource = response.blocking_limit[0]
    limit_response = response.blocking_limit[1]
    
    return {
        "error": "rate_limit_exceeded",
        "blocking_limit": f"{scope}:{resource}",
        "retry_after": limit_response.retry_after_seconds
    }, 429, limit_response.to_headers()
```