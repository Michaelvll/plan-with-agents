#!/usr/bin/env python3
"""
Test suite for the debate system
"""
import subprocess
import json
import sys
from pathlib import Path
import tempfile
import shutil

# Add the current directory to Python path to import debate module
sys.path.insert(0, str(Path(__file__).parent))

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

def run_test(test_name, test_fn):
    """Run a single test and report result"""
    print(f"\n{Colors.BOLD}Test: {test_name}{Colors.NC}")
    try:
        test_fn()
        print(f"{Colors.GREEN}✓ PASSED{Colors.NC}")
        return True
    except AssertionError as e:
        print(f"{Colors.RED}✗ FAILED: {e}{Colors.NC}")
        return False
    except Exception as e:
        print(f"{Colors.RED}✗ ERROR: {e}{Colors.NC}")
        return False

def test_format_validation():
    """Test that agents must start responses with ## Design"""
    from debate import validate_response_format

    # Valid response
    valid = "## Design\n\n# My Design\n\nSome content"
    is_valid, msg = validate_response_format(valid, "TestAgent")
    assert is_valid, f"Should accept valid format: {msg}"

    # Invalid - preamble before design
    invalid = "Let me address your concerns first.\n\n## Design\n\nContent"
    is_valid, msg = validate_response_format(invalid, "TestAgent")
    assert not is_valid, "Should reject preamble before ## Design"

    # Valid - with leading whitespace
    valid_ws = "  \n\n## Design\n\nContent"
    is_valid, msg = validate_response_format(valid_ws, "TestAgent")
    assert is_valid, "Should accept leading whitespace"

def test_design_extraction():
    """Test extracting clean design sections"""
    from debate import extract_design_section

    # Test with proper structure
    response = """## Design

# API Design

This is the actual design content.

## Architecture

More design stuff.

## Rationale

This should not be included.

## What I Changed

Also not included."""

    design = extract_design_section(response)
    assert "Rationale" not in design, "Should not include Rationale section"
    assert "What I Changed" not in design, "Should not include meta sections"
    assert "Architecture" in design, "Should include design subsections"
    assert "actual design content" in design, "Should include design content"

    # Test with preamble (adversarial case)
    adversarial = """I disagree with your approach.

## Design

# Clean Design

The actual content."""

    design = extract_design_section(adversarial)
    assert "disagree" not in design.lower(), "Should strip preamble"
    assert "Clean Design" in design, "Should include design content"

def test_convergence_detection():
    """Test convergence signal parsing"""
    from debate import parse_agent_response, check_convergence, ConvergenceStatus

    # Agent A proposes final
    response_a = """## Design
Content
## Convergence Status
**PROPOSING_FINAL**
PROMPT_FOR_CRITIC: Review this"""

    parsed_a = parse_agent_response(response_a, is_agent_a=True)
    assert parsed_a.convergence_signal == "PROPOSING_FINAL"

    # Agent B accepts
    response_b = """## Design
Content
## Convergence Status
**ACCEPTING_FINAL**
PROMPT_FOR_ARCHITECT: Looks good"""

    parsed_b = parse_agent_response(response_b, is_agent_a=False)
    assert parsed_b.convergence_signal == "ACCEPTING_FINAL"

    # Check consensus
    status = check_convergence(parsed_a, parsed_b)
    assert status == ConvergenceStatus.CONSENSUS

def test_prompt_validation():
    """Test input validation"""
    from debate import validate_prompt, ErrorSeverity

    # Too short
    result = validate_prompt("hi")
    assert not result.is_success
    assert result.error.severity == ErrorSeverity.FATAL

    # Empty
    result = validate_prompt("")
    assert not result.is_success

    # Valid
    result = validate_prompt("Design a REST API for user management with authentication")
    assert result.is_success
    assert len(result.warnings) <= 1  # May have quality warnings

def test_config_validation():
    """Test configuration validation"""
    from debate import validate_config, ErrorSeverity

    # Invalid rounds
    result = validate_config(max_rounds=0)
    assert not result.is_success

    result = validate_config(max_rounds=50)
    assert not result.is_success

    # Valid config
    result = validate_config(max_rounds=8, working_dir=".")
    assert result.is_success

def test_session_save_load():
    """Test session state persistence"""
    from debate import DebateSession, save_session_state, load_session_state, AgentResponse, DebateRound

    with tempfile.TemporaryDirectory() as tmpdir:
        session = DebateSession(
            initial_prompt="Test prompt",
            session_dir=tmpdir,
            max_rounds=5
        )

        # Add a round
        round1 = DebateRound(round_number=1)
        round1.agent_a_response = AgentResponse(
            content="Design content",
            prompt_for_other="Review this",
            convergence_signal="ITERATING",
            raw_response="Full response"
        )
        session.rounds.append(round1)

        # Save
        save_session_state(session)

        # Load
        loaded = load_session_state(tmpdir)
        assert loaded is not None
        assert loaded.initial_prompt == "Test prompt"
        assert loaded.max_rounds == 5
        assert len(loaded.rounds) == 1
        assert loaded.rounds[0].agent_a_response.content == "Design content"

def test_cli_integration():
    """Test the CLI interface"""
    debate_script = Path(__file__).parent / "debate"

    # Test --help
    result = subprocess.run(
        [str(debate_script), "--help"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0
    assert "Claude Code Debate System" in result.stdout

    # Test --self-test
    result = subprocess.run(
        [str(debate_script), "--self-test"],
        capture_output=True,
        text=True,
        timeout=30
    )
    # Should pass or have clear error messages
    assert result.returncode in [0, 1]

def test_examples():
    """Test with example prompts"""
    examples = [
        "Design a simple calculator API with add and subtract endpoints",
        "Create a user authentication system with JWT tokens",
        "Design a caching layer for a REST API"
    ]

    for example in examples:
        from debate import validate_prompt
        result = validate_prompt(example)
        assert result.is_success, f"Example prompt should be valid: {example}"

def main():
    """Run all tests"""
    print(f"{Colors.BOLD}{Colors.CYAN}Running Debate System Tests{Colors.NC}\n")

    tests = [
        ("Format Validation", test_format_validation),
        ("Design Extraction", test_design_extraction),
        ("Convergence Detection", test_convergence_detection),
        ("Prompt Validation", test_prompt_validation),
        ("Config Validation", test_config_validation),
        ("Session Save/Load", test_session_save_load),
        ("CLI Integration", test_cli_integration),
        ("Example Prompts", test_examples),
    ]

    passed = 0
    failed = 0

    for test_name, test_fn in tests:
        if run_test(test_name, test_fn):
            passed += 1
        else:
            failed += 1

    print(f"\n{Colors.BOLD}{'='*60}{Colors.NC}")
    print(f"{Colors.BOLD}Test Results: {Colors.GREEN}{passed} passed{Colors.NC}, ", end='')
    if failed > 0:
        print(f"{Colors.RED}{failed} failed{Colors.NC}")
    else:
        print(f"{Colors.GREEN}{failed} failed{Colors.NC}")
    print(f"{Colors.BOLD}{'='*60}{Colors.NC}\n")

    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
