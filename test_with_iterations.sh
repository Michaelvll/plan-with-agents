#!/bin/bash

# Test the debate system with multiple iterations
# This script works around Ralph Loop interference by:
# 1. Temporarily disabling the Ralph Loop
# 2. Running tests
# 3. Re-enabling if it was active

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Parse arguments
MAX_ITERATIONS=${1:-10}
TIMEOUT=${2:-60}

echo "=========================================="
echo "Debate System Test with Iterations"
echo "=========================================="
echo ""
echo "Max iterations: $MAX_ITERATIONS"
echo "Timeout per test: ${TIMEOUT}s"
echo ""

# Save Ralph Loop state
RALPH_STATE_FILE=".claude/ralph-loop.local.md"
RALPH_BACKUP_FILE=".claude/ralph-loop.backup.md"

if [[ -f "$RALPH_STATE_FILE" ]]; then
    echo -e "${YELLOW}⚠ Ralph Loop is active - temporarily disabling${NC}"
    cp "$RALPH_STATE_FILE" "$RALPH_BACKUP_FILE"
    rm "$RALPH_STATE_FILE"
    RESTORE_RALPH=true
else
    RESTORE_RALPH=false
fi

# Cleanup function
cleanup() {
    if [[ "$RESTORE_RALPH" == "true" ]] && [[ -f "$RALPH_BACKUP_FILE" ]]; then
        echo ""
        echo -e "${BLUE}ℹ Restoring Ralph Loop state${NC}"
        mv "$RALPH_BACKUP_FILE" "$RALPH_STATE_FILE"
    fi
}

trap cleanup EXIT

# Test tasks
TASKS=(
    "Design a REST API for a todo list application with user authentication"
    "Design a simple caching layer with TTL support"
    "Design a rate limiting middleware for Express.js"
    "Design a WebSocket chat system with rooms"
    "Design a file upload service with virus scanning"
    "Design a search API with fuzzy matching"
    "Design an email notification system with templates"
    "Design a job queue with priority support"
    "Design a session management system with Redis"
    "Design a logging middleware with structured logs"
)

# Statistics
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0
declare -a FAILED_TASKS=()

# Create log directory
LOGDIR="fix_test_logs"
mkdir -p "$LOGDIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "Running Tests"
echo "=========================================="
echo ""

for i in $(seq 1 $MAX_ITERATIONS); do
    TASK_INDEX=$(( (i - 1) % ${#TASKS[@]} ))
    TASK="${TASKS[$TASK_INDEX]}"

    echo "=========================================="
    echo "Iteration $i/$MAX_ITERATIONS"
    echo "Task: $TASK"
    echo "=========================================="

    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    LOGFILE="$LOGDIR/iteration_${i}_${TIMESTAMP}.log"

    # Run debate with timeout
    set +e
    timeout ${TIMEOUT}s ./debate --max-rounds 3 "$TASK" > "$LOGFILE" 2>&1
    EXIT_CODE=$?
    set -e

    if [[ $EXIT_CODE -eq 0 ]]; then
        echo -e "${GREEN}✓ PASS${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))

        # Check if the output has format violations
        if grep -q "⚠.*Format violation" "$LOGFILE"; then
            echo -e "${YELLOW}  ⚠ Format violations detected (but cleaned)${NC}"
        fi

        # Get the session directory
        SESSION_DIR=$(grep -o "debate_output/session_[0-9_]*" "$LOGFILE" | tail -1)

        if [[ -n "$SESSION_DIR" ]] && [[ -f "$SESSION_DIR/final_design.md" ]]; then
            # Check final design for preambles
            if head -1 "$SESSION_DIR/final_design.md" | grep -q "^## Design"; then
                echo -e "${GREEN}  ✓ Final design starts correctly${NC}"
            else
                echo -e "${YELLOW}  ⚠ Final design has wrong start:${NC}"
                head -1 "$SESSION_DIR/final_design.md" | sed 's/^/    /'
            fi
        fi
    elif [[ $EXIT_CODE -eq 124 ]]; then
        echo -e "${RED}✗ FAIL: Timeout after ${TIMEOUT}s${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_TASKS+=("Iteration $i: $TASK (timeout)")
    else
        echo -e "${RED}✗ FAIL: Exit code $EXIT_CODE${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        FAILED_TASKS+=("Iteration $i: $TASK (exit code $EXIT_CODE)")

        # Show last few lines
        echo "  Last 10 lines:"
        tail -10 "$LOGFILE" | sed 's/^/    /'
    fi

    echo ""
done

# Summary
echo "=========================================="
echo "Test Summary"
echo "=========================================="
echo ""
echo "Total tests: $TOTAL_TESTS"
echo -e "${GREEN}Passed: $PASSED_TESTS${NC}"
echo -e "${RED}Failed: $FAILED_TESTS${NC}"
echo ""

if [[ $FAILED_TESTS -gt 0 ]]; then
    echo "Failed tasks:"
    for task in "${FAILED_TASKS[@]}"; do
        echo "  - $task"
    done
    echo ""
fi

SUCCESS_RATE=$(( (PASSED_TESTS * 100) / TOTAL_TESTS ))
echo "Success rate: ${SUCCESS_RATE}%"

if [[ $SUCCESS_RATE -ge 80 ]]; then
    echo -e "${GREEN}✓ Test run successful!${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠ Success rate below 80%${NC}"
    exit 1
fi
