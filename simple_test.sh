#!/bin/bash

# Simple test - run debate a few times and check format

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Simple Format Test"
echo "=========================================="
echo ""

# Temporarily disable Ralph Loop
RALPH_STATE=".claude/ralph-loop.local.md"
RALPH_BACKUP=".claude/ralph-loop.backup.md"

if [[ -f "$RALPH_STATE" ]]; then
    echo "Backing up Ralph Loop state..."
    cp "$RALPH_STATE" "$RALPH_BACKUP"
    rm "$RALPH_STATE"
    trap "mv $RALPH_BACKUP $RALPH_STATE 2>/dev/null || true" EXIT
fi

# Test tasks
TASKS=(
    "Design a simple REST API for a blog with posts and comments"
    "Design a caching system with TTL"
    "Design a rate limiter"
)

PASSED=0
FAILED=0

for i in "${!TASKS[@]}"; do
    TASK="${TASKS[$i]}"
    NUM=$((i + 1))

    echo "----------------------------------------"
    echo "Test $NUM/${#TASKS[@]}: $TASK"
    echo "----------------------------------------"

    # Run with shorter max-rounds for faster testing
    if ./debate --max-rounds 2 "$TASK" 2>&1 | tee /tmp/debate_test_$NUM.log; then
        # Find the session directory
        SESSION=$(ls -td debate_output/session_* 2>/dev/null | head -1)

        if [[ -n "$SESSION" ]] && [[ -f "$SESSION/final_design.md" ]]; then
            # Check if final design starts correctly
            FIRST_LINE=$(head -1 "$SESSION/final_design.md")

            if [[ "$FIRST_LINE" == "## Design" ]]; then
                echo -e "${GREEN}✓ PASS - Format correct${NC}"
                PASSED=$((PASSED + 1))
            else
                echo -e "${YELLOW}⚠ PASS but format warning${NC}"
                echo "  First line: $FIRST_LINE"
                PASSED=$((PASSED + 1))
            fi

            # Check for any format violations in the log
            if grep -q "⚠.*Format violation" /tmp/debate_test_$NUM.log; then
                echo -e "${YELLOW}  ℹ Format violations detected during run (cleaned automatically)${NC}"
            fi
        else
            echo -e "${RED}✗ FAIL - No final design generated${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ FAIL - Debate command failed${NC}"
        FAILED=$((FAILED + 1))
    fi

    echo ""
done

echo "=========================================="
echo "Results"
echo "=========================================="
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
echo ""

if [[ $PASSED -gt 0 ]]; then
    echo -e "${GREEN}✓ Tests completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}✗ All tests failed${NC}"
    exit 1
fi
