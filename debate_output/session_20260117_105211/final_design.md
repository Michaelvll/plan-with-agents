# Final Agreed Design

**Task:** Design a user profile management API

**Status:** debating

---

## Design

### User Profile Management API - Complete Specification

#### Core Endpoints

**1. Profile Operations**

```
POST   /api/v1/profiles                 # Create new profile
GET    /api/v1/profiles/{userId}        # Get profile by ID
PUT    /api/v1/profiles/{userId}        # Full profile update
PATCH  /api/v1/profiles/{userId}        # Partial profile update
DELETE /api/v1/profiles/{userId}        # Delete profile (soft delete)
GET    /api/v1/profiles                 # List profiles (admin/search)
```

**2. Profile Picture Management**

```
POST   /api/v1/profiles/{userId}/avatar        # Upload avatar
DELETE /api/v1/profiles/{userId}/avatar        # Remove avatar
GET    /api/v1/profiles/{userId}/avatar        # Get avatar URL
```

**3. Privacy & Visibility**

```
PATCH  /api/v1/profiles/{userId}/privacy       # Update privacy settings
GET    /api/v1/profiles/{userId}/visibility    # Check what's publicly visible
```

#### Data Model

```typescript
interface UserProfile {
  userId: string;                    // Unique identifier (UUID)
  email: string;                     // Primary email (validated)
  username: string;                  // Unique username (3-30 chars)
  
  // Personal Information
  firstName: string;
  lastName: string;
  displayName?: string;              // Optional public name
  bio?: string;                      // Max 500 chars
  avatarUrl?: string;
  
  // Contact & Social
  phoneNumber?: string;
  location?: {
    city?: string;
    country?: string;
    timezone?: string;
  };
  socialLinks?: {
    twitter?: string;
    linkedin?: string;
    github?: string;
  };
  
  // Privacy Controls
  privacySettings: {
    profileVisibility: 'public' | 'private' | 'friends';
    showEmail: boolean;
    showPhoneNumber: boolean;
    showLocation: boolean;
  };
  
  // Metadata
  createdAt: string;                 // ISO 8601
  updatedAt: string;                 // ISO 8601
  lastLoginAt?: string;
  isVerified: boolean;               // Email verification status
  status: 'active' | 'suspended' | 'deleted';
  
  // Preferences
  preferences?: {
    language: string;                // ISO 639-1 code
    theme: 'light' | 'dark' | 'auto';
    notifications: {
      email: boolean;
      push: boolean;
    };
  };
}
```

#### Authentication & Authorization

- **Authentication**: Bearer token (JWT) in Authorization header
- **Authorization Rules**:
  - Users can read/update their own profiles
  - Public profiles readable by authenticated users
  - Admin role can access all profiles
  - Rate limiting: 100 requests/minute per user

#### Request/Response Examples

**Create Profile (POST /api/v1/profiles)**

```json
// Request
{
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "password": "securePassword123!",
  "privacySettings": {
    "profileVisibility": "public",
    "showEmail": false,
    "showPhoneNumber": false,
    "showLocation": true
  }
}

// Response (201 Created)
{
  "userId": "550e8400-e29b-41d4-a716-446655440000",
  "email": "user@example.com",
  "username": "johndoe",
  "firstName": "John",
  "lastName": "Doe",
  "privacySettings": { /* as set */ },
  "createdAt": "2024-01-15T10:30:00Z",
  "updatedAt": "2024-01-15T10:30:00Z",
  "isVerified": false,
  "status": "active"
}
```

**Update Profile (PATCH /api/v1/profiles/{userId})**

```json
// Request
{
  "bio": "Software engineer passionate about APIs",
  "location": {
    "city": "San Francisco",
    "country": "USA"
  }
}

// Response (200 OK)
{
  // Full updated profile object
}
```

#### Error Handling

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": [
      {
        "field": "email",
        "message": "Email format is invalid"
      }
    ],
    "timestamp": "2024-01-15T10:30:00Z",
    "requestId": "req_abc123"
  }
}
```

**Standard Error Codes**:
- `400` - Validation errors, malformed requests
- `401` - Unauthorized (missing/invalid token)
- `403` - Forbidden (insufficient permissions)
- `404` - Profile not found
- `409` - Conflict (duplicate email/username)
- `422` - Unprocessable entity (business logic violation)
- `429` - Rate limit exceeded
- `500` - Internal server error

#### Validation Rules

- **Email**: Valid format, unique, max 255 chars
- **Username**: 3-30 alphanumeric + underscore/dash, unique, case-insensitive
- **Password**: Min 8 chars, must include uppercase, lowercase, number, special char
- **Bio**: Max 500 characters
- **Phone**: Valid international format (E.164)
- **Avatar**: Max 5MB, formats: JPEG, PNG, WebP

#### Security Considerations

1. **Data Protection**:
   - Passwords hashed with bcrypt (cost factor 12)
   - PII encrypted at rest
   - HTTPS required for all endpoints

2. **Input Sanitization**:
   - SQL injection prevention via parameterized queries
   - XSS prevention: sanitize all text fields
   - CSRF tokens for state-changing operations

3. **Rate Limiting**:
   - Per-user: 100 req/min
   - Per-IP: 1000 req/hour
   - Avatar upload: 10/hour per user

4. **Audit Logging**:
   - Log all profile modifications
   - Track authentication attempts
   - Retain logs for 90 days

#### Performance Considerations

- **Caching Strategy**:
  - Public profiles cached for 5 minutes
  - Private profiles not cached
  - Avatar URLs cached with CDN (1 week TTL)

- **Database Indexes**:
  - Primary: userId
  - Unique: email, username
  - Composite: (status, createdAt) for listing

- **Pagination**:
  - Default page size: 20
  - Max page size: 100
  - Cursor-based for large result sets