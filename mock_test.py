#!/usr/bin/env python3
"""
Mock test to validate the debate system logic without calling Claude CLI
"""

import sys
from debate import (
    validate_prompt,
    validate_config,
    validate_response_format,
    extract_design_section,
    parse_agent_response,
    check_convergence,
    AgentResponse,
    ConvergenceStatus
)

def test_validate_prompt():
    """Test prompt validation"""
    print("Testing prompt validation...")

    # Valid prompt
    result = validate_prompt("Design a REST API for user authentication")
    assert result.is_success, "Valid prompt should succeed"
    print("  ✓ Valid prompt accepted")

    # Too short
    result = validate_prompt("Design API")
    assert not result.is_success, "Short prompt should fail"
    print("  ✓ Short prompt rejected")

    # Empty
    result = validate_prompt("")
    assert not result.is_success, "Empty prompt should fail"
    print("  ✓ Empty prompt rejected")

    print()

def test_validate_config():
    """Test config validation"""
    print("Testing config validation...")

    # Valid config
    result = validate_config(max_rounds=8, timeout=300, working_dir=".", output_dir="./debate_output")
    assert result.is_success, "Valid config should succeed"
    print("  ✓ Valid config accepted")

    # Invalid rounds
    result = validate_config(max_rounds=0)
    assert not result.is_success, "Invalid rounds should fail"
    print("  ✓ Invalid rounds rejected")

    # Too many rounds
    result = validate_config(max_rounds=50)
    assert not result.is_success, "Too many rounds should fail"
    print("  ✓ Too many rounds rejected")

    print()

def test_response_format_validation():
    """Test response format validation"""
    print("Testing response format validation...")

    # Correct format - starts with ## Design
    correct_response = """## Design

# User Authentication API

This is a design document...

## Rationale
This design was chosen because...

## Convergence Status
ITERATING

PROMPT_FOR_CRITIC:
Please review the security aspects.
"""

    is_valid, error_msg = validate_response_format(correct_response, "Test Agent")
    assert is_valid, f"Correct format should be valid: {error_msg}"
    print("  ✓ Correct format accepted")

    # Incorrect format - has preamble
    incorrect_response = """I appreciate your feedback. Let me create an improved design.

## Design

# User Authentication API

This is a design document...
"""

    is_valid, error_msg = validate_response_format(incorrect_response, "Test Agent")
    assert not is_valid, "Format with preamble should be rejected"
    print("  ✓ Format with preamble rejected")
    print(f"     Error message: {error_msg[:100]}...")

    # Incorrect format - missing ## Design
    no_design_response = """Here is my analysis of the design..."""

    is_valid, error_msg = validate_response_format(no_design_response, "Test Agent")
    assert not is_valid, "Format without ## Design should be rejected"
    print("  ✓ Format without ## Design rejected")

    print()

def test_extract_design_section():
    """Test design section extraction"""
    print("Testing design section extraction...")

    # Response with preamble
    response_with_preamble = """Some preamble text here.

## Design

# Authentication API

## Endpoints
- POST /login
- POST /logout

## Rationale
Security is important...

PROMPT_FOR_CRITIC:
Please review.
"""

    design = extract_design_section(response_with_preamble)
    assert "## Design" in design, "Should contain Design header"
    assert "Some preamble" not in design, "Should not contain preamble"
    assert "## Endpoints" in design or "Endpoints" in design, "Should contain endpoints"
    assert "## Rationale" not in design, "Should not contain Rationale section"
    print("  ✓ Preamble correctly removed")
    print("  ✓ Meta sections correctly excluded")

    print()

def test_parse_agent_response():
    """Test agent response parsing"""
    print("Testing agent response parsing...")

    architect_response = """## Design

# User Auth API

Complete design here...

## Rationale
My reasoning...

## Convergence Status
PROPOSING_FINAL

PROMPT_FOR_CRITIC:
Please review the error handling.
"""

    parsed = parse_agent_response(architect_response, is_agent_a=True)
    assert parsed.convergence_signal == "PROPOSING_FINAL", "Should detect PROPOSING_FINAL"
    assert "Please review the error handling" in parsed.prompt_for_other, "Should extract prompt"
    assert "## Rationale" not in parsed.content, "Content should not include rationale"
    print("  ✓ Architect response parsed correctly")
    print(f"     Convergence signal: {parsed.convergence_signal}")
    print(f"     Prompt for other: {parsed.prompt_for_other[:50]}...")

    reviewer_response = """## Design

# Improved User Auth API

Enhanced design here...

## What I Improved
Added rate limiting...

## Convergence Status
ACCEPTING_FINAL

PROMPT_FOR_ARCHITECT:
The design looks good.
"""

    parsed = parse_agent_response(reviewer_response, is_agent_a=False)
    assert parsed.convergence_signal == "ACCEPTING_FINAL", "Should detect ACCEPTING_FINAL"
    print("  ✓ Reviewer response parsed correctly")
    print(f"     Convergence signal: {parsed.convergence_signal}")

    print()

def test_convergence_checking():
    """Test convergence detection"""
    print("Testing convergence detection...")

    # Both agree - consensus
    agent_a = AgentResponse(
        content="Design content",
        prompt_for_other="Review this",
        convergence_signal="PROPOSING_FINAL",
        raw_response="Full response"
    )
    agent_b = AgentResponse(
        content="Improved design",
        prompt_for_other="Looks good",
        convergence_signal="ACCEPTING_FINAL",
        raw_response="Full response"
    )

    status = check_convergence(agent_a, agent_b)
    assert status == ConvergenceStatus.CONSENSUS, "Should detect consensus"
    print("  ✓ Consensus correctly detected")

    # Architect proposes, reviewer challenges - converging
    agent_b.convergence_signal = "ITERATING"
    status = check_convergence(agent_a, agent_b)
    assert status == ConvergenceStatus.CONVERGING, "Should detect converging"
    print("  ✓ Converging state correctly detected")

    # Both still iterating - debating
    agent_a.convergence_signal = "ITERATING"
    status = check_convergence(agent_a, agent_b)
    assert status == ConvergenceStatus.DEBATING, "Should detect debating"
    print("  ✓ Debating state correctly detected")

    print()

def main():
    print("=" * 60)
    print("Mock Test Suite for Debate System")
    print("=" * 60)
    print()

    try:
        test_validate_prompt()
        test_validate_config()
        test_response_format_validation()
        test_extract_design_section()
        test_parse_agent_response()
        test_convergence_checking()

        print("=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        return 0

    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
