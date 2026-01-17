#!/bin/bash
# Comprehensive test suite for format enforcement
# Tests the validation and cleaning logic without requiring Claude CLI

set -e

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║          PLAN-WITH-DEBATE FORMAT ENFORCEMENT TEST SUITE             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo

TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

run_test() {
    local test_name="$1"
    local test_script="$2"

    echo "──────────────────────────────────────────────────────────────────────"
    echo "Running: $test_name"
    echo "──────────────────────────────────────────────────────────────────────"
    echo

    TOTAL_TESTS=$((TOTAL_TESTS + 1))

    if python3 "$test_script"; then
        PASSED_TESTS=$((PASSED_TESTS + 1))
        echo
        echo "✓ $test_name PASSED"
        return 0
    else
        FAILED_TESTS=$((FAILED_TESTS + 1))
        echo
        echo "✗ $test_name FAILED"
        return 1
    fi
}

# Test 1: Basic validation logic
run_test "Test 1: Format Validation Logic" "test_validation.py"
echo

# Test 2: Format enforcement with cleaning
run_test "Test 2: Format Enforcement & Cleaning" "test_format_enforcement.py"
echo

# Test 3: End-to-end simulation
run_test "Test 3: End-to-End Debate Simulation" "test_end_to_end.py"
echo

# Summary
echo "══════════════════════════════════════════════════════════════════════"
echo "                           TEST SUMMARY                                "
echo "══════════════════════════════════════════════════════════════════════"
echo
echo "Total Tests:  $TOTAL_TESTS"
echo "Passed:       $PASSED_TESTS"
echo "Failed:       $FAILED_TESTS"
echo

if [ $FAILED_TESTS -eq 0 ]; then
    echo "✓ ALL TESTS PASSED!"
    echo
    echo "The format enforcement system is working correctly:"
    echo "  • Validates response format"
    echo "  • Detects preambles before '## Design'"
    echo "  • Shows clear warning messages"
    echo "  • Automatically cleans responses"
    echo "  • Preserves compliant responses"
    echo
    exit 0
else
    echo "✗ $FAILED_TESTS TEST(S) FAILED"
    echo
    echo "Please review the failed tests above."
    exit 1
fi
