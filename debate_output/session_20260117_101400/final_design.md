# Final Agreed Design

**Task:** Design a file upload service with validation and storage

**Status:** debating

---

## Design

### File Upload Service Architecture

#### 1. System Components

**API Gateway Layer**
- RESTful endpoints for file upload operations
- JWT-based authentication and authorization
- Rate limiting per user/API key (100 requests/minute base tier)
- Request size limits enforced at gateway (configurable, default 500MB)

**Upload Service**
- Multipart upload support for files >100MB
- Resumable uploads using tus protocol
- Synchronous uploads for files <10MB
- Asynchronous processing queue for larger files
- Pre-signed URL generation for direct-to-storage uploads (S3/GCS)

**Validation Service**
- Multi-stage validation pipeline:
  1. **Pre-upload validation**: File extension, MIME type check, size limits
  2. **Content validation**: Magic number verification, virus scanning (ClamAV)
  3. **Business logic validation**: Custom validators per file type (image dimensions, document structure, etc.)
- Configurable validation rules stored in database
- Virus scanning offloaded to dedicated scanning service
- Validation results cached for 1 hour per file hash

**Storage Layer**
- Primary: Object storage (S3/GCS) with lifecycle policies
- Hot storage: Recent uploads (30 days)
- Cold storage: Archive tier for older files
- CDN integration for public files
- Storage organization: `{tenant_id}/{upload_date}/{file_hash}.{ext}`

**Metadata Database**
- PostgreSQL for transactional integrity
- Schema:
  ```
  uploads (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL,
    filename VARCHAR(255),
    content_type VARCHAR(100),
    size_bytes BIGINT,
    storage_path TEXT,
    file_hash SHA256,
    validation_status ENUM,
    validation_errors JSONB,
    upload_status ENUM,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    metadata JSONB
  )
  ```
- Indexes on: user_id, file_hash, upload_status, created_at

**Processing Queue**
- Message queue (SQS/Pub/Sub) for async processing
- Workers for: validation, thumbnail generation, metadata extraction
- Dead letter queue for failed processing
- Retry policy: exponential backoff, 3 retries max

#### 2. Upload Flow

**Small Files (<10MB)**
1. Client POST to `/upload` with file in request body
2. API validates auth, checks rate limits
3. Synchronous validation (extension, MIME, size)
4. Generate unique file ID and storage path
5. Upload to storage with server-side encryption
6. Async queue job for virus scan and metadata extraction
7. Return upload ID immediately with 202 Accepted
8. Client polls `/upload/{id}/status` or uses webhooks

**Large Files (>10MB)**
1. Client POST to `/upload/initiate` with metadata
2. Server returns upload URL (pre-signed or multipart upload ID)
3. Client uploads directly to storage in chunks
4. Server receives completion notification
5. Validation and processing via queue
6. Status updates via webhooks or polling

#### 3. Validation Rules Engine

**Configuration Format (YAML)**
```yaml
file_types:
  images:
    extensions: [jpg, jpeg, png, gif, webp]
    max_size: 10485760  # 10MB
    mime_types: [image/jpeg, image/png, image/gif, image/webp]
    validators:
      - image_dimensions:
          min_width: 100
          min_height: 100
          max_width: 8000
          max_height: 8000
      - image_format_validation
      - virus_scan
  documents:
    extensions: [pdf, docx, xlsx]
    max_size: 52428800  # 50MB
    mime_types: [application/pdf, application/vnd.openxmlformats-officedocument.*]
    validators:
      - document_structure_validation
      - virus_scan
      - malware_scan
```

**Validator Plugins**
- Plugin architecture for custom validators
- Each validator implements interface: `validate(file_path) -> (valid: bool, errors: [])`
- Validators run in parallel where possible
- Short-circuit on critical failures (virus detected)

#### 4. Security Measures

- File content verification (magic numbers) prevents extension spoofing
- Virus scanning mandatory for all uploads
- Sandboxed processing environment for validation
- Storage with encryption at rest (AES-256)
- Encryption in transit (TLS 1.3)
- Pre-signed URLs expire after 15 minutes
- Content Security Policy headers on file serving
- No direct file execution on server

#### 5. Scalability & Reliability

- Horizontal scaling of upload service pods
- Storage is decoupled and scales independently
- Queue-based processing prevents system overload
- Circuit breakers on external dependencies (virus scanner)
- Health checks and automatic pod restarts
- Metrics: upload latency, validation time, success rate, storage usage
- Logging: structured logs with trace IDs

#### 6. API Endpoints

```
POST   /v1/upload                    # Small file direct upload
POST   /v1/upload/initiate           # Start multipart upload
POST   /v1/upload/{id}/chunk         # Upload chunk
POST   /v1/upload/{id}/complete      # Finalize upload
GET    /v1/upload/{id}/status        # Check upload status
GET    /v1/upload/{id}               # Get file metadata
DELETE /v1/upload/{id}               # Delete file
GET    /v1/upload/{id}/download      # Download file
POST   /v1/upload/validate           # Pre-validate without uploading
```

---