#!/usr/bin/env python3
"""Quick test to verify format validation works"""

import sys
import os

# Get the directory of this script
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import the validation function from debate
import importlib.util
debate_path = os.path.join(script_dir, "debate")
spec = importlib.util.spec_from_file_location("debate", debate_path)
if spec is None or spec.loader is None:
    print(f"Error: Could not load debate from {debate_path}")
    sys.exit(1)
debate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(debate)

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
    }
]

print("=" * 60)
print("Testing Format Validation")
print("=" * 60)

passed = 0
failed = 0

for test in test_cases:
    is_valid, error_msg = debate.validate_response_format(test["response"], "TestAgent")
    expected = test["expected_valid"]

    status = "✓ PASS" if is_valid == expected else "✗ FAIL"
    if is_valid == expected:
        passed += 1
    else:
        failed += 1

    print(f"\n{status}: {test['name']}")
    print(f"  Expected valid: {expected}, Got: {is_valid}")
    if error_msg:
        print(f"  Error: {error_msg[:100]}...")

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 60)

sys.exit(0 if failed == 0 else 1)
