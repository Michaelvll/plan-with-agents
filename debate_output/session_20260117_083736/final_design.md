# Final Agreed Design

**Task:** Design a REST API for a todo list application with user authentication

**Status:** debating

---

## Design

# Todo List REST API with User Authentication

## Architecture Overview

The API follows a three-tier architecture with clear separation of concerns:
- **Presentation Layer**: REST API endpoints (JSON)
- **Business Logic Layer**: Authentication, authorization, todo management, and business rules
- **Data Layer**: PostgreSQL database with normalized schema

## Technology Stack

- **Framework**: Node.js with Express.js
- **Database**: PostgreSQL 14+ with connection pooling
- **Authentication**: JWT (JSON Web Tokens) with bcrypt for password hashing
- **Validation**: Joi or Zod for schema validation
- **Rate Limiting**: express-rate-limit with Redis store
- **Caching**: Redis (optional, graceful degradation)
- **Logging**: Pino for structured logging
- **API Documentation**: OpenAPI 3.0 specification
- **Email**: Nodemailer with template support

## Data Models

### User Entity
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  email_verified BOOLEAN DEFAULT FALSE,
  verification_token VARCHAR(255),
  verification_token_expires_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,
  failed_login_attempts INT DEFAULT 0,
  locked_until TIMESTAMP,
  password_changed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
CREATE INDEX idx_users_verification_token ON users(verification_token) WHERE verification_token IS NOT NULL;
```

### Password History Entity
```sql
CREATE TABLE password_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_password_history_user_id ON password_history(user_id);
```

### Todo Entity
```sql
CREATE TABLE todos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  completed BOOLEAN DEFAULT FALSE,
  priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high')) DEFAULT 'medium',
  due_date TIMESTAMP,
  completed_at TIMESTAMP,
  deleted_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_todos_user_id ON todos(user_id);
CREATE INDEX idx_todos_user_completed ON todos(user_id, completed) WHERE deleted_at IS NULL;
CREATE INDEX idx_todos_user_due_date ON todos(user_id, due_date) WHERE deleted_at IS NULL AND completed = FALSE;
CREATE INDEX idx_todos_deleted_at ON todos(deleted_at) WHERE deleted_at IS NOT NULL;
```

### Refresh Token Entity
```sql
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(255) NOT NULL UNIQUE,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at) WHERE revoked_at IS NULL;
```

## API Endpoints

### Health Check

#### GET /api/v1/health
Check API health status (no authentication required).

**Response (200):**
```json
{
  "status": "healthy",
  "timestamp": "2026-01-17T10:00:00Z",
  "version": "1.0.0",
  "services": {
    "database": "healthy",
    "redis": "healthy"
  }
}
```

### Authentication Endpoints

#### POST /api/v1/auth/register
Register a new user and send verification email.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (201):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "emailVerified": false,
  "message": "Registration successful. Please check your email to verify your account."
}
```

**Errors:**
- 400: Validation error (invalid email, weak password)
- 409: Email already exists
- 429: Too many registration attempts

**Notes:**
- User receives email with verification link valid for 24 hours
- Account is created but email_verified=false
- User can login but certain features may be restricted

#### POST /api/v1/auth/verify-email
Verify email address using token from email.

**Request:**
```json
{
  "token": "verification-token-from-email"
}
```

**Response (200):**
```json
{
  "message": "Email verified successfully",
  "accessToken": "jwt-access-token",
  "refreshToken": "jwt-refresh-token",
  "expiresIn": 900
}
```

**Errors:**
- 400: Invalid or expired token
- 404: Token not found

#### POST /api/v1/auth/resend-verification
Resend verification email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "Verification email sent"
}
```

**Errors:**
- 400: Email already verified
- 404: User not found
- 429: Too many resend attempts

#### POST /api/v1/auth/login
Authenticate user and receive JWT tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "emailVerified": true,
  "accessToken": "jwt-access-token",
  "refreshToken": "jwt-refresh-token",
  "expiresIn": 900
}
```

**Errors:**
- 401: Invalid credentials
- 403: Account locked due to too many failed attempts
- 423: Account is inactive
- 400: Validation error
- 429: Too many login attempts

**Notes:**
- Failed attempts increment counter
- Account locks for 30 minutes after 5 failed attempts
- Successful login resets failed_login_attempts to 0

#### POST /api/v1/auth/refresh
Refresh access token using refresh token.

**Request:**
```json
{
  "refreshToken": "jwt-refresh-token"
}
```

**Response (200):**
```json
{
  "accessToken": "new-jwt-access-token",
  "refreshToken": "new-jwt-refresh-token",
  "expiresIn": 900
}
```

**Errors:**
- 401: Invalid, expired, or revoked refresh token
- 429: Too many refresh attempts

**Notes:**
- Old refresh token is revoked upon successful refresh
- Implements token rotation for enhanced security

#### POST /api/v1/auth/logout
Revoke refresh token.

**Headers:**
```
Authorization: Bearer <jwt-access-token>
```

**Request:**
```json
{
  "refreshToken": "jwt-refresh-token"
}
```

**Response (204):**
No content.

**Errors:**
- 401: Unauthorized

#### POST /api/v1/auth/change-password
Change user password (requires current password).

**Headers:**
```
Authorization: Bearer <jwt-access-token>
```

**Request:**
```json
{
  "currentPassword": "SecurePass123!",
  "newPassword": "NewSecurePass456!"
}
```

**Response (200):**
```json
{
  "message": "Password changed successfully"
}
```

**Errors:**
- 401: Current password incorrect or unauthorized
- 400: Validation error (weak password, same as old password, matches recent password history)

**Notes:**
- Checks against last 5 passwords in history
- Revokes all refresh tokens for the user (forces re-login on all devices)
- Updates password_changed_at timestamp

#### POST /api/v1/auth/forgot-password
Request password reset email.

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (200):**
```json
{
  "message": "If an account exists with this email, a password reset link has been sent"
}
```

**Errors:**
- 429: Too many reset attempts

**Notes:**
- Always returns 200 even if email not found (security best practice)
- Reset token valid for 1 hour
- Invalidates previous reset tokens

#### POST /api/v1/auth/reset-password
Reset password using token from email.

**Request:**
```json
{
  "token": "reset-token-from-email",
  "newPassword": "NewSecurePass456!"
}
```

**Response (200):**
```json
{
  "message": "Password reset successfully"
}
```

**Errors:**
- 400: Invalid or expired token, or validation error
- 404: Token not found

### Todo Endpoints

All todo endpoints require authentication via `Authorization: Bearer <jwt-access-token>` header.

#### GET /api/v1/todos
Retrieve all todos for authenticated user (excludes soft-deleted by default).

**Query Parameters:**
- `completed` (optional): boolean - filter by completion status
- `priority` (optional): low|medium|high - filter by priority
- `includeDeleted` (optional): boolean - include soft-deleted todos (default: false)
- `sortBy` (optional): created_at|due_date|priority|updated_at|title - sort field (default: created_at)
- `order` (optional): asc|desc - sort order (default: desc)
- `page` (optional): integer - page number (default: 1, min: 1)
- `limit` (optional): integer - items per page (default: 20, min: 1, max: 100)
- `search` (optional): string - search in title and description (min 2 chars)

**Response (200):**
```json
{
  "todos": [
    {
      "id": "uuid",
      "title": "Complete project",
      "description": "Finish the REST API design",
      "completed": false,
      "priority": "high",
      "dueDate": "2026-01-20T00:00:00Z",
      "completedAt": null,
      "createdAt": "2026-01-17T10:00:00Z",
      "updatedAt": "2026-01-17T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "totalPages": 3,
    "hasNext": true,
    "hasPrevious": false
  }
}
```

**Errors:**
- 401: Unauthorized (invalid or expired token)
- 400: Invalid query parameters

#### GET /api/v1/todos/:id
Retrieve a specific todo.

**Response (200):**
```json
{
  "id": "uuid",
  "title": "Complete project",
  "description": "Finish the REST API design",
  "completed": false,
  "priority": "high",
  "dueDate": "2026-01-20T00:00:00Z",
  "completedAt": null,
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found or deleted
- 403: Todo belongs to another user

#### POST /api/v1/todos
Create a new todo.

**Request:**
```json
{
  "title": "Complete project",
  "description": "Finish the REST API design",
  "priority": "high",
  "dueDate": "2026-01-20T00:00:00Z"
}
```

**Response (201):**
```json
{
  "id": "uuid",
  "title": "Complete project",
  "description": "Finish the REST API design",
  "completed": false,
  "priority": "high",
  "dueDate": "2026-01-20T00:00:00Z",
  "completedAt": null,
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 400: Validation error (missing title, invalid priority, title too long)
- 422: Due date is in the past

#### PUT /api/v1/todos/:id
Update an existing todo (full replacement).

**Request:**
```json
{
  "title": "Complete project - Updated",
  "description": "Finish the REST API design with documentation",
  "completed": true,
  "priority": "medium",
  "dueDate": "2026-01-21T00:00:00Z"
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "title": "Complete project - Updated",
  "description": "Finish the REST API design with documentation",
  "completed": true,
  "priority": "medium",
  "dueDate": "2026-01-21T00:00:00Z",
  "completedAt": "2026-01-17T12:00:00Z",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T12:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user
- 400: Validation error
- 422: Due date is in the past

**Notes:**
- When completed changes from false to true, sets completedAt to current timestamp
- When completed changes from true to false, sets completedAt to null

#### PATCH /api/v1/todos/:id
Partially update a todo.

**Request:**
```json
{
  "completed": true
}
```

**Response (200):**
```json
{
  "id": "uuid",
  "title": "Complete project",
  "description": "Finish the REST API design",
  "completed": true,
  "priority": "high",
  "dueDate": "2026-01-20T00:00:00Z",
  "completedAt": "2026-01-17T12:00:00Z",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T12:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user
- 400: Validation error

#### DELETE /api/v1/todos/:id
Soft delete a todo (sets deleted_at timestamp).

**Query Parameters:**
- `permanent` (optional): boolean - permanently delete (default: false)

**Response (204):**
No content.

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user

**Notes:**
- Default behavior is soft delete (sets deleted_at)
- Permanent delete only works if user has already soft-deleted the item
- This prevents accidental permanent deletion

#### POST /api/v1/todos/:id/restore
Restore a soft-deleted todo.

**Response (200):**
```json
{
  "id": "uuid",
  "title": "Complete project",
  "description": "Finish the REST API design",
  "completed": false,
  "priority": "high",
  "dueDate": "2026-01-20T00:00:00Z",
  "completedAt": null,
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T12:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found or not deleted
- 403: Todo belongs to another user

#### GET /api/v1/todos/stats
Get todo statistics for the authenticated user.

**Response (200):**
```json
{
  "total": 100,
  "completed": 45,
  "pending": 55,
  "overdue": 10,
  "dueToday": 5,
  "dueThisWeek": 15,
  "byPriority": {
    "low": 30,
    "medium": 50,
    "high": 20
  },
  "completionRate": 0.45
}
```

**Errors:**
- 401: Unauthorized

**Notes:**
- Stats exclude soft-deleted todos
- Results cached for 2 minutes if Redis is available
- Overdue count only includes incomplete todos past due date

## Security Implementation

### Password Requirements
- Minimum 12 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)
- Cannot match last 5 passwords
- Cannot contain user's email local part

### Password Hashing
- Use bcrypt with salt rounds of 12
- Store password hash only, never plain text
- Maintain password_history table to prevent reuse

### JWT Configuration
- **Access tokens**: 15 minute expiration
- **Refresh tokens**: 7 day expiration with rotation
- **Algorithm**: RS256 (asymmetric)
- **Access token payload**: { userId, email, iat, exp, jti }
- **Refresh token payload**: { userId, tokenId, iat, exp, jti }
- Implement token revocation via refresh_tokens table
- Generate new key pair on application bootstrap if not exists

### Account Security
- Lock account after 5 failed login attempts
- Automatic unlock after 30 minutes
- Track last_login_at timestamp
- Email notifications for:
  - Successful login from new IP (optional feature)
  - Password change
  - Account lock event
  - Email verification
  - Password reset

### Email Verification
- Required for full account access
- Unverified users can login but with limited capabilities
- Verification token expires after 24 hours
- Token is random 32-byte hex string
- Can resend verification email (rate limited: max 3 per hour)

### Rate Limiting

Per-IP limits (unauthenticated):
- POST /api/v1/auth/register: 3 per hour
- POST /api/v1/auth/login: 10 per 15 minutes
- POST /api/v1/auth/forgot-password: 3 per hour
- POST /api/v1/auth/reset-password: 5 per hour
- POST /api/v1/auth/verify-email: 10 per hour
- POST /api/v1/auth/resend-verification: 3 per hour

Per-user limits (authenticated):
- POST /api/v1/auth/refresh: 20 per hour
- POST /api/v1/auth/change-password: 5 per hour
- Todo endpoints: 300 per 15 minutes
- GET /api/v1/todos/stats: 100 per 15 minutes

Global limits:
- All GET endpoints: 1000 per 15 minutes per IP
- Health check: No limit

Return 429 with `Retry-After` header.

### Input Validation
- Email: RFC 5322 compliant, max 255 chars
- Title: 1-255 characters, required
- Description: 0-5000 characters, optional
- Priority: enum (low, medium, high)
- Due date: ISO 8601 format, must be future date for new todos
- Passwords: validated against requirements above
- UUIDs: valid v4 format
- Sanitize inputs to prevent XSS (strip HTML tags)
- Use parameterized queries (prevents SQL injection)

### CORS Configuration
- Production: Whitelist specific origins from environment variable
- Development: Allow localhost with credentials
- Allowed methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
- Allowed headers: Content-Type, Authorization
- Expose headers: X-API-Version, X-Request-ID
- Max age: 86400 (24 hours)
- Credentials: true

### Security Headers (Helmet)
```javascript
{
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", "data:", "https:"]
    }
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true
  },
  noSniff: true,
  frameguard: { action: 'deny' },
  xssFilter: true
}
```

## Error Response Format

All errors follow this consistent structure:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "email",
        "message": "Email is already registered",
        "code": "DUPLICATE_EMAIL"
      }
    ],
    "timestamp": "2026-01-17T10:00:00Z",
    "path": "/api/v1/auth/register",
    "requestId": "uuid"
  }
}
```

### Standard Error Codes
- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_ERROR`: Authentication failed
- `AUTHORIZATION_ERROR`: Insufficient permissions
- `RESOURCE_NOT_FOUND`: Requested resource doesn't exist
- `DUPLICATE_RESOURCE`: Resource already exists (email, etc.)
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Server error (never expose internal details)
- `ACCOUNT_LOCKED`: Account locked due to failed attempts
- `ACCOUNT_INACTIVE`: Account is deactivated
- `EMAIL_NOT_VERIFIED`: Email verification required for this action
- `TOKEN_EXPIRED`: JWT or verification token expired
- `TOKEN_INVALID`: Malformed or invalid token

## HTTP Status Codes

- 200: Success
- 201: Created
- 204: No Content
- 400: Bad Request (validation errors)
- 401: Unauthorized (missing or invalid token)
- 403: Forbidden (insufficient permissions, email not verified)
- 404: Not Found
- 409: Conflict (duplicate resource)
- 422: Unprocessable Entity (semantic errors)
- 423: Locked (account locked)
- 429: Too Many Requests
- 500: Internal Server Error
- 503: Service Unavailable

## Middleware Stack (Execution Order)

1. **Request ID**: Generate UUID for request tracing
2. **Structured Logging**: Log request start with context
3. **CORS**: Configure allowed origins and credentials
4. **Helmet**: Apply security headers
5. **Body Parser**: JSON parsing with 10kb limit
6. **Rate Limiter**: IP and user-based rate limiting with Redis backend
7. **Request Validator**: Schema validation and sanitization
8. **Authentication**: JWT verification for protected routes
9. **Email Verification Check**: Enforce email verification for sensitive operations
10. **Route Handlers**: Business logic
11. **Error Handler**: Centralized error processing (must be last)

## Database Connection Management

```javascript
{
  pool: {
    min: 2,
    max: 20,
    acquireTimeoutMillis: 30000,
    idleTimeoutMillis: 30000
  },
  connectionTimeoutMillis: 5000,
  statementTimeout: 10000,
  queryTimeout: 10000,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: true } : false
}
```

- Implement circuit breaker pattern with 50% failure threshold
- Exponential backoff for reconnection: 1s, 2s, 4s, 8s, max 30s
- Health check query every 30 seconds: `SELECT 1`
- Use transactions for multi-query operations
- Implement query timeout monitoring and alerting

## Observability

### Logging Strategy
```javascript
{
  level: process.env.LOG_LEVEL || 'info',
  formatters: {
    level: (label) => ({ level: label }),
    bindings: (bindings) => ({ 
      pid: bindings.pid, 
      hostname: bindings.hostname,
      nodeVersion: process.version
    })
  },
  redact: ['password', 'token', 'accessToken', 'refreshToken', 'authorization'],
  serializers: {
    req: (req) => ({
      id: req.id,
      method: req.method,
      url: req.url,
      query: req.query,
      params: req.params,
      remoteAddress: req.ip
    }),
    res: (res) => ({
      statusCode: res.statusCode
    }),
    err: pino.stdSerializers.err
  }
}
```

**Log Events:**
- All HTTP requests (method, path, status, duration, requestId)
- Authentication events (login, logout, token refresh, failures)
- Failed login attempts with IP address
- Account lock/unlock events
- Email verification events
- Password changes
- Database query errors
- Rate limit violations
- Unhandled errors with stack traces

### Metrics Collection

- `http_request_duration_seconds`: Histogram by method, route, status
- `http_requests_total`: Counter by method, route, status
- `auth_attempts_total`: Counter by result (success, failure, locked)
- `db_query_duration_seconds`: Histogram by query type
- `db_pool_connections`: Gauge (active, idle, total)
- `cache_hits_total`: Counter by cache key type
- `cache_misses_total`: Counter by cache key type
- `rate_limit_exceeded_total`: Counter by endpoint
- `tokens_issued_total`: Counter by type (access, refresh)
- `tokens_revoked_total`: Counter

### Health Monitoring

**Endpoints for monitoring:**
- GET /api/v1/health: Basic health check
- GET /api/v1/health/ready: Readiness probe (checks DB, Redis)
- GET /api/v1/health/live: Liveness probe (app responsive)

**Alerts:**
- Error rate > 5% for 5 minutes
- P95 response time > 1 second
- Database connection pool exhaustion
- Redis connection failures
- Failed login rate > 50 per minute (potential attack)
- Disk space < 10%

## Caching Strategy

Redis is **optional** for this API. The system degrades gracefully without Redis:

**With Redis:**
- Rate limiting counters (required for accurate rate limiting)
- User stats cache: 2 minute TTL
- User profile cache: 5 minute TTL
- Email verification rate limit counters

**Without Redis:**
- Rate limiting falls back to in-memory (per-instance, less accurate)
- Stats and profiles are computed on every request (slower but functional)
- Application remains fully functional

**Cache Keys:**
```
user:profile:{userId}
user:stats:{userId}
ratelimit:{endpoint}:{identifier}
```

**Cache Invalidation:**
- User profile: invalidate on password change, email verification
- User stats: invalidate on todo create, update, delete, complete
- Use Redis EXPIRE for TTL-based expiration
- Implement cache warming for frequently accessed user stats

**Fallback Strategy:**
```javascript
async function getCachedOrFetch(key, fetchFn, ttl) {
  if (!redisClient || !redisClient.isReady) {
    return await fetchFn();
  }
  
  try {
    const cached = await redisClient.get(key);
    if (cached) return JSON.parse(cached);
    
    const data = await fetchFn();
    await redisClient.setEx(key, ttl, JSON.stringify(data));
    return data;
  } catch (err) {
    logger.warn({ err, key }, 'Cache error, falling back to direct fetch');
    return await fetchFn();
  }
}
```

## Scalability Considerations

### Horizontal Scaling
- Stateless application design (all state in DB or Redis)
- Load balancer with health check endpoint
- Session-less authentication (JWT)
- Shared Redis for rate limiting across instances
- Database read replicas for GET endpoints

### Database Optimization
- Compound indexes for common query patterns:
  - `(user_id, completed, deleted_at)` for todo listing
  - `(user_id, due_date)` for overdue queries
- Implement query result caching for stats endpoint
- Use `EXPLAIN ANALYZE` to optimize slow queries
- Consider partitioning todos table by user_id if dataset > 10M rows
- Implement read replica routing for GET requests

### Performance Targets
- P95 response time < 200ms for todo CRUD
- P95 response time < 500ms for stats endpoint
- Support 1000 concurrent users per instance
- Database connection pool should handle 20 concurrent requests

## API Versioning

- URL-based versioning: `/api/v1/`, `/api/v2/`
- Response header: `X-API-Version: 1.0.0`
- Maintain backward compatibility within major versions
- Deprecation process:
  1. Announce deprecation 6 months in advance
  2. Add `Deprecated` header to responses
  3. Log usage of deprecated endpoints
  4. Provide migration guide in API docs
  5. Remove in next major version

## Deployment and Operations

### Environment Variables
```
NODE_ENV=production
PORT=3000
DATABASE_URL=postgresql://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379
JWT_PRIVATE_KEY_PATH=/secrets/jwt-private.pem
JWT_PUBLIC_KEY_PATH=/secrets/jwt-public.pem
CORS_ORIGINS=https://example.com,https://app.example.com
EMAIL_SMTP_HOST=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_FROM=noreply@example.com
EMAIL_SMTP_USER=username
EMAIL_SMTP_PASSWORD=password
API_BASE_URL=https://api.example.com
LOG_LEVEL=info
```

### Backup and Recovery
- Automated daily PostgreSQL backups at 2 AM UTC
- Point-in-time recovery enabled (WAL archiving)
- Backup retention: 30 days for daily, 90 days for weekly
- Test restoration monthly in staging environment
- Document RTO (4 hours) and RPO (1 hour)

### Monitoring and Alerting
- Application performance monitoring (APM)
- Error tracking with stack traces
- Log aggregation and searching
- Uptime monitoring from multiple regions
- Database query performance monitoring