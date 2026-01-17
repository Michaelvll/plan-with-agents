#!/bin/bash

# Quick test to verify format fix

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

# Disable Ralph Loop
RALPH_STATE=".claude/ralph-loop.local.md"
RALPH_BACKUP=".claude/ralph-loop.backup.md"

if [[ -f "$RALPH_STATE" ]]; then
    cp "$RALPH_STATE" "$RALPH_BACKUP"
    rm "$RALPH_STATE"
    trap "mv $RALPH_BACKUP $RALPH_STATE 2>/dev/null || true" EXIT
fi

PASSED=0
FAILED=0

for i in {1..3}; do
    TASK="Test task $i"
    echo "Test $i/3..."
    
    ./debate --max-rounds 2 "Design a simple ${i}-tier API" > /dev/null 2>&1 || continue
    
    SESSION=$(ls -td debate_output/session_* | head -1)
    if [[ -f "$SESSION/final_design.md" ]]; then
        SEPARATOR_LINE=$(grep -n "^---$" "$SESSION/final_design.md" | tail -1 | cut -d: -f1)
        NEXT_LINE=$((SEPARATOR_LINE + 2))
        FIRST_CONTENT=$(sed -n "${NEXT_LINE}p" "$SESSION/final_design.md")
        
        if [[ "$FIRST_CONTENT" == "## Design" ]]; then
            echo -e "${GREEN}✓ Format correct${NC}"
            PASSED=$((PASSED + 1))
        else
            echo -e "${RED}✗ Wrong: '$FIRST_CONTENT'${NC}"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ No output${NC}"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "Results: $PASSED passed, $FAILED failed"
[[ $FAILED -eq 0 ]] && echo -e "${GREEN}All tests passed!${NC}" || echo -e "${RED}Some tests failed${NC}"
