#!/bin/bash

# Fix and Test Script for Debate System
# This script will:
# 1. Test the current example
# 2. If it passes, generate and test new examples
# 3. Run up to 10 iterations total

set -e

MAX_ITERATIONS=10
ROUNDS_PER_DEBATE=2  # 2 rounds is usually enough for consensus
TIMEOUT_SECONDS=720  # 12 minutes - enough for 2 rounds with 2 agents, allowing up to 150s per API call
OUTPUT_DIR="debate_output"
LOG_DIR="fix_test_logs"

# Create log directory
mkdir -p "$LOG_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAIN_LOG="$LOG_DIR/test_run_${TIMESTAMP}.log"

# Test tasks
TASKS=(
    "Design a REST API for a todo list application with user authentication"
    "Design a simple caching layer with TTL support"
    "Design a rate limiting system using token bucket algorithm"
    "Design a file upload service with validation and storage"
    "Design a webhook delivery system with retries"
    "Design a notification service with email and push notifications"
    "Design a task queue system with priority support"
    "Design a user profile management API"
    "Design a blog API with posts, comments, and tags"
    "Design a shopping cart API with inventory management"
)

echo "==========================================" | tee -a "$MAIN_LOG"
echo "Debate System Fix and Test" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"

SUCCESS_COUNT=0
FAIL_COUNT=0

for i in $(seq 1 $MAX_ITERATIONS); do
    # Select task
    TASK_INDEX=$((i - 1))
    TASK="${TASKS[$TASK_INDEX]}"

    echo "" | tee -a "$MAIN_LOG"
    echo "==========================================" | tee -a "$MAIN_LOG"
    echo "Iteration $i/$MAX_ITERATIONS" | tee -a "$MAIN_LOG"
    echo "Task: $TASK" | tee -a "$MAIN_LOG"
    echo "==========================================" | tee -a "$MAIN_LOG"

    ITER_LOG="$LOG_DIR/iteration_${i}_${TIMESTAMP}.log"

    # Run debate with timeout and reasonable API timeout
    if timeout $TIMEOUT_SECONDS ./debate "$TASK" --max-rounds $ROUNDS_PER_DEBATE --timeout 150 --no-color > "$ITER_LOG" 2>&1; then
        # Check if consensus was reached
        if grep -q "CONSENSUS REACHED" "$ITER_LOG"; then
            echo "✓ PASS: Consensus reached" | tee -a "$MAIN_LOG"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        elif grep -q "Debate complete" "$ITER_LOG"; then
            echo "⚠ PARTIAL: Debate completed but no consensus" | tee -a "$MAIN_LOG"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        else
            echo "✗ FAIL: Debate ran but unclear status" | tee -a "$MAIN_LOG"
            FAIL_COUNT=$((FAIL_COUNT + 1))
            echo "  Last 20 lines of log:" | tee -a "$MAIN_LOG"
            tail -20 "$ITER_LOG" | sed 's/^/  /' | tee -a "$MAIN_LOG"
        fi
    else
        EXIT_CODE=$?
        echo "✗ FAIL: Debate timed out or errored (exit code: $EXIT_CODE)" | tee -a "$MAIN_LOG"
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo "  Last 20 lines of log:" | tee -a "$MAIN_LOG"
        tail -20 "$ITER_LOG" | sed 's/^/  /' | tee -a "$MAIN_LOG"
    fi
done

echo "" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
echo "Final Results" | tee -a "$MAIN_LOG"
echo "==========================================" | tee -a "$MAIN_LOG"
echo "Successful: $SUCCESS_COUNT/$MAX_ITERATIONS" | tee -a "$MAIN_LOG"
echo "Failed: $FAIL_COUNT/$MAX_ITERATIONS" | tee -a "$MAIN_LOG"
echo "" | tee -a "$MAIN_LOG"

if [ $SUCCESS_COUNT -eq $MAX_ITERATIONS ]; then
    echo "✓ All tests passed!" | tee -a "$MAIN_LOG"
    exit 0
elif [ $SUCCESS_COUNT -ge 7 ]; then
    echo "⚠ Most tests passed (${SUCCESS_COUNT}/${MAX_ITERATIONS})" | tee -a "$MAIN_LOG"
    exit 0
else
    echo "✗ Too many failures (${FAIL_COUNT}/${MAX_ITERATIONS})" | tee -a "$MAIN_LOG"
    exit 1
fi
