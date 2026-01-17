#!/bin/bash
# Comprehensive test for debate system with multiple examples

cd "$(dirname "$0")"

MAX_ITERATIONS=${1:-10}
FAILED=0
PASSED=0

# Test examples
declare -a EXAMPLES=(
    "Design a simple user authentication API with login and logout endpoints"
    "Design a RESTful API for a todo list application with CRUD operations"
    "Design a database schema for an e-commerce order system"
    "Design a caching layer for a high-traffic web application"
    "Design a notification service that supports email, SMS, and push notifications"
)

echo "========================================="
echo "Comprehensive Debate System Test"
echo "Running up to $MAX_ITERATIONS iterations"
echo "========================================="
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    echo ""
    echo "========================================"
    echo "Iteration $i of $MAX_ITERATIONS"
    echo "========================================"

    # Select a test case (cycle through them)
    idx=$((($i - 1) % ${#EXAMPLES[@]}))
    test_case="${EXAMPLES[$idx]}"

    echo "Test case: $test_case"
    echo ""

    # Run the debate
    if ! python3 debate "$test_case" --max-rounds 3 --no-color; then
        echo "❌ FAILED: Debate script returned error"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Find the most recent session
    latest_session=$(ls -td debate_output/session_* 2>/dev/null | head -1)

    if [ ! -d "$latest_session" ]; then
        echo "❌ FAILED: No session directory created"
        FAILED=$((FAILED + 1))
        continue
    fi

    echo ""
    echo "Checking session: $latest_session"

    # Check if final_design.md exists
    if [ ! -f "$latest_session/final_design.md" ]; then
        echo "❌ FAILED: No final_design.md created"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Validate format - check if design content starts cleanly
    design_line=$(grep -n "^## Design" "$latest_session/final_design.md" | head -1 | cut -d: -f1)

    if [ -z "$design_line" ]; then
        echo "❌ FAILED: No '## Design' section found in final_design.md"
        FAILED=$((FAILED + 1))
        continue
    fi

    # Check for preamble (non-header text before ## Design)
    # We skip lines that are part of the wrapper (# Final, **, ---, empty)
    preamble_count=$(head -n $((design_line - 1)) "$latest_session/final_design.md" | \
        grep -v "^#" | \
        grep -v "^\*\*" | \
        grep -v "^---" | \
        grep -v "^$" | \
        wc -l)

    if [ "$preamble_count" -gt 0 ]; then
        echo "❌ FAILED: Found $preamble_count lines of preamble before ## Design"
        echo ""
        echo "Preview of violation:"
        head -n $design_line "$latest_session/final_design.md" | tail -n 15
        FAILED=$((FAILED + 1))
        continue
    fi

    # Check if the design has substantive content
    design_content_lines=$(tail -n +$design_line "$latest_session/final_design.md" | \
        grep -v "^$" | \
        wc -l)

    if [ "$design_content_lines" -lt 20 ]; then
        echo "⚠️  WARNING: Design seems short ($design_content_lines non-empty lines)"
    fi

    echo "✅ PASSED: Format is clean, ## Design at line $design_line, no preamble"
    PASSED=$((PASSED + 1))

    # Show a preview
    echo ""
    echo "Preview (first 10 lines after ## Design):"
    tail -n +$design_line "$latest_session/final_design.md" | head -n 10

    echo ""
done

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo "Total iterations: $((PASSED + FAILED))"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi
