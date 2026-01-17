# Final Agreed Design

**Task:** Design authentication system with JWT refresh tokens

Requirements:
- Secure login flow with JWT tokens
- Refresh token mechanism for session extension
- Token revocation capability
- Protection against common attacks (CSRF, XSS, replay)
- Support for multiple devices/sessions

**Status:** consensus

---

# JWT Authentication System with Global Distribution & Production Hardening

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GLOBAL REGIONS                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐         ┌──────────────────┐            │
│  │   US-EAST        │         │   EU-WEST        │            │
│  │                  │         │                  │            │
│  │  ┌────────────┐  │         │  ┌────────────┐  │            │
│  │  │ API Gateway│  │         │  │ API Gateway│  │            │
│  │  └────────────┘  │         │  └────────────┘  │            │
│  │        ↓         │         │        ↓         │            │
│  │  ┌────────────┐  │         │  ┌────────────┐  │            │
│  │  │ Redis      │←─┼─────────┼─→│ Redis      │  │            │
│  │  │ Regional   │  │ Sync    │  │ Regional   │  │            │
│  │  └────────────┘  │         │  └────────────┘  │            │
│  │        ↓         │         │        ↓         │            │
│  │  ┌────────────┐  │         │  ┌────────────┐  │            │
│  │  │ App Nodes  │  │         │  │ App Nodes  │  │            │
│  │  │ (3+ pods)  │  │         │  │ (3+ pods)  │  │            │
│  │  └────────────┘  │         │  └────────────┘  │            │
│  │        ↓         │         │        ↓         │            │
│  │  ┌────────────┐  │         │  ┌────────────┐  │            │
│  │  │ Postgres   │←─┼─────────┼─→│ Postgres   │  │            │
│  │  │ (Primary)  │  │ Replica │  │ (Replica)  │  │            │
│  │  └────────────┘  │         │  └────────────┘  │            │
│  └──────────────────┘         └──────────────────┘            │
│           ↓                             ↓                      │
│  ┌──────────────────────────────────────────────────────┐     │
│  │         Global Blacklist Propagation Bus             │     │
│  │         (Pub/Sub: Redis Streams + Postgres WAL)     │     │
│  └──────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

## Multi-Region Strategy with Consistency Guarantees

### 1. Token Types and Regional Behavior

**Access Tokens** (15-minute lifetime):
- ✅ **Stateless validation** - verify signature + check local blacklist
- ✅ **Regional Redis cache** - 99.9% of validations hit local cache
- ⚠️ **Blacklist propagation delay** - acceptable (see security analysis)

**Refresh Tokens** (30-day lifetime):
- ✅ **Always write to PRIMARY Postgres** (strong consistency)
- ✅ **Refresh allowed in any region** (global mobility)
- ✅ **Token family tracking** - detects cross-region reuse attacks

### 2. Blacklist Propagation Strategy

**Design Principle**: **"Eventually consistent blacklist with risk-based synchronous verification"**

```typescript
interface BlacklistPropagationConfig {
  // How fast does blacklist propagate between regions?
  propagationTarget: {
    p50: 50,      // 50ms - Redis Streams
    p99: 500,     // 500ms - includes Postgres replication
    p99.9: 2000   // 2 seconds - degraded network
  };
  
  // Which operations require synchronous cross-region check?
  requireSyncCheck: {
    highRiskOperations: true,    // Admin actions, delete account, payment
    tokenAge: '<5min',           // Recently issued tokens (likely from logout)
    userRiskScore: '>0.7',       // Suspicious activity score
    crossRegionRefresh: true     // User moved to different region
  };
  
  // Fallback behavior during propagation delay
  acceptanceCriteria: {
    maxAge: 300000,              // 5 minutes since token issued
    requireCompensatingControls: true,
    logSecurityEvent: true
  };
}

// Global blacklist propagation bus
class GlobalBlacklistBus {
  private regionalRedis: Map<Region, RedisClient>;
  private postgresWalSubscription: PostgresReplicationClient;
  private publishQueue: RedisStream;
  
  constructor() {
    // Subscribe to Postgres WAL for blacklist INSERTs
    this.postgresWalSubscription = new PostgresReplicationClient({
      tables: ['token_blacklist'],
      operations: ['INSERT'],
      onMessage: (change) => this.propagateBlacklistEntry(change)
    });
    
    // Redis Streams for cross-region pub/sub
    this.publishQueue = new RedisStream('blacklist:global');
  }
  
  async blacklistToken(
    jti: string, 
    userId: string, 
    reason: string,
    metadata: BlacklistMetadata
  ): Promise<void> {
    const startTime = performance.now();
    
    // 1. Write to PRIMARY Postgres immediately (source of truth)
    const expiresAt = new Date(Date.now() + 15 * 60 * 1000);
    await db.query(
      `INSERT INTO token_blacklist 
       (jti, user_id, expires_at, reason, blacklisted_at, source_region, session_id)
       VALUES ($1, $2, $3, $4, NOW(), $5, $6)`,
      [jti, userId, expiresAt, reason, getCurrentRegion(), metadata.sessionId]
    );
    
    logger.info('Token blacklisted in primary DB', {
      jti,
      userId,
      reason,
      latency: performance.now() - startTime
    });
    
    // 2. Publish to Redis Stream for immediate regional propagation
    await this.publishQueue.add('blacklist', {
      jti,
      userId,
      expiresAt: expiresAt.toISOString(),
      reason,
      sourceRegion: getCurrentRegion(),
      timestamp: Date.now()
    });
    
    // 3. Update local region Redis immediately
    await this.regionalRedis.get(getCurrentRegion())?.setex(
      `blacklist:jti:${jti}`,
      15 * 60,
      JSON.stringify({ userId, reason, blacklistedAt: new Date() })
    );
    
    // 4. Add to local bloom filter immediately
    blacklistBloomFilter.add(jti);
    
    metrics.histogram('blacklist.propagation.latency', performance.now() - startTime);
  }
  
  async propagateBlacklistEntry(entry: BlacklistEntry): Promise<void> {
    // Propagate to all regional Redis clusters
    const propagationPromises = Array.from(this.regionalRedis.entries())
      .filter(([region]) => region !== entry.sourceRegion) // Skip source
      .map(([region, redis]) => 
        this.propagateToRegion(region, redis, entry)
      );
    
    await Promise.allSettled(propagationPromises);
  }
  
  private async propagateToRegion(
    region: Region,
    redis: RedisClient,
    entry: BlacklistEntry
  ): Promise<void> {
    const startTime = performance.now();
    
    try {
      await redis.setex(
        `blacklist:jti:${entry.jti}`,
        entry.ttlSeconds,
        JSON.stringify(entry)
      );
      
      metrics.histogram('blacklist.cross_region_propagation', 
        performance.now() - startTime,
        { source: entry.sourceRegion, target: region }
      );
      
    } catch (error) {
      logger.error('Failed to propagate blacklist to region', {
        region,
        jti: entry.jti,
        error: error.message
      });
      
      metrics.increment('blacklist.propagation.failure', {
        source: entry.sourceRegion,
        target: region
      });
      
      // Not critical - Postgres replication will eventually sync
    }
  }
  
  // Check blacklist with cross-region awareness
  async checkBlacklist(
    jti: string,
    riskLevel: 'low' | 'medium' | 'high',
    tokenIssuedAt: number,
    currentRegion: Region,
    tokenIssuedInRegion?: Region
  ): Promise<BlacklistCheckResult> {
    
    // 1. Check local Redis first (99.9% of requests)
    const localResult = await this.regionalRedis.get(currentRegion)?.get(
      `blacklist:jti:${jti}`
    );
    
    if (localResult !== null) {
      return { 
        blacklisted: true, 
        source: 'local_redis',
        latency: 1 
      };
    }
    
    // 2. Determine if we need synchronous cross-region check
    const needsSyncCheck = this.shouldCheckAllRegions(
      jti,
      riskLevel,
      tokenIssuedAt,
      currentRegion,
      tokenIssuedInRegion
    );
    
    if (!needsSyncCheck) {
      // Trust local cache (low risk)
      return { 
        blacklisted: false, 
        source: 'local_redis',
        latency: 1
      };
    }
    
    // 3. Check PRIMARY Postgres (authoritative source)
    // This handles cross-region edge cases
    const startTime = performance.now();
    const pgResult = await db.query({
      name: 'check_blacklist_global',
      text: `SELECT 1 FROM token_blacklist 
             WHERE jti = $1 AND expires_at > NOW() 
             LIMIT 1`,
      values: [jti]
    });
    
    const latency = performance.now() - startTime;
    
    metrics.histogram('blacklist.cross_region_check.latency', latency, {
      risk_level: riskLevel,
      cross_region: tokenIssuedInRegion !== currentRegion
    });
    
    return {
      blacklisted: pgResult.rowCount > 0,
      source: 'postgres_primary',
      latency
    };
  }
  
  private shouldCheckAllRegions(
    jti: string,
    riskLevel: 'low' | 'medium' | 'high',
    tokenIssuedAt: number,
    currentRegion: Region,
    tokenIssuedInRegion?: Region
  ): boolean {
    
    // Always check Postgres for high-risk operations
    if (riskLevel === 'high') {
      return true;
    }
    
    // Check if token was issued in different region (possible logout in other region)
    if (tokenIssuedInRegion && tokenIssuedInRegion !== currentRegion) {
      return true;
    }
    
    // Check if token is very recently issued (< 5 minutes)
    // Likely from recent logout that may not have propagated yet
    const tokenAge = Date.now() - tokenIssuedAt;
    if (tokenAge < 5 * 60 * 1000) {
      return true;
    }
    
    return false;
  }
}

interface BlacklistEntry {
  jti: string;
  userId: string;
  expiresAt: string;
  reason: string;
  sourceRegion: Region;
  ttlSeconds: number;
  timestamp: number;
  sessionId?: string;
}

interface BlacklistMetadata {
  sessionId?: string;
  deviceId?: string;
  ipAddress?: string;
  userAgent?: string;
}

interface BlacklistCheckResult {
  blacklisted: boolean;
  source: 'local_redis' | 'remote_redis' | 'postgres_primary' | 'bloom_filter';
  latency: number;
}

type Region = 'us-east' | 'us-west' | 'eu-west' | 'ap-southeast' | 'ap-northeast';

function getCurrentRegion(): Region {
  return process.env.AWS_REGION as Region || 'us-east';
}
```

### 3. Cross-Region Token Refresh Strategy

**Challenge**: User logs in US-EAST, travels to EU-WEST, refreshes token.

**Requirements**:
- ✅ Refresh must succeed (user mobility)
- ✅ Prevent token reuse attacks across regions
- ✅ Detect compromised token families

**Solution**: **Regional read replicas + primary write with conflict detection**

```typescript
async function performCrossRegionRefresh(
  refreshToken: string,
  fingerprint: string,
  currentRegion: Region
): Promise<AuthResponse> {
  
  const tokenHash = hashToken(refreshToken);
  const startTime = performance.now();
  
  // 1. Acquire distributed lock (prefer local Redis, fallback to Postgres)
  const lockAcquired = await acquireCrossRegionLock(tokenHash, currentRegion);
  
  if (!lockAcquired) {
    throw new AuthError('CONCURRENT_REFRESH_IN_PROGRESS');
  }
  
  try {
    // 2. Read token from PRIMARY Postgres (not replica)
    // This ensures we see the absolute latest state across all regions
    const client = await getPrimaryDbClient();
    
    await client.query('BEGIN TRANSACTION ISOLATION LEVEL SERIALIZABLE');
    
    const tokenResult = await client.query(
      `SELECT * FROM refresh_tokens 
       WHERE token_hash = $1 
       FOR UPDATE`,
      [tokenHash]
    );
    
    if (tokenResult.rowCount === 0) {
      throw new AuthError('INVALID_REFRESH_TOKEN');
    }
    
    const tokenData = tokenResult.rows[0];
    
    // 3. Enhanced validation for cross-region refresh
    await validateRefreshToken(tokenData, fingerprint, currentRegion);
    
    // 4. Check for token reuse (CRITICAL for cross-region security)
    if (tokenData.used) {
      // Token reuse detected - revoke entire family
      await handleTokenFamilyCompromise(
        tokenData.token_family_id,
        'CROSS_REGION_TOKEN_REUSE',
        client
      );
      
      throw new AuthError('TOKEN_REUSE_DETECTED');
    }
    
    // 5. Mark token as used (in PRIMARY database)
    await client.query(
      `UPDATE refresh_tokens 
       SET used = true, 
           used_at = NOW(),
           used_in_region = $2
       WHERE token_hash = $1`,
      [tokenHash, currentRegion]
    );
    
    // 6. Generate new token pair
    const user = await getUserById(tokenData.user_id);
    
    const newAccessToken = generateAccessToken(user, {
      sessionId: tokenData.session_id,
      deviceId: tokenData.device_id,
      tokenVersion: user.token_version,
      issuedInRegion: currentRegion,  // NEW: Track issuing region
      previousRegion: tokenData.issued_in_region
    });
    
    const newRefreshToken = await generateAndStoreRefreshToken(
      user,
      {
        sessionId: tokenData.session_id,
        deviceId: tokenData.device_id,
        deviceFingerprint: fingerprint,
        parentTokenId: tokenData.id,
        tokenFamilyId: tokenData.token_family_id,
        timesRefreshed: tokenData.times_refreshed + 1,
        issuedInRegion: currentRegion,  // NEW: Track issuing region
        previousRegion: tokenData.issued_in_region
      },
      client
    );
    
    await client.query('COMMIT');
    
    // 7. Update regional cache (eventual consistency is OK here)
    try {
      await cache.set(
        `refresh:${tokenHash}:used`,
        true,
        900
      );
    } catch {
      // Not critical
    }
    
    metrics.histogram('auth.cross_region_refresh.latency', 
      performance.now() - startTime,
      { 
        from_region: tokenData.issued_in_region,
        to_region: currentRegion
      }
    );
    
    return {
      accessToken: newAccessToken.token,
      refreshToken: newRefreshToken.token,
      expiresIn: 900,
      tokenType: 'Bearer',
      refreshExpiresIn: 2592000
    };
    
  } finally {
    await releaseCrossRegionLock(tokenHash, currentRegion);
  }
}

async function validateRefreshToken(
  tokenData: RefreshTokenRow,
  fingerprint: string,
  currentRegion: Region
): Promise<void> {
  
  // 1. Check expiry
  if (tokenData.expires_at < new Date()) {
    throw new AuthError('REFRESH_TOKEN_EXPIRED');
  }
  
  // 2. Check revocation
  if (tokenData.revoked) {
    throw new AuthError('REFRESH_TOKEN_REVOKED');
  }
  
  // 3. Validate fingerprint
  const fingerprintHash = hashFingerprint(fingerprint);
  if (tokenData.device_fingerprint_hash !== fingerprintHash) {
    
    // Cross-region fingerprint mismatch could be legitimate (VPN, proxy)
    // Check if user has history of cross-region usage
    const userTravelPattern = await getUserTravelPattern(tokenData.user_id);
    
    if (!userTravelPattern.crossRegionAllowed) {
      // User has never used service from multiple regions - suspicious
      await createSecurityEvent({
        userId: tokenData.user_id,
        eventType: 'CROSS_REGION_FINGERPRINT_MISMATCH',
        severity: 'HIGH',
        details: {
          originalRegion: tokenData.issued_in_region,
          currentRegion,
          originalFingerprint: tokenData.device_fingerprint_hash.substring(0, 16),
          currentFingerprint: fingerprintHash.substring(0, 16)
        }
      });
      
      throw new AuthError('FINGERPRINT_MISMATCH');
    }
    
    // Log but allow (user has established cross-region pattern)
    logger.warn('Cross-region fingerprint mismatch allowed', {
      userId: tokenData.user_id,
      fromRegion: tokenData.issued_in_region,
      toRegion: currentRegion
    });
  }
  
  // 4. Check refresh count (detect infinite refresh loops)
  if (tokenData.times_refreshed > 1000) {
    // Suspicious - single refresh chain shouldn't exceed 1000 refreshes
    // (30 days / 15 min = 2880 max normal refreshes, but user should re-login)
    await createSecurityEvent({
      userId: tokenData.user_id,
      eventType: 'EXCESSIVE_REFRESH_COUNT',
      severity: 'MEDIUM',
      details: {
        timesRefreshed: tokenData.times_refreshed,
        tokenFamilyId: tokenData.token_family_id
      }
    });
    
    throw new AuthError('REFRESH_LIMIT_EXCEEDED');
  }
}

// Cross-region distributed lock using Redis + Postgres fallback
async function acquireCrossRegionLock(
  tokenHash: string,
  region: Region,
  timeoutMs: number = 5000
): Promise<boolean> {
  
  const lockKey = `lock:refresh:${tokenHash}`;
  const lockValue = `${region}:${uuidv4()}:${Date.now()}`;
  
  // Try regional Redis first
  const regionalRedis = getRegionalRedis(region);
  
  try {
    const acquired = await regionalRedis.set(
      lockKey,
      lockValue,
      'NX',
      'PX',
      timeoutMs
    );
    
    if (acquired) {
      return true;
    }
  } catch (error) {
    logger.warn('Regional Redis lock failed, trying Postgres', {
      tokenHash: tokenHash.substring(0, 16),
      region,
      error: error.message
    });
  }
  
  // Fallback to Postgres advisory lock
  // Use hash of token as lock ID (deterministic across regions)
  const lockId = hashToInt64(tokenHash);
  
  const result = await db.query(
    'SELECT pg_try_advisory_lock($1) as acquired',
    [lockId]
  );
  
  return result.rows[0].acquired;
}

async function releaseCrossRegionLock(
  tokenHash: string,
  region: Region
): Promise<void> {
  
  const lockKey = `lock:refresh:${tokenHash}`;
  
  // Try Redis first
  try {
    const regionalRedis = getRegionalRedis(region);
    await regionalRedis.del(lockKey);
  } catch (error) {
    // Fallback to Postgres advisory lock release
    const lockId = hashToInt64(tokenHash);
    await db.query('SELECT pg_advisory_unlock($1)', [lockId]);
  }
}
```

### 4. Enhanced Schema for Multi-Region Support

```sql
-- Refresh tokens table with region tracking
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash VARCHAR(64) NOT NULL UNIQUE,
  user_id UUID NOT NULL REFERENCES users(id),
  session_id UUID NOT NULL,
  device_id VARCHAR(255) NOT NULL,
  device_fingerprint_hash VARCHAR(64) NOT NULL,
  
  -- NEW: Region tracking
  issued_in_region VARCHAR(50) NOT NULL,
  used_in_region VARCHAR(50),
  
  expires_at TIMESTAMP NOT NULL,
  issued_at TIMESTAMP NOT NULL DEFAULT NOW(),
  used BOOLEAN DEFAULT FALSE,
  used_at TIMESTAMP,
  revoked BOOLEAN DEFAULT FALSE,
  revoked_at TIMESTAMP,
  
  -- Token family tracking
  token_family_id UUID NOT NULL,
  parent_token_id UUID REFERENCES refresh_tokens(id),
  times_refreshed INTEGER DEFAULT 0,
  
  -- Audit
  ip_address INET,
  user_agent TEXT,
  created_at TIMESTAMP DEFAULT NOW()
);

-- Composite index for cross-region lookups
CREATE INDEX idx_refresh_tokens_hash_region ON refresh_tokens(token_hash, issued_in_region);
CREATE INDEX idx_refresh_tokens_family ON refresh_tokens(token_family_id, issued_at DESC);
CREATE INDEX idx_refresh_tokens_user_active ON refresh_tokens(user_id, expires_at) 
  WHERE NOT used AND NOT revoked;

-- Token blacklist with region tracking
CREATE TABLE token_blacklist (
  jti VARCHAR(255) PRIMARY KEY,
  user_id UUID NOT NULL,
  revoked_at TIMESTAMP NOT NULL DEFAULT NOW(),
  expires_at TIMESTAMP NOT NULL,
  reason VARCHAR(100),
  session_id UUID,
  
  -- NEW: Region tracking for propagation monitoring
  source_region VARCHAR(50) NOT NULL,
  blacklisted_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  ip_address INET,
  user_agent TEXT
);

-- Index for cross-region blacklist checks
CREATE INDEX idx_blacklist_active ON token_blacklist(jti, expires_at)
  WHERE expires_at > NOW();
CREATE INDEX idx_blacklist_user_recent ON token_blacklist(user_id, revoked_at DESC);
CREATE INDEX idx_blacklist_region ON token_blacklist(source_region, blacklisted_at DESC);

-- User travel patterns (for risk assessment)
CREATE TABLE user_region_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id),
  region VARCHAR(50) NOT NULL,
  first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
  last_seen TIMESTAMP NOT NULL DEFAULT NOW(),
  request_count INTEGER DEFAULT 1,
  
  UNIQUE(user_id, region)
);

CREATE INDEX idx_user_region_history_user ON user_region_history(user_id, last_seen DESC);
```

## Load Testing & Failure Scenarios

### 1. Load Testing Plan

```typescript
// Load test scenarios
const loadTestScenarios = [
  {
    name: 'Peak Traffic - Normal Operation',
    duration: '10min',
    rps: 100000, // 100K requests/sec
    operations: {
      tokenValidation: 0.70,  // 70% reads (API calls)
      tokenRefresh: 0.25,     // 25% refresh operations
      logout: 0.05            // 5% logout (blacklist writes)
    },
    assertions: {
      p99Latency: '<50ms',
      errorRate: '<0.01%',
      redisHitRate: '>99.5%'
    }
  },
  
  {
    name: 'Redis Failure - Circuit Breaker Activation',
    duration: '5min',
    setup: 'Stop Redis at t=60s, restart at t=180s',
    rps: 50000,
    operations: {
      tokenValidation: 0.80,
      tokenRefresh: 0.15,
      logout: 0.05
    },
    assertions: {
      circuitBreakerOpens: '<10s after Redis down',
      fallbackLatency: '<100ms p99',
      errorRate: '<1%',
      recoveryTime: '<30s after Redis up',
      noDataLoss: 'All blacklist entries in Postgres'
    }
  },
  
  {
    name: 'Postgres Connection Pool Exhaustion',
    duration: '3min',
    setup: 'max_connections=100, 20 app instances',
    rps: 10000,
    operations: {
      // Force all requests to Postgres (Redis disabled)
      tokenValidation: 0.90,
      tokenRefresh: 0.10
    },
    assertions: {
      connectionPoolUtilization: '<80%',
      p99Latency: '<200ms',
      errorRate: '<5%',
      noConnectionLeaks: 'Pool size stable'
    }
  },
  
  {
    name: 'Circuit Breaker Flapping',
    duration: '10min',
    setup: 'Intermittent Redis failures (30s down, 30s up)',
    rps: 50000,
    operations: {
      tokenValidation: 0.80,
      tokenRefresh: 0.15,
      logout: 0.05
    },
    assertions: {
      circuitBreakerFlaps: '<5 times',
      halfOpenDuration: '<30s',
      errorRate: '<2%',
      cacheCoherence: 'Local cache syncs after recovery'
    }
  },
  
  {
    name: 'Cross-Instance Rate Limit Bypass',
    duration: '5min',
    setup: '10 app instances, rate limit 100 req/min per user',
    rps: 5000,
    operations: {
      // Single user attacking across all instances
      singleUserAttack: true,
      targetRate: 1000 // 10x rate limit
    },
    assertions: {
      effectiveRateLimit: '<150 req/min', // Allow 50% overage
      postgresSync: 'Within 10 seconds',
      blockAfterSync: 'Within 1 request'
    }
  },
  
  {
    name: 'Cross-Region Token Refresh',
    duration: '10min',
    setup: 'Users refresh from different region than login',
    rps: 10000,
    operations: {
      loginRegion: 'us-east',
      refreshRegion: 'eu-west',
      percentCrossRegion: 50
    },
    assertions: {
      crossRegionLatency: '<200ms p99',
      tokenReuseDetection: '100%',
      blacklistPropagation: '<500ms p99',
      noFalsePositives: 'Zero legitimate refreshes blocked'
    }
  },
  
  {
    name: 'Bloom Filter False Positive Rate',
    duration: '30min',
    setup: '1M active tokens, 100K blacklisted',
    rps: 100000,
    operations: {
      tokenValidation: 1.0
    },
    assertions: {
      bloomFalsePositiveRate: '<0.01%',
      postgresCheckRate: '<10 req/s',
      noFalseNegatives: 'Zero blacklisted tokens accepted'
    }
  }
];

// Chaos engineering scenarios
const chaosScenarios = [
  {
    name: 'Network Partition - Region Isolation',
    setup: 'Isolate EU-WEST region for 60 seconds',
    expectedBehavior: [
      'EU-WEST continues serving from local Redis + Postgres replica',
      'New blacklists in US-EAST do not propagate to EU-WEST',
      'High-risk operations in EU-WEST check PRIMARY Postgres',
      'After partition heals, blacklists propagate within 5 seconds'
    ]
  },
  
  {
    name: 'Postgres Primary Failover',
    setup: 'Promote replica to primary (30s downtime)',
    expectedBehavior: [
      'Token refreshes fail during failover window',
      'Token validation continues (cached data)',
      'After promotion, refreshes resume within 10 seconds',
      'No token reuse vulnerabilities introduced'
    ]
  },
  
  {
    name: 'Memory Pressure - Cache Eviction',
    setup: 'Fill LRU cache to capacity, continue adding entries',
    expectedBehavior: [
      'LRU evicts oldest entries',
      'Cache hit rate remains >95%',
      'No memory leak (heap size stable)',
      'Evicted entries refetched from Redis/Postgres'
    ]
  }
];
```

### 2. Load Testing Implementation

```typescript
// Load testing harness using k6 or artillery
import { check, group, sleep } from 'k6';
import http from 'k6/http';

export const options = {
  stages: [
    { duration: '2m', target: 50000 }, // Ramp up
    { duration: '5m', target: 100000 }, // Peak
    { duration: '2m', target: 0 }     // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(99)<50'],
    http_req_failed: ['rate<0.0001'],
    'circuit_breaker_open': ['count<1']
  }
};

export default function() {
  const scenario = Math.random();
  
  if (scenario < 0.70) {
    // Token validation (70% of traffic)
    testTokenValidation();
  } else if (scenario < 0.95) {
    // Token refresh (25% of traffic)
    testTokenRefresh();
  } else {
    // Logout (5% of traffic)
    testLogout();
  }
  
  sleep(Math.random() * 2); // Random delay 0-2s
}

function testTokenValidation() {
  const token = __ENV.TEST_ACCESS_TOKEN;
  
  const res = http.get('https://api.example.com/protected', {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'latency < 50ms': (r) => r.timings.duration < 50,
    'cache hit': (r) => r.headers['X-Cache-Layer'] === 'redis'
  });
}

function testTokenRefresh() {
  const refreshToken = __ENV.TEST_REFRESH_TOKEN;
  
  const res = http.post('https://api.example.com/auth/refresh', 
    JSON.stringify({ refreshToken }),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(res, {
    'status is 200': (r) => r.status === 200,
    'returns new tokens': (r) => r.json('accessToken') !== undefined,
    'latency < 100ms': (r) => r.timings.duration < 100
  });
}

// Failure injection for chaos testing
export function injectRedisFailure() {
  // Use Kubernetes pod deletion or network policy
  exec(`kubectl delete pod -l app=redis-cache -n production`);
  
  sleep(10); // Wait for circuit breaker to trip
  
  // Verify fallback behavior
  const res = http.get('https://api.example.com/protected', {
    headers: { 'Authorization': `Bearer ${__ENV.TEST_ACCESS_TOKEN}` }
  });
  
  check(res, {
    'fallback successful': (r) => r.status === 200,
    'postgres fallback used': (r) => r.headers['X-Cache-Layer'] === 'postgres'
  });
}
```

## Operational Runbook

### 1. Incident Response Playbooks

```yaml
# Runbook: Redis Unavailable (Circuit Breaker Open)

incident_type: "Redis Unavailable"
severity: P2 (High)
detection: Alert "RedisCircuitBreakerOpen" fires

immediate_actions:
  - verify_fallback:
      cmd: "curl https://api.example.com/health/fallback"
      expected: '{"status":"degraded","fallback":"postgres","latency_p99":150}'
      
  - check_postgres_load:
      cmd: "SELECT count(*) FROM pg_stat_activity WHERE state = 'active'"
      threshold: "< 80% of max_connections"
      
  - verify_no_data_loss:
      cmd: "SELECT COUNT(*) FROM token_blacklist WHERE blacklisted_at > NOW() - INTERVAL '5 minutes'"
      compare_with: "Redis blacklist count (should match)"

investigation:
  - check_redis_health:
      - "kubectl get pods -n production -l app=redis"
      - "kubectl logs -n production -l app=redis --tail=100"
      - "redis-cli -h redis.internal PING"
      
  - check_sentinel_status:
      - "redis-cli -h sentinel.internal -p 26379 SENTINEL masters"
      - "redis-cli -h sentinel.internal -p 26379 SENTINEL slaves auth-master"
      
  - check_network:
      - "kubectl get networkpolicies -n production"
      - "traceroute redis.internal"

mitigation:
  - if_redis_pod_crash:
      action: "Kubernetes should auto-restart"
      verify: "Wait 30s, check if circuit breaker closes"
      
  - if_sentinel_failover:
      action: "Wait for automatic failover (< 30s)"
      verify: "SENTINEL masters shows new master"
      
  - if_persistent_failure:
      action: "Scale Postgres read replicas"
      cmd: "kubectl scale deployment postgres-replica --replicas=5"

recovery_verification:
  - circuit_breaker_closed:
      query: "circuit_breaker_state{service='redis'} == 0"
      
  - latency_normal:
      query: "histogram_quantile(0.99, cache_get_latency) < 10"
      
  - error_rate_normal:
      query: "rate(http_requests_total{status=~'5..'}[5m]) < 0.001"

post_mortem:
  - analyze_root_cause: true
  - update_circuit_breaker_thresholds: "if flapping observed"
  - review_postgres_capacity: "if connection pool saturated"
```

```yaml
# Runbook: Bloom Filter False Positive Rate Spike

incident_type: "Bloom Filter False Positive Rate High"
severity: P3 (Medium)
detection: Alert "BloomFilterFalsePositiveRateHigh" fires

immediate_actions:
  - check_metrics:
      query: "rate(auth_bloom_filter_false_positive_total[5m])"
      threshold: "> 0.01%"
      
  - verify_no_false_negatives:
      cmd: "SELECT COUNT(*) FROM security_events WHERE event_type = 'BLACKLISTED_TOKEN_ACCEPTED' AND created_at > NOW() - INTERVAL '5 minutes'"
      expected: "0"

investigation:
  - check_bloom_filter_size:
      cmd: "curl http://api.example.com/internal/bloom-filter/stats"
      expected: '{"entries":100000,"capacity":1000000,"load_factor":0.1}'
      
  - check_sync_lag:
      cmd: "SELECT MAX(NOW() - blacklisted_at) FROM token_blacklist"
      threshold: "< 60 seconds"
      
  - analyze_blacklist_growth:
      query: "rate(token_blacklist_inserts_total[1h])"
      compare_with: "Historical average"

mitigation:
  - if_overloaded:
      condition: "load_factor > 0.8"
      action: "Rebuild bloom filter with larger capacity"
      cmd: "curl -X POST http://api.example.com/internal/bloom-filter/rebuild?capacity=10000000"
      
  - if_sync_lag:
      condition: "sync lag > 60s"
      action: "Trigger immediate sync from Postgres"
      cmd: "curl -X POST http://api.example.com/internal/bloom-filter/sync"

recovery_verification:
  - false_positive_rate_normal:
      query: "rate(auth_bloom_filter_false_positive_total[5m]) < 0.0001"
      
  - no_security_incidents:
      cmd: "SELECT COUNT(*) FROM security_events WHERE severity = 'HIGH' AND created_at > NOW() - INTERVAL '10 minutes'"
      expected: "0"

prevention:
  - implement_auto_scaling:
      description: "Automatically resize bloom filter when load_factor > 0.7"
      
  - add_capacity_alerts:
      alert: "BloomFilterCapacityWarning"
      threshold: "load_factor > 0.6"
```

```yaml
# Runbook: Postgres Fallback Latency High

incident_type: "Postgres Fallback Latency Exceeds SLA"
severity: P2 (High)
detection: Alert "PostgresFallbackLatencyHigh" fires

immediate_actions:
  - check_sla_breach:
      query: "histogram_quantile(0.99, blacklist_check_latency{source='postgres'}) > 200"
      
  - verify_connection_pool:
      cmd: "SELECT count(*) FROM pg_stat_activity"
      threshold: "< max_connections * 0.8"
      
  - check_query_performance:
      cmd: "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10"

investigation:
  - analyze_slow_queries:
      cmd: "SELECT pid, query_start, state, query FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '1 second'"
      
  - check_index_usage:
      cmd: "SELECT schemaname, tablename, indexname, idx_scan FROM pg_stat_user_indexes WHERE schemaname = 'public' AND idx_scan = 0"
      
  - check_table_bloat:
      cmd: "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC"

mitigation:
  - if_connection_pool_exhausted:
      action: "Increase connection pool size"
      cmd: "kubectl set env deployment/api-server DB_POOL_SIZE=200"
      
  - if_missing_index:
      action: "Create missing indexes"
      cmd: "psql -c 'CREATE INDEX CONCURRENTLY idx_missing ON table(column)'"
      
  - if_table_bloat:
      action: "Run VACUUM ANALYZE"
      cmd: "psql -c 'VACUUM ANALYZE token_blacklist'"
      
  - if_query_slow:
      action: "Optimize query or add caching"
      review: "src/auth/blacklist-check.ts"

emergency_mitigation:
  - reduce_postgres_checks:
      description: "Temporarily reduce risk threshold for Postgres checks"
      cmd: "kubectl set env deployment/api-server BLACKLIST_CHECK_RISK_THRESHOLD=high"
      impact: "Medium/low risk operations skip Postgres check (accept stale cache)"
      rollback: "After Postgres performance recovers"

recovery_verification:
  - latency_within_sla:
      query: "histogram_quantile(0.99, blacklist_check_latency{source='postgres'}) < 100"
      
  - connection_pool_healthy:
      cmd: "SELECT count(*) FROM pg_stat_activity WHERE state = 'idle'"
      expected: "> 20% of pool size"

post_mortem:
  - review_query_plans: true
  - optimize_indexes: true
  - consider_read_replicas: "if load is consistently high"
  - review_cache_ttl: "increase TTL to reduce Postgres load"
```

### 2. Monitoring Dashboard

```typescript
// Grafana dashboard JSON
const authSystemDashboard = {
  title: "JWT Auth System - Production Monitoring",
  panels: [
    {
      title: "Request Rate by Operation",
      targets: [
        'sum(rate(http_requests_total{service="auth"}[5m])) by (operation)',
      ],
      visualization: "timeseries"
    },
    
    {
      title: "Cache Hit Rate by Layer",
      targets: [
        'sum(rate(cache_hit_total[5m])) by (layer) / sum(rate(cache_requests_total[5m])) by (layer)',
      ],
      visualization: "gauge",
      thresholds: [
        { value: 0.95, color: "green" },
        { value: 0.90, color: "yellow" },
        { value: 0.85, color: "red" }
      ]
    },
    
    {
      title: "Circuit Breaker State",
      targets: [
        'circuit_breaker_state{service="redis"}',
      ],
      visualization: "stat",
      mappings: [
        { value: 0, text: "CLOSED", color: "green" },
        { value: 0.5, text: "HALF_OPEN", color: "yellow" },
        { value: 1, text: "OPEN", color: "red" }
      ]
    },
    
    {
      title: "Token Validation Latency (p50, p99, p99.9)",
      targets: [
        'histogram_quantile(0.50, sum(rate(auth_token_validation_latency_bucket[5m])) by (le))',
        'histogram_quantile(0.99, sum(rate(auth_token_validation_latency_bucket[5m])) by (le))',
        'histogram_quantile(0.999, sum(rate(auth_token_validation_latency_bucket[5m])) by (le))',
      ],
      visualization: "timeseries"
    },
    
    {
      title: "Postgres Connection Pool Utilization",
      targets: [
        'pg_stat_activity_count / pg_settings_max_connections',
      ],
      visualization: "gauge",
      thresholds: [
        { value: 0.80, color: "red" },
        { value: 0.60, color: "yellow" },
        { value: 0.40, color: "green" }
      ]
    },
    
    {
      title: "Blacklist Propagation Latency (Cross-Region)",
      targets: [
        'histogram_quantile(0.99, sum(rate(blacklist_cross_region_propagation_bucket[5m])) by (source, target, le))',
      ],
      visualization: "heatmap"
    },
    
    {
      title: "Security Events (Last 1 Hour)",
      targets: [
        'sum(increase(security_events_total[1h])) by (event_type)',
      ],
      visualization: "table"
    },
    
    {
      title: "Bloom Filter Statistics",
      targets: [
        'bloom_filter_entries',
        'bloom_filter_capacity',
        'bloom_filter_load_factor',
        'rate(bloom_filter_false_positive_total[5m])',
      ],
      visualization: "stat"
    }
  ],
  
  alerts: [
    {
      name: "RedisCircuitBreakerOpen",
      condition: "circuit_breaker_state{service='redis'} == 1",
      for: "1m",
      severity: "critical"
    },
    {
      name: "HighPostgresFallback",
      condition: "rate(cache_fallback_postgres_total[5m]) > 100",
      for: "5m",
      severity: "warning"
    },
    {
      name: "TokenValidationLatencyHigh",
      condition: "histogram_quantile(0.99, auth_token_validation_latency_bucket) > 100",
      for: "5m",
      severity: "warning"
    },
    {
      name: "BloomFilterFalsePositiveRateHigh",
      condition: "rate(bloom_filter_false_positive_total[5m]) > 0.0001",
      for: "10m",
      severity: "warning"
    },
    {
      name: "PostgresConnectionPoolSaturated",
      condition: "pg_stat_activity_count / pg_settings_max_connections > 0.8",
      for: "5m",
      severity: "critical"
    },
    {
      name: "CrossRegionBlacklistPropagationSlow",
      condition: "histogram_quantile(0.99, blacklist_cross_region_propagation_bucket) > 1000",
      for: "5m",
      severity: "warning"
    },
    {
      name: "SecurityEventSpike",
      condition: "rate(security_events_total{severity='HIGH'}[5m]) > 10",
      for: "2m",
      severity: "critical"
    }
  ]
};
```

### 3. Health Check Endpoints

```typescript
// Health check implementation
app.get('/health', async (req, res) => {
  const health = {
    status: 'healthy',
    timestamp: new Date().toISOString(),
    version: process.env.APP_VERSION,
    uptime: process.uptime(),
    
    components: {
      redis: await checkRedisHealth(),
      postgres: await checkPostgresHealth(),
      bloomFilter: await checkBloomFilterHealth()
    },
    
    metrics: {
      circuitBreakerState: circuitBreaker.getState(),
      cacheHitRate: await getCacheHitRate(),
      requestRate: await getRequestRate(),
      errorRate: await getErrorRate()
    }
  };
  
  // Overall health based on components
  if (health.components.redis.status === 'unhealthy' && 
      health.components.postgres.status === 'unhealthy') {
    health.status = 'unhealthy';
    return res.status(503).json(health);
  }
  
  if (health.components.redis.status === 'unhealthy' ||
      health.components.postgres.status === 'degraded') {
    health.status = 'degraded';
    return res.status(200).json(health);
  }
  
  res.status(200).json(health);
});

async function checkRedisHealth(): Promise<ComponentHealth> {
  try {
    const start = Date.now();
    await redis.ping();
    const latency = Date.now() - start;
    
    return {
      status: latency < 10 ? 'healthy' : 'degraded',
      latency,
      message: 'Redis operational'
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      latency: null,
      message: `Redis unavailable: ${error.message}`
    };
  }
}

async function checkPostgresHealth(): Promise<ComponentHealth> {
  try {
    const start = Date.now();
    await db.query('SELECT 1');
    const latency = Date.now() - start;
    
    const poolSize = await db.query('SELECT count(*) FROM pg_stat_activity');
    const maxConnections = await db.query('SHOW max_connections');
    const utilization = poolSize.rows[0].count / maxConnections.rows[0].max_connections;
    
    return {
      status: latency < 50 && utilization < 0.8 ? 'healthy' : 'degraded',
      latency,
      metadata: {
        poolUtilization: `${(utilization * 100).toFixed(1)}%`,
        activeConnections: poolSize.rows[0].count
      },
      message: 'Postgres operational'
    };
  } catch (error) {
    return {
      status: 'unhealthy',
      latency: null,
      message: `Postgres unavailable: ${error.message}`
    };
  }
}

async function checkBloomFilterHealth(): Promise<ComponentHealth> {
  const stats = blacklistBloomFilter.getStats();
  const loadFactor = stats.entries / stats.capacity;
  
  return {
    status: loadFactor < 0.8 ? 'healthy' : 'degraded',
    metadata: {
      entries: stats.entries,
      capacity: stats.capacity,
      loadFactor: `${(loadFactor * 100).toFixed(1)}%`,
      lastSync: stats.lastSync
    },
    message: loadFactor < 0.8 ? 'Bloom filter healthy' : 'Bloom filter approaching capacity'
  };
}

interface ComponentHealth {
  status: 'healthy' | 'degraded' | 'unhealthy';
  latency?: number | null;
  metadata?: Record<string, any>;
  message: string;
}
```