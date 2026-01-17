#!/usr/bin/env python3
"""
Demonstrate that the format fixes work correctly.
This simulates what would happen with agent responses.
"""

import sys
from typing import Tuple

def validate_response_format(response: str, agent_name: str) -> Tuple[bool, str]:
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
    """Extract just the Design section, stripping any preamble."""
    design_start_patterns = ['## Design\n', '### Design\n', '## Design\r\n', '### Design\r\n']

    for pattern in design_start_patterns:
        if pattern in response:
            response = pattern + response.split(pattern, 1)[1]
            break

    lines = response.split('\n')
    design_lines = []
    in_design = False

    for line in lines:
        if line.strip().startswith('### Design') or line.strip().startswith('## Design'):
            in_design = True
            design_lines.append(line)
            continue
        if in_design and (line.strip().startswith('### ') or line.strip().startswith('## ')):
            meta_sections = ['Rationale', 'What I Changed', 'What I Kept', 'What I Incorporated',
                           'Open Questions', 'Convergence', 'Prompt for', 'Remaining',
                           'What I Improved', 'PROMPT_FOR']
            if any(meta in line for meta in meta_sections):
                break
            design_lines.append(line)
            continue
        if in_design:
            design_lines.append(line)

    design = '\n'.join(design_lines).strip()
    return design if design else response

# Simulate problematic responses (like the ones we found)
problematic_responses = [
    {
        "name": "E-Commerce Schema (from session_20260116_221850)",
        "response": """You've caught legitimate bugs in my implementation - I respect that. But your "fixes" introduce MORE complexity than necessary.

## Design

# E-Commerce Order Schema - ARCHITECT Response (Round 5)

## Core Schema Design

```sql
CREATE TABLE orders (
    order_id BIGSERIAL PRIMARY KEY,
    customer_id BIGINT NOT NULL,
    total DECIMAL(10, 2) NOT NULL
);
```

## Rationale

This design balances simplicity with scalability.
"""
    },
    {
        "name": "Calculator API (current task)",
        "response": """I appreciate your feedback on the previous iteration. Let me create an improved design.

## Design

# Simple Calculator API

## Architecture Overview

REST API with add and subtract operations.

## Rationale

Kept it simple and focused.
"""
    }
]

# Simulate good responses
good_responses = [
    {
        "name": "Clean Calculator API",
        "response": """## Design

# Simple Calculator API

## Architecture Overview

RESTful API exposing mathematical operations through HTTP endpoints.

## Technology Stack

- Runtime: Node.js 20+
- Language: TypeScript 5.x

## Rationale

This design prioritizes simplicity and clarity.
"""
    }
]

print("=" * 70)
print("DEMONSTRATION: Format Validation & Cleaning")
print("=" * 70)
print()

# Test problematic responses
print("📋 TESTING PROBLEMATIC RESPONSES (Before Fixes)")
print("-" * 70)

for test in problematic_responses:
    print(f"\n🔍 Testing: {test['name']}")
    print()

    # Validate
    is_valid, error_msg = validate_response_format(test['response'], "Agent A")

    if not is_valid:
        print(f"❌ VALIDATION: Format violation detected")
        print(f"   {error_msg.split(chr(10))[0]}")
        print()

    # Extract and clean
    cleaned = extract_design_section(test['response'])

    print(f"📄 CLEANED OUTPUT (first 200 chars):")
    print(f"   {cleaned[:200]}...")

    # Verify cleaning worked
    if cleaned.strip().startswith('## Design'):
        print(f"✅ RESULT: Preamble successfully removed")
    else:
        print(f"❌ RESULT: Cleaning failed")
    print()

print("\n" + "=" * 70)
print("📋 TESTING GOOD RESPONSES (Expected Format)")
print("-" * 70)

for test in good_responses:
    print(f"\n🔍 Testing: {test['name']}")
    print()

    # Validate
    is_valid, error_msg = validate_response_format(test['response'], "Agent A")

    if is_valid:
        print(f"✅ VALIDATION: Format is correct")
    else:
        print(f"❌ VALIDATION: Unexpected issue")
        print(f"   {error_msg}")

    # Extract
    cleaned = extract_design_section(test['response'])

    print(f"📄 OUTPUT (first 200 chars):")
    print(f"   {cleaned[:200]}...")
    print()

print("=" * 70)
print("SUMMARY")
print("=" * 70)
print()
print("✅ Format validation detects preambles correctly")
print("✅ Extraction removes preambles automatically")
print("✅ Good responses pass validation")
print("✅ System provides two layers of protection:")
print("   1. Validation warns users about violations")
print("   2. Extraction cleans output automatically")
print()
print("🎯 Result: Final designs will be clean even if agents violate format")
print()
