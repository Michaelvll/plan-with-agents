#!/bin/bash
# Automated test cycle - runs debate with different examples and validates output

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEBATE="${SCRIPT_DIR}/debate"
OUTPUT_DIR="${SCRIPT_DIR}/debate_output"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Test examples
EXAMPLES=(
    "Design a simple calculator API with add and subtract endpoints"
    "Create a user authentication system with login and logout"
    "Design a REST API for a todo list application"
    "Build a caching layer for database queries"
    "Create an API rate limiting system"
)

MAX_ITERATIONS=${1:-10}
ITERATION=0
PASSED=0
FAILED=0

echo -e "${BOLD}${CYAN}=== Debate System Test Cycle ===${NC}"
echo -e "Max iterations: $MAX_ITERATIONS\n"

while [ $ITERATION -lt $MAX_ITERATIONS ]; do
    ITERATION=$((ITERATION + 1))
    EXAMPLE_IDX=$((ITERATION % ${#EXAMPLES[@]}))
    EXAMPLE="${EXAMPLES[$EXAMPLE_IDX]}"

    echo -e "${BOLD}Iteration $ITERATION/$MAX_ITERATIONS${NC}"
    echo -e "${CYAN}Testing: $EXAMPLE${NC}\n"

    # Run debate with 2 rounds (quick test)
    if timeout 180 "$DEBATE" "$EXAMPLE" \
        --max-rounds 2 \
        --working-dir "$SCRIPT_DIR" \
        --timeout 90 \
        --model haiku \
        2>&1 | tee /tmp/debate_test_$ITERATION.log | grep -qE "(Debate complete|CONSENSUS)"; then

        # Validate output
        LATEST_SESSION=$(ls -t "$OUTPUT_DIR"/session_* 2>/dev/null | head -1)

        if [ -n "$LATEST_SESSION" ] && [ -f "$LATEST_SESSION/final_design.md" ]; then
            DESIGN_SIZE=$(wc -c < "$LATEST_SESSION/final_design.md")

            if [ $DESIGN_SIZE -gt 100 ]; then
                echo -e "${GREEN}✓ Test passed (design size: $DESIGN_SIZE bytes)${NC}\n"
                PASSED=$((PASSED + 1))
            else
                echo -e "${YELLOW}⚠ Test warning: Design too small ($DESIGN_SIZE bytes)${NC}\n"
                FAILED=$((FAILED + 1))
            fi
        else
            echo -e "${YELLOW}⚠ Test warning: No output generated${NC}\n"
            FAILED=$((FAILED + 1))
        fi
    else
        echo -e "${RED}✗ Test failed: Debate did not complete${NC}\n"
        FAILED=$((FAILED + 1))

        # Show last few lines of log
        echo -e "${YELLOW}Last output:${NC}"
        tail -10 /tmp/debate_test_$ITERATION.log
        echo
    fi

    # Brief pause between iterations
    sleep 2
done

# Results
echo -e "${BOLD}============================================================${NC}"
echo -e "${BOLD}Cycle Results:${NC}"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo -e "  Success rate: $((PASSED * 100 / MAX_ITERATIONS))%"
echo -e "${BOLD}============================================================${NC}\n"

[ $FAILED -eq 0 ]
