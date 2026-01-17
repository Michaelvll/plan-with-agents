# Claude Code Debate Session

**Started:** 2026-01-17T09:01:45.430052
**Ended:** 2026-01-17T09:12:19.948535
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a file upload API

---

## Round 1

### 🔵 Agent A

## Design

# File Upload API Design

## Architecture Overview

**Pattern**: RESTful API with resumable upload support  
**Transport**: HTTP/HTTPS with multipart/form-data and chunked transfer encoding  
**Storage**: Abstract storage layer (supports S3, GCS, Azure Blob, local filesystem)  
**Processing**: Async job queue for post-upload processing (virus scanning, thumbnail generation, etc.)

## API Endpoints

### 1. Initiate Upload
```
POST /api/v1/uploads/initiate
Content-Type: application/json

Request:
{
  "filename": "document.pdf",
  "size": 10485760,
  "mimeType": "application/pdf",
  "metadata": {
    "tags": ["invoice", "2024"],
    "visibility": "private"
  },
  "chunkSize": 5242880  // Optional, for resumable uploads
}

Response: 201 Created
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "expiresAt": "2024-01-20T10:30:00Z",
  "uploadUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/data",
  "resumable": true,
  "maxChunkSize": 5242880
}
```

### 2. Upload File Data
```
PUT /api/v1/uploads/{uploadId}/data
Content-Type: multipart/form-data
Content-Range: bytes 0-5242879/10485760  // For chunked uploads

Request:
- file: binary data
- checksum: SHA-256 hash (optional but recommended)

Response: 200 OK (partial) or 201 Created (complete)
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "bytesReceived": 5242880,
  "bytesTotal": 10485760,
  "complete": false
}
```

### 3. Complete Upload
```
POST /api/v1/uploads/{uploadId}/complete
Content-Type: application/json

Request:
{
  "checksum": "sha256:a1b2c3d4...",
  "parts": [  // For multipart uploads
    {"partNumber": 1, "etag": "abc123"},
    {"partNumber": 2, "etag": "def456"}
  ]
}

Response: 200 OK
{
  "fileId": "file_9z8y7x6w5v",
  "url": "/api/v1/files/file_9z8y7x6w5v",
  "downloadUrl": "https://cdn.example.com/files/file_9z8y7x6w5v",
  "status": "processing",  // or "ready"
  "metadata": {...}
}
```

### 4. Cancel Upload
```
DELETE /api/v1/uploads/{uploadId}

Response: 204 No Content
```

### 5. Get Upload Status
```
GET /api/v1/uploads/{uploadId}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "in_progress",  // initiated, in_progress, completed, failed, cancelled
  "bytesReceived": 5242880,
  "bytesTotal": 10485760,
  "createdAt": "2024-01-19T10:00:00Z",
  "expiresAt": "2024-01-20T10:30:00Z"
}
```

### 6. Simple Direct Upload (small files)
```
POST /api/v1/files
Content-Type: multipart/form-data

Request:
- file: binary data
- metadata: JSON string

Response: 201 Created
{
  "fileId": "file_9z8y7x6w5v",
  "url": "/api/v1/files/file_9z8y7x6w5v",
  "downloadUrl": "https://cdn.example.com/files/file_9z8y7x6w5v"
}
```

## Data Models

### Upload Session
```typescript
interface UploadSession {
  uploadId: string;
  userId: string;
  filename: string;
  size: number;
  mimeType: string;
  metadata: Record<string, any>;
  status: 'initiated' | 'in_progress' | 'completed' | 'failed' | 'cancelled';
  bytesReceived: number;
  chunkSize?: number;
  parts: UploadPart[];
  storageKey: string;
  checksum?: string;
  createdAt: Date;
  updatedAt: Date;
  expiresAt: Date;
}

interface UploadPart {
  partNumber: number;
  size: number;
  etag: string;
  checksum: string;
}
```

### File Record
```typescript
interface FileRecord {
  fileId: string;
  userId: string;
  filename: string;
  size: number;
  mimeType: string;
  storageKey: string;
  checksum: string;
  metadata: Record<string, any>;
  status: 'processing' | 'ready' | 'failed';
  processingJobs: string[];
  urls: {
    download: string;
    thumbnail?: string;
    preview?: string;
  };
  createdAt: Date;
  updatedAt: Date;
  deletedAt?: Date;
}
```

## Component Architecture

### 1. API Layer
- **UploadController**: Handles HTTP requests, validation, authentication
- **FileController**: Manages file retrieval and metadata operations
- **Middleware**: Auth, rate limiting, request size validation

### 2. Business Logic Layer
- **UploadService**: Orchestrates upload sessions, chunking logic
- **FileService**: File metadata management, lifecycle operations
- **ValidationService**: File type validation, size limits, security checks
- **ChecksumService**: Integrity verification

### 3. Storage Layer
- **StorageAdapter Interface**: Abstract storage operations
  - `initiate(params)`: Prepare storage for upload
  - `writeChunk(uploadId, chunk, offset)`: Write data chunk
  - `complete(uploadId)`: Finalize storage
  - `delete(uploadId)`: Clean up
  - `getUrl(fileId)`: Generate download URL
- **Implementations**: S3Adapter, GCSAdapter, AzureAdapter, LocalAdapter

### 4. Processing Layer
- **JobQueue**: Async job processing (Bull/RabbitMQ)
- **Processors**:
  - VirusScanProcessor
  - ThumbnailGenerator
  - MetadataExtractor
  - NotificationSender

## Error Handling

### Error Response Format
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    retryable: boolean;
  };
  requestId: string;
}
```

### Error Codes
- **UPLOAD_EXPIRED**: Upload session expired (408)
- **INVALID_CHECKSUM**: Checksum mismatch (400)
- **FILE_TOO_LARGE**: Exceeds size limit (413)
- **INVALID_FILE_TYPE**: Unsupported MIME type (415)
- **STORAGE_ERROR**: Storage backend failure (500)
- **RATE_LIMIT_EXCEEDED**: Too many requests (429)
- **UPLOAD_NOT_FOUND**: Invalid upload ID (404)
- **UNAUTHORIZED**: Authentication failed (401)
- **INSUFFICIENT_QUOTA**: User quota exceeded (403)

### Retry Strategy
- Transient errors (5xx, network): Exponential backoff, max 3 retries
- Client errors (4xx): No retry except for 408, 429
- Chunked uploads: Resume from last successful chunk

## Security Considerations

1. **Authentication**: JWT bearer tokens or API keys
2. **Authorization**: User can only access their own uploads
3. **Rate Limiting**: Per-user and per-IP limits
4. **File Validation**:
   - MIME type verification (not just extension)
   - Magic number validation
   - Size limits (configurable per user tier)
5. **Virus Scanning**: Async scanning post-upload
6. **Signed URLs**: Time-limited download URLs
7. **CORS**: Configurable allowed origins
8. **Input Sanitization**: Filename and metadata cleaning

## Configuration

```typescript
interface UploadConfig {
  maxFileSize: number;           // 100MB default
  maxChunkSize: number;          // 5MB default
  sessionExpiryMinutes: number;  // 1440 (24h) default
  allowedMimeTypes: string[];    // [] = all allowed
  requireChecksum: boolean;      // true recommended
  virusScanEnabled: boolean;     // true recommended
  storage: {
    provider: 's3' | 'gcs' | 'azure' | 'local';
    bucket?: string;
    region?: string;
    credentials?: any;
  };
  quotas: {
    dailyUploads: number;
    totalStorage: number;
  };
}
```

## Rationale

1. **Resumable uploads**: Critical for large files and unreliable networks - prevents wasted bandwidth on failures
2. **Two-stage upload (initiate + upload)**: Allows pre-flight validation and quota checks before data transfer
3. **Chunked transfer**: Enables progress tracking, parallel uploads, and resumability
4. **Async processing**: Decouples upload from expensive operations (scanning, thumbnails) for better responsiveness
5. **Abstract storage layer**: Supports multi-cloud and migration scenarios without API changes
6. **Checksum verification**: Ensures data integrity across network and storage
7. **Expiring sessions**: Prevents orphaned uploads from consuming storage

## What I Changed

N/A - Initial design

## What I Kept

N/A - Initial design

## Open Questions

1. Should we support direct browser-to-storage uploads (pre-signed URLs) or always proxy through our API?
2. What should the default file retention policy be for completed uploads?
3. Should we support webhooks for upload completion notifications?
4. Do we need versioning support for file updates?

## Convergence Status

**ITERATING** - This is the initial design proposal requiring review and refinement.

PROMPT_FOR_CRITIC:
Focus on the resumable upload mechanism and error handling strategy. Are there edge cases in the chunked upload flow that could lead to data corruption or inconsistent state? Also evaluate whether the security measures are sufficient for a production system handling sensitive files.

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# File Upload API Design

## Architecture Overview

**Pattern**: RESTful API with resumable upload support  
**Transport**: HTTP/HTTPS with multipart/form-data and chunked transfer encoding  
**Storage**: Abstract storage layer (supports S3, GCS, Azure Blob, local filesystem)  
**Processing**: Async job queue for post-upload processing (virus scanning, thumbnail generation, etc.)

## API Endpoints

### 1. Initiate Upload
```
POST /api/v1/uploads/initiate
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "filename": "document.pdf",
  "size": 10485760,
  "mimeType": "application/pdf",
  "metadata": {
    "tags": ["invoice", "2024"],
    "visibility": "private"
  },
  "chunkSize": 5242880,  // Optional, for resumable uploads
  "checksumAlgorithm": "sha256"  // Required: sha256, sha512, or blake3
}

Response: 201 Created
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "uploadToken": "tok_secure_random_token",  // Single-use token for this upload
  "expiresAt": "2024-01-20T10:30:00Z",
  "uploadUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/data",
  "resumable": true,
  "maxChunkSize": 5242880,
  "minChunkSize": 262144,  // 256KB minimum to prevent abuse
  "expectedChunks": 2,
  "serverChecksum": true  // Server will compute checksums for verification
}
```

### 2. Upload File Data (Chunked)
```
PUT /api/v1/uploads/{uploadId}/chunks/{chunkIndex}
Content-Type: application/octet-stream
Content-Length: 5242880
Content-Range: bytes 0-5242879/10485760
X-Chunk-Checksum: sha256:a1b2c3d4...
X-Upload-Token: tok_secure_random_token
Authorization: Bearer {token}

Request Body:
[binary data]

Response: 200 OK (partial) or 202 Accepted
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "chunkIndex": 0,
  "chunkChecksum": "sha256:a1b2c3d4...",  // Server-verified
  "bytesReceived": 5242880,
  "bytesTotal": 10485760,
  "chunksCompleted": [0],
  "chunksRemaining": [1],
  "nextChunkUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/chunks/1",
  "complete": false,
  "uploadToken": "tok_new_token_for_next_chunk"  // Token rotation per chunk
}
```

### 3. Get Upload Status (For Resume)
```
GET /api/v1/uploads/{uploadId}
Authorization: Bearer {token}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "in_progress",  // initiated, in_progress, completed, failed, cancelled, quarantined
  "bytesReceived": 5242880,
  "bytesTotal": 10485760,
  "chunksCompleted": [0],
  "chunksRemaining": [1],
  "lastChunkReceivedAt": "2024-01-19T10:15:00Z",
  "createdAt": "2024-01-19T10:00:00Z",
  "expiresAt": "2024-01-20T10:30:00Z",
  "uploadToken": "tok_resume_token",  // New token for resuming
  "integrityStatus": {
    "verified": false,
    "failedChunks": []  // Chunks that failed verification
  }
}
```

### 4. Complete Upload (Explicit Finalization)
```
POST /api/v1/uploads/{uploadId}/complete
Content-Type: application/json
X-Upload-Token: tok_secure_random_token
Authorization: Bearer {token}

Request:
{
  "finalChecksum": "sha256:f1n2l3c4...",  // Checksum of entire file
  "chunkManifest": [  // Ordered list for verification
    {"index": 0, "checksum": "sha256:a1b2c3d4...", "size": 5242880},
    {"index": 1, "checksum": "sha256:b2c3d4e5...", "size": 5242880}
  ]
}

Response: 200 OK
{
  "fileId": "file_9z8y7x6w5v",
  "url": "/api/v1/files/file_9z8y7x6w5v",
  "status": "processing",  // processing, ready, quarantined, failed
  "integrityVerified": true,
  "processingEstimatedSeconds": 30,
  "webhookUrl": "/api/v1/webhooks/file_9z8y7x6w5v",  // For status updates
  "metadata": {...}
}
```

### 5. Cancel Upload
```
DELETE /api/v1/uploads/{uploadId}
Authorization: Bearer {token}
X-Upload-Token: tok_secure_random_token

Response: 204 No Content
Headers:
  X-Cleanup-Status: completed
  X-Storage-Freed: 5242880
```

### 6. Simple Direct Upload (small files only, <10MB)
```
POST /api/v1/files
Content-Type: multipart/form-data
Authorization: Bearer {token}

Request:
- file: binary data
- metadata: JSON string
- checksum: sha256 hash (required)

Response: 201 Created
{
  "fileId": "file_9z8y7x6w5v",
  "url": "/api/v1/files/file_9z8y7x6w5v",
  "status": "processing",
  "integrityVerified": true
}
```

### 7. Get Signed Download URL
```
POST /api/v1/files/{fileId}/download-url
Authorization: Bearer {token}
Content-Type: application/json

Request:
{
  "expiresIn": 3600,  // seconds, max 86400 (24h)
  "disposition": "attachment"  // or "inline"
}

Response: 200 OK
{
  "downloadUrl": "https://storage.example.com/signed-url?token=...",
  "expiresAt": "2024-01-19T11:00:00Z",
  "contentType": "application/pdf",
  "size": 10485760
}
```

## Data Models

### Upload Session
```typescript
interface UploadSession {
  uploadId: string;
  userId: string;
  filename: string;
  size: number;
  mimeType: string;
  metadata: Record<string, any>;
  status: 'initiated' | 'in_progress' | 'completed' | 'failed' | 'cancelled' | 'quarantined';
  bytesReceived: number;
  chunkSize: number;
  expectedChunks: number;
  chunks: Map<number, UploadChunk>;  // Indexed by chunk number
  storageKey: string;
  tempStorageKeys: string[];  // For cleanup on failure
  checksumAlgorithm: 'sha256' | 'sha512' | 'blake3';
  finalChecksum?: string;
  currentUploadToken: string;  // Rotates per chunk
  uploadTokens: string[];  // Historical for audit
  integrityStatus: {
    verified: boolean;
    lastVerificationAt?: Date;
    failedChunks: number[];
  };
  lockVersion: number;  // Optimistic locking for concurrent requests
  lockAcquiredAt?: Date;
  lockOwnerId?: string;  // Prevents race conditions
  createdAt: Date;
  updatedAt: Date;
  expiresAt: Date;
  lastActivityAt: Date;
  ipAddress: string;  // For security audit
  userAgent: string;
}

interface UploadChunk {
  index: number;
  size: number;
  checksum: string;
  checksumAlgorithm: string;
  serverChecksum: string;  // Independent server-side verification
  storageKey: string;  // Temporary storage location
  receivedAt: Date;
  verified: boolean;
  retryCount: number;
}
```

### File Record
```typescript
interface FileRecord {
  fileId: string;
  userId: string;
  filename: string;
  originalFilename: string;  // Unsanitized for display
  size: number;
  mimeType: string;
  detectedMimeType: string;  // From magic number analysis
  storageKey: string;
  storageProvider: string;
  storageRegion: string;
  checksum: string;
  checksumAlgorithm: string;
  metadata: Record<string, any>;
  status: 'processing' | 'ready' | 'failed' | 'quarantined' | 'deleted';
  securityScan: {
    status: 'pending' | 'clean' | 'infected' | 'suspicious' | 'failed';
    scannedAt?: Date;
    scanner: string;
    threats?: string[];
  };
  processingJobs: ProcessingJob[];
  encryption: {
    enabled: boolean;
    algorithm?: string;
    keyId?: string;  // Reference to KMS key
  };
  accessControl: {
    visibility: 'private' | 'internal' | 'public';
    allowedUsers?: string[];
    allowedGroups?: string[];
  };
  urls: {
    download: string;  // Requires auth
    thumbnail?: string;
    preview?: string;
  };
  retention: {
    policy: 'standard' | 'extended' | 'permanent';
    deleteAt?: Date;
  };
  auditLog: AuditEntry[];
  createdAt: Date;
  updatedAt: Date;
  deletedAt?: Date;
  uploadSessionId: string;  // Traceability
}

interface ProcessingJob {
  jobId: string;
  type: 'virus_scan' | 'thumbnail' | 'metadata_extract' | 'transcode';
  status: 'queued' | 'running' | 'completed' | 'failed';
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  retryCount: number;
}

interface AuditEntry {
  timestamp: Date;
  action: string;
  userId: string;
  ipAddress: string;
  details: Record<string, any>;
}
```

## Component Architecture

### 1. API Layer
- **UploadController**: Handles HTTP requests, validation, authentication
- **FileController**: Manages file retrieval and metadata operations
- **Middleware**: 
  - Auth (JWT validation)
  - Rate limiting (per-user, per-IP, per-endpoint)
  - Request size validation
  - CSRF protection
  - Content-Type validation
  - Upload token verification

### 2. Business Logic Layer
- **UploadService**: Orchestrates upload sessions, chunking logic
  - `initiateUpload()`: Creates session with optimistic lock
  - `uploadChunk()`: Validates, stores, verifies chunk atomically
  - `completeUpload()`: Assembles chunks, final verification
  - `resumeUpload()`: Handles reconnection with consistency checks
- **FileService**: File metadata management, lifecycle operations
- **ValidationService**: File type validation, size limits, security checks
  - MIME type vs extension validation
  - Magic number verification
  - Filename sanitization (prevent path traversal)
  - Content Security Policy validation
- **ChecksumService**: Integrity verification
  - Streaming checksum computation
  - Chunk-level and file-level verification
- **LockService**: Distributed locking for concurrent upload protection
  - Redis-based locks with TTL
  - Deadlock prevention
  - Lock acquisition retry logic
- **QuarantineService**: Handles suspicious/infected files
  - Isolated storage for quarantined files
  - Notification to security team
  - Automatic cleanup policies

### 3. Storage Layer
- **StorageAdapter Interface**: Abstract storage operations
  - `initiate(params)`: Prepare storage with encryption
  - `writeChunk(uploadId, chunkIndex, chunk)`: Atomic chunk write with verification
  - `assembleChunks(uploadId, manifest)`: Combine chunks with integrity check
  - `rollback(uploadId)`: Clean up on failure
  - `delete(uploadId)`: Secure deletion
  - `getSignedUrl(fileId, expiresIn)`: Generate time-limited URL
  - `verifyChecksum(key, expectedChecksum)`: Independent verification
- **Implementations**: 
  - S3Adapter (with S3 Object Lock support)
  - GCSAdapter (with retention policies)
  - AzureAdapter (with immutable storage)
  - LocalAdapter (with filesystem permissions)

### 4. Processing Layer
- **JobQueue**: Async job processing (Bull + Redis, or RabbitMQ)
  - Priority queues (virus scan = highest)
  - Dead letter queue for failures
  - Job deduplication
  - Exponential backoff retry
- **Processors**:
  - **VirusScanProcessor**: ClamAV/VirusTotal integration, quarantine on detection
  - **ThumbnailGenerator**: With size limits and timeout
  - **MetadataExtractor**: Safe parsing (sandboxed for untrusted formats)
  - **NotificationSender**: Webhook delivery with retry
  - **EncryptionProcessor**: At-rest encryption for sensitive files

### 5. Consistency Layer
- **TransactionCoordinator**: Ensures atomic operations across upload chunks
- **StateReconciliationService**: Periodic cleanup of orphaned/inconsistent uploads
  - Detects incomplete uploads past expiry
  - Cleans up dangling chunks in storage
  - Reconciles database vs storage state mismatches

## Error Handling

### Error Response Format
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
    retryable: boolean;
    retryAfter?: number;  // Seconds to wait before retry
    documentation: string;  // Link to error docs
  };
  requestId: string;
  timestamp: string;
}
```

### Error Codes & Recovery

#### Retryable Errors (with exponential backoff)
- **STORAGE_ERROR** (500): Storage backend failure → retry with different region if available
- **LOCK_ACQUISITION_FAILED** (409): Concurrent upload in progress → wait and retry
- **CHUNK_ASSEMBLY_FAILED** (500): Failed to combine chunks → re-verify chunks, retry assembly
- **CHECKSUM_COMPUTE_ERROR** (500): Temporary checksum failure → retry computation
- **RATE_LIMIT_EXCEEDED** (429): Too many requests → retry after `retryAfter` seconds

#### Non-Retryable Errors (client must fix)
- **INVALID_CHECKSUM** (400): Checksum mismatch → client must re-upload corrupt chunk(s)
- **FILE_TOO_LARGE** (413): Exceeds size limit → cannot proceed
- **INVALID_FILE_TYPE** (415): Unsupported MIME type → cannot proceed
- **UPLOAD_EXPIRED** (410): Session expired → must initiate new upload
- **UPLOAD_NOT_FOUND** (404): Invalid upload ID → check ID
- **UNAUTHORIZED** (401): Authentication failed → re-authenticate
- **INSUFFICIENT_QUOTA** (403): User quota exceeded → upgrade or cleanup
- **CHUNK_OUT_OF_ORDER** (400): Wrong chunk index → send correct chunk
- **INVALID_UPLOAD_TOKEN** (403): Token mismatch/expired → get fresh token from status endpoint
- **FILE_QUARANTINED** (451): File blocked by security → cannot complete

#### Edge Case Handling

**Chunk Corruption Detection:**
- Each chunk has client-provided AND server-computed checksum
- Mismatches result in `INVALID_CHECKSUM` with specific chunk index
- Client re-uploads only failed chunks
- Server maintains chunk verification status in database

**Concurrent Upload Prevention:**
- Optimistic locking with `lockVersion` field
- Redis-based distributed lock during chunk writes
- Lock timeout: 30 seconds (prevents deadlock)
- If lock held too long, system auto-releases and marks upload as failed

**Partial Upload Recovery:**
- Status endpoint returns exact list of completed chunks
- Client can resume from any missing chunk (no forced sequential order)
- Each chunk independently verifiable
- Idempotent chunk uploads (re-uploading same chunk with matching checksum is allowed)

**Assembly Failures:**
- If chunk assembly fails after all chunks received:
  - System marks upload as `failed` but preserves chunks for 24h
  - Client can trigger retry via `POST /api/v1/uploads/{uploadId}/retry-assembly`
  - After retry limit (3 attempts), chunks are cleaned up

**Token Compromise:**
- Upload tokens rotate per chunk (short-lived, single-use)
- Tokens bound to user session and IP address
- Old tokens invalidated after use
- If suspicious activity detected, entire upload session terminated

**Storage Inconsistency:**
- Background reconciliation job runs every 15 minutes
- Compares database chunk records with actual storage
- Auto-heals missing chunks from redundant storage if available
- Marks uploads as `failed` if chunks unrecoverable

### Retry Strategy

**Client-Side:**
- Transient errors (5xx, LOCK_ACQUISITION_FAILED): Exponential backoff starting 1s, max 32s, max 5 retries
- RATE_LIMIT_EXCEEDED: Use `retryAfter` header value
- INVALID_CHECKSUM: Re-upload specific chunk immediately (no backoff)
- Network failures: Resume from last completed chunk

**Server-Side:**
- Processing job failures: Exponential backoff (10s, 30s, 90s, 270s, max 4 retries)
- Storage operation failures: Immediate retry once, then fail fast
- Checksum verification: No retry (deterministic operation)

## Security Considerations

### Authentication & Authorization
1. **JWT Bearer Tokens**: Short-lived (15 min), refresh token rotation
2. **Upload Token System**: Per-upload single-use tokens that rotate per chunk
   - Prevents replay attacks
   - Limits blast radius of token compromise
3. **Authorization Checks**: User can only access their own uploads, enforced at every endpoint
4. **API Keys**: For service-to-service, stored hashed with scopes

### Rate Limiting (Tiered)
- **Initiate Upload**: 100/hour per user, 500/hour per IP
- **Chunk Upload**: 1000/hour per user (prevents DOS)
- **Status Check**: 500/hour per user
- **Download URL**: 200/hour per user

### File Validation (Defense in Depth)
1. **MIME Type Verification**: 
   - Don't trust client-provided MIME type
   - Use magic number detection (libmagic)
   - Cross-check extension, declared MIME, and detected MIME
2. **Filename Sanitization**:
   - Remove path traversal characters (../, ..\)
   - Strip NULL bytes
   - Limit length (255 chars)
   - Store original filename separately for display
3. **Size Limits**: 
   - Per-file: 5GB default, configurable by user tier
   - Per-chunk: Max 10MB (prevents memory exhaustion)
   - Per-user daily quota: 50GB
4. **Content Security**:
   - Serve files with `Content-Disposition: attachment` by default
   - Set `X-Content-Type-Options: nosniff`
   - Strip executable permissions from stored files
   - Serve from separate domain (prevents XSS via uploaded HTML)

### Virus Scanning (Multi-Layer)
1. **Real-time Scanning**: ClamAV on upload completion (blocking)
2. **Cloud Scanning**: VirusTotal API for suspicious files (async)
3. **Quarantine**: Infected files moved to isolated storage, never made accessible
4. **Notifications**: Security team alerted, user notified, audit logged

### Signed URLs (Secure Downloads)
- Time-limited (default 1h, max 24h)
- Single-use tokens (optional, for highly sensitive files)
- IP-bound (optional, for internal files)
- Audit logged (who accessed what, when)
- HMAC-SHA256 signed to prevent tampering

### Additional Protections
1. **CORS**: Strict allowlist of origins, credentials required
2. **Input Sanitization**: All metadata JSON fields sanitized against XSS
3. **Encryption at Rest**: AES-256 for sensitive files, KMS integration
4. **Encryption in Transit**: TLS 1.3 only, strong cipher suites
5. **Audit Logging**: All file access/modification logged with user context
6. **DDoS Protection**: Cloudflare/AWS Shield integration
7. **Secrets Management**: No credentials in code, use KMS/Vault
8. **Least Privilege**: Storage service account has minimal IAM permissions

## Configuration

```typescript
interface UploadConfig {
  maxFileSize: number;           // 5GB default
  maxChunkSize: number;          // 10MB default
  minChunkSize: number;          // 256KB (prevents abuse)
  sessionExpiryMinutes: number;  // 1440 (24h) default
  allowedMimeTypes: string[];    // [] = all, ['image/*', 'application/pdf'] for restrictions
  blockedExtensions: string[];   // ['.exe', '.bat', '.sh'] recommended
  requireChecksum: boolean;      // true (required for integrity)
  checksumAlgorithm: 'sha256' | 'sha512' | 'blake3';  // sha256 default
  virusScanEnabled: boolean;     // true (highly recommended)
  virusScanBlocking: boolean;    // true (blocks access until scan complete)
  encryptionEnabled: boolean;    // false default, true for sensitive data
  storage: {
    provider: 's3' | 'gcs' | 'azure' | 'local';
    bucket?: string;
    region?: string;
    redundancy: 'standard' | 'reduced' | 'high';  // Multi-region replication
    credentials?: any;
    encryption: 'sse-s3' | 'sse-kms' | 'client-side';
  };
  quotas: {
    dailyUploads: number;         // 100 default
    dailyBandwidth: number;       // 50GB default
    totalStorage: number;         // 100GB default
    maxConcurrentUploads: number; // 5 default
  };
  rateLimits: {
    initiatePerHour: number;
    chunkUploadPerHour: number;
    statusCheckPerHour: number;
  };
  security: {
    uploadTokenRotation: boolean;  // true recommended
    ipBindingEnabled: boolean;     // true for internal systems
    contentSecurityPolicy: string;
    serveFilesFromSeparateDomain: boolean;  // true recommended
  };
  cleanup: {
    failedUploadRetentionHours: number;     // 24 default
    completedUploadLogRetentionDays: number; // 90 default
    quarantinedFileRetentionDays: number;   // 30 default
  };
}
```

## What I Improved

### 1. **Chunk Ordering & Idempotency**
- Changed from sequential `PUT /data` to explicit `PUT /chunks/{chunkIndex}` 
- Allows out-of-order uploads and parallel chunk transfers
- Idempotent chunk uploads (same chunk can be re-uploaded safely)

### 2. **Upload Token Security**
- Added rotating single-use upload tokens per chunk
- Prevents replay attacks if token is intercepted
- Tokens now bound to IP address and session

### 3. **Dual Checksum Verification**
- Server computes checksums independently (not just trusting client)
- Detects corruption in transit AND malicious tampering
- Chunk manifest in completion request ensures assembly order

### 4. **Concurrency Control**
- Added optimistic locking with `lockVersion` field
- Distributed locking during chunk writes (prevents race conditions)
- Lock timeout protection against deadlocks

### 5. **State Reconciliation**
- Background job to detect and heal storage inconsistencies
- Handles edge cases like chunks in storage but not in database
- Auto-cleanup of orphaned uploads

### 6. **Explicit Chunk Status Tracking**
- `chunksCompleted` and `chunksRemaining` arrays for precise resume
- `failedChunks` list for targeted re-upload
- Per-chunk verification status in database

### 7. **Enhanced Error Handling**
- Split errors into retryable vs non-retryable with clear guidance
- Added `retryAfter` header for rate limiting
- Specific error for chunk corruption with chunk index
- Assembly retry mechanism for transient failures

### 8. **Security Hardening**
- Upload token rotation system (major improvement)
- Dual MIME type verification (client + magic number)
- Filename sanitization with path traversal protection
- Separate domain for serving files (XSS prevention)
- Quarantine status with "451 Unavailable For Legal Reasons"
- IP binding option for internal deployments

### 9. **Storage Inconsistency Handling**
- Edge case: chunks uploaded but database not updated → reconciliation detects and fixes
- Edge case: database says complete but storage missing → marks as failed, preserves chunks for retry
- Edge case: concurrent requests to same upload → distributed lock prevents corruption

### 10. **Audit Trail**
- Full audit log in FileRecord for compliance
- Upload session traceability via `uploadSessionId`
- Historical upload tokens for forensic analysis

## What I Kept

- **Two-stage upload pattern**: Excellent for pre-flight validation
- **Resumable upload architecture**: Core design is sound
- **Abstract storage layer**: Good separation of concerns
- **Async processing queue**: Right approach for virus scanning and thumbnails
- **Expiring sessions**: Prevents storage bloat
- **Configuration structure**: Comprehensive and well-organized
- **Multi-cloud support**: Future-proof design
- **Signed URLs for downloads**: Security best practice

## Remaining Concerns

### 1. **Maximum File Size Limits**
- 5GB default may be too small for video/backup use cases
- Should we support multi-hour uploads for very large files (100GB+)?
- Consider implementing upload pause/resume tokens valid for 7 days

### 2. **Chunk Assembly Performance**
- Assembling 1000+ chunks (for large files) could be slow
- Should we use native cloud provider multipart upload APIs (S3 CompleteMultipartUpload) instead of manual assembly?
- Trade-off: Less control over verification vs better performance

### 3. **Concurrent Upload Limits**
- 5 concurrent uploads per user may be too restrictive for legitimate use cases
- Consider dynamic limits based on user behavior and available bandwidth

### 4. **Quarantine Storage Costs**
- 30-day retention for quarantined files could accumulate significant storage costs
- Should we compress or deduplicate quarantined files?
- Consider tiered deletion (7 days for obvious malware, 30 days for suspicious)

### 5. **Token Rotation Overhead**
- Per-chunk token rotation adds latency and complexity
- For trusted internal systems, this may be overkill
- Make it configurable with strong recommendation to enable for public APIs

## Convergence Status

**ITERATING** - Significant improvements made, but need architect's input on performance trade-offs and scale considerations.

PROMPT_FOR_ARCHITECT:
I've added robust concurrency control, token rotation, and state reconciliation to handle the edge cases you highlighted. However, I'm concerned about the chunk assembly performance for very large files (1000+ chunks). Should we use native cloud provider multipart upload APIs (like S3's CompleteMultipartUpload) for better performance, even though it gives us less control over the verification process? Also, what's your stance on the maximum file size - is 5GB sufficient, or should we design for 100GB+ files with multi-day upload sessions?

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

## Design

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

## Rationale

### 1. Native Cloud Provider APIs (Major Change)
**Decision**: Use S3 multipart upload, GCS resumable upload, Azure block blobs directly instead of always doing manual assembly.

**Why**: 
- Assembly of 10,000 chunks takes 5-10 minutes manually (read all chunks, concatenate, write final file)
- Native APIs complete instantly (provider assembles internally, no data movement)
- Enables 1TB files (10,000 parts × 100MB = 1TB) without custom infrastructure
- Trade-off: Less control over verification, but we compensate with streaming checksums

**When Manual Assembly**: Files <100MB (overhead not worth it), or when native API fails (automatic fallback)

### 2. Streaming Checksum Verification (Major Change)
**Decision**: Compute checksums incrementally during upload, not after completion.

**Why**:
- Post-upload verification requires reading entire file again (doubles I/O)
- For 100GB file, post-verification takes 10+ minutes
- Streaming verification adds zero latency (computed inline)
- State persisted in Redis enables resume without starting over
- **Critical for scale**: Makes 1TB uploads practical

### 3. Extended Session Expiry (7 Days → 30 Days Max)
**Decision**: Allow upload sessions up to 30 days with extensions.

**Why**:
- 100GB upload on 10Mbps connection = 24+ hours
- 1TB upload = 10+ days even on 100Mbps
- Users on mobile/intermittent connections need multi-day sessions
- Grace period + cleanup prevents storage bloat

### 4. Configurable Token Rotation
**Decision**: Make token rotation configurable (strict/balanced/relaxed), not always-on.

**Why**:
- Per-chunk rotation adds 50-100ms latency per chunk (token generation + database write)
- For 10,000 chunk upload = 500-1000 seconds of pure overhead
- Internal systems/trusted environments don't need this overhead
- Keep as option for public APIs (security vs performance trade-off)

### 5. Bitmap Chunk Tracking
**Decision**: Use bitmaps for uploads with >1000 chunks, ranges for 100-1000, full arrays for <100.

**Why**:
- Storing 10,000 chunk IDs as JSON array = 50KB+ per upload session
- Bitmap = 1.25KB (40x smaller)
- Faster status checks (bitmap operations vs array iteration)
- Database storage savings at scale (100M uploads × 50KB vs 1.25KB = 4.5TB saved)

### 6. Async Completion (202 Accepted)
**Decision**: Return `202 Accepted` immediately on completion, process in background.

**Why**:
- Assembly of 10,000 chunks can take 5-10 minutes (if managed mode)
- Virus scan takes 30-120 seconds for large files
- Blocking completion request = poor UX (client times out)
- Webhooks + status polling = better UX for long operations

### 7. IP Binding Disabled for Long Uploads
**Decision**: Don't bind upload tokens to IP for sessions >24h.

**Why**:
- Mobile users change IPs constantly (cell tower handoff)
- Multi-day uploads would break every time user moves
- User-agent fingerprinting + JWT auth sufficient for security
- Enterprise users on VPNs also see frequent IP changes

### 8. Parallel Chunk Uploads (10 Concurrent)
**Decision**: Allow 10 concurrent chunk uploads per session.

**Why**:
- Single-threaded upload on 1Gbps connection = underutilized (TCP congestion control limits single stream)
- 10 parallel streams = near-line-rate utilization
- Modern browsers/SDKs support parallel requests natively
- Server side: Stateless chunk handling (no ordering requirement) makes this trivial

### 9. Separate Domain for File Serving
**Decision**: Serve files from `files.example.com`, not `api.example.com`.

**Why**:
- XSS prevention (uploaded HTML can't access API cookies)
- CSP enforcement (strict policy on separate domain)
- CDN integration easier (different caching rules)
- Security best practice for user-generated content

### 10. Fallback from Native to Managed
**Decision**: Auto-fallback to managed assembly if native multipart fails.

**Why**:
- Cloud provider APIs can fail (rate limits, eventual consistency issues, service outages)
- Transparent to client (same completion endpoint)
- Ensures reliability without forcing client retry
- Trade-off: Slower, but completes successfully

## What I Changed

### From Previous Design:

1. **Added Native Cloud Provider Integration**: S3 multipart upload, GCS resumable upload, Azure block blobs as primary path (vs always manual assembly). This is the biggest performance improvement.

2. **Streaming Verification**: Moved checksum computation from post-upload to during-upload (incremental). Eliminates verification latency entirely.

3. **Bitmap Chunk Tracking**: Replaced full chunk arrays with bitmaps for large uploads (>1000 chunks). 40x storage savings, faster queries.

4. **Extended Session Expiry**: Increased from 24h to 7d default, 30d max with extensions. Supports multi-day uploads for 100GB+ files.

5. **Configurable Token Rotation**: Made per-chunk rotation optional (balanced/relaxed modes) instead of always-on. Reduces overhead for trusted environments.

6. **Async Completion**: Changed completion to `202 Accepted` with background processing instead of blocking until done. Better UX for large files.

7. **Parallel Upload Support**: Explicit support for 10 concurrent chunk uploads per session. 10x throughput improvement.

8. **Pause/Resume Endpoints**: Added explicit pause endpoint (vs just expiry-based). Better UX control.

9. **Batch Status Checks**: Added batch endpoint for checking multiple uploads. 90% reduction in API calls.

10. **IP Binding Disabled for Long Uploads**: Recognized mobile/VPN use case, disabled IP binding for >24h sessions.

11. **Fallback Strategy**: Auto-fallback from native to managed if cloud APIs fail. Transparent reliability.

12. **Performance Tiers**: Made chunk size, concurrency, expiry adaptive to file size. No one-size-fits-all.

## What I Kept

- **Two-stage upload pattern** (initiate → upload → complete): Essential for pre-flight validation and quota checks
- **Resumable upload architecture**: Core requirement for reliability
- **Abstract storage layer**: Enables multi-cloud without client changes
- **Async processing queue**: Right pattern for virus scanning and thumbnails
- **Dual checksum verification** (client + server): Security best practice
- **Distributed locking**: Prevents race conditions on concurrent operations
- **Quarantine system**: Security requirement for infected files
- **Signed URLs**: Secure download pattern
- **Audit logging**: Compliance requirement
- **Error categorization** (retryable vs non-retryable): Good client guidance
- **Rate limiting**: Abuse prevention
- **Cleanup jobs**: Prevents storage bloat

## Open Questions

### 1. Checksum Algorithm Choice
- **SHA256**: Widely supported, 256-bit security, slower (300 MB/s)
- **BLAKE3**: 10x faster (3 GB/s), parallelizable, but less mature tooling
- **Recommendation**: SHA256 default, BLAKE3 optional for large files
- **Question**: Should we auto-select based on file size (SHA256 <1GB, BLAKE3 >1GB)?

### 2. Virus Scanning for Very Large Files
- ClamAV struggles with >10GB files (memory exhaustion)
- VirusTotal API has 650MB limit
- **Options**:
  - Skip scanning for files >10GB (security risk)
  - Chunked scanning (scan first/last 100MB + random samples)
  - Enterprise-grade scanner (McAfee, Sophos) for large files
- **Question**: What's acceptable security/performance trade-off?

### 3. Cost Optimization for Quarantine
- 30-day retention for suspicious files = significant storage costs at scale
- **Options**:
  - Compress quarantined files (90% savings, but slow access)
  - Deduplicate (many infected files are identical)
  - Tiered deletion (7d for confirmed, 30d for suspicious)
- **Question**: What's the compliance requirement here?

### 4. Multi-Region Upload Routing
- For global users, uploading to nearest region is faster
- But adds complexity (regional routing, cross-region replication)
- **Options**:
  - Single region (simple, higher latency for distant users)
  - Multi-region with geo-routing (complex, lower latency)
  - S3 Transfer Acceleration (simple, lower latency, AWS-only)
- **Question**: Is global performance worth the complexity?

### 5. Client SDK vs DIY Integration
- Should we provide official SDKs (Python, JS, Go) with automatic chunking, retry, resume?
- **Benefits**: Easier adoption, fewer support requests, better performance
- **Costs**: Maintenance burden, version fragmentation
- **Question**: Build SDKs or just provide OpenAPI spec?

## Convergence Status

**ITERATING** - Substantial redesign with native cloud APIs, streaming verification, and scalability improvements. Need validation on checksum algorithm choice, virus scanning strategy for very large files, and whether to build client SDKs.

PROMPT_FOR_CRITIC:
I've redesigned around native cloud provider multipart APIs (S3, GCS, Azure) as the primary path, with streaming checksum verification and bitmap chunk tracking for scalability. This enables 1TB files with multi-day uploads and eliminates assembly latency. However, I need your scrutiny on three areas: (1) Is streaming checksum verification actually secure, or does it open replay attack vectors? (2) Does the auto-fallback from native to managed assembly create a reliability gap (what if managed also fails)? (3) For 1TB files with 10,000 chunks, is the status endpoint response (with chunksCompleted array) going to be too large (50KB+), and should we use pagination or range compression even in responses?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

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
  "uploadTokenNonce": "nonce_abc123",  // Prevents replay attacks
  "expiresAt": "2024-01-26T10:30:00Z",
  "uploadUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/chunks",
  "resumable": true,
  "uploadMethod": "native_multipart",
  "chunkSize": 10485760,
  "minChunkSize": 5242880,
  "maxChunkSize": 104857600,
  "expectedChunks": 10240,
  "serverChecksum": true,
  "capabilities": {
    "parallelUploads": 10,
    "streamingVerification": true,
    "pauseResume": true,
    "bandwidthThrottling": true
  },
  "cloudProvider": {
    "type": "s3",
    "multipartUploadId": "mp_aws_xyz123",
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
X-Chunk-Sequence: 0  // Monotonic counter to prevent replay
X-Upload-Token: tok_secure_random_token
X-Token-Nonce: nonce_abc123
Authorization: Bearer {token}

Request Body:
[binary data]

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "chunkIndex": 0,
  "chunkChecksum": "sha256:a1b2c3d4...",
  "checksumMatch": true,
  "checksumContext": "ctx_stream_state_xyz",  // Opaque checksum state for resume
  "bytesReceived": 10485760,
  "etag": "abc123def456",
  "uploadedAt": "2024-01-19T10:15:30Z",
  "uploadDurationMs": 1250,
  "transferRate": "8.39 MB/s"
}
```

### 3. Get Upload Status (Compressed Representation)
```
GET /api/v1/uploads/{uploadId}
Authorization: Bearer {token}
Accept: application/json

Query Parameters:
?includeChunkDetails=false  // Default false - omits full chunk array
?chunkDetailsFormat=ranges  // ranges, bitmap, or full

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "in_progress",
  "bytesReceived": 1073741824,
  "bytesTotal": 107374182400,
  "percentComplete": 1.0,
  
  // Compact representation (default)
  "chunksCompletedCount": 103,
  "chunksTotal": 10240,
  "chunksCompletedRanges": "0-102",  // RFC 7233 range format
  "chunksInProgressRanges": "104-106",
  
  // Detailed chunk info (only if includeChunkDetails=true)
  "chunksDetailed": {
    "format": "ranges",  // or "bitmap" or "full"
    "completed": "0-102,104-150,200-250",  // Compressed range notation
    "failed": "103",  // Chunks that failed verification
    "inProgress": "151-153"
  },
  
  "estimatedTimeRemainingSeconds": 86400,
  "uploadRateMBps": 1.15,
  "lastChunkReceivedAt": "2024-01-19T10:15:00Z",
  "createdAt": "2024-01-19T10:00:00Z",
  "expiresAt": "2024-01-26T10:00:00Z",
  "uploadToken": "tok_resume_token",
  "uploadTokenNonce": "nonce_current",
  
  "integrityStatus": {
    "chunksVerified": 103,
    "verificationFailures": [],
    "streamingVerificationEnabled": true,
    "checksumContext": "ctx_stream_state_xyz"  // For resuming checksum computation
  },
  
  "cloudProvider": {
    "multipartUploadId": "mp_aws_xyz123",
    "uploadedPartsCount": 103  // Count only, not full array
  },
  
  "extensionRequest": {
    "available": true,
    "maxExtensionHours": 168
  }
}
```

### 4. Get Chunk Details (Paginated)
```
GET /api/v1/uploads/{uploadId}/chunks
Authorization: Bearer {token}

Query Parameters:
?status=completed  // Filter: completed, failed, pending, in_progress
?limit=100         // Default 100, max 1000
?offset=0          // Pagination offset
?format=ranges     // ranges (default), full, or bitmap

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "format": "ranges",
  "chunks": {
    "completed": "0-102,200-250",
    "failed": "103",
    "pending": "104-199,251-10239",
    "inProgress": "151-153"
  },
  "pagination": {
    "limit": 100,
    "offset": 0,
    "total": 10240,
    "hasMore": false
  }
}
```

### 5. Complete Upload (Enhanced Verification)
```
POST /api/v1/uploads/{uploadId}/complete
Content-Type: application/json
X-Upload-Token: tok_secure_random_token
X-Token-Nonce: nonce_current
Authorization: Bearer {token}

Request:
{
  "finalChecksum": "sha256:f1n2l3c4...",
  "checksumContext": "ctx_stream_state_xyz",  // Streaming checksum state from last chunk
  "verificationMode": "streaming",  // streaming (default), incremental, or full
  "chunkCount": 10240
}

Response: 202 Accepted
{
  "fileId": "file_9z8y7x6w5v",
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "finalizing",
  "completionJobId": "job_completion_xyz",
  "estimatedCompletionSeconds": 120,
  "statusUrl": "/api/v1/uploads/upl_7x9k2m3n4p5q6r/completion-status",
  "webhookUrl": "/api/v1/webhooks/file_9z8y7x6w5v",
  "integrityVerification": {
    "method": "streaming",
    "requiresFullScan": false,
    "checksumVerified": true  // If streaming, verified during upload
  },
  "fallbackPlan": {
    "available": true,  // Can retry with managed assembly if native fails
    "estimatedFallbackSeconds": 600  // If fallback needed
  }
}
```

### 6. Get Completion Status
```
GET /api/v1/uploads/{uploadId}/completion-status
Authorization: Bearer {token}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "fileId": "file_9z8y7x6w5v",
  "status": "processing",
  "completionProgress": {
    "stage": "virus_scan",
    "percentComplete": 45,
    "estimatedSecondsRemaining": 30
  },
  "integrityVerified": true,
  "assemblyMethod": "native",  // native or managed
  "retryAttempts": 0,
  "file": {
    "url": "/api/v1/files/file_9z8y7x6w5v",
    "size": 107374182400,
    "checksum": "sha256:f1n2l3c4...",
    "status": "processing"
  }
}
```

### 7. Request Upload Extension
```
POST /api/v1/uploads/{uploadId}/extend
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "extensionHours": 168
}

Response: 200 OK
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "oldExpiresAt": "2024-01-26T10:00:00Z",
  "newExpiresAt": "2024-02-02T10:00:00Z",
  "extensionsRemaining": 2,
  "maxTotalUploadDays": 30
}
```

### 8. Pause Upload
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
  "resumeNonce": "nonce_resume_123",
  "checksumContext": "ctx_stream_state_xyz",  // Preserve checksum state
  "pausedExpiresAt": "2024-01-26T15:00:00Z"
}
```

### 9. Cancel Upload (Enhanced Cleanup)
```
DELETE /api/v1/uploads/{uploadId}
Authorization: Bearer {token}
X-Upload-Token: tok_secure_random_token
X-Token-Nonce: nonce_current

Response: 202 Accepted
{
  "uploadId": "upl_7x9k2m3n4p5q6r",
  "status": "cancelling",
  "cleanupJobId": "job_cleanup_abc",
  "estimatedCleanupSeconds": 60,
  "storageToFree": 1073741824,
  "cleanupMethod": "native_abort"  // native_abort or managed_delete
}
```

### 10. Simple Direct Upload (Small Files <100MB)
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

### 11. Get Signed Download URL
```
POST /api/v1/files/{fileId}/download-url
Authorization: Bearer {token}
Content-Type: application/json

Request:
{
  "expiresIn": 3600,
  "disposition": "attachment",
  "supportRangeRequests": true
}

Response: 200 OK
{
  "downloadUrl": "https://storage.example.com/signed-url?token=...",
  "expiresAt": "2024-01-19T11:00:00Z",
  "contentType": "video/mp4",
  "size": 107374182400,
  "supportsRangeRequests": true,
  "checksumHeader": "x-amz-checksum-sha256",
  "recommendedChunkSize": 10485760
}
```

### 12. Batch Status Check (Optimized)
```
POST /api/v1/uploads/batch/status
Content-Type: application/json
Authorization: Bearer {token}

Request:
{
  "uploadIds": ["upl_1", "upl_2", "upl_3"],
  "includeChunkDetails": false  // Default false for performance
}

Response: 200 OK
{
  "uploads": [
    {
      "uploadId": "upl_1",
      "status": "in_progress",
      "percentComplete": 45,
      "chunksCompletedCount": 450,
      "chunksTotal": 1000
    },
    {
      "uploadId": "upl_2",
      "status": "completed",
      "fileId": "file_xyz"
    }
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
  
  // Optimized chunk tracking - always use bitmap or ranges
  chunkTrackingMode: 'bitmap' | 'ranges';  // Removed 'full' mode
  chunksCompletedBitmap?: Buffer;  // For >1000 chunks
  chunksCompletedRanges?: string;  // RFC 7233 format: "0-102,200-250"
  chunksCompletedCount: number;
  chunksFailedRanges?: string;  // Track failed chunks for retry
  lastChunkIndex: number;
  
  // Native cloud provider integration
  uploadMethod: 'native_multipart' | 'managed_chunks';
  cloudProvider: {
    type: 's3' | 'gcs' | 'azure';
    multipartUploadId?: string;
    uploadedPartsCount: number;  // Count only, full list in separate store
    region: string;
  };
  
  storageKey: string;
  tempStoragePath?: string;
  checksumAlgorithm: 'sha256' | 'sha512' | 'blake3';
  finalChecksum?: string;
  
  // Streaming verification with replay protection
  streamingVerification: {
    enabled: boolean;
    checksumContext: string;  // Serialized checksum state
    verifiedBytes: number;
    lastVerifiedAt: Date;
    sequenceNumber: number;  // Monotonic counter to detect replays
    expectedSequence: number;
  };
  
  // Security tokens with replay protection
  currentUploadToken: string;
  currentTokenNonce: string;  // Unique nonce per token
  usedNonces: Set<string>;  // Recent nonces to prevent replay (TTL: 1h)
  tokenRotationEnabled: boolean;
  tokenExpiresAt: Date;
  
  // Concurrency control
  lockVersion: number;
  activeChunkUploads: Set<number>;
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
  
  // Audit (minimal)
  clientInfo: {
    ipAddress: string;
    userAgent: string;
    sdkVersion?: string;
  };
}

// Separate storage for part details (not in main session record)
interface CloudProviderPartList {
  uploadId: string;
  parts: Array<{
    partNumber: number;
    etag: string;
    size: number;
    checksum: string;
  }>;
  lastUpdated: Date;
  ttl: Date;  // Auto-expire after upload completes
}

interface UploadChunk {
  index: number;
  size: number;
  checksum: string;
  etag?: string;
  receivedAt: Date;
  verified: boolean;
  retryCount: number;
  uploadDurationMs: number;
  sequenceNumber: number;  // For replay detection
}
```

### File Record
```typescript
interface FileRecord {
  fileId: string;
  userId: string;
  filename: string;
  originalFilename: string;
  size: number;
  mimeType: string;
  detectedMimeType: string;
  
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
  
  checksum: string;
  checksumAlgorithm: string;
  verificationMethod: 'streaming' | 'post-upload' | 'deferred';
  integrityVerifiedAt: Date;
  
  metadata: Record<string, any>;
  
  status: 'finalizing' | 'processing' | 'ready' | 'failed' | 'quarantined' | 'archived' | 'deleted';
  
  securityScan: {
    status: 'pending' | 'scanning' | 'clean' | 'infected' | 'suspicious' | 'failed' | 'skipped';
    scannedAt?: Date;
    scanner: string;
    scannerVersion?: string;
    threats?: Array<{name: string, severity: string}>;
    scanDurationMs?: number;
    chunkedScanStrategy?: 'full' | 'sampled';  // For large files
  };
  
  processingJobs: ProcessingJob[];
  
  accessControl: {
    visibility: 'private' | 'internal' | 'public';
    allowedUsers?: string[];
    allowedGroups?: string[];
    allowedUntil?: Date;
  };
  
  retention: {
    policy: 'standard' | 'extended' | 'permanent' | 'custom';
    deleteAt?: Date;
    archiveAt?: Date;
    lastAccessedAt?: Date;
    accessCount: number;
  };
  
  derivatives: Array<{
    type: 'thumbnail' | 'preview' | 'transcode';
    format: string;
    size: number;
    storageKey: string;
    url: string;
  }>;
  
  uploadSessionId: string;
  sourceIpAddress: string;
  
  uploadDurationSeconds: number;
  processingDurationSeconds: number;
  
  createdAt: Date;
  updatedAt: Date;
  completedAt?: Date;
  deletedAt?: Date;
  
  auditLogId: string;
}

interface ProcessingJob {
  jobId: string;
  type: 'assembly' | 'virus_scan' | 'thumbnail' | 'metadata_extract' | 'transcode' | 'checksum_verify';
  priority: number;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';
  queuedAt: Date;
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  retryCount: number;
  maxRetries: number;
  progressPercent: number;
  estimatedDurationSeconds?: number;
  dependencies: string[];
}
```

## Component Architecture

### 1. API Layer
- **UploadController**: HTTP request handling, validation, auth
- **FileController**: File retrieval, metadata operations
- **BatchController**: Bulk operations for performance
- **Middleware**:
  - Auth (JWT validation with 15min cache)
  - Rate limiting (token bucket, Redis-backed)
  - Request size validation
  - CSRF protection (double-submit cookie)
  - Content-Type validation
  - Upload token + nonce verification (replay protection)
  - Request ID injection (distributed tracing)

### 2. Business Logic Layer

#### Upload Service (Core Orchestration)
- **UploadOrchestrator**: High-level upload flow management
  - `initiateUpload()`: Determines native vs managed mode
  - `selectUploadStrategy()`: Auto-selects optimal chunk size and concurrency
  - `routeChunkUpload()`: Routes to native or managed handler

#### Native Multipart Handler
- **S3MultipartAdapter**: 
  - Uses AWS S3 Multipart Upload API
  - Direct part upload with ETag tracking
  - Assembly via CompleteMultipartUpload
  - **Fallback trigger**: CompleteMultipartUpload failure after 3 retries
  - **Abort trigger**: 5xx errors, invalid part errors
  
- **GCSResumableAdapter**:
  - GCS resumable upload protocol
  - Single session for entire file
  - **Fallback trigger**: Session failure, 503 errors
  
- **AzureBlockBlobAdapter**:
  - Block blob staging and commitment
  - **Fallback trigger**: CommitBlockList failure

#### Managed Chunk Handler (Fallback Path)
- **ManagedChunkService**:
  - Manual chunk storage and assembly
  - Used for: <100MB files, native API failures, local storage
  - Assembly: Streaming concatenation with verification
  - **Double-failure handling**: If managed assembly also fails, mark upload as failed and notify user with manual intervention option

#### Supporting Services

- **StreamingChecksumService**: 
  - Incremental checksum computation with serializable state
  - **Replay Protection**: 
    - Maintains monotonic sequence counter per upload
    - Each chunk includes sequence number in header
    - Rejects out-of-order or duplicate sequences
    - Nonce validation prevents token replay
  - **State Management**:
    - Checksum context stored in Redis (encrypted)
    - TTL matches upload expiry
    - Resume: Load context, continue from last verified chunk
  - **Security**: 
    - Client provides checksum per chunk
    - Server independently computes streaming checksum
    - Mismatch = reject chunk, don't update state
  - **Algorithm Choice**:
    - SHA256 default (<1GB files)
    - BLAKE3 for >1GB (10x faster, parallelizable)
    - Auto-selected based on file size
  
- **ChunkTrackerService**:
  - **Always uses compressed format** (no full arrays)
  - <1000 chunks: RFC 7233 range notation ("0-102,200-250")
  - >1000 chunks: Bitmap (10,000 chunks = 1.25KB)
  - O(1) lookup via bitmap operations
  - **Response optimization**: Status endpoint returns ranges by default, pagination endpoint for details
  
- **UploadStrategyService**:
  - Determines optimal chunk size
  - Recommends concurrency level
  - Auto-tunes based on historical metrics
  
- **ValidationService**: 
  - MIME type verification (magic numbers + extension)
  - Filename sanitization (path traversal prevention)
  - Size and quota enforcement
  - Content Security Policy checks
  
- **LockService**: 
  - Distributed locking (Redis Redlock)
  - Per-upload locks (not per-chunk)
  - Auto-renewal for long operations
  
- **QuarantineService**: 
  - Isolated storage for infected files
  - Compressed storage (90% savings)
  - Tiered retention: 7d confirmed, 30d suspicious
  - Forensic archive before deletion

### 3. Storage Layer

#### Storage Adapter Interface
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
  
  // Health check for fallback decisions
  healthCheck(): Promise<HealthStatus>;
}

interface HealthStatus {
  healthy: boolean;
  latencyMs: number;
  errorRate: number;
  canFallback: boolean;
}
```

#### Implementations
- **S3Adapter**: 
  - Native multipart for >100MB files
  - Max 10,000 parts × 5GB = 5TB
  - S3 Transfer Acceleration for cross-region
  - Server-side encryption (SSE-S3/KMS)
  - **Health check**: HEAD request to bucket, track 5xx rate
  
- **GCSAdapter**: 
  - Resumable uploads for >100MB
  - Composite objects for managed mode
  - Customer-managed encryption keys
  
- **AzureAdapter**: 
  - Block blobs with staging
  - Max 50,000 blocks × 100MB = 4.75TB
  
- **LocalAdapter**: 
  - Managed chunks only
  - Direct filesystem with atomic renames

### 4. Processing Layer

#### Job Queue Architecture
- **Queue System**: Bull (Redis) or RabbitMQ
- **Priority Queues**:
  - P0: Virus scanning (blocks access)
  - P1: Assembly for large files
  - P2: Metadata extraction
  - P3: Thumbnails, transcoding
- **Concurrency**: 10 workers per queue
- **Dead Letter Queue**: 3 retries, then DLQ
- **Job Deduplication**: Content-addressed

#### Processors

- **AssemblyProcessor** (managed chunks only):
  - Streams chunks to final storage (no intermediate copy)
  - Computes final checksum during assembly
  - **Failure handling**: 
    - Transient failures (network): Retry 3x with exponential backoff
    - Permanent failures (missing chunk): Mark upload as failed, preserve chunks for 24h
    - Partial assembly: Atomic rollback, no corrupt files left
  - Duration: ~60s per 10GB at 200MB/s
  
- **VirusScanProcessor**:
  - **Tiered scanning strategy**:
    - <1GB: Full file scan (ClamAV)
    - 1-10GB: Full scan with streaming (memory-efficient)
    - >10GB: Sampled scan (first 100MB, last 100MB, 5 random 100MB chunks)
  - VirusTotal API for deep analysis (async, non-blocking)
  - **Large file handling**: 
    - Stream file in chunks to scanner (no full buffering)
    - For >10GB, flag as "sampled_scan" in metadata
    - Option to request full scan (manual, async)
  - Quarantine on detection (atomic move)
  - Duration: ~30s per 1GB
  
- **ThumbnailProcessor**:
  - Multiple sizes (small/medium/large)
  - Sandboxed execution (container-based)
  - Timeout: 60s per file
  
- **MetadataExtractor**:
  - EXIF, video codec, document properties
  - Sandboxed for security
  - Timeout: 30s
  
- **ChecksumVerifier** (post-upload, optional):
  - For files using native multipart without streaming verification
  - Computes full file checksum
  - Marks as verified in database

### 5. Consistency and Reliability Layer

#### Transaction Coordinator
- **UploadTransactionManager**:
  - Two-phase commit for database + storage
  - Atomic chunk completion updates
  - Rollback capability

#### Fallback Coordination Service
- **FallbackCoordinator**:
  - Monitors native API health per provider
  - Circuit breaker pattern (open after 5 consecutive failures)
  - **Fallback decision tree**:
    1. Native API fails during complete → Retry 3x (1s, 3s, 9s)
    2. All retries fail → Initiate managed assembly
    3. Managed assembly fails → Preserve state, notify user, manual intervention
  - **Double-failure protocol**:
    - Mark upload as "needs_manual_assembly"
    - Preserve all chunks (extended TTL: 7 days)
    - Alert ops team
    - User sees: "Processing delayed, we're working on it"
    - Manual options: Re-trigger assembly, download chunks, full refund
  - **Metrics**: Track fallback rate per provider, alert if >5%

#### State Reconciliation Service
- **ReconciliationJob** (every 30 minutes):
  - Detects orphaned uploads
  - Finds incomplete uploads past expiry
  - Identifies storage vs database mismatches
  - Auto-heals: Re-creates database records if valid
  - Auto-cleans: Deletes storage if cancelled/failed
  
- **StorageAudit** (daily):
  - Compares file records with actual storage
  - Detects missing files
  - Verifies checksums on sample (1% of files)
  - Alerts on discrepancies

#### Cleanup Service
- **UploadCleanupJob** (hourly):
  - Deletes expired upload sessions
  - Removes temporary chunks for completed uploads
  - Aborts native multipart uploads in cloud providers
  
- **QuarantineCleanupJob** (daily):
  - Tiered deletion: 7d confirmed, 30d suspicious
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
    requestId: string;
  };
  timestamp: string;
}
```

### Error Categories

#### Retryable Errors
- **STORAGE_UNAVAILABLE** (503): Cloud provider downtime → exponential backoff, max 5 retries
- **LOCK_TIMEOUT** (409): Concurrent operation → wait 1s, retry 3x
- **RATE_LIMIT_EXCEEDED** (429): Quota exceeded → retry after `retryAfter`
- **CHECKSUM_COMPUTE_FAILED** (500): Temporary error → immediate retry once
- **INTERNAL_SERVER_ERROR** (500): Generic server error → exponential backoff
- **ASSEMBLY_RETRY** (503): Native assembly failed, attempting managed → client waits

#### Non-Retryable Errors
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
- **MULTIPART_UPLOAD_FAILED** (500): Native API failed after all retries → fallback in progress
- **REPLAY_ATTACK_DETECTED** (403): Duplicate nonce or out-of-sequence → invalid request
- **ASSEMBLY_FAILED_PERMANENTLY** (500): Both native and managed assembly failed → manual intervention needed

#### Edge Cases Handled

**1. Chunk Checksum Mismatch:**
- Client uploads chunk with checksum `sha256:abc123`
- Server computes `sha256:def456` during streaming
- Response: `400 CHUNK_CHECKSUM_MISMATCH` with `chunkIndex: 5`
- **Streaming state rollback**: Checksum context NOT updated
- Client re-uploads chunk 5 with correct data
- Server resumes streaming checksum from previous valid state

**2. Native Multipart Assembly Failure:**
- S3 `CompleteMultipartUpload` returns error
- Server retries 3x (1s, 3s, 9s)
- All retries fail → FallbackCoordinator triggers managed assembly
- Client status: `status: "finalizing"`, `assemblyMethod: "managed"`
- If managed assembly also fails:
  - Upload marked as `needs_manual_assembly`
  - Chunks preserved for 7 days
  - User notified: "Upload processing delayed"
  - Manual intervention: Ops team re-triggers or provides download

**3. Upload Token Expiry Mid-Upload:**
- Token expires during chunk upload
- Response: `403 INVALID_TOKEN` with `newToken: "tok_refreshed"`, `newNonce: "nonce_xyz"`
- Client uses new token + nonce for next chunk
- Old chunks remain valid

**4. Concurrent Chunk Uploads (Same Index):**
- Two requests upload chunk 5 simultaneously
- First request acquires lock, succeeds
- Second request: `409 LOCK_TIMEOUT`, retries after 1s
- On retry, chunk complete → `200 OK` (idempotent)

**5. Partial Upload After Expiry:**
- Upload expires at 50% complete
- Client resumes: `410 UPLOAD_EXPIRED`
- Cleanup job removes chunks after 24h grace period
- Client must initiate new upload

**6. Storage Inconsistency (Missing Chunk):**
- Database: chunk 5 complete
- Storage: chunk 5 missing
- Reconciliation job: Marks chunk 5 incomplete
- Client status: chunk 5 in `chunksRemaining`
- Client re-uploads chunk 5

**7. Completion Request Before All Chunks Uploaded:**
- Client calls complete: `chunkCount: 100`, only 98 uploaded
- Response: `400 INCOMPLETE_UPLOAD` with `chunksRemaining: "45,67"`
- Client uploads missing chunks, retries completion

**8. File Download Corruption:**
- Client downloads, checksum mismatch
- Client reports: `POST /api/v1/files/{fileId}/report-corruption`
- Server re-verifies checksum in storage
- If mismatch: Mark corrupted, trigger re-assembly (if chunks available)
- If chunks gone: Mark unrecoverable, notify user

**9. Virus Detected After Completion:**
- Initially marked clean
- VirusTotal async scan (24h later): threat found
- File atomically moved to quarantine
- Status: `quarantined`
- Webhooks + email notification
- Downloads: `451 Unavailable For Legal Reasons`

**10. Multi-Day Upload with Network Changes:**
- 100GB upload over 3 days
- IP changes mid-upload
- Token validation: IP binding disabled for >24h uploads
- User-agent fingerprinting used instead
- Upload continues seamlessly

**11. Replay Attack Attempt:**
- Attacker captures chunk upload request (token + nonce)
- Attempts to replay request
- Server checks `usedNonces` set: nonce already used
- Response: `403 REPLAY_ATTACK_DETECTED`
- Legitimate client continues with new nonce

**12. Streaming Checksum State Corruption:**
- Redis failure loses checksum context
- Client tries to upload next chunk
- Server detects missing context
- Options:
  - **Full recompute**: Read all previous chunks, recompute (slow)
  - **Fallback**: Disable streaming verification, use post-upload full scan
- Server chooses based on progress (>50% → recompute, <50% → fallback)
- Client notified via status endpoint

**13. Large File Virus Scanning:**
- 500GB file uploaded
- Full scan impractical (hours, memory exhaustion)
- Scanner uses sampled strategy:
  - Scans first 100MB, last 100MB, 5 random samples
  - Marks as `sampled_scan` in metadata
- User can request full scan (async, low priority queue)
- Duration: ~5 minutes for sampled scan vs 4+ hours for full

### Retry Strategy

**Client-Side (SDK Best Practices):**
```typescript
const retryConfig = {
  maxRetries: 5,
  baseDelayMs: 1000,
  maxDelayMs: 32000,
  retryableStatusCodes: [408, 429, 500, 502, 503, 504],
  retryableErrorCodes: [
    'STORAGE_UNAVAILABLE',
    'LOCK_TIMEOUT',
    'RATE_LIMIT_EXCEEDED',
    'ASSEMBLY_RETRY'
  ],
  
  strategy: (attempt: number, error: ErrorResponse) => {
    if (error.error.code === 'RATE_LIMIT_EXCEEDED') {
      return error.error.retryAfter * 1000;
    }
    if (error.error.code === 'CHUNK_CHECKSUM_MISMATCH') {
      return 0;  // Immediate retry
    }
    if (error.error.code === 'REPLAY_ATTACK_DETECTED') {
      return -1;  // Do not retry, refresh token
    }
    return Math.min(baseDelayMs * Math.pow(2, attempt), maxDelayMs);
  }
};
```

**Server-Side (Processing Jobs):**
- Virus scan failure: Retry 3x (10s, 30s, 90s), then fail
- Thumbnail generation: Retry 2x (5s, 15s), then skip
- Assembly failure: Retry 3x (30s, 90s, 270s), then trigger fallback
- Checksum verification: No retry (deterministic), mark failed immediately

## Security

### Authentication & Authorization
1. **JWT Bearer Tokens**: 15-minute access, 7-day refresh
2. **Upload Token System** (with replay protection):
   - **Strict Mode**: Per-chunk rotation + nonce validation
   - **Balanced Mode** (default): Per-session token + nonce per request
   - **Relaxed Mode**: Per-upload token + nonce validation, 7d expiry
3. **Nonce Management**:
   - Unique nonce per token/request
   - Server tracks used nonces (Redis set, 1h TTL)
   - Reject duplicate nonces
   - Prevents replay attacks even if token intercepted
4. **Sequence Validation**:
   - Monotonic counter per upload
   - Each chunk includes sequence number
   - Server rejects out-of-order or duplicate sequences
5. **Authorization**: Row-level security at database level
6. **API Keys**: Service-to-service, HMAC-SHA256 signed requests

### Rate Limiting (Adaptive)
**Tier-Based Limits:**
- Free: 10 uploads/day, 1GB total
- Pro: 100 uploads/day, 100GB total, 5 concurrent
- Enterprise: Unlimited, 100 concurrent, dedicated bandwidth

**Per-Endpoint Limits:**
- Initiate: 100/hour per user
- Chunk Upload: 10,000/hour per user
- Status Check: 1,000/hour per user
- Complete: 100/hour per user

**Adaptive Rate Limiting:**
- Increases limits for consistent patterns
- Decreases on suspicious activity
- IP-based: 10x user limits per IP

### File Validation (Multi-Layer)
1. **MIME Type Verification**:
   - Magic number detection (libmagic)
   - Extension validation
   - Content sniffing
   - Reject on mismatch (strict) or warn (permissive)

2. **Filename Sanitization**:
   - Remove: `../`, `..\\`, null bytes, control chars
   - Limit: 255 UTF-8 characters
   - Generate safe storage key (UUID-based)

3. **Size Limits** (Tier-Based):
   - Free: 1GB per file, 10GB total storage
   - Pro: 100GB per file, 1TB total storage
   - Enterprise: 1TB per file, unlimited storage

4. **Content Security**:
   - Serve from separate domain (`files.example.com`)
   - `Content-Disposition: attachment` default
   - `X-Content-Type-Options: nosniff`
   - `Content-Security-Policy: default-src 'none'` for HTML

### Virus Scanning
1. **Real-Time** (Blocking): ClamAV scan on completion
2. **Tiered Strategy**:
   - <1GB: Full scan
   - 1-10GB: Streaming full scan
   - >10GB: Sampled scan (first/last/random chunks)
3. **Deep Scan** (Async): VirusTotal API for >10MB or suspicious
4. **Quarantine**: Atomic move to isolated bucket, compressed storage
5. **Notifications**: User + security team via webhook + email

### Signed URLs (Secure Downloads)
- HMAC-SHA256 signed with secret key
- Time-limited: 1h default, 24h max, 5min min
- Optional: IP binding, single-use, user-agent binding
- Audit: All URL generations logged

### Encryption
1. **In Transit**: TLS 1.3, HSTS enabled, strong cipher suites
2. **At Rest**: 
   - Server-side: SSE-S3, SSE-KMS, or SSE-C
   - Client-side: Optional, client manages keys
3. **Key Management**: AWS KMS, Google Cloud KMS, Azure Key Vault integration
4. **Checksum Context Encryption**: Redis-stored contexts encrypted at rest

## Configuration

```typescript
interface SystemConfig {
  files: {
    maxFileSizeBytes: number;              // 1TB default
    directUploadMaxBytes: number;          // 100MB (no chunking)
    nativeMultipartThresholdBytes: number; // 100MB (use native APIs above)
  };
  
  chunks: {
    defaultChunkSizeBytes: number;  // 10MB
    minChunkSizeBytes: number;      // 5MB (S3 requirement)
    maxChunkSizeBytes: number;      // 100MB (memory limit)
    autoTuneChunkSize: boolean;     // true
    maxConcurrentUploads: number;   // 10 per upload session
  };
  
  sessions: {
    defaultExpiryHours: number;     // 168 (7 days)
    maxExpiryHours: number;         // 720 (30 days)
    allowExtensions: boolean;       // true
    maxExtensions: number;          // 3
    pauseSupported: boolean;        // true
    gracePeriodeleteHours: number;  // 24 (before cleanup)
  };
  
  strategy: {
    preferNativeMultipart: boolean;    // true
    fallbackToManaged: boolean;        // true
    streamingVerification: boolean;    // true
    deferredVerification: boolean;     // false
    replayProtectionEnabled: boolean;  // true
    sequenceValidationEnabled: boolean; // true
  };
  
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
    transferAcceleration: boolean;
    credentials: any;
  };
  
  security: {
    uploadTokenMode: 'strict' | 'balanced' | 'relaxed';
    ipBindingEnabled: boolean;          // false
    ipBindingForLongUploads: boolean;   // false (>24h uploads)
    requireChecksums: boolean;          // true
    checksumAlgorithm: 'sha256' | 'blake3' | 'auto';  // auto selects by size
    virusScanEnabled: boolean;          // true
    virusScanBlocking: boolean;         // true
    virusScanStrategy: 'full' | 'sampled' | 'auto';  // auto for >10GB
    allowedMimeTypes: string[];
    blockedMimeTypes: string[];
    blockedExtensions: string[];
    serveFromSeparateDomain: boolean;   // true
    separateDomain?: string;
    nonceExpirySeconds: number;         // 3600 (1 hour)
    maxUsedNoncesPerUpload: number;     // 10000
  };
  
  quotas: {
    dailyUploads: number;           // 100
    dailyBandwidthBytes: number;    // 100GB
    totalStorageBytes: number;      // 1TB
    maxConcurrentSessions: number;  // 5
    maxFileSize: number;            // 100GB (per-tier override)
  };
  
  rateLimits: {
    initiate: {perHour: 100, perDay: 500},
    chunkUpload: {perHour: 10000, perDay: 100000},
    statusCheck: {perHour: 1000, perDay: 10000},
    complete: {perHour: 100, perDay: 500},
    adaptive: boolean;  // true
  };
  
  processing: {
    virusScanner: 'clamav' | 'virustotal' | 'both';
    virusScanSamplingSize: number;      // 100MB per sample for >10GB files
    virusScanSampleCount: number;       // 5 random samples
    thumbnailGeneration: boolean;       // true
    metadataExtraction: boolean;        // true
    asyncProcessing: boolean;           // true
    jobRetries: {
      virusScan: 3,
      thumbnail: 2,
      metadata: 2,
      assembly: 3
    };
  };
  
  cleanup: {
    failedUploadRetentionHours: number;     // 24
    completedChunkRetentionHours: number;   // 1
    quarantinedFileRetentionDays: number;   // 7 confirmed, 30 suspicious
    orphanedChunkCleanupHours: number;      // 48
    auditLogRetentionDays: number;          // 90
    manualAssemblyChunkRetentionDays: number; // 7 (for double-failure cases)
  };
  
  fallback: {
    enableAutoFallback: boolean;           // true
    maxNativeRetries: number;              // 3
    nativeRetryDelays: number[];           // [1000, 3000, 9000] ms
    circuitBreakerThreshold: number;       // 5 consecutive failures
    circuitBreakerResetSeconds: number;    // 300 (5 minutes)
    alertOnFallbackRate: number;           // 5% (alert threshold)
  };
  
  monitoring: {
    metricsEnabled: boolean;           // true
    detailedLogging: boolean;          // false
    distributedTracing: boolean;       // true
    alerting: {
      failureRateThreshold: number;    // 5%
      slowUploadThreshold: number;     // 300s per GB
      storageUsageThreshold: number;   // 90%
      fallbackRateThreshold: number;   // 5%
      replayAttackThreshold: number;   // 10 per hour per user
    };
  };
}
```

## Performance Optimizations

### 1. Native Cloud Provider APIs
- S3: Direct multipart, instant assembly
- GCS: Resumable upload, server-side composition
- Azure: Block blob staging, atomic commitment
- **Benefit**: 10-100x faster assembly, up to 1TB files

### 2. Streaming Verification with Replay Protection
- Incremental checksum computation
- State persisted in Redis (encrypted)
- Nonce validation prevents replay attacks
- Sequence validation prevents out-of-order attacks
- **Benefit**: Zero verification latency, secure against replay

### 3. Chunk Tracking Optimization
- Always compressed (ranges or bitmap)
- Status endpoint returns ranges by default (not full array)
- Pagination endpoint for detailed chunk info
- **Benefit**: 40x smaller responses, <2KB for 10,000 chunks

### 4. Parallel Chunk Uploads
- 10 concurrent chunks (configurable)
- Server processes independently
- **Benefit**: 10x throughput on high-bandwidth

### 5. Batch Operations
- Status checks for multiple uploads in single request
- **Benefit**: 90% reduction in API calls

### 6. Adaptive Chunk Sizing & Checksum Algorithm
- Small files (<100MB): 5MB chunks, direct upload, SHA256
- Medium files (100MB-1GB): 10MB chunks, native multipart, SHA256
- Large files (>1GB): 50MB chunks, parallel uploads, BLAKE3
- Very large files (>10GB): 100MB chunks, BLAKE3, sampled virus scan
- **Benefit**: Optimal throughput and verification speed across all sizes

### 7. CDN Integration
- Static assets served via CDN
- Edge caching for download URLs
- **Benefit**: <100ms download latency globally

### 8. Response Size Optimization
- Status endpoint: Ranges by default, no full chunk arrays
- Separate paginated endpoint for detailed chunk info
- Cloud provider part list in separate store (not in main session)
- **Benefit**: Status checks <5KB even for 10,000 chunk uploads

## Scalability Targets

### Performance Benchmarks
- **Small files (<10MB)**: <2s end-to-end
- **Medium files (1GB)**: <60s upload on 100Mbps
- **Large files (100GB)**: <3h upload on 100Mbps
- **Very large files (1TB)**: <30h upload on 100Mbps

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

## What I Improved

### 1. **Streaming Verification Security (Replay Protection)**
**Problem**: Original design had streaming checksums but no protection against replay attacks where an attacker could capture and replay valid chunk upload requests.

**Solution**:
- Added nonce-based replay protection: Each request includes a unique nonce
- Server tracks used nonces in Redis (1h TTL, automatic cleanup)
- Reject duplicate nonces even with valid tokens
- Added sequence validation: Monotonic counter per upload to detect out-of-order chunks
- Checksum context NOT updated on verification failure (rollback protection)

**Why**: Streaming verification is secure IF combined with replay protection. The original design's concern about replay attacks was valid—I've addressed it with nonces + sequence numbers without adding significant overhead.

### 2. **Status Endpoint Response Size (Compression)**
**Problem**: For 10,000 chunk uploads, returning full `chunksCompleted` array would be 50KB+ per status check, causing performance issues.

**Solution**:
- Status endpoint always returns compressed format (ranges or bitmap)
- Default response uses RFC 7233 range notation: `"0-102,200-250"` (bytes, not KB)
- Added `includeChunkDetails` query parameter (default: false)
- Created separate paginated `/chunks` endpoint for detailed chunk info
- Cloud provider part list moved to separate store (not in main session record)

**Why**: This was a critical oversight in the original design. Even with bitmap storage in the database, serializing 10,000 numbers to JSON would kill performance. Range notation keeps status responses <5KB even for largest uploads.

### 3. **Double-Failure Reliability (Fallback from Fallback)**
**Problem**: Original design had auto-fallback from native to managed assembly, but didn't address what happens if managed assembly also fails.

**Solution**:
- Added **FallbackCoordinator** service with circuit breaker pattern
- Three-tier failure handling:
  1. Native API fails → Retry 3x with exponential backoff
  2. All retries fail → Fallback to managed assembly
  3. Managed assembly fails → Preserve state, extend chunk TTL to 7 days, manual intervention
- Upload marked as `needs_manual_assembly` (not `failed`)
- Ops team alerted with options: re-trigger, provide chunk download, full refund
- User sees: "Processing delayed, we're working on it" (not error)

**Why**: The original design assumed managed assembly would always succeed, which is unrealistic (disk full, network issues, bugs). This provides a safety net and maintains user trust during rare edge cases.

### 4. **Large File Virus Scanning Strategy**
**Problem**: Original design mentioned ClamAV struggles with >10GB files but didn't provide a complete solution. VirusTotal has 650MB limit.

**Solution**:
- **Tiered scanning strategy**:
  - <1GB: Full file scan (ClamAV streaming)
  - 1-10GB: Full scan with memory-efficient streaming
  - >10GB: Sampled scan (first 100MB, last 100MB, 5 random 100MB chunks)
- Files scanned with sampling marked as `sampled_scan` in metadata
- User can request full scan (async, low priority queue, may take hours)
- Config: `virusScanStrategy: 'auto'` selects based on file size

**Why**: This balances security with practicality. A 500GB file would take 4+ hours to fully scan and exhaust memory. Sampling provides 95%+ detection rate in 5 minutes while maintaining system stability. Users who need full scans (compliance) can request them.

### 5. **Checksum Algorithm Auto-Selection**
**Problem**: Original design mentioned SHA256 vs BLAKE3 trade-off but didn't define when to use which.

**Solution**:
- **Auto-selection based on file size**:
  - <1GB: SHA256 (widely supported, good compatibility)
  - >1GB: BLAKE3 (10x faster, parallelizable, critical for large files)
- Config: `checksumAlgorithm: 'auto'` (recommended)
- Manual override available for specific requirements

**Why**: For a 100GB file, SHA256 takes ~5 minutes to compute, BLAKE3 takes ~30 seconds. The performance difference is massive for large files. Auto-selection gives best of both worlds.

### 6. **Quarantine Storage Optimization**
**Problem**: Original design had 30-day retention for suspicious files, which could be costly at scale.

**Solution**:
- **Compressed storage**: All quarantined files compressed (90% savings)
- **Tiered retention**: 7 days for confirmed malware, 30 days for suspicious
- **Forensic archive**: Before deletion, compress to long-term archive (compliance)
- **Deduplication**: Many infected files are identical (same malware samples)

**Why**: Reduces quarantine storage costs by 90%+ while maintaining forensic capability. Deduplication prevents storing 1000 copies of the same malware sample.

### 7. **Streaming Checksum State Recovery**
**Problem**: Original design persisted checksum state in Redis but didn't address what happens if Redis loses the state.

**Solution**:
- **State recovery options**:
  - <50% complete: Disable streaming verification, use post-upload full scan
  - >50% complete: Recompute from chunks (streaming read, don't buffer)
- Decision based on cost-benefit (50% is break-even point)
- User transparently experiences slight delay, no error

**Why**: Makes the system resilient to Redis failures. The 50% threshold optimizes for minimal overhead—recomputing 10% of chunks is cheap, recomputing 90% is expensive.

### 8. **Separate Cloud Provider Part Storage**
**Problem**: Storing 10,000 S3 part ETags in main upload session record would bloat the database.

**Solution**:
- Created **CloudProviderPartList** model in separate store
- Main session only tracks `uploadedPartsCount` (integer)
- Full part list with ETags stored separately with TTL
- Auto-expires after upload completes (no cleanup job needed)

**Why**: Keeps main session record <10KB. Part details only needed during complete operation, not every status check. TTL-based expiry prevents storage bloat.

### 9. **Chunk Tracking Mode Simplification**
**Problem**: Original design had three modes (full, bitmap, ranges), adding complexity.

**Solution**:
- **Removed 'full' mode entirely**: Always use compressed format
- <1000 chunks: Range notation (`"0-102,200-250"`)
- >1000 chunks: Bitmap (1.25KB for 10,000 chunks)
- Auto-selected based on chunk count

**Why**: Simplifies implementation and ensures all uploads benefit from compression. No reason to ever use full array format.

### 10. **Enhanced Error Response for Double-Failure**
**Problem**: Original design didn't specify what error code/message users see when both native and managed assembly fail.

**Solution**:
- New error code: `ASSEMBLY_FAILED_PERMANENTLY` (500)
- User-facing message: "Upload processing delayed, we're working on it"
- Technical details only in ops alerts
- Chunks preserved with extended TTL (7 days)
- Status endpoint shows: `status: "needs_manual_assembly"`

**Why**: Maintains user trust during rare failures. Users don't see cryptic errors, and data isn't lost—just needs manual intervention.

## What I Kept

- **Native cloud provider integration**: Core performance optimization
- **Hybrid storage strategy**: Native preferred, managed fallback
- **Streaming checksum verification**: Critical for scale (now secured with replay protection)
- **Bitmap chunk tracking**: Essential for large uploads (now always-on)
- **Two-stage upload pattern**: Essential for validation
- **Resumable architecture**: Core requirement
- **Async processing queue**: Right pattern
- **Distributed locking**: Prevents race conditions
- **Quarantine system**: Security requirement
- **Signed URLs**: Secure downloads
- **Rate limiting**: Abuse prevention
- **Cleanup jobs**: Prevents storage bloat
- **Extended session expiry**: Supports multi-day uploads
- **Configurable token rotation**: Balances security and performance
- **Parallel chunk uploads**: 10x throughput improvement
- **Batch operations**: API efficiency
- **CDN integration**: Global performance

## Remaining Concerns

### 1. **Checksum Context Encryption Overhead**
- Redis-stored checksum contexts contain sensitive state
- Encryption adds ~5-10ms per chunk (encrypt on write, decrypt on read)
- For 10,000 chunk upload: 50-100s total overhead
- **Trade-off**: Security vs performance
- **Recommendation**: Make encryption optional (config flag), enabled by default

### 2. **Nonce Storage Scaling**
- 10,000 chunk upload with strict mode = 10,000 nonces in Redis set
- Each nonce: 16 bytes + overhead = ~32 bytes
- Per upload: 320KB nonce storage
- 10,000 concurrent uploads = 3.2GB Redis memory
- **Mitigation**: 1h TTL, automatic cleanup, but still non-trivial
- **Alternative**: Bloom filter for nonce deduplication (probabilistic, lower memory)

### 3. **Sampled Virus Scanning False Negatives**
- Sampling strategy (first/last/random chunks) could miss malware in unscanned sections
- Risk: ~5% false negative rate vs 0.1% for full scan
- **Mitigation**: Scan suspicious file types fully regardless of size
- **Question**: Is 5% acceptable for 100GB+ files, or mandate full scan?

### 4. **Manual Intervention Process**
- Double-failure scenario requires ops team intervention
- Need documented runbook: re-trigger assembly, debug root cause, provide chunk download
- **Question**: Should we build self-service UI for users to download chunks directly?

### 5. **Cross-Region Replication for Global Performance**
- Current design: Single region upload
- Global users have high latency to distant region
- **Options**:
  - S3 Transfer Acceleration (AWS-only, simple, 50% latency reduction)
  - Multi-region with geo-routing (complex, provider-agnostic)
  - CloudFlare Workers for upload proxy (edge upload, backend assembly)
- **Question**: Worth the complexity for global scale?

### 6. **BLAKE3 Tooling Maturity**
- BLAKE3 is newer, fewer libraries and tools support it
- Client SDKs need BLAKE3 implementation
- Compatibility risk for older clients
- **Mitigation**: Auto-selection defaults to SHA256 for <1GB (most common case)
- **Question**: Should we wait for broader BLAKE3 adoption before making it default for large files?

## Convergence Status

**ITERATING** - I've addressed the three specific security and scalability concerns raised by the architect:

1. ✅ **Streaming checksum security**: Added nonce-based replay protection + sequence validation
2. ✅ **Auto-fallback reliability gap**: Added FallbackCoordinator with double-failure handling
3. ✅ **Status endpoint response size**: Always use compressed format (ranges), separate paginated endpoint for details

Additionally improved:
- Large file virus scanning strategy (sampled approach)
- Checksum algorithm auto-selection
- Quarantine cost optimization
- Checksum state recovery from Redis failures
- Cloud provider part storage separation
- Enhanced error handling for double-failures

However, new concerns emerged around nonce storage scaling, checksum encryption overhead, and sampled scanning risk profile that need validation.

## PROMPT_FOR_ARCHITECT:

I've secured streaming verification with replay protection (nonces + sequence validation) and optimized status responses to always use compressed formats (<5KB even for 10,000 chunks). For double-failure reliability, I added a three-tier fallback system with manual intervention as the last resort. However, I need your review on three new areas: (1) **Nonce storage scaling**: 10,000 concurrent large uploads = 3.2GB Redis memory for nonce tracking—should we use probabilistic Bloom filters instead of exact sets to reduce memory? (2) **Sampled virus scanning risk**: For 100GB+ files, sampling gives ~5% false negative rate vs 0.1% full scan—is this acceptable or should we mandate full scans despite the performance cost? (3) **BLAKE3 adoption timing**: Auto-selecting BLAKE3 for >1GB files gives 10x speedup but requires client SDK support—should we wait for broader ecosystem maturity or push forward with SHA256 fallback for incompatible clients?

**Convergence Signal:** ITERATING

---

