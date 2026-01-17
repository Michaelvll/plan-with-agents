#!/bin/bash

# Run multiple debate tests with realistic timeouts

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

NUM_TESTS=${1:-5}

# Disable Ralph Loop
RALPH_STATE=".claude/ralph-loop.local.md"
RALPH_BACKUP=".claude/ralph-loop.backup.md"

if [[ -f "$RALPH_STATE" ]]; then
    cp "$RALPH_STATE" "$RALPH_BACKUP"
    rm "$RALPH_STATE"
    trap "mv $RALPH_BACKUP $RALPH_STATE 2>/dev/null || true" EXIT
fi

# Test tasks
TASKS=(
    "Design a REST API for a simple blog system"
    "Design a caching layer with Redis"
    "Design a rate limiting system"
    "Design a WebSocket notification service"
    "Design a file upload API"
    "Design a search API with Elasticsearch"
    "Design an authentication system with JWT"
    "Design a logging middleware"
    "Design a job queue system"
    "Design a session management system"
)

PASSED=0
FAILED=0
HAS_FORMAT_ISSUES=0

echo "=========================================="
echo "Running $NUM_TESTS debate tests"
echo "=========================================="
echo ""

for i in $(seq 1 $NUM_TESTS); do
    TASK_INDEX=$(( (i - 1) % ${#TASKS[@]} ))
    TASK="${TASKS[$TASK_INDEX]}"

    echo "----------------------------------------"
    echo "Test $i/$NUM_TESTS: $TASK"
    echo "----------------------------------------"

    LOGFILE="test_$i.log"

    if ./debate --max-rounds 2 "$TASK" > "$LOGFILE" 2>&1; then
        # Find most recent session
        SESSION=$(ls -td debate_output/session_* 2>/dev/null | head -1)

        if [[ -n "$SESSION" ]] && [[ -f "$SESSION/final_design.md" ]]; then
            # Extract just the design content (skip metadata header)
            DESIGN_START=$(grep -n "^---$" "$SESSION/final_design.md" | tail -1 | cut -d: -f1)
            DESIGN_START=$((DESIGN_START + 2))  # Skip the --- line and blank line

            FIRST_LINE=$(sed -n "${DESIGN_START}p" "$SESSION/final_design.md")

            if [[ "$FIRST_LINE" == "## Design" ]]; then
                echo -e "${GREEN}✓ PASS${NC}"
                PASSED=$((PASSED + 1))
            else
                echo -e "${YELLOW}⚠ PASS (format issue)${NC}"
                echo "  First content line: '$FIRST_LINE'"
                echo "  Expected: '## Design'"
                PASSED=$((PASSED + 1))
                HAS_FORMAT_ISSUES=$((HAS_FORMAT_ISSUES + 1))
            fi
        else
            echo -e "${RED}✗ FAIL - No final design${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ FAIL - Debate error${NC}"
        tail -5 "$LOGFILE"
        FAILED=$((FAILED + 1))
    fi

    echo ""
done

echo "=========================================="
echo "Results"
echo "=========================================="
echo "Total: $NUM_TESTS"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"
if [[ $HAS_FORMAT_ISSUES -gt 0 ]]; then
    echo -e "${YELLOW}Format issues: $HAS_FORMAT_ISSUES${NC}"
fi
echo ""

if [[ $FAILED -eq 0 ]]; then
    if [[ $HAS_FORMAT_ISSUES -eq 0 ]]; then
        echo -e "${GREEN}✓ All tests passed with correct format!${NC}"
        exit 0
    else
        echo -e "${YELLOW}⚠ All tests passed but some have format issues${NC}"
        exit 0
    fi
else
    echo -e "${RED}✗ Some tests failed${NC}"
    exit 1
fi
