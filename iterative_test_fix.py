#!/usr/bin/env python3
"""
Iterative test-fix cycle for the debate system.

This script:
1. Runs debates with various prompts
2. Analyzes outputs for format violations
3. Identifies issues
4. Reports findings
5. Can iterate up to N times
"""

import subprocess
import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Tuple
import json
from datetime import datetime

class Colors:
    GREEN = '\033[0;32m'
    RED = '\033[0;31m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    BOLD = '\033[1m'
    NC = '\033[0m'

class TestResult:
    def __init__(self, test_name: str, passed: bool, details: str = ""):
        self.test_name = test_name
        self.passed = passed
        self.details = details
        self.session_dir = None

def print_header(text: str):
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text}{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*70}{Colors.NC}\n")

def print_test(name: str, passed: bool, details: str = ""):
    status = f"{Colors.GREEN}✓ PASS{Colors.NC}" if passed else f"{Colors.RED}✗ FAIL{Colors.NC}"
    print(f"{status}: {name}")
    if details:
        print(f"  {details}")

def get_latest_session() -> Path:
    """Get the most recent session directory"""
    sessions = list(Path("debate_output").glob("session_*"))
    if not sessions:
        return None
    return max(sessions, key=lambda p: p.stat().st_mtime)

def check_format_violations(final_design_path: Path) -> Tuple[bool, List[str]]:
    """Check for format violations in final design"""
    violations = []

    if not final_design_path.exists():
        return False, ["File does not exist"]

    content = final_design_path.read_text()
    lines = content.split('\n')

    # Find ## Design line
    design_line_num = None
    for i, line in enumerate(lines):
        if line.strip() == "## Design":
            design_line_num = i
            break

    if design_line_num is None:
        violations.append("No '## Design' section found")
        return False, violations

    # Check for preambles before Design section
    preamble_patterns = [
        r"^(You've caught|I appreciate|I disagree|Let me address|Your approach|Now I will|Let me create|I'm calling out)",
        r"^(I think|You're right|However|But|Although|While)",
        r"^(Thanks for|Thank you for|Good point|Fair point)",
    ]

    for i in range(min(design_line_num, 20)):  # Check first 20 lines before Design
        line = lines[i].strip()
        if not line:
            continue
        if line.startswith("#"):  # Skip headers
            continue
        if line.startswith("**") and line.endswith("**"):  # Skip metadata
            continue
        if line.startswith("---"):  # Skip dividers
            continue

        for pattern in preamble_patterns:
            if re.match(pattern, line, re.IGNORECASE):
                violations.append(f"Preamble found at line {i+1}: '{line[:80]}'")

    # Check if Design appears reasonably early
    if design_line_num > 20:
        violations.append(f"## Design appears late (line {design_line_num+1})")

    return len(violations) == 0, violations

def run_debate_test(prompt: str, max_rounds: int = 2, timeout: int = 120) -> TestResult:
    """Run a single debate test"""
    test_name = f"Debate: {prompt[:50]}"

    print(f"\n{Colors.BOLD}Running: {test_name}...{Colors.NC}")

    # Run debate
    cmd = [
        "python3", "debate",
        prompt,
        "--max-rounds", str(max_rounds),
        "--no-color"
    ]

    try:
        result = subprocess.run(
            cmd,
            timeout=timeout,
            capture_output=True,
            text=True
        )

        # Get the latest session
        session = get_latest_session()
        if not session:
            return TestResult(test_name, False, "No session created")

        # Check for final design
        final_design = session / "final_design.md"
        if not final_design.exists():
            return TestResult(test_name, False, f"No final_design.md in {session.name}")

        # Check format
        passed, violations = check_format_violations(final_design)

        result = TestResult(test_name, passed)
        result.session_dir = session

        if violations:
            result.details = "; ".join(violations)
        else:
            result.details = f"Clean format in {session.name}"

        return result

    except subprocess.TimeoutExpired:
        return TestResult(test_name, False, "Timeout")
    except Exception as e:
        return TestResult(test_name, False, str(e))

def run_all_tests(iteration: int) -> List[TestResult]:
    """Run all test cases"""
    test_prompts = [
        "Design a REST API for a simple blog with posts and comments",
        "Create a user authentication system with email verification",
        "Design a database schema for a library management system",
        "Build a rate limiting middleware for Express.js",
        "Design a caching strategy for a high-traffic API",
    ]

    # Use different prompts each iteration
    prompt = test_prompts[iteration % len(test_prompts)]

    results = []

    print_header(f"Iteration {iteration + 1} - Testing with various prompts")

    # Run test
    result = run_debate_test(prompt, max_rounds=2, timeout=120)
    results.append(result)

    return results

def analyze_results(results: List[TestResult]) -> Dict:
    """Analyze test results and identify issues"""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    issues = []
    for result in results:
        if not result.passed:
            issues.append({
                'test': result.test_name,
                'details': result.details,
                'session': result.session_dir.name if result.session_dir else None
            })

    return {
        'passed': passed,
        'failed': failed,
        'total': len(results),
        'issues': issues
    }

def print_summary(iteration: int, analysis: Dict):
    """Print iteration summary"""
    print_header(f"Iteration {iteration + 1} Summary")

    print(f"Results: {Colors.GREEN}{analysis['passed']} passed{Colors.NC}, ", end='')
    if analysis['failed'] > 0:
        print(f"{Colors.RED}{analysis['failed']} failed{Colors.NC}")
    else:
        print(f"{Colors.GREEN}{analysis['failed']} failed{Colors.NC}")

    if analysis['issues']:
        print(f"\n{Colors.YELLOW}Issues Found:{Colors.NC}")
        for issue in analysis['issues']:
            print(f"  - {issue['test']}")
            print(f"    {issue['details']}")
            if issue['session']:
                print(f"    Session: {issue['session']}")
    else:
        print(f"\n{Colors.GREEN}✓ All tests passed!{Colors.NC}")

def main():
    max_iterations = 10

    if len(sys.argv) > 1:
        try:
            max_iterations = int(sys.argv[1])
        except ValueError:
            print(f"Invalid max iterations: {sys.argv[1]}")
            sys.exit(1)

    print_header(f"Iterative Test-Fix Cycle (Max {max_iterations} iterations)")

    all_results = []

    for iteration in range(max_iterations):
        # Run tests
        results = run_all_tests(iteration)

        # Print individual results
        print(f"\n{Colors.BOLD}Test Results:{Colors.NC}")
        for result in results:
            print_test(result.test_name, result.passed, result.details)

        # Analyze
        analysis = analyze_results(results)
        all_results.append(analysis)

        # Print summary
        print_summary(iteration, analysis)

        # Check if all tests passed
        if analysis['failed'] == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed! System is working correctly.{Colors.NC}")
            if iteration < max_iterations - 1:
                print(f"\n{Colors.CYAN}Running additional iteration with new example...{Colors.NC}")
                continue
            else:
                break
        else:
            print(f"\n{Colors.YELLOW}Issues found. Check the sessions for details.{Colors.NC}")
            print(f"\n{Colors.CYAN}Recommendations:{Colors.NC}")
            print("1. Review the final_design.md files in the failed sessions")
            print("2. Check if agents are following format requirements")
            print("3. Verify that validation warnings are being shown")
            print("4. Consider strengthening system prompts further")

            # Don't continue if tests fail
            print(f"\n{Colors.RED}Stopping due to test failures.{Colors.NC}")
            break

    # Final summary
    print_header("Overall Summary")
    print(f"Iterations completed: {len(all_results)}")

    for i, analysis in enumerate(all_results):
        status = f"{Colors.GREEN}PASS{Colors.NC}" if analysis['failed'] == 0 else f"{Colors.RED}FAIL{Colors.NC}"
        print(f"  Iteration {i+1}: {status} ({analysis['passed']}/{analysis['total']})")

    # Success if last iteration passed
    if all_results and all_results[-1]['failed'] == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ System verification complete!{Colors.NC}")
        return 0
    else:
        print(f"\n{Colors.RED}System needs attention.{Colors.NC}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
