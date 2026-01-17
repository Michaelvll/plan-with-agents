#!/usr/bin/env python3
"""
Generate diverse test examples to verify format enforcement works across
different types of design tasks and violation patterns.
"""

import sys

def validate_response_format(response: str, agent_name: str) -> tuple:
    """Validate that response starts with ## Design with no preamble."""
    stripped = response.lstrip()

    if not stripped.startswith('## Design'):
        lines = response.split('\n')
        design_line_num = None
        preamble_lines = []

        for i, line in enumerate(lines):
            if line.strip().startswith('## Design'):
                design_line_num = i
                break
            if line.strip():
                preamble_lines.append(f"  Line {i+1}: {line[:80]}")

        if design_line_num is not None:
            preamble = '\n'.join(preamble_lines[:5])
            return False, f"{agent_name} violated format requirements.\n\nForbidden preamble detected before '## Design' (found at line {design_line_num + 1}):\n{preamble}\n\nThe response will be automatically cleaned."
        else:
            return False, f"{agent_name} response missing '## Design' section header."

    return True, ""

def extract_design_section(response: str) -> str:
    """Extract just the design section, removing any preamble."""
    lines = response.split('\n')
    design_start = None

    for i, line in enumerate(lines):
        if line.strip().startswith('## Design'):
            design_start = i
            break

    if design_start is not None:
        return '\n'.join(lines[design_start:])

    return response

# Different design task categories
examples = [
    {
        "category": "Database Design",
        "task": "Design a database schema for an e-commerce platform",
        "good_response": """## Design

# E-commerce Database Schema

## Tables

### users
- id: UUID PRIMARY KEY
- email: VARCHAR(255) UNIQUE NOT NULL
- password_hash: VARCHAR(255) NOT NULL
- created_at: TIMESTAMP

### products
- id: UUID PRIMARY KEY
- name: VARCHAR(200) NOT NULL
- price: DECIMAL(10,2) NOT NULL
- stock: INTEGER NOT NULL
- category_id: UUID REFERENCES categories(id)

### orders
- id: UUID PRIMARY KEY
- user_id: UUID REFERENCES users(id)
- total: DECIMAL(10,2) NOT NULL
- status: VARCHAR(50) NOT NULL
- created_at: TIMESTAMP

## Rationale
Normalized design with proper foreign keys.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the schema structure.
""",
        "bad_response": """I've reviewed your requirements and will now present the schema.

## Design

# E-commerce Database Schema

## Tables

### users
- id: UUID PRIMARY KEY
- email: VARCHAR(255) UNIQUE NOT NULL
- password_hash: VARCHAR(255) NOT NULL

### products
- id: UUID PRIMARY KEY
- name: VARCHAR(200) NOT NULL
- price: DECIMAL(10,2) NOT NULL

## Rationale
Basic schema structure.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review this.
"""
    },
    {
        "category": "System Architecture",
        "task": "Design a microservices architecture for a streaming platform",
        "good_response": """## Design

# Streaming Platform Microservices Architecture

## Services

### Video Service
- Handles video upload, transcoding, storage
- Tech: Node.js, FFmpeg, S3

### User Service
- Authentication, profiles, preferences
- Tech: Go, PostgreSQL

### Recommendation Service
- ML-based video recommendations
- Tech: Python, TensorFlow, Redis

### Streaming Service
- CDN integration, adaptive bitrate
- Tech: NGINX, HLS protocol

## Communication
- Async: RabbitMQ for events
- Sync: gRPC for service-to-service

## Rationale
Separation of concerns, scalable architecture.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the service boundaries.
""",
        "bad_response": """Your previous architecture had some issues. Let me propose a better approach.

## Design

# Streaming Platform Architecture

## Services

### Video Service
- Upload and transcoding
- Node.js + FFmpeg

### User Service
- Auth and profiles
- Go + PostgreSQL

## Rationale
Simplified architecture.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review this.
"""
    },
    {
        "category": "API Design",
        "task": "Design a GraphQL API for social media posts",
        "good_response": """## Design

# Social Media GraphQL API

## Schema

```graphql
type User {
  id: ID!
  username: String!
  posts: [Post!]!
  followers: [User!]!
}

type Post {
  id: ID!
  content: String!
  author: User!
  likes: Int!
  comments: [Comment!]!
  createdAt: DateTime!
}

type Comment {
  id: ID!
  content: String!
  author: User!
  post: Post!
}
```

## Queries

```graphql
type Query {
  user(id: ID!): User
  post(id: ID!): Post
  feed(limit: Int = 20): [Post!]!
}
```

## Mutations

```graphql
type Mutation {
  createPost(content: String!): Post!
  likePost(postId: ID!): Post!
  addComment(postId: ID!, content: String!): Comment!
}
```

## Rationale
GraphQL allows flexible querying and reduces over-fetching.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the schema design.
""",
        "bad_response": """Okay, I'll design the GraphQL schema now.

## Design

# Social Media GraphQL API

## Schema

```graphql
type User {
  id: ID!
  username: String!
}

type Post {
  id: ID!
  content: String!
}
```

## Rationale
Basic schema.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review.
"""
    },
    {
        "category": "Security Design",
        "task": "Design an OAuth 2.0 authentication flow",
        "good_response": """## Design

# OAuth 2.0 Authentication Flow

## Flow: Authorization Code Grant

1. Client redirects user to authorization server
   - GET /authorize?response_type=code&client_id=...&redirect_uri=...&scope=...

2. User authenticates and grants permission

3. Authorization server redirects back with code
   - Redirect: callback?code=AUTH_CODE

4. Client exchanges code for tokens
   - POST /token
   - Body: grant_type=authorization_code&code=AUTH_CODE&client_id=...&client_secret=...

5. Server responds with tokens
   ```json
   {
     "access_token": "...",
     "refresh_token": "...",
     "expires_in": 3600
   }
   ```

6. Client uses access token for API requests
   - Header: Authorization: Bearer ACCESS_TOKEN

7. Refresh token when expired
   - POST /token
   - Body: grant_type=refresh_token&refresh_token=...

## Security Measures
- PKCE for mobile/SPA
- State parameter to prevent CSRF
- Short-lived access tokens (1 hour)
- Long-lived refresh tokens (30 days)
- Rotate refresh tokens on use

## Rationale
Authorization Code Grant is most secure for web apps.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the security measures.
""",
        "bad_response": """I see what you mean about security. Let me design a better flow.

## Design

# OAuth 2.0 Flow

## Steps
1. Redirect to auth server
2. Get authorization code
3. Exchange for token
4. Use token for API calls

## Rationale
Standard OAuth flow.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review.
"""
    }
]

print("="*70)
print("GENERATING TEST EXAMPLES ACROSS MULTIPLE DOMAINS")
print("="*70)
print()

total_examples = len(examples) * 2  # Each example has good and bad response
violations_detected = 0
violations_cleaned = 0
compliant_preserved = 0

for i, example in enumerate(examples, 1):
    print(f"\n{'='*70}")
    print(f"Example {i}: {example['category']}")
    print(f"Task: {example['task']}")
    print(f"{'='*70}")

    # Test good response
    print(f"\n  Testing compliant response...")
    is_valid, _ = validate_response_format(example['good_response'], "Agent")
    if is_valid:
        print(f"  ✓ Compliant response preserved")
        compliant_preserved += 1
    else:
        print(f"  ✗ ERROR: Good response flagged as invalid!")

    # Test bad response
    print(f"\n  Testing non-compliant response...")
    is_valid, error_msg = validate_response_format(example['bad_response'], "Agent")
    if not is_valid:
        print(f"  ✓ Violation detected")
        violations_detected += 1

        # Clean it
        cleaned = extract_design_section(example['bad_response'])
        is_clean, _ = validate_response_format(cleaned, "Agent")

        if is_clean:
            print(f"  ✓ Response cleaned successfully")
            violations_cleaned += 1
        else:
            print(f"  ✗ ERROR: Cleaning failed!")
    else:
        print(f"  ✗ ERROR: Bad response not detected!")

print(f"\n\n{'='*70}")
print("EXAMPLE GENERATION SUMMARY")
print(f"{'='*70}")
print()
print(f"Total examples tested:      {total_examples}")
print(f"Compliant preserved:        {compliant_preserved}/{len(examples)}")
print(f"Violations detected:        {violations_detected}/{len(examples)}")
print(f"Violations cleaned:         {violations_cleaned}/{len(examples)}")
print()

expected_compliant = len(examples)
expected_violations = len(examples)

if (compliant_preserved == expected_compliant and
    violations_detected == expected_violations and
    violations_cleaned == expected_violations):
    print("✓ ALL EXAMPLES PASSED!")
    print()
    print("Format enforcement verified across:")
    print("  • Database design tasks")
    print("  • System architecture tasks")
    print("  • API design tasks")
    print("  • Security design tasks")
    print()
    print("The system correctly handles diverse design domains.")
    sys.exit(0)
else:
    print("✗ SOME EXAMPLES FAILED")
    sys.exit(1)
