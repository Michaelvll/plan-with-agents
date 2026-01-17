#!/usr/bin/env python3
"""
End-to-end test demonstrating the debate system with format enforcement.
This simulates a debate without requiring actual Claude CLI calls.
"""

import sys
from pathlib import Path

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

def simulate_debate_round(agent_name: str, response: str) -> tuple:
    """Simulate processing one agent's response."""
    print(f"\n{'='*70}")
    print(f"🤖 {agent_name} responding...")
    print(f"{'='*70}")

    # Validate
    is_valid, error_msg = validate_response_format(response, agent_name)

    if not is_valid:
        print(f"\n⚠️  FORMAT VIOLATION DETECTED:")
        print(f"{error_msg}")
        print()

        # Clean
        cleaned = extract_design_section(response)
        print(f"✓ Response automatically cleaned")
        print(f"  Removed {len(response) - len(cleaned)} characters of preamble")

        # Verify cleaned version
        is_clean_valid, _ = validate_response_format(cleaned, agent_name)
        if is_clean_valid:
            print(f"  ✓ Cleaned response is now compliant")
        else:
            print(f"  ✗ ERROR: Cleaned response still invalid!")
            return False, cleaned

        return True, cleaned
    else:
        print(f"✓ Response format is compliant")
        return True, response

# Simulated debate scenario
print("="*70)
print("END-TO-END DEBATE SIMULATION WITH FORMAT ENFORCEMENT")
print("="*70)
print("\nTask: Design a REST API for a blog with posts and comments")
print()

# Round 1: Agent A (Architect) - VIOLATES format with preamble
agent_a_round1 = """I'll create a comprehensive design for the blog API.

## Design

# Blog API with Posts and Comments

## Architecture
- RESTful API using Express.js
- PostgreSQL database
- JWT authentication

## Endpoints

### Posts
- GET /api/posts - List all posts
- POST /api/posts - Create post
- GET /api/posts/:id - Get single post
- PUT /api/posts/:id - Update post
- DELETE /api/posts/:id - Delete post

### Comments
- GET /api/posts/:id/comments - List comments for post
- POST /api/posts/:id/comments - Create comment
- DELETE /api/comments/:id - Delete comment

## Rationale
Standard REST design following HTTP conventions.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Please review the endpoint structure and suggest improvements.
"""

success, cleaned_a1 = simulate_debate_round("Agent A (Architect)", agent_a_round1)
if not success:
    print("\n✗ TEST FAILED: Agent A round 1 cleaning failed")
    sys.exit(1)

# Round 1: Agent B (Reviewer) - Compliant format
agent_b_round1 = """## Design

# Enhanced Blog API with Posts and Comments

## Architecture
- RESTful API using Express.js
- PostgreSQL with connection pooling
- JWT authentication with refresh tokens
- Rate limiting middleware

## Endpoints

### Posts
- GET /api/posts?page=1&limit=20 - Paginated post list
- POST /api/posts - Create post (auth required)
- GET /api/posts/:id - Get single post with comments
- PUT /api/posts/:id - Update post (auth required)
- DELETE /api/posts/:id - Soft delete post (auth required)

### Comments
- GET /api/posts/:id/comments?page=1&limit=50 - Paginated comments
- POST /api/posts/:id/comments - Create comment (auth required)
- PUT /api/comments/:id - Update comment (auth required)
- DELETE /api/comments/:id - Soft delete comment (auth required)

## Improvements Over Previous
- Added pagination for scalability
- Soft deletes to preserve data
- Rate limiting to prevent abuse
- Refresh tokens for security

## Rationale
These enhancements address production requirements.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the pagination and soft delete approach.
"""

success, cleaned_b1 = simulate_debate_round("Agent B (Reviewer)", agent_b_round1)
if not success:
    print("\n✗ TEST FAILED: Agent B round 1 cleaning failed")
    sys.exit(1)

# Round 2: Agent A improves - VIOLATES with "Thank you" preamble
agent_a_round2 = """Thank you for the suggestions on pagination and soft deletes.

## Design

# Blog API with Enhanced Features

## Architecture
- RESTful API using Express.js
- PostgreSQL with connection pooling
- JWT with refresh tokens
- Rate limiting (100 req/min per user)
- Redis for caching

## Endpoints

### Posts
- GET /api/posts?page=1&limit=20&sort=created_at&order=desc
- POST /api/posts - Create with validation
- GET /api/posts/:id - Cached response
- PUT /api/posts/:id - Invalidate cache on update
- DELETE /api/posts/:id - Soft delete with cascade

### Comments
- GET /api/posts/:id/comments?page=1&limit=50
- POST /api/posts/:id/comments - Spam detection
- PUT /api/comments/:id - Edit tracking
- DELETE /api/comments/:id - Soft delete

## What I Added
- Sorting options for posts
- Redis caching layer
- Spam detection for comments
- Edit tracking

## Rationale
Caching improves read performance. Spam detection protects quality.

## Convergence Status
PROPOSING_FINAL

PROMPT_FOR_CRITIC:
Final review - is this production ready?
"""

success, cleaned_a2 = simulate_debate_round("Agent A (Architect)", agent_a_round2)
if not success:
    print("\n✗ TEST FAILED: Agent A round 2 cleaning failed")
    sys.exit(1)

# Summary
print("\n" + "="*70)
print("SIMULATION COMPLETE")
print("="*70)
print()
print("Summary:")
print("  • 3 rounds simulated")
print("  • 2 format violations detected (Agent A rounds 1 & 2)")
print("  • 2 responses automatically cleaned")
print("  • 1 response was compliant (Agent B round 1)")
print()
print("✓ Format enforcement system working correctly!")
print()
print("Key behaviors demonstrated:")
print("  1. Detection - Violations are identified immediately")
print("  2. Warning - Clear messages explain the problem")
print("  3. Cleaning - Preambles are automatically removed")
print("  4. Preservation - Compliant responses pass through unchanged")
print()
print("✓ ALL TESTS PASSED")
sys.exit(0)
