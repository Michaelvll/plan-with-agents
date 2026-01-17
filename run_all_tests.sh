#!/bin/bash
# Master test script - runs all tests iteratively
# Usage: ./run_all_tests.sh [--max-iterations N]

set -e

MAX_ITERATIONS=10
ITERATION=1

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --max-iterations)
            MAX_ITERATIONS="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--max-iterations N]"
            exit 1
            ;;
    esac
done

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║         PLAN-WITH-DEBATE ITERATIVE TEST SUITE                       ║"
echo "║         Testing format enforcement with multiple iterations          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo
echo "Configuration:"
echo "  Max iterations: $MAX_ITERATIONS"
echo

TOTAL_PASSED=0
TOTAL_FAILED=0

for ((ITERATION=1; ITERATION<=MAX_ITERATIONS; ITERATION++)); do
    echo
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "                        ITERATION $ITERATION/$MAX_ITERATIONS"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo

    ITER_PASSED=0
    ITER_FAILED=0

    # Run test suite
    echo "Running comprehensive test suite..."
    echo

    if ./run_comprehensive_tests.sh > /dev/null 2>&1; then
        ITER_PASSED=$((ITER_PASSED + 3))  # 3 tests in comprehensive suite
        TOTAL_PASSED=$((TOTAL_PASSED + 3))
        echo "✓ Iteration $ITERATION: Comprehensive tests PASSED (3/3)"
    else
        ITER_FAILED=$((ITER_FAILED + 3))
        TOTAL_FAILED=$((TOTAL_FAILED + 3))
        echo "✗ Iteration $ITERATION: Comprehensive tests FAILED"
    fi

    # Run diverse examples
    if python3 generate_test_examples.py > /dev/null 2>&1; then
        ITER_PASSED=$((ITER_PASSED + 1))
        TOTAL_PASSED=$((TOTAL_PASSED + 1))
        echo "✓ Iteration $ITERATION: Example generation PASSED"
    else
        ITER_FAILED=$((ITER_FAILED + 1))
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
        echo "✗ Iteration $ITERATION: Example generation FAILED"
    fi

    echo
    echo "  Iteration $ITERATION summary: $ITER_PASSED passed, $ITER_FAILED failed"

    # Stop if any test fails
    if [ $ITER_FAILED -gt 0 ]; then
        echo
        echo "✗ Iteration $ITERATION failed. Stopping."
        break
    fi

    # Brief pause between iterations
    if [ $ITERATION -lt $MAX_ITERATIONS ]; then
        sleep 0.5
    fi
done

# Final summary
echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "                         FINAL SUMMARY"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo
echo "Iterations completed: $ITERATION/$MAX_ITERATIONS"
echo "Total tests passed:   $TOTAL_PASSED"
echo "Total tests failed:   $TOTAL_FAILED"
echo

if [ $TOTAL_FAILED -eq 0 ] && [ $ITERATION -eq $MAX_ITERATIONS ]; then
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                    ✓ ALL TESTS PASSED!                              ║"
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo
    echo "The format enforcement system is stable across $MAX_ITERATIONS iterations:"
    echo "  • Format validation working correctly"
    echo "  • Violation detection accurate"
    echo "  • Automatic cleaning functional"
    echo "  • Compliant responses preserved"
    echo "  • Works across diverse design domains"
    echo
    exit 0
elif [ $TOTAL_FAILED -eq 0 ]; then
    echo "✓ All tests passed (stopped after $ITERATION iterations)"
    exit 0
else
    echo "✗ Tests failed - see details above"
    exit 1
fi
