#!/bin/bash
# Run multiple test iterations of the debate system

set -e

cd "$(dirname "$0")"

MAX_ITERATIONS=10
ROUNDS_PER_DEBATE=3

echo "=========================================="
echo "Running $MAX_ITERATIONS test iterations"
echo "=========================================="
echo ""

# Test tasks
TASKS=(
    "Design a REST API for user authentication with login and logout"
    "Design a simple caching layer for a web application"
    "Design a database schema for a blog with posts and comments"
    "Design an API rate limiting system"
    "Design a file upload service with validation"
    "Design a notification system with email and SMS"
    "Design a simple e-commerce cart API"
    "Design a user profile management system"
    "Design a simple task queue system"
    "Design a webhook delivery system"
)

passed=0
failed=0

for i in $(seq 1 $MAX_ITERATIONS); do
    task_idx=$((i - 1))
    task="${TASKS[$task_idx]}"

    echo ""
    echo "=========================================="
    echo "Iteration $i/$MAX_ITERATIONS"
    echo "Task: $task"
    echo "=========================================="

    # Run debate with timeout
    if timeout 180 python3 debate "$task" --max-rounds $ROUNDS_PER_DEBATE --no-color > /tmp/debate_iter_$i.log 2>&1; then
        # Find the most recent session
        latest_session=$(ls -td debate_output/session_* 2>/dev/null | head -1)

        if [ -d "$latest_session" ] && [ -f "$latest_session/final_design.md" ]; then
            # Check for format violations in final design
            if head -20 "$latest_session/final_design.md" | grep -q "^You've caught\|^I appreciate\|^I disagree\|^Let me address\|^Your approach"; then
                echo "✗ FAIL: Format violation detected in final design"
                echo "  Preview:"
                head -10 "$latest_session/final_design.md"
                failed=$((failed + 1))
            else
                # Check if ## Design appears reasonably early
                design_line=$(grep -n "^## Design" "$latest_session/final_design.md" | head -1 | cut -d: -f1)
                if [ ! -z "$design_line" ] && [ "$design_line" -le 10 ]; then
                    echo "✓ PASS: Format is clean (## Design at line $design_line)"
                    passed=$((passed + 1))
                else
                    echo "⚠  WARNING: ## Design found at line $design_line (expected <= 10)"
                    echo "  Preview:"
                    head -15 "$latest_session/final_design.md"
                    failed=$((failed + 1))
                fi
            fi

            echo "  Session: $latest_session"
        else
            echo "✗ FAIL: No final design produced"
            failed=$((failed + 1))
        fi
    else
        echo "✗ FAIL: Debate timed out or errored"
        if [ -f "/tmp/debate_iter_$i.log" ]; then
            echo "  Last 10 lines of log:"
            tail -10 "/tmp/debate_iter_$i.log" | sed 's/^/  /'
        fi
        failed=$((failed + 1))
    fi

    # Brief pause between iterations
    sleep 2
done

echo ""
echo "=========================================="
echo "Final Results"
echo "=========================================="
echo "Passed: $passed/$MAX_ITERATIONS"
echo "Failed: $failed/$MAX_ITERATIONS"
echo ""

if [ $failed -eq 0 ]; then
    echo "✓ All tests passed!"
    exit 0
else
    echo "✗ Some tests failed"
    exit 1
fi
