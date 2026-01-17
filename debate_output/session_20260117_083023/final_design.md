# Final Agreed Design

**Task:** Design a REST API for a simple blog system

**Status:** debating

---

## Design

# REST API for Simple Blog System

## 1. Architecture Overview

A RESTful API service with the following layers:
- **Presentation Layer**: HTTP endpoints with JSON serialization
- **Business Logic Layer**: Service classes for blog operations
- **Data Access Layer**: Repository pattern with database abstraction
- **Database**: PostgreSQL with full-text search capabilities
- **Cache Layer**: Redis for sessions, rate limiting, and query results
- **Background Jobs**: Queue system for async operations (email, analytics)

## 2. Data Models

### User
```json
{
  "id": "uuid",
  "username": "string (unique, 3-30 chars, case-insensitive)",
  "email": "string (unique, valid email, case-insensitive)",
  "password_hash": "string (bcrypt, cost factor 12)",
  "display_name": "string (optional, max 100 chars)",
  "bio": "string (optional, max 500 chars)",
  "is_active": "boolean (default: true)",
  "email_verified": "boolean (default: false)",
  "role": "enum: [user, moderator] (default: user)",
  "created_at": "timestamp",
  "updated_at": "timestamp"
}
```

### Post
```json
{
  "id": "uuid",
  "title": "string (required, max 200 chars)",
  "content": "text (required, markdown format)",
  "excerpt": "string (auto-generated if not provided, max 300 chars)",
  "author_id": "uuid (foreign key to User)",
  "slug": "string (unique, URL-safe, indexed)",
  "status": "enum: [draft, published, archived]",
  "published_at": "timestamp (nullable)",
  "view_count": "integer (default: 0)",
  "is_flagged": "boolean (default: false, for moderation)",
  "flag_count": "integer (default: 0)",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "deleted_at": "timestamp (nullable, soft delete)"
}
```

### Comment
```json
{
  "id": "uuid",
  "post_id": "uuid (foreign key to Post)",
  "author_id": "uuid (foreign key to User)",
  "content": "text (required, 1-2000 chars, markdown support)",
  "parent_comment_id": "uuid (nullable, for nested comments)",
  "depth": "integer (denormalized, max: 3)",
  "is_edited": "boolean (default: false)",
  "is_flagged": "boolean (default: false)",
  "flag_count": "integer (default: 0)",
  "created_at": "timestamp",
  "updated_at": "timestamp",
  "deleted_at": "timestamp (nullable, soft delete)"
}
```

### ContentFlag (for moderation)
```json
{
  "id": "uuid",
  "flaggable_type": "enum: [post, comment]",
  "flaggable_id": "uuid",
  "reporter_id": "uuid (foreign key to User)",
  "reason": "enum: [spam, harassment, inappropriate, other]",
  "details": "text (optional, max 500 chars)",
  "status": "enum: [pending, reviewed, dismissed]",
  "reviewed_by": "uuid (nullable, foreign key to User)",
  "reviewed_at": "timestamp (nullable)",
  "created_at": "timestamp"
}
```

## 3. API Endpoints

### Authentication
```
POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/logout
POST   /api/v1/auth/refresh-token
POST   /api/v1/auth/verify-email
POST   /api/v1/auth/resend-verification
POST   /api/v1/auth/forgot-password
POST   /api/v1/auth/reset-password
```

### Users
```
GET    /api/v1/users/:id
PUT    /api/v1/users/:id               # Full profile update (own only)
PATCH  /api/v1/users/:id               # Partial profile update (own only)
PATCH  /api/v1/users/:id/password      # Change password
DELETE /api/v1/users/:id               # Soft delete (own only)
GET    /api/v1/users/:id/posts         # Public posts by user
GET    /api/v1/users/me                # Current authenticated user
```

### Posts
```
GET    /api/v1/posts                   # List posts (paginated, published for public)
GET    /api/v1/posts/:id               # Get single post (increments view_count)
POST   /api/v1/posts                   # Create post (authenticated)
PUT    /api/v1/posts/:id               # Full update (author only)
PATCH  /api/v1/posts/:id               # Partial update (author only)
DELETE /api/v1/posts/:id               # Soft delete (author or moderator)
PATCH  /api/v1/posts/:id/publish       # Publish draft (author only)
PATCH  /api/v1/posts/:id/archive       # Archive post (author only)
GET    /api/v1/posts/slug/:slug        # Get post by slug
POST   /api/v1/posts/:id/flag          # Flag post for moderation (authenticated)
```

### Comments
```
GET    /api/v1/posts/:postId/comments       # List comments (nested tree)
POST   /api/v1/posts/:postId/comments       # Create comment (authenticated)
PATCH  /api/v1/comments/:id                 # Update comment (author, 15min window)
DELETE /api/v1/comments/:id                 # Soft delete (author or moderator)
POST   /api/v1/comments/:id/flag            # Flag comment (authenticated)
```

### Moderation (moderator role only)
```
GET    /api/v1/moderation/flags             # List pending flags
PATCH  /api/v1/moderation/flags/:id         # Review flag (approve/dismiss)
DELETE /api/v1/moderation/posts/:id         # Delete flagged post
DELETE /api/v1/moderation/comments/:id      # Delete flagged comment
PATCH  /api/v1/moderation/users/:id/suspend # Suspend user account
```

## 4. Request/Response Examples

### POST /api/v1/posts
**Request:**
```json
{
  "title": "My First Blog Post",
  "content": "This is the **markdown** content of my post...",
  "excerpt": "A brief introduction",
  "status": "draft"
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "title": "My First Blog Post",
  "slug": "my-first-blog-post",
  "content": "This is the **markdown** content of my post...",
  "excerpt": "A brief introduction",
  "author": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "username": "johndoe",
    "display_name": "John Doe"
  },
  "status": "draft",
  "published_at": null,
  "view_count": 0,
  "created_at": "2026-01-17T10:00:00Z",
  "updated_at": "2026-01-17T10:00:00Z"
}
```

### GET /api/v1/posts?page=1&limit=10&sort=published_at&order=desc
**Response (200 OK):**
```json
{
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "My First Blog Post",
      "slug": "my-first-blog-post",
      "excerpt": "A brief introduction",
      "author": {
        "id": "123e4567-e89b-12d3-a456-426614174000",
        "username": "johndoe",
        "display_name": "John Doe"
      },
      "comment_count": 5,
      "view_count": 142,
      "published_at": "2026-01-17T10:00:00Z",
      "created_at": "2026-01-17T09:00:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 10,
    "total_items": 95,
    "items_per_page": 10,
    "has_next": true,
    "has_prev": false
  }
}
```

### POST /api/v1/posts/:postId/comments
**Request:**
```json
{
  "content": "Great post! Really helpful.",
  "parent_comment_id": null
}
```

**Response (201 Created):**
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "post_id": "550e8400-e29b-41d4-a716-446655440000",
  "content": "Great post! Really helpful.",
  "author": {
    "id": "223e4567-e89b-12d3-a456-426614174001",
    "username": "janedoe",
    "display_name": "Jane Doe"
  },
  "parent_comment_id": null,
  "depth": 0,
  "is_edited": false,
  "created_at": "2026-01-17T11:00:00Z",
  "updated_at": "2026-01-17T11:00:00Z",
  "can_edit": true,
  "edit_expires_at": "2026-01-17T11:15:00Z"
}
```

### POST /api/v1/posts/:id/flag
**Request:**
```json
{
  "reason": "spam",
  "details": "This post contains promotional content"
}
```

**Response (201 Created):**
```json
{
  "id": "770e8400-e29b-41d4-a716-446655440002",
  "message": "Content has been flagged for review. Thank you for helping keep our community safe.",
  "created_at": "2026-01-17T11:00:00Z"
}
```

## 5. Error Handling

### Standard Error Response Format
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Post with id '123' not found",
    "details": {},
    "request_id": "req_abc123xyz",
    "timestamp": "2026-01-17T10:00:00Z"
  }
}
```

### Validation Error Response
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Input validation failed",
    "details": {
      "fields": {
        "title": ["Title is required", "Title must be between 1 and 200 characters"],
        "email": ["Email format is invalid"]
      }
    },
    "request_id": "req_abc123xyz",
    "timestamp": "2026-01-17T10:00:00Z"
  }
}
```

### HTTP Status Codes
- **200 OK**: Successful GET/PUT/PATCH requests
- **201 Created**: Successful POST requests
- **204 No Content**: Successful DELETE requests
- **400 Bad Request**: Invalid input data or malformed request
- **401 Unauthorized**: Missing or invalid authentication token
- **403 Forbidden**: Authenticated but not authorized
- **404 Not Found**: Resource doesn't exist
- **409 Conflict**: Resource conflict (duplicate slug/username)
- **422 Unprocessable Entity**: Validation errors
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Unexpected server errors
- **503 Service Unavailable**: Service temporarily down

### Error Codes
- `VALIDATION_ERROR`: Input validation failed
- `AUTHENTICATION_REQUIRED`: No auth token provided
- `INVALID_CREDENTIALS`: Wrong username/password
- `TOKEN_EXPIRED`: JWT token expired
- `FORBIDDEN`: User lacks permission
- `RESOURCE_NOT_FOUND`: Resource doesn't exist
- `DUPLICATE_RESOURCE`: Unique constraint violation
- `RATE_LIMIT_EXCEEDED`: Too many requests
- `COMMENT_EDIT_EXPIRED`: Comment edit window expired
- `MAX_NESTING_DEPTH`: Comment nesting too deep
- `INTERNAL_ERROR`: Unexpected server error
- `SERVICE_UNAVAILABLE`: Service temporarily unavailable

## 6. Authentication & Authorization

### JWT-based Authentication
- **Access tokens**: 15 min expiry, contains user_id, username, role
- **Refresh tokens**: 7 days expiry, stored in database (revocable), httpOnly cookie with SameSite=Strict
- **Token format**: 
  ```
  Authorization: Bearer <access_token>
  ```
- **Refresh mechanism**: POST /api/v1/auth/refresh-token with refresh token in httpOnly cookie
- **Token revocation**: Blacklist in Redis on logout (TTL = token expiry)

### Authorization Rules
- **Public access**: Read published posts, read comments
- **Authenticated users**: Create posts/comments, read own drafts, flag content
- **Resource owners**: Update/delete own posts and comments (within time limits for comments)
- **Moderators**: Review flags, delete flagged content, suspend users
- **Comment edit window**: 15 minutes from creation (hardcoded for MVP, configurable in settings table for future)
- **Post visibility**:
  - `draft`: Only author
  - `published`: Everyone
  - `archived`: Only author

### Security Headers
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Content-Security-Policy: default-src 'self'
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

## 7. Validation Rules

### Post Validation
- Title: required, 1-200 characters, sanitized for XSS
- Content: required, minimum 10 characters, markdown format
- Excerpt: optional, max 300 chars (auto-generated from first 300 chars of content if not provided)
- Status: must be one of [draft, published, archived]
- Slug: auto-generated from title (lowercase, hyphenated, unique), max 250 chars

### Comment Validation
- Content: required, 1-2000 characters, markdown support, sanitized for XSS
- Post must exist, be published, and not be deleted
- Parent comment (if specified) must exist, belong to same post, not be deleted
- Nesting depth: maximum 3 levels (enforced via denormalized `depth` field)
- Comment replies to deleted comments: allowed (preserves thread structure)

### User Validation
- Username: required, 3-30 chars, alphanumeric + underscore/hyphen, unique, case-insensitive
- Email: required, valid email format (RFC 5322), unique, case-insensitive
- Password: minimum 8 chars, must contain uppercase, lowercase, number, special character
- Display name: optional, 1-100 chars
- Bio: optional, max 500 chars

### Content Flag Validation
- Reason: must be one of [spam, harassment, inappropriate, other]
- Details: optional, max 500 chars
- Cannot flag own content
- Cannot flag same content more than once
- After 3 flags, content automatically hidden pending review

### Slug Generation Logic
1. Convert title to lowercase
2. Replace spaces with hyphens
3. Remove special characters (keep alphanumeric and hyphens)
4. Truncate to 245 chars (leaving room for suffix)
5. If slug exists, append incrementing number: `my-post`, `my-post-2`, `my-post-3`
6. Maximum length: 250 characters

## 8. Query Parameters & Filtering

### GET /api/v1/posts
- `page`: Page number (default: 1, min: 1)
- `limit`: Items per page (default: 10, min: 1, max: 100)
- `author_id`: Filter by author UUID
- `status`: Filter by status (only `published` for non-authors)
- `sort`: Sort field (created_at, published_at, title, view_count) (default: published_at)
- `order`: Sort order (asc, desc) (default: desc)
- `search`: Full-text search in title and content (PostgreSQL tsvector)

### GET /api/v1/posts/:postId/comments
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 50, max: 100)
- `sort`: Sort field (created_at) (default: created_at)
- `order`: Sort order (asc, desc) (default: asc)
- Response format: Nested tree structure with parent-child relationships

### GET /api/v1/moderation/flags
- `page`: Page number (default: 1)
- `limit`: Items per page (default: 20, max: 100)
- `status`: Filter by flag status (pending, reviewed, dismissed) (default: pending)
- `type`: Filter by flaggable_type (post, comment)
- `sort`: Sort field (created_at, flag_count) (default: created_at)
- `order`: Sort order (asc, desc) (default: desc)

## 9. Rate Limiting

### Rate Limits by User Type
- **Anonymous users**: 100 requests/hour (by IP address)
- **Authenticated users**: 1000 requests/hour (by user_id)
- **Write operations**: 50 requests/hour per user (POST, PUT, PATCH, DELETE)
- **Auth endpoints**: 10 requests/15 minutes per IP (login, register, password reset)
- **Flag submissions**: 10 flags/hour per user (prevent abuse)

### Rate Limit Headers
```
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 995
X-RateLimit-Reset: 1642435200
Retry-After: 3600
```

### Rate Limit Response (429)
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests. Please try again later.",
    "details": {
      "limit": 1000,
      "remaining": 0,
      "reset_at": "2026-01-17T11:00:00Z"
    },
    "timestamp": "2026-01-17T10:00:00Z"
  }
}
```

## 10. Content Security

### XSS Prevention
- All user input sanitized before storage using DOMPurify
- Markdown content rendered through safe parser with HTML tag whitelist
- HTML tags whitelist: `<p>, <strong>, <em>, <a>, <ul>, <ol>, <li>, <code>, <pre>, <blockquote>, <h1>-<h6>`
- Auto-escape user display names in responses
- Link targets forced to `target="_blank" rel="noopener noreferrer"`

### SQL Injection Prevention
- Parameterized queries only (no string concatenation)
- ORM with prepared statements (SQLAlchemy/TypeORM recommended)
- Input validation before database operations

### CSRF Protection
- Not applicable for stateless JWT API
- SameSite cookie attribute for refresh tokens: `SameSite=Strict`
- Origin header validation for write operations

## 11. Pagination Strategy

### Offset-based Pagination (Default for MVP)
Standard page/limit approach for simplicity:
```
GET /api/v1/posts?page=1&limit=10
```

### Cursor-based Pagination (Future Enhancement)
For scale beyond 100k posts, implement cursor-based pagination:
```
GET /api/v1/posts?cursor=eyJpZCI6IjEyMyIsImNyZWF0ZWRfYXQiOiIyMDI2LTAxLTE3In0&limit=10
```

Response includes `next_cursor` and `prev_cursor` for efficient navigation.

**MVP Decision**: Use offset pagination initially. Add cursor pagination when dataset exceeds 100k posts or when query performance degrades.

## 12. Performance Optimizations

### Database Indexes
- `posts.slug` (unique index)
- `posts.author_id` (index)
- `posts.status, posts.published_at` (composite index for list queries)
- `posts.deleted_at` (partial index for WHERE deleted_at IS NULL)
- `posts.title, posts.content` (GIN index for full-text search tsvector)
- `comments.post_id` (index)
- `comments.parent_comment_id` (index)
- `comments.depth` (index for filtering nested comments)
- `users.username` (unique index)
- `users.email` (unique index)
- `content_flags.flaggable_type, content_flags.flaggable_id` (composite index)
- `content_flags.status` (partial index for pending flags)

### Caching Strategy
- **Published posts**: Cache for 5 minutes (Redis), invalidate on update/delete
- **User profiles**: Cache for 10 minutes, invalidate on update
- **Comment trees**: Cache for 3 minutes per post, invalidate on new comment
- **Full-text search results**: Cache for 15 minutes (expensive queries)
- **ETag headers**: For conditional requests (304 Not Modified)
- **View counts**: Buffer in Redis, flush to database every 5 minutes (batch update)

### Response Optimization
- Don't include full `content` in list endpoints (use `excerpt` only)
- Support `fields` query parameter for partial responses: `/api/v1/posts?fields=id,title,author`
- Compress responses with gzip/brotli
- Return `can_edit` and `edit_expires_at` fields in comment responses (avoid client-side calculation)

### Full-Text Search Implementation
- **MVP approach**: Use PostgreSQL's built-in full-text search with tsvector
- **Indexing**: Create GIN index on `to_tsvector('english', title || ' ' || content)`
- **Query**: Use `ts_query` with ranking for relevance
- **Migration path**: If search becomes bottleneck (>1M posts), migrate to Elasticsearch
- **Search response time target**: <200ms for 95th percentile

## 13. Moderation System

### Auto-Moderation Rules
- Content with 3+ flags automatically hidden (sets `is_flagged=true`)
- Flagged content still accessible to author and moderators
- Email notification sent to moderators when content reaches flag threshold
- Suspended users cannot create posts/comments but can read content

### Moderator Actions
- Review individual flags (mark as reviewed/dismissed)
- Delete flagged posts/comments (soft delete)
- Suspend user accounts (sets `is_active=false`, revokes tokens)
- View moderation log (audit trail of all moderator actions)

### Flag Review Workflow
1. User flags content with reason
2. Flag count increments on content
3. After 3 flags, content hidden and moderator notified
4. Moderator reviews flag and content
5. Moderator dismisses flag OR deletes content/suspends user
6. Reporter receives notification of outcome (optional future feature)