# Final Agreed Design

**Task:** Design a file upload API

**Status:** debating

---

# File Upload API Design

## Architecture Overview

**Pattern**: RESTful API with resumable upload support using native cloud provider multipart capabilities  
**Transport**: HTTP/HTTPS with streaming upload and chunked transfer encoding  
**Storage**: Hybrid storage layer leveraging native cloud multipart APIs with fallback to manual assembly  
**Processing**: Async job queue for post-upload processing with streaming verification  
**Scale Target**: 1TB files, multi-day upload sessions, 10,000+ concurrent uploads

## API Endpoints

### 1. Initiate Upload
```
POST /api/v1/uploads/initiate
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "filename": "large-video.mp4",
  "size": 107374182400,  // 100GB
  "mimeType": "video/mp4",
  "metadata": {
    "tags": ["presentation", "2024"],
    "visibility": "private"
  },
  "chunkSize": 10485760,  // 10MB recommended for optimal throughput
  "checksumAlgorithm": "sha256",
  "uploadMode": "auto"  // auto, native, or manual - server chooses best method
}

Response: 201 Created
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "uploadToken": "tok_secure_random_token",
  "expiresAt": "2024-01-26T10:30:00Z",  // 7 days for large files
  "uploadUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/chunks",
  "resumable": true,
  "uploadMethod": "native_multipart",  // native_multipart or managed_chunks
  "chunkSize": 10485760,
  "minChunkSize": 5242880,  // 5MB minimum for S3 compatibility
  "maxChunkSize": 104857600,  // 100MB maximum
  "expectedChunks": 10240,
  "serverChecksum": true,
  "capabilities": {
    "parallelUploads": 10,  // Number of chunks that can be uploaded concurrently
    "streamingVerification": true,  // Server verifies checksums during upload
    "pauseResume": true,
    "bandwidthThrottling": true
  },
  "cloudProvider": {
    "type": "s3",  // Exposed for client optimization
    "multipartUploadId": "mp_aws_xyz123",  // Native cloud provider upload ID
    "region": "us-east-1"
  }
}
```

### 2. Upload Chunk (Parallel-Friendly)
```
PUT /api/v1/uploads/{uploadId}/chunks/{chunkIndex}
Content-Type: application/octet-stream
Content-Length: 10485760
Content-Range: bytes 0-10485759/107374182400
X-Chunk-Checksum: sha256:a1b2c3d4...
X-Upload-Token: tok_secure_random_token
Authorization: Bearer {token}

Request Body:
[binary data]

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "chunkIndex": 0,
  "chunkChecksum": "sha256:a1b2c3d4...",
  "checksumMatch": true,  // Immediate verification during upload
  "bytesReceived": 10485760,
  "etag": "abc123def456",  // Cloud provider ETag for native multipart
  "uploadedAt": "2024-01-19T10:15:30Z",
  "uploadDurationMs": 1250,
  "transferRate": "8.39 MB/s"
}
```

### 3. Get Upload Status (Enhanced Resume Information)
```
GET /api/v1/uploads/{uploadId}
Authorization: Bearer {token}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "in_progress",
  "bytesReceived": 1073741824,  // 1GB so far
  "bytesTotal": 107374182400,
  "percentComplete": 1.0,
  "chunksCompleted": [0, 1, 2, 3, ..., 102],  // Can be large array
  "chunksCompletedCount": 103,
  "chunksRemaining": 10137,
  "chunksInProgress": [104, 105, 106],  // Currently being uploaded by client
  "estimatedTimeRemainingSeconds": 86400,  // 24 hours at current rate
  "uploadRateMBps": 1.15,
  "lastChunkReceivedAt": "2024-01-19T10:15:00Z",
  "createdAt": "2024-01-19T10:00:00Z",
  "expiresAt": "2024-01-26T10:00:00Z",
  "uploadToken": "tok_resume_token",
  "integrityStatus": {
    "chunksVerified": 103,
    "verificationFailures": [],
    "streamingVerificationEnabled": true
  },
  "cloudProvider": {
    "multipartUploadId": "mp_aws_xyz123",
    "uploadedParts": [  // Native cloud provider part tracking
      {"partNumber": 1, "etag": "abc123"},
      {"partNumber": 2, "etag": "def456"}
    ]
  },
  "extensionRequest": {
    "available": true,  // Can request extension before expiry
    "maxExtensionHours": 168  // Additional 7 days
  }
}
```

### 4. Complete Upload (Hybrid Verification)
```
POST /api/v1/uploads/{uploadId}/complete
Content-Type: application/json
X-Upload-Token: tok_secure_random_token
Authorization: Bearer {token}

Request:
{
  "finalChecksum": "sha256:f1n2l3c4...",
  "verificationMode": "streaming",  // streaming or full - streaming skips re-verification
  "chunkCount": 10240  // Simple count check, not full manifest for large files
}

Response: 202 Accepted  // Async completion for large files
{
  "fileId": "file_9z8y7x6w5v",
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "finalizing",  // finalizing -> processing -> ready
  "completionJobId": "job_completion_xyz",
  "estimatedCompletionSeconds": 120,
  "statusUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/completion-status",
  "webhookUrl": "/api/v1/webhooks/file_9z8y7x6w5v",
  "integrityVerification": {
    "method": "streaming",  // Already verified during upload
    "requiresFullScan": false
  }
}
```

### 5. Get Completion Status
```
GET /api/v1/uploads/{uploadId}/completion-status
Authorization: Bearer {token}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "fileId": "file_9z8y7x6w5v",
  "status": "processing",  // finalizing, processing, ready, failed
  "completionProgress": {
    "stage": "virus_scan",  // assembly, checksum_verification, virus_scan, metadata_extraction
    "percentComplete": 45,
    "estimatedSecondsRemaining": 30
  },
  "integrityVerified": true,
  "file": {
    "url": "/api/v1/files/file_9z8y7x6w5v",
    "size": 107374182400,
    "checksum": "sha256:f1n2l3c4...",
    "status": "processing"
  }
}
```

### 6. Request Upload Extension
```
POST /api/v1/uploads/{uploadId}/extend
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "extensionHours": 168  // Request 7 more days
}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "oldExpiresAt": "2024-01-26T10:00:00Z",
  "newExpiresAt": "2024-02-02T10:00:00Z",
  "extensionsRemaining": 2,  // Limit extensions to prevent abuse
  "maxTotalUploadDays": 30
}
```

### 7. Pause Upload (Explicit State Management)
```
POST /api/v1/uploads/{uploadId}/pause
Authorization: Bearer {token}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "paused",
  "pausedAt": "2024-01-19T15:00:00Z",
  "bytesReceived": 1073741824,
  "chunksCompleted": 103,
  "resumeToken": "tok_resume_xyz",
  "pausedExpiresAt": "2024-01-26T15:00:00Z"  // Paused uploads still expire
}
```

### 8. Cancel Upload (Enhanced Cleanup)
```
DELETE /api/v1/uploads/{uploadId}
Authorization: Bearer {token}
X-Upload-Token: tok_secure_random_token

Response: 202 Accepted  // Async cleanup for large uploads
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "cancelling",
  "cleanupJobId": "job_cleanup_abc",
  "estimatedCleanupSeconds": 60,
  "storageToFree": 1073741824
}

Headers:
  X-Cleanup-Status: in_progress
```

### 9. Simple Direct Upload (Small Files <100MB)
```
POST /api/v1/files/direct
Content-Type: multipart/form-data
Authorization: Bearer {token}

Request:
- file: binary data
- metadata: JSON string
- checksum: sha256 hash

Response: 201 Created
{
  "fileId": "file_9z8y7x6w5v",
  "url": "/api/v1/files/file_9z8y7x6w5v",
  "status": "processing",
  "integrityVerified": true,
  "size": 10485760
}
```

### 10. Get Signed Download URL (With Resume Support)
```
POST /api/v1/files/{fileId}/download-url
Authorization: Bearer {token}
Content-Type: application/json

Request:
{
  "expiresIn": 3600,
  "disposition": "attachment",
  "supportRangeRequests": true  // Enable resume for downloads
}

Response: 200 OK
{
  "downloadUrl": "https://storage.example.com/signed-url?token=...",
  "expiresAt": "2024-01-19T11:00:00Z",
  "contentType": "video/mp4",
  "size": 107374182400,
  "supportsRangeRequests": true,
  "checksumHeader": "x-amz-checksum-sha256",  // Header to verify download integrity
  "recommendedChunkSize": 10485760
}
```

### 11. Batch Operations (Performance Optimization)
```
POST /api/v1/uploads/batch/status
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "uploadIds": ["upl_1", "upl_2", "upl_3", ...]  // Up to 100 IDs
}

Response: 200 OK
{
  "uploads": [
    {"uploadId": "upl_1", "status": "in_progress", "percentComplete": 45, ...},
    {"uploadId": "upl_2", "status": "completed", "fileId": "file_xyz", ...}
  ]
}
```

## Data Models

### Upload Session (Optimized for Scale)
```typescript
interface UploadSession {
  uploadId: string;
  userId: string;
  filename: string;
  size: number;
  mimeType: string;
  metadata: Record<string, any>;
  status: 'initiated' | 'in_progress' | 'paused' | 'finalizing' | 'completed' | 'failed' | 'cancelled' | 'quarantined';
  bytesReceived: number;
  chunkSize: number;
  expectedChunks: number;
  
  // Hybrid chunk tracking - full list for small uploads, summary for large
  chunkTrackingMode: 'full' | 'bitmap' | 'summary';
  chunksCompletedBitmap?: Buffer;  // Efficient bitmap for 10,000+ chunks
  chunksCompletedCount: number;
  chunksCompletedRanges?: Array<{start: number, end: number}>;  // Compressed representation
  lastChunkIndex: number;
  
  // Native cloud provider integration
  uploadMethod: 'native_multipart' | 'managed_chunks';
  cloudProvider: {
    type: 's3' | 'gcs' | 'azure';
    multipartUploadId?: string;  // S3 multipart upload ID
    uploadedParts: Array<{partNumber: number, etag: string, size: number}>;
    region: string;
  };
  
  storageKey: string;
  tempStoragePath?: string;  // Only for managed_chunks mode
  checksumAlgorithm: 'sha256' | 'sha512' | 'blake3';
  finalChecksum?: string;
  
  // Streaming verification (incremental checksum computation)
  streamingVerification: {
    enabled: boolean;
    currentChecksum: string;  // Running checksum state
    verifiedBytes: number;
    lastVerifiedAt: Date;
  };
  
  // Security tokens (simplified for performance)
  currentUploadToken: string;
  tokenRotationEnabled: boolean;  // Configurable - false for internal systems
  tokenExpiresAt: Date;
  
  // Concurrency control (lightweight)
  lockVersion: number;
  activeChunkUploads: Set<number>;  // Track in-flight chunks
  maxConcurrentChunks: number;
  
  // Lifecycle management
  createdAt: Date;
  updatedAt: Date;
  lastActivityAt: Date;
  expiresAt: Date;
  extensionCount: number;
  pausedAt?: Date;
  
  // Performance metrics
  metrics: {
    averageChunkUploadMs: number;
    averageTransferRateMBps: number;
    totalRetries: number;
    failedChunks: number;
  };
  
  // Audit (minimal, expanded in separate audit log)
  clientInfo: {
    ipAddress: string;
    userAgent: string;
    sdkVersion?: string;
  };
}

interface UploadChunk {
  index: number;
  size: number;
  checksum: string;
  etag?: string;  // Cloud provider ETag
  receivedAt: Date;
  verified: boolean;
  retryCount: number;
  uploadDurationMs: number;
}
```

### File Record (Production-Ready)
```typescript
interface FileRecord {
  fileId: string;
  userId: string;
  filename: string;
  originalFilename: string;
  size: number;
  mimeType: string;
  detectedMimeType: string;
  
  // Storage details
  storage: {
    provider: 's3' | 'gcs' | 'azure' | 'local';
    key: string;
    bucket: string;
    region: string;
    storageClass: 'standard' | 'infrequent' | 'archive';
    redundancy: 'single-region' | 'multi-region';
    encryption: {
      type: 'sse-s3' | 'sse-kms' | 'client-side' | 'none';
      keyId?: string;
      algorithm?: string;
    };
  };
  
  // Integrity
  checksum: string;
  checksumAlgorithm: string;
  verificationMethod: 'streaming' | 'post-upload' | 'deferred';
  integrityVerifiedAt: Date;
  
  metadata: Record<string, any>;
  
  // Status and processing
  status: 'finalizing' | 'processing' | 'ready' | 'failed' | 'quarantined' | 'archived' | 'deleted';
  
  securityScan: {
    status: 'pending' | 'scanning' | 'clean' | 'infected' | 'suspicious' | 'failed' | 'skipped';
    scannedAt?: Date;
    scanner: string;
    scannerVersion?: string;
    threats?: Array<{name: string, severity: string}>;
    scanDurationMs?: number;
  };
  
  processingJobs: ProcessingJob[];
  
  // Access control
  accessControl: {
    visibility: 'private' | 'internal' | 'public';
    allowedUsers?: string[];
    allowedGroups?: string[];
    allowedUntil?: Date;  // Temporary access grants
  };
  
  // URLs (lazy-generated, not stored)
  // Use signed URL generation endpoint instead
  
  // Retention and lifecycle
  retention: {
    policy: 'standard' | 'extended' | 'permanent' | 'custom';
    deleteAt?: Date;
    archiveAt?: Date;
    lastAccessedAt?: Date;
    accessCount: number;
  };
  
  // Derived files (thumbnails, transcodes)
  derivatives: Array<{
    type: 'thumbnail' | 'preview' | 'transcode';
    format: string;
    size: number;
    storageKey: string;
    url: string;
  }>;
  
  // Traceability
  uploadSessionId: string;
  sourceIpAddress: string;
  
  // Performance metadata
  uploadDurationSeconds: number;
  processingDurationSeconds: number;
  
  // Timestamps
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
  deletedAt?: Date;
  
  // Audit trail reference (not embedded for performance)
  auditLogId: string;
}

interface ProcessingJob {
  jobId: string;
  type: 'assembly' | 'virus_scan' | 'thumbnail' | 'metadata_extract' | 'transcode' | 'checksum_verify';
  priority: number;  // Higher priority = processed first
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  queuedAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  retryCount: number;
  maxRetries: number;
  progressPercent: number;
  estimatedDurationSeconds?: number;
  dependencies: string[];  // Job IDs that must complete first
}
```

## Component Architecture

### 1. API Layer
- **UploadController**: HTTP request handling, validation, auth
- **FileController**: File retrieval, metadata operations
- **BatchController**: Bulk operations for performance
- **Middleware**:
  - Auth (JWT validation with 15min cache)
  - Rate limiting (token bucket algorithm, Redis-backed)
  - Request size validation
  - CSRF protection (double-submit cookie)
  - Content-Type validation
  - Upload token verification (conditional based on config)
  - Request ID injection (distributed tracing)

### 2. Business Logic Layer

#### Upload Service (Core Orchestration)
- **UploadOrchestrator**: High-level upload flow management
  - `initiateUpload()`: Determines native vs managed mode based on file size and provider
  - `selectUploadStrategy()`: Auto-selects optimal chunk size and concurrency
  - `routeChunkUpload()`: Routes to native or managed handler

#### Native Multipart Handler (Performance Path)
- **S3MultipartAdapter**: 
  - Uses `CreateMultipartUpload`, `UploadPart`, `CompleteMultipartUpload` APIs
  - Each chunk maps to S3 part (1:1 mapping)
  - Verification: Client checksum + S3 ETag validation
  - Assembly: S3 native (instant, no data movement)
  - Trade-off: Less control, maximum performance
  - Supports up to 10,000 parts (10TB at 1GB chunks)
  
- **GCSResumableAdapter**:
  - Uses GCS resumable upload protocol
  - Single resumable session for entire file
  - Verification: MD5 hash + CRC32C
  - Assembly: Native (automatic)
  
- **AzureBlockBlobAdapter**:
  - Uses Block Blob staging and commitment
  - Blocks up to 50,000 (4.75TB at 100MB blocks)
  - Verification: MD5 per block + CRC64 for blob

#### Managed Chunk Handler (Control Path)
- **ManagedChunkService**:
  - Manual chunk storage and assembly
  - Used when: file < 100MB, or native APIs unavailable
  - Verification: Dual checksum (client + server streaming)
  - Assembly: Custom concatenation with re-verification
  - Trade-off: Full control, slower for large files

#### Supporting Services
- **StreamingChecksumService**: 
  - Computes checksums incrementally during upload (no buffering)
  - Maintains checksum state in Redis (serializable)
  - Supports resume without recomputing from start
  
- **ChunkTrackerService**:
  - Bitmap storage for 10,000+ chunk tracking
  - Range compression (e.g., "0-500, 750-1000" vs list of 1001 numbers)
  - O(1) chunk completion lookup
  
- **UploadStrategyService**:
  - Determines optimal chunk size based on file size and network conditions
  - Recommends concurrency level (adaptive to user tier and system load)
  - Auto-tunes based on historical performance metrics
  
- **ValidationService**: 
  - MIME type verification (magic numbers + extension)
  - Filename sanitization (path traversal prevention)
  - Size and quota enforcement
  - Content Security Policy checks
  
- **LockService**: 
  - Distributed locking (Redis with Redlock algorithm)
  - Per-upload locks (not per-chunk for performance)
  - Lock timeouts: 30s default, auto-renewal for long operations
  
- **QuarantineService**: 
  - Isolated storage for infected files (separate bucket/container)
  - Tiered retention: 7 days (confirmed malware) or 30 days (suspicious)
  - Auto-notification to security team

### 3. Storage Layer

#### Storage Adapter Interface (Hybrid)
```typescript
interface StorageAdapter {
  // Native multipart operations
  initiateMultipartUpload(params: InitiateParams): Promise<MultipartUpload>;
  uploadPart(uploadId: string, partNumber: number, data: Buffer): Promise<PartETag>;
  completeMultipartUpload(uploadId: string, parts: PartETag[]): Promise<FileKey>;
  abortMultipartUpload(uploadId: string): Promise<void>;
  
  // Managed chunk operations (fallback)
  writeChunk(uploadId: string, chunkIndex: number, chunk: Buffer): Promise<ChunkMetadata>;
  assembleChunks(uploadId: string, manifest: ChunkManifest): Promise<FileKey>;
  
  // Common operations
  verifyChecksum(key: string, expectedChecksum: string, algorithm: string): Promise<boolean>;
  getSignedUrl(key: string, expiresIn: number, options: UrlOptions): Promise<string>;
  delete(key: string): Promise<void>;
  getMetadata(key: string): Promise<StorageMetadata>;
  
  // Streaming operations
  getStreamingChecksum(key: string, algorithm: string): Promise<string>;
  
  // Capabilities
  supportsNativeMultipart(): boolean;
  getMaxPartSize(): number;
  getMaxParts(): number;
}
```

#### Implementations
- **S3Adapter**: 
  - Native multipart for all files >100MB
  - Max 10,000 parts × 5GB = 5TB per file
  - Uses S3 Transfer Acceleration for cross-region uploads
  - Server-side encryption (SSE-S3 or SSE-KMS)
  
- **GCSAdapter**: 
  - Resumable uploads for files >100MB
  - Composite objects for managed mode
  - Customer-managed encryption keys (CMEK)
  
- **AzureAdapter**: 
  - Block blobs with staging
  - Max 50,000 blocks × 100MB = 4.75TB per file
  
- **LocalAdapter**: 
  - Managed chunks only
  - Direct filesystem with atomic renames
  - For development and testing

### 4. Processing Layer

#### Job Queue Architecture
- **Queue System**: Bull (Redis-backed) or RabbitMQ for enterprise
- **Priority Queues**:
  - P0 (Critical): Virus scanning - blocks file access
  - P1 (High): Assembly for large files
  - P2 (Normal): Metadata extraction
  - P3 (Low): Thumbnail generation, transcoding
- **Concurrency**: 10 workers per queue by default
- **Dead Letter Queue**: 3 retry limit, then DLQ for manual review
- **Job Deduplication**: Content-addressed (checksum-based)

#### Processors
- **AssemblyProcessor** (managed chunks only):
  - Streams chunks directly to final storage (no intermediate copy)
  - Computes final checksum during assembly
  - Duration: ~60s per 10GB at 200MB/s
  
- **VirusScanProcessor**:
  - ClamAV for real-time blocking scan
  - VirusTotal API for deep analysis (async, non-blocking)
  - Streaming scan (no full file buffering)
  - Quarantine on detection (moves file atomically)
  - Duration: ~30s per 1GB
  
- **ThumbnailProcessor**:
  - Generates multiple sizes (small/medium/large)
  - Timeout: 60s per file
  - Sandboxed execution (container-based)
  
- **MetadataExtractor**:
  - Extracts EXIF, video codec info, document properties
  - Sandboxed for security
  - Timeout: 30s per file
  
- **ChecksumVerifier** (post-upload, optional):
  - For files that used native multipart without streaming verification
  - Computes full file checksum
  - Marks file as verified in database

### 5. Consistency and Reliability Layer

#### Transaction Coordinator
- **UploadTransactionManager**:
  - Two-phase commit for database + storage updates
  - Atomic chunk completion (update both Redis tracking and database)
  - Rollback capability for failed operations

#### State Reconciliation Service
- **ReconciliationJob** (runs every 30 minutes):
  - Detects orphaned uploads (chunks in storage, no database record)
  - Finds incomplete uploads past expiry (cleanup trigger)
  - Identifies storage vs database mismatches
  - Auto-heals: Re-creates database records if storage valid + unexpired
  - Auto-cleans: Deletes storage if database shows cancelled/failed
  
- **StorageAudit** (runs daily):
  - Compares file records with actual storage
  - Detects missing files (corruption or accidental deletion)
  - Verifies checksums on sample of files (statistical integrity check)
  - Alerts on discrepancies

#### Cleanup Service
- **UploadCleanupJob** (runs hourly):
  - Deletes expired upload sessions (paused or in-progress)
  - Removes temporary chunks for completed uploads
  - Cleans up aborted multipart uploads in cloud providers
  
- **QuarantineCleanupJob** (runs daily):
  - Tiered deletion: 7 days for confirmed threats, 30 days for suspicious
  - Compression before deletion (forensic archive)

## Error Handling

### Error Response Format
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    retryable: boolean;
    retryAfter?: number;
    retryStrategy?: 'exponential_backoff' | 'immediate' | 'none';
    documentation: string;
    requestId: string;  // For support
  };
  timestamp: string;
}
```

### Error Categories

#### Retryable Errors (Client should retry)
- **STORAGE_UNAVAILABLE** (503): Cloud provider downtime → exponential backoff, max 5 retries
- **LOCK_TIMEOUT** (409): Concurrent operation → wait 1s, retry up to 3 times
- **RATE_LIMIT_EXCEEDED** (429): Quota exceeded → retry after `retryAfter` seconds
- **CHECKSUM_COMPUTE_FAILED** (500): Temporary server error → immediate retry once
- **INTERNAL_SERVER_ERROR** (500): Generic server error → exponential backoff

#### Non-Retryable Errors (Client must fix)
- **CHUNK_CHECKSUM_MISMATCH** (400): Data corruption → re-upload specific chunk
- **FILE_SIZE_EXCEEDED** (413): File too large → cannot proceed
- **INVALID_MIME_TYPE** (415): Unsupported file type → cannot proceed
- **UPLOAD_EXPIRED** (410): Session expired → initiate new upload
- **UPLOAD_NOT_FOUND** (404): Invalid upload ID → verify ID
- **UNAUTHORIZED** (401): Invalid/expired token → re-authenticate
- **QUOTA_EXCEEDED** (403): Storage quota full → upgrade or delete files
- **INVALID_CHUNK_INDEX** (400): Chunk out of range → use correct index
- **INVALID_TOKEN** (403): Upload token mismatch → get fresh token
- **FILE_QUARANTINED** (451): Security block → file not accessible
- **MULTIPART_UPLOAD_FAILED** (500): Native cloud API error → retry initiation with managed mode

#### Edge Cases Handled

**1. Chunk Checksum Mismatch:**
- Client uploads chunk with checksum `sha256:abc123`
- Server computes `sha256:def456` during streaming
- Response: `400 CHUNK_CHECKSUM_MISMATCH` with `chunkIndex: 5`
- Client action: Re-upload only chunk 5
- Server: Allows idempotent re-upload of same chunk

**2. Native Multipart Assembly Failure:**
- S3 `CompleteMultipartUpload` returns error (rare: eventual consistency issue)
- Server retries 3 times with exponential backoff
- If all retries fail: Abort multipart upload, switch to managed assembly
- Client notified: `202 Accepted` with `status: "finalizing_with_fallback"`
- Transparent to client (same completion endpoint)

**3. Upload Token Expiry Mid-Upload:**
- Token expires during chunk upload
- Response: `403 INVALID_TOKEN` with `newToken: "tok_refreshed"`
- Client automatically uses new token for next chunk
- Old chunks remain valid (token only gates new uploads)

**4. Concurrent Chunk Uploads (Same Index):**
- Two requests upload chunk 5 simultaneously
- First request acquires lock, succeeds
- Second request gets `409 LOCK_TIMEOUT`, retries after 1s
- On retry, chunk already completed → returns `200 OK` (idempotent)

**5. Partial Upload After Expiry:**
- Upload expires with 50% complete
- Client tries to resume: `410 UPLOAD_EXPIRED`
- Server cleanup job removes chunks after 24h grace period
- Client must initiate new upload (no recovery possible)

**6. Storage Inconsistency (Missing Chunk):**
- Database says chunk 5 complete, but storage doesn't have it
- Detected by reconciliation job
- Job marks chunk as incomplete in database
- Client's next status check shows chunk 5 in `chunksRemaining`
- Client re-uploads chunk 5

**7. Completion Request Before All Chunks Uploaded:**
- Client calls complete with `chunkCount: 100` but only 98 uploaded
- Response: `400 INCOMPLETE_UPLOAD` with `chunksRemaining: [45, 67]`
- Client uploads missing chunks, retries completion

**8. File Download Corruption:**
- Client downloads file, checksum doesn't match
- Client reports corruption via `POST /api/v1/files/{fileId}/report-corruption`
- Server: Re-verifies checksum in storage
- If mismatch: Marks file as corrupted, triggers re-assembly from chunks (if available)
- If chunks gone: File marked as unrecoverable, user notified

**9. Virus Detected After Completion:**
- File initially marked clean
- VirusTotal async scan (24h later) finds threat
- File atomically moved to quarantine
- Status changed to `quarantined`
- User notified via webhook + email
- Download URLs return `451 Unavailable For Legal Reasons`

**10. Multi-Day Upload with Network Changes:**
- User uploads 100GB over 3 days
- IP address changes mid-upload
- Token validation: IP binding disabled for long uploads (>24h)
- User agent fingerprinting used instead
- Upload continues seamlessly

### Retry Strategy

**Client-Side (SDK Best Practices):**
```typescript
const retryConfig = {
  maxRetries: 5,
  baseDelayMs: 1000,
  maxDelayMs: 32000,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
  retryableErrorCodes: ['STORAGE_UNAVAILABLE', 'LOCK_TIMEOUT', 'RATE_LIMIT_EXCEEDED'],
  
  strategy: (attempt: number, error: ErrorResponse) => {
    if (error.error.code === 'RATE_LIMIT_EXCEEDED') {
      return error.error.retryAfter * 1000;  // Use server-provided delay
    }
    if (error.error.code === 'CHUNK_CHECKSUM_MISMATCH') {
      return 0;  // Immediate retry for corrupted chunk
    }
    return Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);  // Exponential backoff
  }
};
```

**Server-Side (Processing Jobs):**
- Virus scan failure: Retry 3 times (10s, 30s, 90s), then fail
- Thumbnail generation: Retry 2 times (5s, 15s), then skip
- Assembly failure: Retry 3 times (30s, 90s, 270s), then alert ops team
- Checksum verification: No retry (deterministic), mark as failed immediately

## Security

### Authentication & Authorization
1. **JWT Bearer Tokens**: 15-minute access, 7-day refresh, rotation on use
2. **Upload Token System** (Configurable):
   - **Strict Mode** (public APIs): Per-chunk rotation, single-use
   - **Balanced Mode** (default): Per-session token, 24h expiry
   - **Relaxed Mode** (internal systems): Per-upload token, 7d expiry
3. **Authorization**: User isolation enforced at database query level (row-level security)
4. **API Keys**: For service-to-service, HMAC-SHA256 signed requests

### Rate Limiting (Adaptive)
**Tier-Based Limits:**
- Free Tier: 10 uploads/day, 1GB total
- Pro Tier: 100 uploads/day, 100GB total, 5 concurrent
- Enterprise: Unlimited, 100 concurrent, dedicated bandwidth

**Per-Endpoint Limits:**
- Initiate: 100/hour per user (prevents session exhaustion)
- Chunk Upload: 10,000/hour per user (supports 100GB/hour at 10MB chunks)
- Status Check: 1,000/hour per user
- Complete: 100/hour per user

**Adaptive Rate Limiting:**
- Increases limits for users with consistent upload patterns
- Decreases limits on suspicious activity (rapid session creation)
- IP-based limits: 10x user limits per IP (multi-user scenarios)

### File Validation (Multi-Layer)
1. **MIME Type Verification**:
   - Magic number detection (libmagic)
   - Extension validation
   - Content sniffing
   - Reject if mismatch (strict mode) or warn (permissive mode)

2. **Filename Sanitization**:
   - Remove: `../`, `..\\`, null bytes, control characters
   - Limit: 255 UTF-8 characters
   - Generate safe storage key (UUID-based), preserve original for display

3. **Size Limits** (Tier-Based):
   - Free: 1GB per file, 10GB total storage
   - Pro: 100GB per file, 1TB total storage
   - Enterprise: 1TB per file, unlimited storage

4. **Content Security**:
   - Serve from separate domain (e.g., `files.example.com` vs `api.example.com`)
   - `Content-Disposition: attachment` default
   - `X-Content-Type-Options: nosniff`
   - `Content-Security-Policy: default-src 'none'` for HTML files

### Virus Scanning
1. **Real-Time** (Blocking): ClamAV scan on completion, <5s for small files
2. **Deep Scan** (Async): VirusTotal API for files >10MB or suspicious types
3. **Quarantine**: Atomic move to isolated bucket, access revoked immediately
4. **Notifications**: User + security team via webhook + email

### Signed URLs (Secure Downloads)
- HMAC-SHA256 signed with secret key
- Time-limited: 1h default, 24h max, 5min min
- Optional: IP binding, single-use, user-agent binding
- Audit: All URL generations logged

### Encryption
1. **In Transit**: TLS 1.3, HSTS enabled, strong cipher suites only
2. **At Rest**: 
   - Server-side: SSE-S3, SSE-KMS, or SSE-C (customer key)
   - Client-side: Optional, client manages keys
3. **Key Management**: AWS KMS, Google Cloud KMS, Azure Key Vault integration

## Configuration

```typescript
interface SystemConfig {
  // File size limits
  files: {
    maxFileSizeBytes: number;              // 1TB default (1099511627776)
    directUploadMaxBytes: number;          // 100MB (no chunking)
    nativeMultipartThresholdBytes: number; // 100MB (use native APIs above this)
  };
  
  // Chunking
  chunks: {
    defaultChunkSizeBytes: number;  // 10MB (optimal for most networks)
    minChunkSizeBytes: number;      // 5MB (S3 requirement)
    maxChunkSizeBytes: number;      // 100MB (memory limit)
    autoTuneChunkSize: boolean;     // true (adjust based on file size)
    maxConcurrentUploads: number;   // 10 per upload session
  };
  
  // Session management
  sessions: {
    defaultExpiryHours: number;     // 168 (7 days)
    maxExpiryHours: number;         // 720 (30 days)
    allowExtensions: boolean;       // true
    maxExtensions: number;          // 3
    pauseSupported: boolean;        // true
    gracePeriodeleteHours: number; // 24 (before cleanup)
  };
  
  // Upload strategy
  strategy: {
    preferNativeMultipart: boolean;  // true (use cloud native APIs)
    fallbackToManaged: boolean;      // true (if native fails)
    streamingVerification: boolean;  // true (verify during upload)
    deferredVerification: boolean;   // false (post-upload verification)
  };
  
  // Storage
  storage: {
    provider: 's3' | 'gcs' | 'azure' | 'local';
    bucket: string;
    region: string;
    storageClass: 'standard' | 'infrequent' | 'archive';
    redundancy: 'single-region' | 'multi-region';
    encryption: {
      type: 'sse-s3' | 'sse-kms' | 'client-side';
      kmsKeyId?: string;
    };
    transferAcceleration: boolean;  // S3 only
    credentials: any;
  };
  
  // Security
  security: {
    uploadTokenMode: 'strict' | 'balanced' | 'relaxed';
    ipBindingEnabled: boolean;          // false (breaks mobile uploads)
    ipBindingForLongUploads: boolean;   // false (>24h uploads)
    requireChecksums: boolean;          // true
    checksumAlgorithm: 'sha256' | 'sha512' | 'blake3';
    virusScanEnabled: boolean;          // true
    virusScanBlocking: boolean;         // true
    allowedMimeTypes: string[];         // [] = all allowed
    blockedMimeTypes: string[];         // ['application/x-msdownload', ...]
    blockedExtensions: string[];        // ['.exe', '.bat', '.scr', ...]
    serveFromSeparateDomain: boolean;   // true (security best practice)
    separateDomain?: string;
  };
  
  // Quotas (per user tier)
  quotas: {
    dailyUploads: number;           // 100
    dailyBandwidthBytes: number;    // 100GB
    totalStorageBytes: number;      // 1TB
    maxConcurrentSessions: number;  // 5
    maxFileSize: number;            // 100GB (per-tier override)
  };
  
  // Rate limiting
  rateLimits: {
    initiate: {perHour: 100, perDay: 500},
    chunkUpload: {perHour: 10000, perDay: 100000},
    statusCheck: {perHour: 1000, perDay: 10000},
    complete: {perHour: 100, perDay: 500},
    adaptive: boolean;  // true (increase limits for trusted users)
  };
  
  // Processing
  processing: {
    virusScanner: 'clamav' | 'virustotal' | 'both';
    thumbnailGeneration: boolean;       // true for images/videos
    metadataExtraction: boolean;        // true
    asyncProcessing: boolean;           // true (don't block completion)
    jobRetries: {
      virusScan: 3,
      thumbnail: 2,
      metadata: 2,
      assembly: 3
    };
  };
  
  // Cleanup
  cleanup: {
    failedUploadRetentionHours: number;     // 24
    completedChunkRetentionHours: number;   // 1 (cleanup after assembly)
    quarantinedFileRetentionDays: number;   // 7 for confirmed, 30 for suspicious
    orphanedChunkCleanupHours: number;      // 48
    auditLogRetentionDays: number;          // 90
  };
  
  // Monitoring
  monitoring: {
    metricsEnabled: boolean;           // true
    detailedLogging: boolean;          // false (performance impact)
    distributedTracing: boolean;       // true
    alerting: {
      failureRateThreshold: number;    // 5% (alert if exceeded)
      slowUploadThreshold: number;     // 300s per GB
      storageUsageThreshold: number;   // 90% capacity
    };
  };
}
```

## Performance Optimizations

### 1. Native Cloud Provider APIs
- S3: Direct multipart upload (no proxy), instant assembly
- GCS: Resumable upload protocol, server-side composition
- Azure: Block blob staging, atomic commitment
- **Benefit**: 10-100x faster assembly (no data movement), up to 1TB files

### 2. Streaming Verification
- Checksum computed incrementally during upload (not post-upload)
- State persisted in Redis (resume without recomputation)
- **Benefit**: Zero additional latency for verification, enables 100GB+ files

### 3. Chunk Tracking Optimization
- Bitmap storage: 10,000 chunks = 1.25KB (vs 50KB JSON array)
- Range compression: "0-5000" vs 5000 separate numbers
- **Benefit**: 40x smaller database payload, faster status checks

### 4. Parallel Chunk Uploads
- Client uploads 10 chunks concurrently (configurable)
- Server processes independently (no ordering requirement)
- **Benefit**: 10x throughput on high-bandwidth connections

### 5. Batch Operations
- Status checks for multiple uploads in single request
- **Benefit**: 90% reduction in API calls for multi-file uploads

### 6. Adaptive Chunk Sizing
- Small files (<100MB): 5MB chunks, direct upload
- Medium files (100MB-10GB): 10MB chunks, native multipart
- Large files (>10GB): 50MB chunks, parallel uploads
- **Benefit**: Optimal throughput across all file sizes

### 7. CDN Integration
- Static assets (thumbnails, small files) served via CDN
- Edge caching for download URLs
- **Benefit**: <100ms download latency globally

## Scalability Targets

### Performance Benchmarks
- **Small files (<10MB)**: <2s end-to-end (upload + processing)
- **Medium files (1GB)**: <60s upload on 100Mbps connection
- **Large files (100GB)**: <3h upload on 100Mbps connection
- **Very large files (1TB)**: <30h upload on 100Mbps connection

### System Capacity
- **Concurrent uploads**: 10,000+ simultaneous sessions
- **Throughput**: 10 PB/day aggregate
- **File count**: 100M active files
- **API requests**: 100,000 req/s
- **Database**: 10M upload sessions, 100M file records

### Horizontal Scaling
- API servers: Stateless, auto-scale on CPU/memory
- Job processors: Worker pool scales on queue depth
- Redis: Cluster mode for session/lock management
- Database: Read replicas for status checks, sharded by user ID