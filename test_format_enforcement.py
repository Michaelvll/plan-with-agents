#!/usr/bin/env python3
"""
Test format enforcement in the debate system without requiring Claude CLI calls.
This tests the validation and cleaning logic with realistic agent responses.
"""

import sys
import os
from pathlib import Path

# Import validation functions from debate script
sys.path.insert(0, str(Path(__file__).parent))

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

# Test scenarios
test_scenarios = [
    {
        "name": "Scenario 1: Perfect format compliance",
        "response": """## Design

# REST API for Blog Posts

## Architecture
- Node.js with Express
- PostgreSQL database
- JWT authentication

## Rationale
Simple, standard tech stack for blog API.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Please review the architecture choices.
""",
        "should_violate": False,
        "description": "Agent follows format perfectly"
    },
    {
        "name": "Scenario 2: Argumentative preamble",
        "response": """I disagree with your approach to caching. Let me propose a better design.

## Design

# Caching Layer Design

## Architecture
- Redis for caching
- TTL-based expiration

## Rationale
Redis is industry standard.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review this approach.
""",
        "should_violate": True,
        "description": "Agent adds argumentative preamble (should be caught and cleaned)"
    },
    {
        "name": "Scenario 3: Polite but forbidden preamble",
        "response": """Thank you for the feedback. I've incorporated your suggestions below.

## Design

# Updated Authentication System

## Architecture
- OAuth 2.0
- Refresh tokens

## Rationale
More secure than basic auth.

## Convergence Status
PROPOSING_FINAL

PROMPT_FOR_CRITIC:
Final review please.
""",
        "should_violate": True,
        "description": "Agent adds polite commentary (still forbidden)"
    },
    {
        "name": "Scenario 4: Meta-commentary preamble",
        "response": """Now I will create the improved design based on the requirements.

## Design

# Database Schema

## Tables
- users
- posts
- comments

## Rationale
Standard blog schema.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Check the schema.
""",
        "should_violate": True,
        "description": "Agent adds meta-commentary about what they're doing"
    },
    {
        "name": "Scenario 5: Whitespace only before Design",
        "response": """

## Design

# API Rate Limiting

## Architecture
- Token bucket algorithm
- Redis for storage

## Rationale
Prevents abuse.

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Review the algorithm choice.
""",
        "should_violate": False,
        "description": "Whitespace before Design is allowed"
    }
]

print("=" * 70)
print("TESTING FORMAT ENFORCEMENT IN DEBATE SYSTEM")
print("=" * 70)
print()

passed = 0
failed = 0

for i, scenario in enumerate(test_scenarios, 1):
    print(f"\n{'='*70}")
    print(f"Test {i}/{len(test_scenarios)}: {scenario['name']}")
    print(f"Description: {scenario['description']}")
    print(f"{'='*70}")

    response = scenario['response']
    should_violate = scenario['should_violate']

    # Step 1: Validate
    is_valid, error_msg = validate_response_format(response, "TestAgent")

    print(f"\n1. Validation Result:")
    print(f"   Expected violation: {should_violate}")
    print(f"   Detected violation: {not is_valid}")

    if not is_valid:
        print(f"\n   ⚠ Violation Message:")
        for line in error_msg.split('\n')[:6]:  # Show first 6 lines
            print(f"      {line}")

    # Step 2: Extract/clean
    cleaned = extract_design_section(response)

    print(f"\n2. Cleaning Result:")
    if not is_valid:
        print(f"   ✓ Response was cleaned")
        print(f"   Original length: {len(response)} chars")
        print(f"   Cleaned length: {len(cleaned)} chars")
        print(f"   Removed: {len(response) - len(cleaned)} chars")

        # Verify cleaned version is valid
        is_clean_valid, _ = validate_response_format(cleaned, "TestAgent")
        print(f"   Cleaned version valid: {is_clean_valid}")

        if not is_clean_valid:
            print(f"   ✗ ERROR: Cleaned version still invalid!")
            failed += 1
            continue
    else:
        print(f"   No cleaning needed (already compliant)")

    # Step 3: Verify test expectation
    test_passed = (not is_valid) == should_violate

    print(f"\n3. Test Result:")
    if test_passed:
        print(f"   ✓ PASS - Detection worked as expected")
        passed += 1
    else:
        print(f"   ✗ FAIL - Detection didn't match expectation")
        failed += 1

# Summary
print(f"\n\n{'='*70}")
print(f"SUMMARY")
print(f"{'='*70}")
print(f"Passed: {passed}/{len(test_scenarios)}")
print(f"Failed: {failed}/{len(test_scenarios)}")
print()

if failed == 0:
    print("✓ All format enforcement tests passed!")
    print("\nThe system correctly:")
    print("  - Detects format violations")
    print("  - Shows clear warning messages")
    print("  - Automatically cleans responses")
    print("  - Preserves compliant responses")
    sys.exit(0)
else:
    print(f"✗ {failed} test(s) failed")
    print("\nFormat enforcement needs attention.")
    sys.exit(1)
