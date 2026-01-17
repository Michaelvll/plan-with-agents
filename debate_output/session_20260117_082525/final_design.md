# Final Agreed Design

**Task:** Design a simple REST API for user profiles

**Status:** debating

---

## Design

# User Profile REST API

## API Overview

A RESTful API service for managing user profiles with CRUD operations, built using Node.js/Express with PostgreSQL database.

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │ HTTP/JSON
┌──────▼──────────────┐
│  API Layer          │
│  (Express Router)   │
│  - Rate Limiting    │
│  - Request Validation│
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  Service Layer      │
│  (Business Logic)   │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  Data Access Layer  │
│  (Repository)       │
└──────┬──────────────┘
       │
┌──────▼──────────────┐
│  PostgreSQL DB      │
└─────────────────────┘
```

## Data Model

### User Profile Schema

```sql
CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    username VARCHAR(50) UNIQUE NOT NULL,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    bio TEXT,
    avatar_url VARCHAR(500),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_user_profiles_email ON user_profiles(email) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_profiles_username ON user_profiles(username) WHERE deleted_at IS NULL;
CREATE INDEX idx_user_profiles_deleted_at ON user_profiles(deleted_at);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_user_profiles_updated_at BEFORE UPDATE
    ON user_profiles FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

### TypeScript Interface

```typescript
interface UserProfile {
  id: string;
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  bio?: string;
  avatarUrl?: string;
  createdAt: Date;
  updatedAt: Date;
}

interface CreateUserProfileRequest {
  email: string;
  username: string;
  firstName: string;
  lastName: string;
  bio?: string;
  avatarUrl?: string;
}

interface UpdateUserProfileRequest {
  firstName?: string;
  lastName?: string;
  bio?: string;
  avatarUrl?: string;
}

interface ProfileListQuery {
  page?: number;
  limit?: number;
  sortBy?: 'createdAt' | 'username';
  sortOrder?: 'asc' | 'desc';
}
```

## API Endpoints

### 1. Create User Profile
```
POST /api/v1/profiles
Content-Type: application/json

Request Body:
{
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "bio": "Software developer",
  "avatarUrl": "https://example.com/avatar.jpg"
}

Response: 201 Created
Location: /api/v1/profiles/550e8400-e29b-41d4-a716-446655440000
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "bio": "Software developer",
  "avatarUrl": "https://example.com/avatar.jpg",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

### 2. Get User Profile by ID
```
GET /api/v1/profiles/:id

Response: 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "bio": "Software developer",
  "avatarUrl": "https://example.com/avatar.jpg",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

### 3. Get User Profile by Username
```
GET /api/v1/profiles/username/:username

Response: 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "bio": "Software developer",
  "avatarUrl": "https://example.com/avatar.jpg",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:00:00Z"
}
```

### 4. List User Profiles (Paginated)
```
GET /api/v1/profiles?page=1&limit=20&sortBy=createdAt&sortOrder=desc

Query Parameters:
- page: Page number (default: 1, min: 1)
- limit: Items per page (default: 20, min: 1, max: 100)
- sortBy: Sort field (default: createdAt, options: createdAt, username)
- sortOrder: Sort direction (default: desc, options: asc, desc)

Response: 200 OK
{
  "data": [...],
  "pagination": {
    "page": 1,
    "limit": 20,
    "total": 100,
    "totalPages": 5,
    "hasNextPage": true,
    "hasPreviousPage": false
  }
}
```

### 5. Update User Profile
```
PATCH /api/v1/profiles/:id
Content-Type: application/json

Request Body:
{
  "firstName": "Jane",
  "bio": "Senior software developer"
}

Response: 200 OK
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "Jane",
  "lastName": "Doe",
  "bio": "Senior software developer",
  "avatarUrl": "https://example.com/avatar.jpg",
  "createdAt": "2026-01-17T10:00:00Z",
  "updatedAt": "2026-01-17T10:30:00Z"
}
```

### 6. Delete User Profile (Soft Delete)
```
DELETE /api/v1/profiles/:id

Response: 204 No Content
```

**Note**: Profiles are soft-deleted (marked with `deleted_at` timestamp). Soft-deleted profiles remain in the database but are excluded from all queries. Hard deletion is not provided to maintain simplicity and data integrity.

## Error Handling

### Error Response Format
```typescript
interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, string>;
    timestamp: string;
    path: string;
  }
}
```

### HTTP Status Codes
- **200 OK**: Successful GET, PATCH requests
- **201 Created**: Successful POST requests
- **204 No Content**: Successful DELETE requests
- **400 Bad Request**: Invalid input data or malformed request
- **404 Not Found**: Resource not found
- **409 Conflict**: Duplicate email/username
- **422 Unprocessable Entity**: Valid syntax but semantically incorrect data
- **429 Too Many Requests**: Rate limit exceeded
- **500 Internal Server Error**: Server errors
- **503 Service Unavailable**: Database connection issues

### Example Error Responses

**Validation Error (400)**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request data",
    "details": {
      "email": "Invalid email format",
      "username": "Username must be 3-50 characters and contain only letters, numbers, and underscores"
    },
    "timestamp": "2026-01-17T10:00:00Z",
    "path": "/api/v1/profiles"
  }
}
```

**Not Found (404)**
```json
{
  "error": {
    "code": "PROFILE_NOT_FOUND",
    "message": "User profile not found",
    "timestamp": "2026-01-17T10:00:00Z",
    "path": "/api/v1/profiles/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Conflict (409)**
```json
{
  "error": {
    "code": "DUPLICATE_EMAIL",
    "message": "A user with this email already exists",
    "timestamp": "2026-01-17T10:00:00Z",
    "path": "/api/v1/profiles"
  }
}
```

**Rate Limit (429)**
```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Too many requests, please try again later",
    "timestamp": "2026-01-17T10:00:00Z",
    "path": "/api/v1/profiles"
  }
}
```

## Validation Rules

### Input Validation
- **email**: Valid email format per RFC 5322, max 255 characters, case-insensitive stored as lowercase
- **username**: 3-50 characters, alphanumeric and underscores only, case-insensitive, no leading/trailing whitespace
- **firstName**: 1-100 characters, required, trimmed
- **lastName**: 1-100 characters, required, trimmed
- **bio**: Max 1000 characters, optional, trimmed
- **avatarUrl**: Valid HTTPS URL format, max 500 characters, optional

### Sanitization
- All string inputs are trimmed
- Email is converted to lowercase before storage
- Username is converted to lowercase before storage
- HTML/script tags are stripped from bio field to prevent XSS

### Business Rules
- Email and username are immutable after creation for simplicity
- Soft-deleted profiles prevent reuse of email/username
- Attempting to create a profile with email/username of soft-deleted profile returns 409 Conflict

## Security & Rate Limiting

### Rate Limiting (Application Level via express-rate-limit)

Rate limiting is implemented at the application level for simplicity and portability. For production at scale, this can be moved to infrastructure (API Gateway, Nginx) without changing the API contract.

```typescript
// Middleware configuration
import rateLimit from 'express-rate-limit';

const createProfileLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 5,
  standardHeaders: true,
  legacyHeaders: false,
});

const readLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
});

const updateLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 10,
  standardHeaders: true,
  legacyHeaders: false,
});

const deleteLimiter = rateLimit({
  windowMs: 60 * 1000,
  max: 5,
  standardHeaders: true,
  legacyHeaders: false,
});
```

**Rate Limits by Endpoint:**
```
POST /api/v1/profiles: 5 requests per minute per IP
GET endpoints: 100 requests per minute per IP
PATCH /api/v1/profiles/:id: 10 requests per minute per IP
DELETE /api/v1/profiles/:id: 5 requests per minute per IP
```

**Standard headers included in responses:**
```
RateLimit-Limit: 100
RateLimit-Remaining: 95
RateLimit-Reset: 1642420800
```

### Security Headers
```typescript
// Helmet middleware configuration
import helmet from 'helmet';

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
  },
}));
```

Applied headers:
- X-Content-Type-Options: nosniff
- X-Frame-Options: DENY
- Strict-Transport-Security: max-age=31536000; includeSubDomains
- Content-Security-Policy: default-src 'self'

### Input Security
- Request body size limit: 10KB for profile endpoints
- SQL injection prevented via parameterized queries (pg library)
- XSS prevention via input sanitization
- CORS configured to allow only specific origins (environment-based)

## Implementation Code Structure

```
src/
├── controllers/
│   └── profileController.ts    # Request/response handling, HTTP status codes
├── services/
│   └── profileService.ts        # Business logic, validation, sanitization
├── repositories/
│   └── profileRepository.ts     # Database operations, query building
├── models/
│   └── profile.ts               # TypeScript interfaces and types
├── middleware/
│   ├── validation.ts            # Request validation schemas (Zod)
│   ├── rateLimiter.ts           # Rate limiting configuration
│   └── errorHandler.ts          # Global error handler
├── routes/
│   └── profileRoutes.ts         # Route definitions
├── utils/
│   ├── errors.ts                # Custom error classes
│   └── sanitizer.ts             # Input sanitization utilities
└── config/
    ├── database.ts              # DB connection config
    └── rateLimit.ts             # Rate limit config
```

### Key Implementation Snippets

**Service Layer (profileService.ts)**
```typescript
export class ProfileService {
  constructor(private repository: ProfileRepository) {}

  async createProfile(data: CreateUserProfileRequest): Promise<UserProfile> {
    // Sanitize and normalize inputs
    const sanitized = {
      email: data.email.toLowerCase().trim(),
      username: data.username.toLowerCase().trim(),
      firstName: data.firstName.trim(),
      lastName: data.lastName.trim(),
      bio: data.bio ? sanitizeHtml(data.bio.trim()) : undefined,
      avatarUrl: data.avatarUrl?.trim(),
    };

    // Validate
    const validation = createProfileSchema.safeParse(sanitized);
    if (!validation.success) {
      throw new ValidationError(validation.error);
    }

    // Check for existing email/username (including soft-deleted)
    const existing = await this.repository.findByEmailOrUsername(
      sanitized.email,
      sanitized.username,
      { includeSoftDeleted: true }
    );
    
    if (existing) {
      if (existing.email === sanitized.email) {
        throw new ConflictError('DUPLICATE_EMAIL', 'Email already in use');
      }
      throw new ConflictError('DUPLICATE_USERNAME', 'Username already in use');
    }

    return this.repository.create(sanitized);
  }

  async updateProfile(
    id: string,
    data: UpdateUserProfileRequest
  ): Promise<UserProfile> {
    // Sanitize inputs
    const sanitized: Partial<UpdateUserProfileRequest> = {};
    if (data.firstName) sanitized.firstName = data.firstName.trim();
    if (data.lastName) sanitized.lastName = data.lastName.trim();
    if (data.bio) sanitized.bio = sanitizeHtml(data.bio.trim());
    if (data.avatarUrl) sanitized.avatarUrl = data.avatarUrl.trim();

    // Validate
    const validation = updateProfileSchema.safeParse(sanitized);
    if (!validation.success) {
      throw new ValidationError(validation.error);
    }

    const profile = await this.repository.update(id, sanitized);
    if (!profile) {
      throw new NotFoundError('PROFILE_NOT_FOUND', 'User profile not found');
    }

    return profile;
  }
}
```

**Repository Layer (profileRepository.ts)**
```typescript
export class ProfileRepository {
  constructor(private db: Pool) {}

  async findById(id: string): Promise<UserProfile | null> {
    const result = await this.db.query(
      `SELECT id, email, username, first_name as "firstName", 
              last_name as "lastName", bio, avatar_url as "avatarUrl",
              created_at as "createdAt", updated_at as "updatedAt"
       FROM user_profiles 
       WHERE id = $1 AND deleted_at IS NULL`,
      [id]
    );
    return result.rows[0] || null;
  }

  async findByEmailOrUsername(
    email: string,
    username: string,
    options: { includeSoftDeleted?: boolean } = {}
  ): Promise<UserProfile | null> {
    const deletedClause = options.includeSoftDeleted 
      ? '' 
      : 'AND deleted_at IS NULL';
    
    const result = await this.db.query(
      `SELECT id, email, username, first_name as "firstName",
              last_name as "lastName", bio, avatar_url as "avatarUrl",
              created_at as "createdAt", updated_at as "updatedAt"
       FROM user_profiles 
       WHERE (email = $1 OR username = $2) ${deletedClause}
       LIMIT 1`,
      [email, username]
    );
    return result.rows[0] || null;
  }

  async softDelete(id: string): Promise<boolean> {
    const result = await this.db.query(
      `UPDATE user_profiles 
       SET deleted_at = CURRENT_TIMESTAMP 
       WHERE id = $1 AND deleted_at IS NULL`,
      [id]
    );
    return result.rowCount > 0;
  }
}
```

## Database Considerations

### Connection Pooling
```typescript
import { Pool } from 'pg';

export const pool = new Pool({
  host: process.env.DB_HOST,
  port: parseInt(process.env.DB_PORT || '5432'),
  database: process.env.DB_NAME,
  user: process.env.DB_USER,
  password: process.env.DB_PASSWORD,
  max: 20,                    // Maximum pool size
  idleTimeoutMillis: 30000,   // Close idle clients after 30s
  connectionTimeoutMillis: 2000,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
});
```

### Query Performance
- All queries use parameterized statements (SQL injection prevention + prepared statement caching)
- Partial indexes on email/username exclude soft-deleted records for optimal query performance
- Connection pool reuse minimizes connection overhead
- Query timeout set to 5000ms to prevent long-running queries