# Authentication System - API Documentation

## Overview

This is a complete authentication system implementation supporting user registration, login, logout, and session management.

## Features

- ✓ User registration with password validation
- ✓ Secure login with session tokens
- ✓ Session management and validation
- ✓ Logout functionality
- ✓ Multiple concurrent sessions per user
- ✓ Logout all sessions capability
- ✓ Account deactivation support
- ✓ Comprehensive error handling
- ✓ Security best practices (password hashing, token generation)

## API Endpoints

### 1. Register User

**Endpoint:** `POST /auth/register`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123",
  "confirmPassword": "SecurePassword123"
}
```

**Response (201):**
```json
{
  "message": "User registered successfully",
  "user": {
    "id": "user-001",
    "email": "user@example.com"
  }
}
```

**Errors:**
- `400 Bad Request` - Missing fields, passwords don't match, password too short, user already exists
- `500 Internal Server Error` - Server error

---

### 2. Login

**Endpoint:** `POST /auth/login`

**Request:**
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123"
}
```

**Response (200):**
```json
{
  "sessionId": "abc123def456",
  "token": "user-001-1704067200000-a1b2c3d4e5f6g7h8i9",
  "user": {
    "id": "user-001",
    "email": "user@example.com"
  },
  "expiresAt": "2024-01-01T00:00:00Z"
}
```

**Errors:**
- `400 Bad Request` - Missing email or password, invalid email format
- `401 Unauthorized` - Invalid credentials, user account disabled
- `500 Internal Server Error` - Server error

**Notes:**
- Token is valid for 24 hours
- Token can be used in `Authorization: Bearer {token}` header
- Session ID should be stored for logout operation

---

### 3. Logout

**Endpoint:** `POST /auth/logout`

**Headers:**
```
X-Session-Id: abc123def456
```

**Response (200):**
```json
{
  "success": true,
  "message": "Successfully logged out"
}
```

**Errors:**
- `400 Bad Request` - Missing session ID
- `404 Not Found` - Session not found
- `500 Internal Server Error` - Server error

---

### 4. Validate Token

**Endpoint:** `POST /auth/validate`

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200):**
```json
{
  "valid": true,
  "userId": "user-001"
}
```

**Errors:**
- `400 Bad Request` - Token missing
- `401 Unauthorized` - Token invalid or expired
- `500 Internal Server Error` - Server error

---

### 5. Get Profile (Protected)

**Endpoint:** `GET /auth/profile`

**Headers:**
```
Authorization: Bearer {token}
```

**Response (200):**
```json
{
  "id": "user-001",
  "email": "user@example.com",
  "createdAt": "2024-01-01T00:00:00Z"
}
```

**Errors:**
- `401 Unauthorized` - Missing or invalid token
- `404 Not Found` - User not found
- `500 Internal Server Error` - Server error

---

## Authentication Flow

### Login Flow

1. Client sends email and password to `/auth/login`
2. Server validates credentials
3. Server generates secure session token
4. Server stores session in repository
5. Server returns token and session ID
6. Client stores token (typically in HTTP-only cookie)

### Protected Request Flow

1. Client includes token in `Authorization: Bearer {token}` header
2. Middleware validates token with session repository
3. If valid and not expired, request proceeds
4. If invalid or expired, server returns 401 Unauthorized

### Logout Flow

1. Client sends logout request with session ID
2. Server finds and deletes session from repository
3. Token becomes invalid immediately

---

## Security Features

### Password Security
- Passwords are hashed using bcrypt (production) or SHA256 (demo)
- Raw passwords are never stored
- Comparison uses constant-time to prevent timing attacks

### Token Generation
- Cryptographically secure random tokens
- Format: `{userId}-{timestamp}-{random}`
- 24-hour expiration
- Server-side storage prevents token forgery

### Session Management
- Server validates every token request
- Expired sessions are automatically deleted
- Supports multiple concurrent sessions
- IP address and user agent tracked for audit

### Error Handling
- Generic authentication error messages prevent user enumeration
- Validation errors provide helpful feedback
- All errors are properly typed and logged

---

## Usage Examples

### Example 1: Complete Login/Logout Cycle

```bash
# Register new user
curl -X POST http://localhost:3000/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123",
    "confirmPassword": "SecurePass123"
  }'

# Login
curl -X POST http://localhost:3000/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "john@example.com",
    "password": "SecurePass123"
  }'

# Save token and sessionId from response

# Validate token
curl -X POST http://localhost:3000/auth/validate \
  -H "Authorization: Bearer {token}"

# Access protected resource
curl -X GET http://localhost:3000/auth/profile \
  -H "Authorization: Bearer {token}"

# Logout
curl -X POST http://localhost:3000/auth/logout \
  -H "X-Session-Id: {sessionId}"
```

### Example 2: Multiple Device Sessions

```javascript
// Device 1 - Desktop
const desktop = await fetch('/auth/login', { /* ... */ });
const desktopToken = desktop.token;

// Device 2 - Mobile
const mobile = await fetch('/auth/login', { /* ... */ });
const mobileToken = mobile.token;

// Both tokens are valid simultaneously
// Logout from one doesn't affect the other

// Logout from all devices
await fetch('/auth/logout-all', {
  headers: { 'Authorization': `Bearer ${desktopToken}` }
});
```

---

## Data Models

### User
```typescript
{
  id: string;
  email: string;
  passwordHash: string;
  createdAt: Date;
  updatedAt: Date;
  isActive: boolean;
}
```

### Session
```typescript
{
  id: string;
  userId: string;
  token: string;
  expiresAt: Date;
  createdAt: Date;
  ipAddress: string;
  userAgent: string;
}
```

---

## Error Codes Reference

| Code | Error Type | Meaning |
|------|-----------|---------|
| 400 | ValidationError | Missing or invalid input |
| 401 | AuthenticationError | Invalid credentials or expired token |
| 404 | NotFoundError | Resource (user/session) not found |
| 500 | InternalError | Server-side error |

---

## Testing

The system includes 10 comprehensive unit tests:

```bash
node test-runner.js
```

**Test Coverage:**
- ✓ Successful login
- ✓ Invalid email handling
- ✓ Wrong password handling
- ✓ Missing credentials validation
- ✓ Successful logout
- ✓ Invalid session logout
- ✓ Session validation
- ✓ Invalid token handling
- ✓ Disabled user login prevention
- ✓ Logout all sessions

All tests pass with 100% success rate.

---

## Configuration

### Environment Variables

```env
NODE_ENV=development|production
PORT=3000
SESSION_TIMEOUT_HOURS=24
PASSWORD_MIN_LENGTH=8
```

### Session Configuration

Current defaults:
- Session timeout: 24 hours
- Token format: `{userId}-{timestamp}-{random}`
- Concurrent sessions: Unlimited (per user)

---

## Performance Considerations

- **Repository**: In-memory (suitable for small-scale). For production, use database.
- **Token validation**: O(1) using token index
- **Session cleanup**: Expired sessions deleted on validation
- **Scalability**: Needs Redis or cache layer for distributed systems

---

## Future Enhancements

1. Rate limiting on login attempts (prevent brute force)
2. Password reset functionality
3. Email verification for new accounts
4. Two-factor authentication (2FA)
5. Refresh tokens for long-lived sessions
6. OAuth2/OpenID Connect integration
7. Device management interface
8. Login history and audit logs
9. JWT-based stateless tokens
10. CORS and CSRF protection

---

## Support

For issues, feature requests, or questions, please contact the development team.
