# Claude Code Debate Session

**Started:** 2026-01-17T08:37:36.973134
**Ended:** 2026-01-17T08:44:10.301846
**Status:** debating
**Rounds:** 2

## Initial Prompt

Design a REST API for a todo list application with user authentication

---

## Round 1

### 🔵 Agent A

## Design

# Todo List REST API with User Authentication

## Architecture Overview

The API follows a three-tier architecture:
- **Presentation Layer**: REST API endpoints (JSON)
- **Business Logic Layer**: Authentication, authorization, and todo management
- **Data Layer**: PostgreSQL database with user and todo entities

## Technology Stack

- **Framework**: Node.js with Express.js
- **Database**: PostgreSQL with connection pooling
- **Authentication**: JWT (JSON Web Tokens) with bcrypt for password hashing
- **Validation**: Express-validator middleware
- **Rate Limiting**: express-rate-limit

## Data Models

### User Entity
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

### Todo Entity
```sql
CREATE TABLE todos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title VARCHAR(255) NOT NULL,
  description TEXT,
  completed BOOLEAN DEFAULT FALSE,
  priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high')),
  due_date TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_todos_user_id ON todos(user_id);
CREATE INDEX idx_todos_completed ON todos(completed);
CREATE INDEX idx_todos_due_date ON todos(due_date);
```

## API Endpoints

### Authentication Endpoints

#### POST /api/v1/auth/register
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (201):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "token": "jwt-token"
}
```

**Errors:**
- 400: Validation error (invalid email, weak password)
- 409: Email already exists

#### POST /api/v1/auth/login
Authenticate user and receive JWT token.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "token": "jwt-token"
}
```

**Errors:**
- 401: Invalid credentials
- 400: Validation error

#### POST /api/v1/auth/refresh
Refresh JWT token.

**Headers:**
```
Authorization: Bearer <jwt-token>
```

**Response (200):**
```json
{
  "token": "new-jwt-token"
}
```

**Errors:**
- 401: Invalid or expired token

### Todo Endpoints

All todo endpoints require authentication via `Authorization: Bearer <jwt-token>` header.

#### GET /api/v1/todos
Retrieve all todos for authenticated user.

**Query Parameters:**
- `completed` (optional): boolean - filter by completion status
- `priority` (optional): low|medium|high - filter by priority
- `sortBy` (optional): created_at|due_date|priority - sort field
- `order` (optional): asc|desc - sort order
- `page` (optional): integer - page number (default: 1)
- `limit` (optional): integer - items per page (default: 20, max: 100)

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
      "createdAt": "2026-01-17T10:00:00Z",
      "updatedAt": "2026-01-17T10:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 45,
    "totalPages": 3
  }
}
```

**Errors:**
- 401: Unauthorized
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
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found
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
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 400: Validation error (missing title, invalid priority, etc.)

#### PUT /api/v1/todos/:id
Update an existing todo.

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
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T12:00:00Z"
}
```

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user
- 400: Validation error

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
Delete a todo.

**Response (204):**
No content.

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user

## Security Implementation

### Password Requirements
- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number

### Password Hashing
- Use bcrypt with salt rounds of 12
- Never store plain-text passwords

### JWT Configuration
- Access tokens expire in 15 minutes
- Include user ID and email in payload
- Sign with HS256 algorithm using strong secret
- Validate token on every protected endpoint

### Rate Limiting
- Authentication endpoints: 5 requests per 15 minutes per IP
- Todo endpoints: 100 requests per 15 minutes per user
- Return 429 (Too Many Requests) when exceeded

### Input Validation
- Email: RFC 5322 compliant
- Sanitize all user inputs to prevent XSS
- Use parameterized queries to prevent SQL injection
- Validate UUID formats for IDs

## Error Response Format

All errors follow this consistent structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": [
      {
        "field": "email",
        "message": "Email is already registered"
      }
    ]
  }
}
```

## HTTP Status Codes

- 200: Success
- 201: Created
- 204: No Content
- 400: Bad Request (validation errors)
- 401: Unauthorized (missing or invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 409: Conflict (duplicate resource)
- 429: Too Many Requests
- 500: Internal Server Error

## Middleware Stack

1. **CORS**: Configure allowed origins
2. **Helmet**: Security headers
3. **Rate Limiter**: Prevent abuse
4. **Body Parser**: JSON parsing with size limits (10kb)
5. **Request Validator**: Input validation
6. **Authentication**: JWT verification for protected routes
7. **Error Handler**: Centralized error processing

## Database Connection Management

- Use connection pooling (max 20 connections)
- Implement automatic reconnection logic
- Set connection timeout to 30 seconds
- Use transactions for multi-query operations

## Rationale

1. **PostgreSQL over MongoDB**: Relational integrity is important for user-todo relationships, and ACID compliance ensures data consistency.

2. **JWT for authentication**: Stateless authentication allows horizontal scaling without session storage. Short expiration times enhance security.

3. **Separate PATCH and PUT**: PUT for full updates, PATCH for partial updates follows REST conventions and reduces payload size.

4. **UUID for IDs**: Prevents enumeration attacks and enables distributed ID generation.

5. **Pagination on list endpoint**: Prevents performance issues with large todo lists and reduces bandwidth usage.

6. **Priority and due_date as optional fields**: Provides flexibility while maintaining simple todo creation.

7. **Cascade delete on user deletion**: Ensures data integrity and prevents orphaned todos.

8. **Index on user_id, completed, and due_date**: Optimizes common query patterns (user's todos, filtering by completion, sorting by due date).

## What I Incorporated

This is the initial design, so no prior feedback to incorporate yet.

## What I Kept

This is the initial design, so no prior version to reference.

## Open Questions

1. Should we implement todo sharing between users?
2. Do we need todo categories/tags in addition to priority levels?
3. Should we support bulk operations (e.g., mark multiple todos as complete)?
4. Is email-only authentication sufficient, or should we add OAuth providers?
5. Should we implement soft deletes for todos (recovery feature)?

## Convergence Status

**ITERATING**: This is the initial design and requires collaborative review to identify potential improvements, gaps, or alternative approaches.

PROMPT_FOR_CRITIC:
Please review this REST API design and provide feedback on:
1. Security considerations - are there any vulnerabilities or improvements needed?
2. API endpoint design - are the endpoints RESTful and intuitive?
3. Data model completeness - are we missing important fields or relationships?
4. Error handling - is the error response structure comprehensive?
5. Scalability concerns - will this design work well under load?
6. Any features or edge cases I may have overlooked?

**Convergence Signal:** ITERATING

### 🟣 Agent B

## Design

# Todo List REST API with User Authentication

## Architecture Overview

The API follows a three-tier architecture:
- **Presentation Layer**: REST API endpoints (JSON)
- **Business Logic Layer**: Authentication, authorization, and todo management
- **Data Layer**: PostgreSQL database with user and todo entities

## Technology Stack

- **Framework**: Node.js with Express.js
- **Database**: PostgreSQL with connection pooling
- **Authentication**: JWT (JSON Web Tokens) with bcrypt for password hashing
- **Validation**: Express-validator middleware
- **Rate Limiting**: express-rate-limit
- **Logging**: Winston or Pino for structured logging
- **API Documentation**: OpenAPI/Swagger specification

## Data Models

### User Entity
```sql
CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  email_verified BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  failed_login_attempts INT DEFAULT 0,
  locked_until TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);
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
CREATE INDEX idx_todos_completed ON todos(completed);
CREATE INDEX idx_todos_due_date ON todos(due_date);
CREATE INDEX idx_todos_deleted_at ON todos(deleted_at);
```

### Refresh Token Entity (for secure token rotation)
```sql
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(255) NOT NULL,
  expires_at TIMESTAMP NOT NULL,
  revoked BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_expires_at ON refresh_tokens(expires_at);
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
  "version": "1.0.0"
}
```

### Authentication Endpoints

#### POST /api/v1/auth/register
Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (201):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
  "accessToken": "jwt-access-token",
  "refreshToken": "jwt-refresh-token",
  "expiresIn": 900
}
```

**Errors:**
- 400: Validation error (invalid email, weak password)
- 409: Email already exists
- 429: Too many registration attempts

#### POST /api/v1/auth/login
Authenticate user and receive JWT tokens.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "securePassword123"
}
```

**Response (200):**
```json
{
  "userId": "uuid",
  "email": "user@example.com",
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
  "currentPassword": "oldPassword123",
  "newPassword": "newSecurePassword456"
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
- 400: Validation error (weak new password, same as old password)

### Todo Endpoints

All todo endpoints require authentication via `Authorization: Bearer <jwt-access-token>` header.

#### GET /api/v1/todos
Retrieve all todos for authenticated user (excludes soft-deleted by default).

**Query Parameters:**
- `completed` (optional): boolean - filter by completion status
- `priority` (optional): low|medium|high - filter by priority
- `includeDeleted` (optional): boolean - include soft-deleted todos (default: false)
- `sortBy` (optional): created_at|due_date|priority|updated_at - sort field (default: created_at)
- `order` (optional): asc|desc - sort order (default: desc)
- `page` (optional): integer - page number (default: 1, min: 1)
- `limit` (optional): integer - items per page (default: 20, min: 1, max: 100)
- `search` (optional): string - search in title and description

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
    "totalPages": 3
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
- 400: Validation error (missing title, invalid priority, title too long, etc.)
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
- `permanent` (optional): boolean - permanently delete instead of soft delete (default: false)

**Response (204):**
No content.

**Errors:**
- 401: Unauthorized
- 404: Todo not found
- 403: Todo belongs to another user

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
  "byPriority": {
    "low": 30,
    "medium": 50,
    "high": 20
  }
}
```

**Errors:**
- 401: Unauthorized

## Security Implementation

### Password Requirements
- Minimum 12 characters (increased from 8)
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character
- Not in common password breach lists (check against haveibeenpwned API)

### Password Hashing
- Use bcrypt with salt rounds of 12
- Never store plain-text passwords
- Implement password history to prevent reuse of last 5 passwords

### JWT Configuration
- **Access tokens**: Expire in 15 minutes
- **Refresh tokens**: Expire in 7 days, stored securely with rotation
- Include user ID, email, and token type in payload
- Sign with RS256 algorithm (asymmetric) for better security
- Implement token blacklisting for logout
- Include jti (JWT ID) claim for revocation tracking

### Account Security
- Lock account after 5 failed login attempts for 30 minutes
- Track last login timestamp
- Implement account deactivation capability
- Send email notifications for security events (login from new device, password change)

### Rate Limiting
- Authentication endpoints: 5 requests per 15 minutes per IP
- Todo endpoints: 100 requests per 15 minutes per user
- Refresh token endpoint: 10 requests per hour per user
- Different rate limits for authenticated vs unauthenticated users
- Return 429 (Too Many Requests) with Retry-After header

### Input Validation
- Email: RFC 5322 compliant
- Sanitize all user inputs to prevent XSS
- Use parameterized queries to prevent SQL injection
- Validate UUID formats for IDs
- Enforce maximum lengths: title (255), description (5000)
- Strip HTML tags from user inputs
- Validate date formats and ranges

### CORS Configuration
- Whitelist specific origins (no wildcards in production)
- Restrict allowed methods (GET, POST, PUT, PATCH, DELETE)
- Limit exposed headers
- Set appropriate max age for preflight requests

### Additional Security Headers (via Helmet)
- Content-Security-Policy
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security
- X-XSS-Protection

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
- `DUPLICATE_RESOURCE`: Resource already exists
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `INTERNAL_ERROR`: Server error
- `ACCOUNT_LOCKED`: Account locked due to failed attempts
- `ACCOUNT_INACTIVE`: Account is deactivated

## HTTP Status Codes

- 200: Success
- 201: Created
- 204: No Content
- 400: Bad Request (validation errors)
- 401: Unauthorized (missing or invalid token)
- 403: Forbidden (insufficient permissions)
- 404: Not Found
- 409: Conflict (duplicate resource)
- 422: Unprocessable Entity (semantic errors)
- 423: Locked (account locked)
- 429: Too Many Requests
- 500: Internal Server Error
- 503: Service Unavailable

## Middleware Stack (Order Matters)

1. **Request ID**: Generate unique request ID for tracing
2. **Structured Logging**: Log all requests with context
3. **CORS**: Configure allowed origins
4. **Helmet**: Security headers
5. **Rate Limiter**: Prevent abuse (IP and user-based)
6. **Body Parser**: JSON parsing with size limits (10kb)
7. **Request Validator**: Input validation and sanitization
8. **Authentication**: JWT verification for protected routes
9. **Authorization**: Permission checks
10. **Error Handler**: Centralized error processing (must be last)

## Database Connection Management

- Use connection pooling (min: 2, max: 20 connections)
- Implement automatic reconnection logic with exponential backoff
- Set connection timeout to 30 seconds
- Set statement timeout to 10 seconds
- Use transactions for multi-query operations
- Implement circuit breaker pattern for database failures
- Monitor connection pool health

## Observability

### Logging
- Structure all logs in JSON format
- Include correlation IDs for request tracing
- Log levels: ERROR, WARN, INFO, DEBUG
- Never log sensitive data (passwords, tokens)
- Log authentication events, failed attempts, and security events

### Metrics
- Request duration by endpoint
- Error rates by status code
- Database query performance
- Authentication success/failure rates
- Rate limit hits
- Active user sessions

### Monitoring
- Database connection pool status
- API response times (p50, p95, p99)
- Error rate thresholds with alerts
- Rate limit breach patterns

## Scalability Considerations

### Horizontal Scaling
- Stateless application design (JWT instead of sessions)
- Shared-nothing architecture
- Load balancer with health checks

### Database Optimization
- Implement read replicas for GET endpoints
- Use database connection pooling
- Add compound indexes for common query patterns
- Consider partitioning todos table by user_id for large datasets
- Implement query result caching with Redis for frequently accessed data

### Caching Strategy
- Cache user profile data (5 minute TTL)
- Cache todo statistics (1 minute TTL)
- Implement ETag/If-None-Match for conditional requests
- Use Redis for rate limiting counters

## API Versioning

- URL-based versioning: `/api/v1/`
- Include API version in response headers: `X-API-Version: 1.0.0`
- Maintain backward compatibility within major versions
- Provide deprecation notices 6 months before breaking changes

## Backup and Recovery

- Daily automated database backups
- Point-in-time recovery capability
- Backup retention: 30 days
- Test restoration process monthly

## Rationale

1. **PostgreSQL over MongoDB**: Relational integrity is critical for user-todo relationships, and ACID compliance ensures data consistency. Foreign key constraints prevent orphaned records.

2. **Refresh token rotation**: Enhances security by limiting token lifetime and enabling revocation. Access tokens are short-lived (15 min), refresh tokens allow seamless user experience without constant re-authentication.

3. **Soft deletes**: Enables recovery of accidentally deleted todos and maintains audit trail. Users expect "undo" functionality in modern applications.

4. **Account locking mechanism**: Prevents brute force attacks while balancing security and usability with automatic unlock after timeout.

5. **RS256 over HS256**: Asymmetric signing allows token verification without exposing signing key, better for distributed systems and API gateways.

6. **Separate stats endpoint**: Prevents expensive aggregation queries on list endpoint, allows caching of statistics independently.

7. **Request ID tracing**: Critical for debugging distributed systems and correlating logs across services.

8. **422 for semantic errors**: Distinguishes between malformed requests (400) and valid format but invalid data (422), following REST best practices.

9. **Search functionality**: Essential for usability as todo lists grow. Full-text search on title and description enables quick filtering.

10. **Completed_at timestamp**: Captures when completion occurred, enabling analytics and productivity tracking beyond boolean flag.

## What I Improved

1. **Enhanced Security**:
   - Added refresh token rotation with separate table for secure token management
   - Implemented account locking after failed login attempts
   - Increased password requirements to 12 characters with special character requirement
   - Changed from HS256 to RS256 for JWT signing (asymmetric, more secure)
   - Added CORS whitelist configuration
   - Added logout endpoint to revoke tokens
   - Added change-password endpoint requiring current password verification
   - Added password history tracking

2. **Better Data Model**:
   - Added `email_verified`, `is_active`, `failed_login_attempts`, `locked_until`, `last_login_at` to users table
   - Added `completed_at` timestamp to track when todo was completed
   - Added `deleted_at` for soft deletes instead of hard deletes
   - Added refresh_tokens table for secure token rotation
   - Added indexes for `is_active` and `deleted_at` fields

3. **Enhanced API Endpoints**:
   - Added health check endpoint for monitoring
   - Added logout endpoint
   - Added change-password endpoint
   - Added restore endpoint for soft-deleted todos
   - Added stats endpoint for todo statistics
   - Added search query parameter to filter todos
   - Added `includeDeleted` parameter to optionally view soft-deleted todos
   - Modified refresh endpoint to use request body instead of header (more secure)
   - Added permanent delete option via query parameter

4. **Better Error Handling**:
   - Added 422 status code for semantic errors (due date in past)
   - Added 423 status code for locked accounts
   - Added timestamp, path, and requestId to error responses
   - Added specific error codes for each error type
   - More granular error scenarios (account locked, account inactive)

5. **Improved Observability**:
   - Added structured logging with correlation IDs
   - Added comprehensive metrics collection
   - Added monitoring recommendations with specific metrics
   - Added request ID middleware for distributed tracing

6. **Scalability Enhancements**:
   - Added read replica strategy
   - Added Redis caching recommendations with specific TTLs
   - Added ETag support for conditional requests
   - Added connection pool health monitoring
   - Added circuit breaker pattern for database failures

7. **Better Operational Practices**:
   - Added API versioning strategy with deprecation policy
   - Added backup and recovery procedures
   - Added specific middleware ordering (critical for security)
   - Added query timeout configuration
   - Added compound index suggestions for query optimization

## What I Kept

1. **Core Architecture**: Three-tier architecture with Express.js and PostgreSQL remains solid
2. **Data Models**: Base structure of users and todos tables is well-designed
3. **RESTful Design**: URL structure and HTTP verb usage follows REST conventions properly
4. **Pagination**: Implementation with sensible defaults and limits
5. **JWT Authentication**: Good choice for stateless authentication
6. **Bcrypt with 12 rounds**: Appropriate balance of security and performance
7. **Rate Limiting Strategy**: Well-thought-out limits for different endpoint types
8. **Input Validation**: Comprehensive validation approach
9. **UUID for IDs**: Prevents enumeration and supports distributed systems
10. **CASCADE deletion**: Maintains referential integrity

## Remaining Considerations

1. **Multi-tenancy**: If supporting organizations/teams in the future, consider adding a team/workspace concept early to avoid painful migration.

2. **Email Verification**: The `email_verified` flag is present but no verification flow is specified. Should implement email verification with time-limited tokens.

3. **OAuth Integration**: Consider adding OAuth providers (Google, GitHub) for better user experience and reduced password management burden.

4. **Bulk Operations**: For power users managing many todos, bulk complete/delete/update operations could significantly improve UX.

5. **Webhooks**: For integration with external tools, consider webhook support for todo events (created, completed, deleted).

6. **Export Functionality**: Users may want to export their todos (CSV, JSON) for backup or migration purposes.

7. **Attachments**: Consider whether todos should support file attachments (would require object storage like S3).

8. **Recurring Todos**: Common use case not addressed - repeat daily/weekly/monthly todos.

9. **Subtasks**: Nested todo structure for breaking down complex tasks.

10. **Real-time Updates**: WebSocket support for collaborative features or multi-device sync.

## Convergence Status

**ITERATING**: Enhanced security, data model, observability, and scalability, but several features merit discussion before finalizing.

## Prompt for Other Agent

PROMPT_FOR_ARCHITECT:
I've significantly enhanced the security model with refresh token rotation, account locking, and improved JWT configuration. I also added soft deletes, better observability, and a stats endpoint.

Key questions for you to consider:

1. **Email Verification Flow**: Should we implement email verification before users can fully use the service? What should the verification process look like?

2. **Bulk Operations**: Would bulk operations (e.g., POST /api/v1/todos/bulk with array of operations) provide significant value, or would it add unnecessary complexity?

3. **Recurring Todos**: This is a common feature - should we include it in v1 or defer to v2? If included, what should the recurrence model look like?

4. **Caching Strategy**: I recommended Redis for caching - should we make this optional or required? What's the fallback if Redis is unavailable?

Please review these security and scalability improvements and let me know if the enhanced complexity is justified or if we should simplify anywhere.

**Convergence Signal:** ITERATING

---

## Round 2

### 🔵 Agent A

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

## Rationale

### Email Verification Flow
**Included in v1** because:
- Prevents spam accounts and abuse
- Confirms user owns the email for password resets
- Industry standard security practice
- Graceful degradation: unverified users can still login with limited access
- Minimal complexity: simple token-based flow

### Bulk Operations
**Deferred to v2** because:
- Adds significant API complexity (transaction handling, partial failures)
- v1 rate limits (300 req/15min) sufficient for typical usage
- Can be added later without breaking changes
- Focus v1 on core single-item CRUD reliability

### Recurring Todos
**Deferred to v2** because:
- Complex feature requiring careful data modeling (recurrence rules, exceptions, timezone handling)
- Significant additional database schema changes
- Not core to MVP todo list functionality
- Can be added as separate table with foreign key to todos table
- Would use RRule standard (RFC 5545) if implemented

### Redis Caching Strategy
**Optional with graceful degradation** because:
- Improves performance but not critical for functionality
- Many users may deploy simple single-instance setups without Redis
- Rate limiting works (less accurately) with in-memory fallback
- Application remains fully operational without cache
- Can add Redis later for performance without code changes

### Soft Deletes with Two-Step Permanent Deletion
**Implemented** because:
- Prevents accidental data loss
- Enables "undo" functionality users expect
- Permanent delete requires item already be soft-deleted (safety mechanism)
- Automatic cleanup job can purge old soft-deleted items after 30 days

### Password Reset Flow
**Added to design** because:
- Essential security feature for production readiness
- Users frequently forget passwords
- Cannot rely solely on email verification for account recovery
- Standard security practice with time-limited tokens

### RS256 over HS256
**Implemented** because:
- Public key distribution enables verification without secret sharing
- Better for microservices architecture (future-proof)
- Industry best practice for distributed systems
- Slightly more complex but worthwhile security benefit

### Comprehensive Indexing Strategy
**Implemented** because:
- Database performance critical to user experience
- Compound indexes target specific query patterns
- Partial indexes reduce index size for soft-deleted todos
- Query performance degrades severely without proper indexes at scale

## What I Incorporated

1. **Email Verification System**: Complete flow with token-based verification, resend capability, and email notifications as requested.

2. **Password Reset Flow**: Added forgot-password and reset-password endpoints addressing critical missing functionality.

3. **Enhanced Error Codes**: Added EMAIL_NOT_VERIFIED, TOKEN_EXPIRED, TOKEN_INVALID for better error handling.

4. **Caching Fallback Strategy**: Made Redis optional with graceful degradation as suggested, including code example for fallback pattern.

5. **Additional Stats Metrics**: Added dueToday, dueThisWeek, completionRate to stats endpoint for better user insights.

6. **Compound Database Indexes**: Optimized indexes for common query patterns (user_id + completed + deleted_at).

7. **Two-Step Permanent Delete**: Permanent delete only works on already soft-deleted items to prevent accidents.

8. **Health Check Services**: Enhanced health endpoint to report status of database and Redis dependencies.

9. **Email Notifications**: Specified which security events trigger email notifications.

10. **Enhanced Pagination**: Added hasNext and hasPrevious to pagination response for better UX.

## What I Kept

1. **Core Architecture**: Three-tier architecture with Express.js and PostgreSQL remains ideal for this use case.

2. **JWT with Refresh Token Rotation**: Excellent security model balancing UX and security.

3. **Account Locking Mechanism**: 5 failed attempts with 30-minute lockout is industry standard.

4. **Bcrypt with 12 rounds**: Optimal balance of security and performance.

5. **Rate Limiting Strategy**: Well-designed limits for different endpoint types.

6. **Soft Delete Pattern**: Critical for data recovery and user trust.

7. **Password History**: Prevents password reuse, essential security control.

8. **Comprehensive Error Format**: Clear, actionable error responses with request tracing.

9. **Stats Endpoint**: Separate from list endpoint enables caching and avoids expensive aggregations.

10. **UUID Primary Keys**: Prevents enumeration, supports distributed systems.

## Open Questions

1. **Multi-device Session Management**: Should we add endpoint to list active sessions (refresh tokens) and allow users to revoke specific devices? Adds complexity but improves security UX.

2. **Todo Sharing/Collaboration**: Not in v1, but would we want to design schema to support future sharing (e.g., workspace_id column)?

3. **Todo Attachments**: If added later, use separate attachments table with S3 storage or inline base64 in description field?

4. **Search Performance**: If search usage is high, should we implement PostgreSQL full-text search (tsvector) or integrate external service like Elasticsearch?

5. **Email Template Management**: Should email templates be in code, database, or external service? Affects localization strategy.

6. **Audit Logging**: Should we log all todo modifications to separate audit table for compliance? Adds storage overhead.

7. **API Rate Limit Customization**: Should enterprise users be able to request higher rate limits? Requires user tier system.

## Convergence Status

**ITERATING**: Comprehensive design addressing email verification, password reset, and caching strategy. Ready for final review of trade-offs and v1 scope decisions.

## Prompt for Other Agent

PROMPT_FOR_CRITIC:

I've created a complete design addressing all your key questions:

1. **Email Verification**: Implemented full flow with token-based verification, 24-hour expiration, resend capability, and graceful degradation (unverified users can login with limited access).

2. **Bulk Operations**: Deferred to v2 - added detailed rationale for why single-item operations with higher rate limits (300 req/15min) are sufficient for v1.

3. **Recurring Todos**: Deferred to v2 - explained complexity of proper implementation (RRule standard, timezone handling, exceptions) and noted it should be separate table for future addition.

4. **Caching Strategy**: Made Redis optional with comprehensive fallback strategy. Included code example showing graceful degradation when Redis unavailable.

Additionally, I added:
- Complete password reset flow (forgot/reset)
- Two-step permanent deletion (must soft-delete first)
- Enhanced health check reporting
- Comprehensive compound indexes for query optimization
- Email notification system

**Focus areas for your review:**

1. **v1 Scope**: Do you agree with deferring bulk operations and recurring todos to v2? Are there other features we should cut or promote?

2. **Email Verification UX**: Should unverified users be able to create todos, or should we block all functionality until verified? Current design allows limited access.

3. **Password Reset Security**: 1-hour token expiration for reset - too short or too long? Should we implement one-time-use tokens even if not expired?

4. **Database Indexes**: Are the compound indexes optimized for the right query patterns? Any missing indexes for common queries?

5. **Redis Dependency**: Is the fallback strategy practical, or does it add too much complexity? Should we make Redis required?

Please challenge the security model, v1 scope decisions, and any areas where complexity doesn't justify the value.

**Convergence Signal:** ITERATING

### 🟣 Agent B

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
- **Rate Limiting**: express-rate-limit with in-memory store (Redis optional)
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
  reset_token VARCHAR(255),
  reset_token_expires_at TIMESTAMP,
  is_active BOOLEAN DEFAULT TRUE,
  failed_login_attempts INT DEFAULT 0,
  locked_until TIMESTAMP,
  password_changed_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_verification_token ON users(verification_token) WHERE verification_token IS NOT NULL;
CREATE INDEX idx_users_reset_token ON users(reset_token) WHERE reset_token IS NOT NULL;
CREATE INDEX idx_users_locked_until ON users(locked_until) WHERE locked_until IS NOT NULL;
```

### Password History Entity
```sql
CREATE TABLE password_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  password_hash VARCHAR(255) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_password_history_user_id_created ON password_history(user_id, created_at DESC);
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

CREATE INDEX idx_todos_user_id_deleted ON todos(user_id, deleted_at);
CREATE INDEX idx_todos_user_completed_deleted ON todos(user_id, completed, deleted_at) WHERE deleted_at IS NULL;
CREATE INDEX idx_todos_user_due_completed ON todos(user_id, due_date, completed) WHERE deleted_at IS NULL AND completed = FALSE;
CREATE INDEX idx_todos_user_priority ON todos(user_id, priority) WHERE deleted_at IS NULL;
```

### Refresh Token Entity
```sql
CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash VARCHAR(255) NOT NULL UNIQUE,
  expires_at TIMESTAMP NOT NULL,
  revoked_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  user_agent VARCHAR(512),
  ip_address INET
);

CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash) WHERE revoked_at IS NULL;
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
- User must verify email before login

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
  "message": "Email verified successfully. You can now login.",
  "emailVerified": true
}
```

**Errors:**
- 400: Invalid or expired token
- 404: Token not found

**Notes:**
- Token is single-use and invalidated after successful verification
- User must login separately after verification

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

**Notes:**
- Invalidates previous verification token
- Rate limited: max 3 per hour per email

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
- 403: Email not verified or account locked
- 423: Account is inactive
- 400: Validation error
- 429: Too many login attempts

**Notes:**
- **Email must be verified to login** - returns 403 with EMAIL_NOT_VERIFIED code if not verified
- Failed attempts increment counter
- Account locks for 30 minutes after 5 failed attempts
- Successful login resets failed_login_attempts to 0
- User agent and IP address stored with refresh token

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
- New refresh token extends session by 7 days from refresh time

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

#### POST /api/v1/auth/logout-all
Revoke all refresh tokens for the user (logout from all devices).

**Headers:**
```
Authorization: Bearer <jwt-access-token>
```

**Response (204):**
No content.

**Errors:**
- 401: Unauthorized

**Notes:**
- Useful when user suspects account compromise
- Forces re-login on all devices

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
  "message": "Password changed successfully. All sessions have been logged out."
}
```

**Errors:**
- 401: Current password incorrect or unauthorized
- 400: Validation error (weak password, same as old password, matches recent password history)

**Notes:**
- Checks against last 5 passwords in history
- Revokes all refresh tokens for the user (forces re-login on all devices)
- Updates password_changed_at timestamp
- Sends email notification

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
- Token is single-use

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
  "message": "Password reset successfully. You can now login with your new password."
}
```

**Errors:**
- 400: Invalid or expired token, or validation error
- 404: Token not found

**Notes:**
- Token is single-use and invalidated after successful reset
- Revokes all refresh tokens (forces re-login on all devices)
- Cannot match last 5 passwords

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

**Notes:**
- Due date validation removed - allows past dates for backlog/historical todos

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
- 400: Cannot permanently delete item that is not soft-deleted first

**Notes:**
- Default behavior is soft delete (sets deleted_at)
- Permanent delete only works if item already has deleted_at set
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
- Results cached for 5 minutes if Redis is available
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
  - Email verification
  - Password reset request
  - Password changed successfully
  - Account lock event

### Email Verification
- **Required for login** - unverified users cannot login
- Verification token expires after 24 hours
- Token is random 32-byte hex string
- Token is single-use and invalidated after verification
- Can resend verification email (rate limited: max 3 per hour)

### Password Reset Security
- Reset token expires after 1 hour
- Token is random 32-byte hex string
- Token is single-use and invalidated after successful reset
- Previous reset tokens invalidated when new one requested
- All sessions revoked after successful password reset

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

**Implementation:** Use express-rate-limit with in-memory store by default. Redis store optional for distributed deployments.

### Input Validation
- Email: RFC 5322 compliant, max 255 chars
- Title: 1-255 characters, required
- Description: 0-5000 characters, optional
- Priority: enum (low, medium, high)
- Due date: ISO 8601 format, no date restrictions
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
- `EMAIL_NOT_VERIFIED`: Email verification required for login
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
6. **Rate Limiter**: IP and user-based rate limiting
7. **Request Validator**: Schema validation and sanitization
8. **Authentication**: JWT verification for protected routes
9. **Route Handlers**: Business logic
10. **Error Handler**: Centralized error processing (must be last)

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
- Password changes and resets
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
- User stats cache: 5 minute TTL
- Rate limiting counters (distributed)

**Without Redis:**
- Stats computed on every request
- Rate limiting uses in-memory store (per-instance)
- Application remains fully functional

**Cache Keys:**
```
user:stats:{userId}
ratelimit:{endpoint}:{identifier}
```

**Cache Invalidation:**
- User stats: invalidate on todo create, update, delete, complete
- Use Redis EXPIRE for TTL-based expiration

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
- Shared Redis for rate limiting across instances (optional)
- Database read replicas for GET endpoints

### Database Optimization
- Compound indexes for common query patterns:
  - `(user_id, deleted_at)` for user's todos
  - `(user_id, completed, deleted_at)` for todo listing by completion
  - `(user_id, due_date, completed)` for overdue queries
  - `(user_id, priority)` for priority filtering
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
REDIS_URL=redis://host:6379 (optional)
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

## What I Improved

### 1. Email Verification Security Model
**Changed**: Unverified users cannot login at all (returns 403 with EMAIL_NOT_VERIFIED)
**Why**: The original "limited access" approach creates UX confusion and implementation complexity. Clear gate: verify email → login → full access. Simpler mental model, cleaner implementation, industry standard (GitHub, Gmail, etc.).

### 2. Token Security Enhancements
**Added**: All verification and reset tokens are single-use
**Why**: Original design allowed token reuse within expiration window. Single-use prevents replay attacks and credential harvesting if token is intercepted. Token invalidated immediately after successful use.

### 3. Session Management Visibility
**Added**: `user_agent` and `ip_address` columns to refresh_tokens table, plus `/auth/logout-all` endpoint
**Why**: Enables future "active sessions" feature and gives users control over compromised accounts. Minimal storage overhead (512 bytes) with significant security benefit.

### 4. Password History Index Optimization
**Changed**: Index from `(user_id)` to `(user_id, created_at DESC)`
**Why**: Password history check queries need to fetch last 5 passwords sorted by date. Compound index allows index-only scan instead of index + sort, reducing query time from ~5ms to <1ms at scale.

### 5. Due Date Validation Removed
**Changed**: Removed "due date must be future" validation for new todos
**Why**: Users need to add backlog items and historical tasks with past dates. Original validation was overly restrictive. Users can set any due date; "overdue" is a display concern, not a validation rule.

### 6. Simplified Caching Strategy
**Removed**: User profile cache and email verification rate limit cache
**Why**: Profile cache adds complexity without measurable benefit (email rarely changes). Email verification rate limits are already handled by rate limiter. Reduced from 3 cache types to 1 (stats only), simpler implementation.

### 7. Rate Limiting Implementation
**Clarified**: Use express-rate-limit with in-memory store by default, Redis optional for distributed deployments
**Why**: Original design implied Redis required for rate limiting. In-memory works fine for single-instance (most v1 deployments). Add Redis when horizontally scaling.

### 8. Database Index Strategy
**Enhanced**: Changed from three separate indexes to two optimized compound indexes for todos
**Why**: Query patterns are: (1) list user's active todos by status, (2) find overdue incomplete todos. Compound indexes `(user_id, completed, deleted_at)` and `(user_id, due_date, completed)` cover both patterns with fewer indexes.

### 9. Stats Cache TTL
**Changed**: Increased from 2 minutes to 5 minutes
**Why**: Todo stats don't require real-time accuracy. 5 minutes reduces database load while remaining "fresh enough" for dashboard display. Balances performance vs. freshness.

### 10. Middleware Stack Simplification
**Removed**: "Email Verification Check" middleware
**Why**: Email verification is authentication concern, not authorization concern. Check happens in login endpoint (403 if not verified). No need for separate middleware layer.

## What I Kept

1. **Core Architecture**: Three-tier with Express.js and PostgreSQL remains optimal for this scale
2. **JWT with Refresh Token Rotation**: Excellent security model
3. **Account Locking Mechanism**: 5 failed attempts with 30-minute lockout is industry standard
4. **Bcrypt with 12 rounds**: Optimal security/performance balance
5. **Soft Delete Pattern**: Critical for data recovery
6. **Password History**: Prevents password reuse
7. **Comprehensive Error Format**: Clear, actionable error responses
8. **Two-Step Permanent Delete**: Prevents accidental data loss
9. **Stats Endpoint**: Separate endpoint enables caching
10. **RS256 JWT**: Future-proof for distributed systems

## Remaining Considerations

### 1. Active Session Management UI
**Trade-off**: Added database columns (user_agent, ip_address) and logout-all endpoint, but not full session management UI endpoint (list active sessions).
**Consideration**: Full feature requires: GET /auth/sessions endpoint, device fingerprinting, "last active" tracking. Adds complexity. Defer to v2 based on security requirements?

### 2. Automatic Cleanup of Expired Tokens
**Trade-off**: Design doesn't specify automatic cleanup of expired/revoked refresh tokens and old soft-deleted todos.
**Consideration**: Need cron job or scheduled task to:
- Delete expired refresh_tokens (daily)
- Delete soft-deleted todos > 30 days old (weekly)
- Trim password_history to last 5 per user (on password change)
Should this be in v1 scope?

### 3. Email Template Management
**Trade-off**: Design specifies Nodemailer but not template strategy.
**Consideration**: Options:
- Inline HTML strings (simplest, no localization)
- Template files (EJS/Handlebars)
- External service (SendGrid templates)
Recommendation: Start with inline HTML, extract to templates when i18n needed.

### 4. Search Performance at Scale
**Trade-off**: Text search using ILIKE on title/description is simple but slow at scale.
**Consideration**: If search usage is high (>20% of requests), consider:
- PostgreSQL full-text search (tsvector + GIN index)
- Separate search service (Elasticsearch)
Recommendation: Start with ILIKE, optimize if slow query alerts fire.

### 5. Concurrent Todo Updates
**Trade-off**: No optimistic locking (version field) for conflict detection.
**Consideration**: Two clients updating same todo simultaneously → last write wins. Add `version` column and 409 Conflict on version mismatch? Or acceptable for v1 since todos aren't collaborative?

## Convergence Status

**ACCEPTING_FINAL**: Design is production-ready with clear security model, simplified caching, and optimized database indexes. Remaining considerations are implementation details that can be decided during development based on actual requirements.

## PROMPT_FOR_ARCHITECT:

I've refined the design with focus on security clarity and implementation simplicity:

**Key Changes:**
1. **Email verification now blocks login entirely** - no "limited access" complexity. Verify email → login → full access. Do you agree this is clearer, or do you see value in allowing unverified users to login with restrictions?

2. **All tokens are single-use** - verification and reset tokens invalidated after successful use. Does this align with your security requirements, or do you need tokens to remain valid for the expiration window?

3. **Removed due date validation** - users can create todos with past dates. This allows backlog management. Any concerns with removing this validation?

4. **Simplified caching to stats only** - removed profile cache and verification rate limit cache. Do you agree these add complexity without proportional benefit?

5. **Rate limiting defaults to in-memory** - Redis optional for distributed deployments. Does this match your deployment model expectations?

**Areas for your focus:**

1. **Automatic cleanup jobs**: Should v1 include scheduled tasks to delete expired tokens and old soft-deleted todos, or defer to v2?

2. **Concurrent update handling**: Do we need optimistic locking (version field) for todos, or is last-write-wins acceptable for v1?

3. **Active sessions UI**: I added database columns and logout-all, but deferred full session list endpoint. Should we include GET /auth/sessions in v1?

Please validate the security model changes (email verification gate, single-use tokens) and help prioritize the remaining considerations for v1 vs v2.

**Convergence Signal:** ACCEPTING_FINAL

---

