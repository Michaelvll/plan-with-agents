#!/usr/bin/env python3
"""Quick test to verify format validation works"""

from typing import Tuple

def validate_response_format(response: str, agent_name: str) -> Tuple[bool, str]:
    """Validate that response starts with ## Design with no preamble.

    Returns: (is_valid, error_message)
    """
    # Strip leading whitespace but preserve structure
    stripped = response.lstrip()

    # Check if it starts with ## Design
    if not stripped.startswith('## Design'):
        # Find where ## Design actually appears
        lines = response.split('\n')
        design_line_num = None
        preamble_lines = []

        for i, line in enumerate(lines):
            if line.strip().startswith('## Design'):
                design_line_num = i
                break
            if line.strip():  # Non-empty line
                preamble_lines.append(f"  Line {i+1}: {line[:80]}")

        if design_line_num is not None:
            preamble = '\n'.join(preamble_lines[:5])  # Show first 5 lines
            return False, f"{agent_name} violated format requirements.\n\nForbidden preamble detected before '## Design' (found at line {design_line_num + 1}):\n{preamble}\n\nThe response will be automatically cleaned."
        else:
            return False, f"{agent_name} response missing '## Design' section header."

    return True, ""

# Test cases
test_cases = [
    {
        "name": "Good format - starts with ## Design",
        "response": """## Design

# REST API for Todo List

## Architecture
...

## Rationale
...
""",
        "expected_valid": True
    },
    {
        "name": "Bad format - preamble before Design",
        "response": """I appreciate your feedback, but I think there are some issues with your approach.

## Design

# REST API for Todo List

## Architecture
...
""",
        "expected_valid": False
    },
    {
        "name": "Bad format - commentary before Design",
        "response": """Let me create an improved design based on your suggestions.

## Design

# REST API for Todo List
...
""",
        "expected_valid": False
    },
    {
        "name": "Good format - minimal whitespace before Design",
        "response": """

## Design

# REST API
...
""",
        "expected_valid": True
    },
    {
        "name": "Bad format - argumentative preamble",
        "response": """You've caught legitimate bugs in my implementation - I respect that. But your "fixes" introduce MORE complexity than necessary.

## Design

# Improved Implementation
...
""",
        "expected_valid": False
    }
]

print("=" * 60)
print("Testing Format Validation")
print("=" * 60)

passed = 0
failed = 0

for test in test_cases:
    is_valid, error_msg = validate_response_format(test["response"], "TestAgent")
    expected = test["expected_valid"]

    status = "✓ PASS" if is_valid == expected else "✗ FAIL"
    if is_valid == expected:
        passed += 1
    else:
        failed += 1

    print(f"\n{status}: {test['name']}")
    print(f"  Expected valid: {expected}, Got: {is_valid}")
    if error_msg and not is_valid:
        # Just show first line of error
        first_line = error_msg.split('\n')[0]
        print(f"  Error: {first_line}")

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)

if failed == 0:
    print("\n✓ All tests passed! Format validation is working correctly.")
else:
    print(f"\n✗ {failed} test(s) failed.")

import sys
sys.exit(0 if failed == 0 else 1)
