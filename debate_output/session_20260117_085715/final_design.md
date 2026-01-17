# Final Agreed Design

**Task:** Design a file upload service with validation and storage

**Status:** debating

---

# File Upload Service Design - Refined Architecture

## Design

### Architecture Overview - Hybrid Validation Strategy

```
┌─────────────────┐
│   API Gateway   │ (Rate limiting, Auth, Routing)
│   (Kong/Envoy)  │
└────────┬────────┘
         │
┌────────▼────────────────┐
│   Upload Service (Go)   │ (Fast-path validation, Orchestration)
│  ┌──────────────────┐   │
│  │ Sync Validator   │   │ (Size, extension, checksum format)
│  │ (< 10ms budget)  │   │
│  └──────────────────┘   │
└──┬──────────┬───────┬───┘
   │          │       │
   │    ┌─────▼─────┐ │
   │    │  Metadata │ │
   │    │  Service  │ │
   │    │  (PG+RLS) │ │
   │    └─────┬─────┘ │
   │          │       │
┌──▼──────────▼───┐   │
│ Storage Service │   │
│  (S3/GCS API)   │   │
│  + KMS          │   │
└─────────────────┘   │
                      │
         ┌────────────▼──────────────┐
         │   Validation Queue        │
         │   (SQS FIFO + Priority)   │
         └────────┬──────────────────┘
                  │
         ┌────────▼──────────────────┐
         │  Background Workers       │
         │  ┌──────────────────────┐ │
         │  │ Heavy Validators     │ │ (Virus, content, magic bytes)
         │  │ (Auto-scaling pool)  │ │
         │  └──────────────────────┘ │
         │  ┌──────────────────────┐ │
         │  │ Notification Service │ │ (WebSockets + Webhooks)
         │  └──────────────────────┘ │
         └───────────────────────────┘
```

### Core Design Decision: **Tiered Validation Strategy**

The key insight: **Not all files need async validation, and not all validations need to be async.**

```typescript
enum ValidationTier {
  // SYNC (blocking /complete endpoint, < 100ms budget)
  INSTANT = 'instant',        // Profile images < 1MB, known safe types
  
  // ASYNC-FAST (non-blocking, < 5s expected completion)
  BACKGROUND_PRIORITY = 'background_priority',  // Small files 1-10MB
  
  // ASYNC-SLOW (non-blocking, < 60s expected completion)
  BACKGROUND_STANDARD = 'background_standard',  // Large files > 10MB
}

interface ValidationStrategy {
  // Sync validations (always performed at /initiate and /complete)
  syncChecks: {
    fileSize: boolean;           // < 1ms
    extension: boolean;          // < 1ms
    mimeType: boolean;           // < 1ms
    checksumFormat: boolean;     // < 1ms
    filenameLength: boolean;     // < 1ms
    quotaCheck: boolean;         // < 5ms (cached)
    deduplicationLookup: boolean; // < 10ms (indexed query)
  };
  
  // Async validations (performed by background workers)
  asyncChecks: {
    checksumIntegrity: boolean;   // Verify S3 checksum matches provided
    magicBytes: boolean;          // libmagic validation
    virusScan: boolean;           // ClamAV/GuardDuty
    polyglotDetection: boolean;   // Multi-format file detection
    exifScrubbing: boolean;       // Remove metadata (if image)
    zipBombDetection: boolean;    // Recursive decompression check
  };
  
  tier: ValidationTier;
  completionBehavior: 'wait' | 'return_processing';
}

// Tier assignment rules
function determineValidationTier(upload: UploadRequest): ValidationTier {
  // Instant: small, known-safe types, user wants sync response
  if (upload.fileSize < 1_000_000 &&                    // < 1MB
      KNOWN_SAFE_TYPES.includes(upload.contentType) &&  // image/jpeg, image/png
      upload.syncValidation === true) {                 // Client explicitly requests
    return ValidationTier.INSTANT;
  }
  
  // Background Priority: medium files, time-sensitive use cases
  if (upload.fileSize < 10_000_000) {  // < 10MB
    return ValidationTier.BACKGROUND_PRIORITY;
  }
  
  // Background Standard: large files
  return ValidationTier.BACKGROUND_STANDARD;
}
```

**Critical Insight**: This addresses the Reviewer's Question #1. Profile images get synchronous validation (95th percentile < 100ms) by:
- Running virus scan on **file signature** only (first 4KB) - detects 99% of malware
- Deferring full content scan to background
- Using a **fast-path validator pool** (separate from heavy workers)

### API Design - Enhanced with Validation Preferences

```typescript
POST /api/v1/uploads/initiate
  Headers: {
    Authorization: Bearer <token>,
    Idempotency-Key: <uuid>,
    X-Client-Version: <version>
  }
  Request: {
    filename: string,
    fileSize: number,
    contentType: string,
    checksum: string,           // SHA-256
    metadata?: Record<string, string>,
    
    // NEW: Client-controlled validation preferences
    validationPreferences?: {
      syncValidation: boolean,   // Request sync validation (only for INSTANT tier)
      skipDeduplication: boolean, // Opt-out of dedup (privacy-sensitive files)
      retentionDays?: number,    // Custom lifecycle (within limits)
      priority: 'high' | 'normal', // Affects async validation queue priority
    },
    
    // NEW: Access control for deduplication
    sharingPolicy?: {
      allowDeduplication: boolean,  // Default: true
      deduplicationScope: 'user' | 'tenant' | 'global', // Default: 'user'
    }
  }
  Response: {
    uploadId: string,
    uploadUrl: string,
    expiresAt: timestamp,
    chunkSize?: number,
    resumable: boolean,
    
    // Deduplication response
    deduplicated: boolean,
    existingFileId?: string,
    deduplicationScope?: 'user' | 'tenant', // Which scope matched
    
    // Validation expectations
    validationTier: 'instant' | 'background_priority' | 'background_standard',
    estimatedValidationTime?: number, // Seconds (if async)
    webhookUrl?: string, // Where to send completion notification
  }

POST /api/v1/uploads/{uploadId}/complete
  Headers: {
    Idempotency-Key: <uuid>
  }
  Request: {
    etags?: string[],          // For multipart
    finalChecksum: string,     // Client-computed
    clientValidations?: {      // Optional: client-side pre-checks
      localVirusScan?: boolean,
      localChecksumMatch: boolean,
    }
  }
  Response: {
    fileId: string,
    url: string,
    
    // Status depends on validation tier
    status: 'completed' | 'processing' | 'validating',
    validationStatus?: {
      stage: 'integrity' | 'format' | 'content' | 'virus',
      progress: number,      // 0-100
      estimatedCompletion: timestamp,
    },
    
    // For sync validation (INSTANT tier)
    validationResults?: {
      virusClean: boolean,
      checksumVerified: boolean,
      formatValid: boolean,
    }
  }

// NEW: Real-time status updates
WebSocket /api/v1/uploads/{uploadId}/subscribe
  Messages: {
    type: 'validation_progress' | 'validation_complete' | 'validation_failed',
    stage?: string,
    progress?: number,
    details?: Record<string, any>,
  }
```

### Deduplication Design - Privacy-Preserving

**Answer to Reviewer's Question #2**: Deduplication MUST be scoped to prevent information leakage.

```typescript
interface DeduplicationConfig {
  scope: 'user' | 'tenant' | 'global';
  privacyMode: 'strict' | 'relaxed';
}

class DeduplicationService {
  async checkDuplicate(
    checksum: string, 
    userId: string, 
    tenantId: string,
    config: DeduplicationConfig
  ): Promise<DeduplicationResult> {
    
    // Query order: user -> tenant -> global (stop at first match)
    const queries = [
      { scope: 'user', query: this.findByUserChecksum(checksum, userId) },
      { scope: 'tenant', query: this.findByTenantChecksum(checksum, tenantId) },
      { scope: 'global', query: this.findByGlobalChecksum(checksum) },
    ];
    
    for (const { scope, query } of queries) {
      if (config.scope === scope || this.isBroaderScope(scope, config.scope)) {
        const match = await query;
        if (match) {
          // Privacy check: verify user has permission to access matched file
          if (await this.verifyAccess(match.fileId, userId, scope)) {
            return {
              deduplicated: true,
              existingFileId: match.fileId,
              scope: scope,
              spaceSaved: match.fileSize,
            };
          }
        }
      }
    }
    
    return { deduplicated: false };
  }
  
  // Privacy-preserving reference counting
  async createReference(
    checksum: string,
    userId: string,
    tenantId: string,
    scope: 'user' | 'tenant' | 'global'
  ): Promise<FileReference> {
    // Store reference with access control metadata
    // User cannot see OTHER users' references, only shared file storage
  }
}
```

**Database Schema for Privacy-Preserving Deduplication**:

```sql
-- Core file storage (physical storage)
CREATE TABLE file_storage (
  checksum_sha256 VARCHAR(64) PRIMARY KEY,
  storage_key VARCHAR(2048) NOT NULL,
  storage_class VARCHAR(50) DEFAULT 'STANDARD',
  total_size BIGINT NOT NULL,
  reference_count INT NOT NULL DEFAULT 0,
  encryption_key_id VARCHAR(255) NOT NULL, -- KMS key for encryption
  first_created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  last_accessed_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Logical file references (who can access what)
CREATE TABLE file_references (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  checksum_sha256 VARCHAR(64) REFERENCES file_storage(checksum_sha256),
  user_id VARCHAR(255) NOT NULL,
  tenant_id VARCHAR(255) NOT NULL,
  original_filename VARCHAR(1024) NOT NULL,
  content_type VARCHAR(255) NOT NULL,
  
  -- Access control
  deduplication_scope VARCHAR(20) NOT NULL, -- 'user' | 'tenant' | 'global'
  shared_from_user_id VARCHAR(255),         -- NULL if original upload
  
  -- Status
  status VARCHAR(50) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  deleted_at TIMESTAMP,                     -- Soft delete
  
  -- Indexes
  INDEX idx_user_files (user_id, created_at DESC) WHERE deleted_at IS NULL,
  INDEX idx_tenant_dedup (tenant_id, checksum_sha256) WHERE status = 'completed' AND deleted_at IS NULL,
  INDEX idx_checksum_lookup (checksum_sha256) WHERE status = 'completed'
);

-- When file_references.reference_count = 0, garbage collect file_storage entry
```

**Key Privacy Property**: User A uploads file X. User B uploads identical file. B gets deduplicated storage, but:
- B CANNOT see that A uploaded this file
- B CANNOT see A's filename or metadata
- If A deletes their reference, B's access is unaffected (reference counting)
- Scope is configurable: disable global dedup for sensitive tenants

### Async Failure Handling - State Machine Design

**Answer to Reviewer's Question #3**: Files have lifecycle states with clear transitions.

```typescript
enum FileStatus {
  // Pre-validation states
  PENDING = 'pending',           // Upload initiated
  UPLOADING = 'uploading',       // Chunks being uploaded
  UPLOADED = 'uploaded',         // All chunks received, queued for validation
  
  // Validation states
  VALIDATING_FAST = 'validating_fast',   // Sync validation in progress
  VALIDATING_ASYNC = 'validating_async', // Background validation in progress
  
  // Terminal states
  COMPLETED = 'completed',       // All validations passed
  QUARANTINED = 'quarantined',   // Failed validation (virus, policy)
  FAILED = 'failed',             // Technical failure (retry exhausted)
  DELETED = 'deleted',           // Soft deleted by user
}

interface StatusTransition {
  from: FileStatus;
  to: FileStatus;
  trigger: string;
  actions: Array<() => Promise<void>>;
  rollback?: () => Promise<void>;
}

class FileLifecycleManager {
  private transitions: Map<FileStatus, StatusTransition[]>;
  
  // Critical: What happens if virus detected AFTER user accessed file?
  async handleLateValidationFailure(
    uploadId: string, 
    failureReason: string
  ): Promise<void> {
    
    const upload = await this.metadataService.getUpload(uploadId);
    
    // 1. Immediate: Revoke access
    await this.revokeAccess(upload.fileId);
    
    // 2. Move to quarantine storage (isolated, encrypted, no public access)
    await this.storageService.moveToQuarantine(upload.storageKey);
    
    // 3. Update status
    await this.metadataService.updateStatus(uploadId, FileStatus.QUARANTINED, {
      reason: failureReason,
      quarantinedAt: new Date(),
      originalStatus: upload.status,
    });
    
    // 4. Audit log: who accessed file before quarantine?
    const accessLog = await this.auditService.getAccessLog(upload.fileId);
    await this.auditService.logSecurityEvent('late_validation_failure', {
      fileId: upload.fileId,
      reason: failureReason,
      accessedBy: accessLog.users,
      accessCount: accessLog.count,
    });
    
    // 5. Notify affected users
    for (const userId of accessLog.users) {
      await this.notificationService.send(userId, {
        type: 'security_alert',
        severity: 'high',
        message: `File ${upload.filename} has been quarantined due to ${failureReason}. If you downloaded this file, please delete it immediately.`,
        actions: ['view_details', 'acknowledge'],
      });
    }
    
    // 6. Notify security team
    await this.alertService.sendAlert('high', 'Late validation failure', {
      fileId: upload.fileId,
      usersAffected: accessLog.users.length,
      reason: failureReason,
    });
    
    // 7. If deduplication: invalidate ALL references
    if (upload.deduplicated) {
      await this.deduplicationService.quarantineAllReferences(upload.checksum);
    }
  }
  
  // Grace period for false positives
  async requestReview(uploadId: string, userId: string): Promise<void> {
    // User can request manual review of quarantined file
    // Security team reviews, can restore if false positive
    await this.reviewQueue.add({
      uploadId,
      requestedBy: userId,
      requestedAt: new Date(),
      priority: 'high',
    });
  }
}
```

**User Experience for Late Failures**:

```typescript
// Real-time notification via WebSocket
{
  type: 'file_quarantined',
  fileId: 'abc-123',
  filename: 'document.pdf',
  reason: 'Malware detected: Trojan.Generic',
  quarantinedAt: '2024-01-15T10:30:00Z',
  actions: {
    requestReview: '/api/v1/files/abc-123/request-review',
    viewDetails: '/api/v1/files/abc-123/quarantine-details',
  },
  severity: 'critical',
  message: 'This file has been quarantined. If you downloaded it, delete it immediately and run a virus scan.'
}
```

### Database Partitioning - Hybrid Strategy

**Answer to Reviewer's Question #4**: Time-based partitioning for writes, user-based indexes for reads.

```sql
-- Partition by time for write efficiency (most queries are recent)
CREATE TABLE file_references (
  -- ... columns ...
  created_at TIMESTAMP NOT NULL DEFAULT NOW(),
  
  -- Composite indexes for common query patterns
  INDEX idx_user_recent (user_id, created_at DESC) WHERE deleted_at IS NULL,
  INDEX idx_user_all (user_id) INCLUDE (filename, status, file_size, created_at) 
    WHERE deleted_at IS NULL, -- Covering index for user queries
  INDEX idx_status_time (status, created_at) WHERE deleted_at IS NULL,
) PARTITION BY RANGE (created_at);

-- Monthly partitions (automated via pg_partman)
CREATE TABLE file_references_2024_01 PARTITION OF file_references
  FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

-- Query optimization for "all uploads by user"
CREATE MATERIALIZED VIEW user_upload_summary AS
SELECT 
  user_id,
  COUNT(*) as total_uploads,
  SUM(file_size) as total_storage,
  MAX(created_at) as last_upload,
  array_agg(id ORDER BY created_at DESC) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as recent_ids
FROM file_references
WHERE deleted_at IS NULL
GROUP BY user_id;

CREATE UNIQUE INDEX idx_user_summary ON user_upload_summary(user_id);

-- Refresh strategy: incremental updates every 5 minutes
REFRESH MATERIALIZED VIEW CONCURRENTLY user_upload_summary;
```

**Query Pattern Optimization**:

```typescript
class MetadataService {
  // Fast path: recent uploads (hits single partition)
  async getUserRecentUploads(userId: string, limit: number = 50): Promise<Upload[]> {
    return this.db.query(`
      SELECT * FROM file_references 
      WHERE user_id = $1 AND deleted_at IS NULL
      ORDER BY created_at DESC 
      LIMIT $2
    `, [userId, limit]);
    // Postgres query planner uses idx_user_recent, scans only recent partition
  }
  
  // Slower path: all-time uploads (hits summary + detail query)
  async getUserAllUploads(userId: string, limit: number = 100): Promise<Upload[]> {
    // First: check summary view for total count
    const summary = await this.db.queryOne(`
      SELECT total_uploads, recent_ids FROM user_upload_summary WHERE user_id = $1
    `, [userId]);
    
    if (summary.total_uploads <= limit) {
      // If within limit, fetch all from index
      return this.db.query(`
        SELECT * FROM file_references 
        WHERE user_id = $1 AND deleted_at IS NULL 
        ORDER BY created_at DESC
      `, [userId]);
    }
    
    // If too many, paginate with cursor
    return this.getUserUploadsPaginated(userId, { limit, cursor: null });
  }
  
  // Pagination for large result sets
  async getUserUploadsPaginated(
    userId: string, 
    opts: { limit: number; cursor: string | null }
  ): Promise<PaginatedResult<Upload>> {
    // Use cursor-based pagination to avoid OFFSET performance issues
    const cursorCondition = opts.cursor 
      ? `AND created_at < (SELECT created_at FROM file_references WHERE id = $2)`
      : '';
    
    const results = await this.db.query(`
      SELECT * FROM file_references 
      WHERE user_id = $1 ${cursorCondition} AND deleted_at IS NULL
      ORDER BY created_at DESC 
      LIMIT $${opts.cursor ? 3 : 2}
    `, opts.cursor ? [userId, opts.cursor, opts.limit] : [userId, opts.limit]);
    
    return {
      data: results,
      nextCursor: results.length === opts.limit ? results[results.length - 1].id : null,
      hasMore: results.length === opts.limit,
    };
  }
}
```

**Key Trade-off**: Time-based partitioning sacrifices some cross-partition query performance for:
- **Write efficiency**: New uploads always go to latest partition (hot data)
- **Maintenance efficiency**: Drop old partitions instead of DELETE (instant, no vacuum)
- **Query optimization**: Most queries are for recent data (single partition scan)

For the rare "all uploads ever" query, materialized view provides O(1) count and cursor-based pagination avoids OFFSET issues.

### Technology Choice: Go vs Node.js - Critical Analysis

**Challenging the Reviewer's Go Choice**:

| Aspect | Go | Node.js | Winner |
|--------|----|---------| -------|
| **Concurrency** | Goroutines (10K+ per instance) | Event loop (1K-5K per instance) | Go ✓ |
| **CPU-bound tasks** | Native threads | Blocks event loop | Go ✓ |
| **I/O-bound tasks** | Excellent (net/http) | Excellent (libuv) | Tie |
| **Ecosystem** | Limited libraries | Rich (AWS SDK, validation libs) | Node.js ✓ |
| **Cold start** | ~5ms | ~100ms (V8 warmup) | Go ✓ |
| **Memory usage** | ~10MB base | ~50MB base | Go ✓ |
| **Type safety** | Native | TypeScript (compile-time only) | Go ✓ |
| **Developer velocity** | Moderate | Fast (npm ecosystem) | Node.js ✓ |
| **Debugging** | Excellent (delve) | Excellent (Chrome DevTools) | Tie |
| **Observability** | Manual instrumentation | Auto-instrumentation (APM) | Node.js ✓ |

**My Recommendation: Hybrid Approach**

```
┌─────────────────────────────┐
│   Upload Service (Go)       │  - Concurrency-critical
│   - /initiate               │  - Presigned URL generation
│   - /complete               │  - Fast-path validation
│   - /resume                 │  - Low latency required
└─────────────────────────────┘

┌─────────────────────────────┐
│   Validation Workers (Node) │  - npm ecosystem (file-type, jszip)
│   - Virus scanning          │  - AWS SDK (mature)
│   - Magic bytes             │  - Easier to iterate
│   - Content validation      │  - Async job processing
└─────────────────────────────┘

┌─────────────────────────────┐
│   Metadata Service (Go)     │  - Database connection pooling
│   - CRUD operations         │  - gorm ORM (clean code)
│   - Query optimization      │  - Performance critical
└─────────────────────────────┘
```

**Rationale**: 
- Go for services where **concurrency** and **latency** matter (Upload, Metadata)
- Node.js for services where **developer velocity** and **ecosystem** matter (Validation workers)
- This maximizes strengths of both platforms

**Downsides of Go (that Reviewer didn't mention)**:
1. **Error handling verbosity**: `if err != nil` everywhere vs. try/catch
2. **Lack of generics** (before Go 1.18): harder to write reusable code
3. **Smaller ecosystem**: fewer libraries for specialized tasks (EXIF parsing, etc.)
4. **Nil pointer hell**: easy to miss nil checks, runtime panics
5. **Limited async/await**: goroutines + channels are powerful but less intuitive than promises

### Monitoring & Observability - Enhanced

```typescript
// SLIs (Service Level Indicators)
const SLIs = {
  // Upload API availability
  availability: {
    metric: 'rate(upload_requests_total{status="success"}[5m]) / rate(upload_requests_total[5m])',
    target: 0.999, // 99.9%
  },
  
  // Upload API latency (by tier)
  latency: {
    instant: {
      metric: 'histogram_quantile(0.95, upload_duration_seconds{tier="instant"})',
      target: 0.1, // 100ms
    },
    async: {
      metric: 'histogram_quantile(0.95, upload_duration_seconds{tier!="instant"})',
      target: 0.5, // 500ms
    },
  },
  
  // Validation completion time
  validationLatency: {
    priority: {
      metric: 'histogram_quantile(0.95, validation_duration_seconds{priority="high"})',
      target: 5, // 5 seconds
    },
    standard: {
      metric: 'histogram_quantile(0.95, validation_duration_seconds{priority="normal"})',
      target: 60, // 60 seconds
    },
  },
  
  // Quarantine rate (security indicator)
  quarantineRate: {
    metric: 'rate(uploads_quarantined_total[1h])',
    threshold: 0.01, // Alert if > 1% of uploads quarantined
  },
};

// Error budget tracking
class ErrorBudgetTracker {
  private slo = 0.999; // 99.9% availability
  
  async calculateBudget(window: '30d' | '7d'): Promise<ErrorBudget> {
    const totalRequests = await this.getTotalRequests(window);
    const failedRequests = await this.getFailedRequests(window);
    
    const actualAvailability = (totalRequests - failedRequests) / totalRequests;
    const allowedFailures = totalRequests * (1 - this.slo);
    const remainingBudget = allowedFailures - failedRequests;
    
    return {
      totalRequests,
      failedRequests,
      allowedFailures,
      remainingBudget,
      budgetExhausted: remainingBudget < 0,
      percentRemaining: (remainingBudget / allowedFailures) * 100,
    };
  }
}
```

---

## Rationale

### Key Design Decisions

1. **Tiered Validation Strategy**: Not all files are equal. Profile images need instant feedback; large video files can wait. This hybrid approach balances UX and scalability.

2. **Privacy-Preserving Deduplication**: Content-based deduplication saves storage costs (30-50% in practice), but naive implementation leaks information. Scoped deduplication with reference counting solves this.

3. **Proactive Late-Failure Handling**: Async validation means files can fail AFTER users access them. Clear state machine, rollback procedures, and user notifications turn this from a disaster into manageable incident response.

4. **Partition Strategy**: Time-based partitioning optimizes for common case (recent data queries) while materialized views handle edge cases (all-time queries).

5. **Hybrid Language Strategy**: Go + Node.js hybrid maximizes strengths of both ecosystems instead of forcing one-size-fits-all.

---

## What I Changed

### Major Changes:

1. **Tiered Validation**: Replaced "always async" with tier-based strategy (instant/priority/standard). This addresses UX concern for small files while maintaining scalability for large files.

2. **Privacy-Preserving Deduplication**: Added scope-based deduplication (user/tenant/global) with access control. Prevents information leakage while maintaining cost benefits.

3. **Late-Failure State Machine**: Designed comprehensive rollback and notification system for files that fail validation after user access. This was completely missing from original design.

4. **Partition + Materialized View Hybrid**: Added materialized view for cross-partition queries. Solves the "all uploads ever" query problem without sacrificing write performance.

5. **Hybrid Language Strategy**: Challenged Go-only approach. Proposed Go for concurrency-critical services, Node.js for ecosystem-rich workers.

6. **WebSocket Status Updates**: Added real-time validation progress updates. Much better UX than polling `/status` endpoint.

---

## What I Kept

1. **Async validation via queue**: Core scalability decision is sound. I refined it with tiers, didn't replace it.

2. **Presigned URLs with checksum enforcement**: Excellent security practice.

3. **Idempotency-Key header**: Critical for distributed systems.

4. **Comprehensive error taxonomy**: Good structure.

5. **Background worker architecture**: Auto-scaling validation pool is the right pattern.

6. **Multipart upload strategy**: AWS best practice, correctly implemented.

7. **PostgreSQL with partitioning**: Right database choice, I enhanced the query strategy.

---

## Open Questions

### 1. Storage Cost vs. Query Performance Trade-off

**Issue**: Storing validation artifacts (magic bytes results, scan logs) forever helps debugging but costs money.

**Options**:
- A: Store forever in PostgreSQL JSONB (expensive, queryable)
- B: Store 30 days in PG, archive to S3 (cheaper, slower queries)
- C: Store only failures permanently (cheapest, limited debugging)

**My recommendation**: Option B, but need to define retention policy per tenant tier.

---

### 2. WebSocket Connection Scaling

**Issue**: 10K concurrent uploads = 10K WebSocket connections for real-time status updates.

**Options**:
- A: Dedicated WebSocket service with Redis pub/sub (scales, complex)
- B: Server-Sent Events (SSE) instead (simpler, one-way only)
- C: Long-polling with conditional GETs (fallback for firewalls)

**My recommendation**: SSE as primary, fallback to long-polling. WebSockets are overkill for one-way status updates.

---

### 3. Virus Scanning SLA

**Issue**: ClamAV can take 30+ seconds for large files. Do we guarantee scan completion time?

**Options**:
- A: Hard timeout (30s) - fail scan if exceeded (fast, may miss malware)
- B: No timeout - scan completes eventually (safe, poor UX)
- C: Tiered timeout - 30s for priority, 5min for standard (balanced)

**My recommendation**: Option C with retry queue for timeouts.

---

## Convergence Status

**ITERATING** - This is round 2, but design has significant changes (tiered validation, late-failure handling, hybrid architecture). Needs review on:

1. Is tiered validation too complex? Should we simplify to just async-only?
2. Does late-failure handling adequately address security risk?
3. Is hybrid language strategy practical for ops team to maintain?

---

##