#!/bin/bash
# Test script to run multiple debate iterations and verify format compliance

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
MAX_ITERATIONS=${1:-10}
MAX_ROUNDS=3
TIMEOUT=180

# Test prompts - diverse set of design tasks
declare -a TEST_PROMPTS=(
    "Design a REST API for a todo list application with user authentication"
    "Create a caching layer for a high-traffic news website"
    "Design a database schema for a social media platform with posts, comments, and likes"
    "Build a rate limiting system for API endpoints with different tiers"
    "Design a file upload service with virus scanning and CDN integration"
    "Create a notification system supporting email, SMS, and push notifications"
    "Design a search API with autocomplete and filters"
    "Build a payment processing system with multiple payment providers"
    "Design a session management system with Redis backend"
    "Create an audit logging system for compliance tracking"
)

echo -e "${BOLD}${CYAN}================================${NC}"
echo -e "${BOLD}${CYAN}Debate System Iteration Test${NC}"
echo -e "${BOLD}${CYAN}================================${NC}\n"

echo "Configuration:"
echo "  Max iterations: $MAX_ITERATIONS"
echo "  Max rounds per debate: $MAX_ROUNDS"
echo "  Timeout per debate: ${TIMEOUT}s"
echo ""

# Create results directory
RESULTS_DIR="test_results_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

PASSED=0
FAILED=0
TOTAL=0

# Function to check if final design has proper format
check_format() {
    local session_dir=$1
    local final_design="$session_dir/final_design.md"

    if [ ! -f "$final_design" ]; then
        echo "ERROR: final_design.md not found"
        return 1
    fi

    # Check if ## Design appears within first 10 lines (allowing for metadata header)
    local design_line=$(grep -n "^## Design" "$final_design" | head -1 | cut -d: -f1)

    if [ -z "$design_line" ]; then
        echo "ERROR: No '## Design' marker found"
        return 1
    fi

    if [ "$design_line" -gt 20 ]; then
        echo "ERROR: ## Design found at line $design_line (should be within first 20 lines)"
        return 1
    fi

    # Check for forbidden preambles in content after the header (line 15+)
    local content_start=15
    local forbidden_patterns=(
        "I appreciate your"
        "I disagree"
        "You've caught"
        "Let me address"
        "Your approach"
        "I respect that"
    )

    for pattern in "${forbidden_patterns[@]}"; do
        if tail -n +$content_start "$final_design" | head -20 | grep -qi "$pattern"; then
            echo "ERROR: Found forbidden preamble pattern: '$pattern'"
            return 1
        fi
    done

    echo "OK: Format is clean"
    return 0
}

# Run iterations
for i in $(seq 1 $MAX_ITERATIONS); do
    TOTAL=$((TOTAL + 1))

    # Select prompt (cycle through the array)
    prompt_index=$(( (i - 1) % ${#TEST_PROMPTS[@]} ))
    PROMPT="${TEST_PROMPTS[$prompt_index]}"

    echo -e "\n${BOLD}${CYAN}Iteration $i/$MAX_ITERATIONS${NC}"
    echo -e "${YELLOW}Prompt: $PROMPT${NC}\n"

    # Run debate with timeout
    timeout $TIMEOUT ./debate --max-rounds $MAX_ROUNDS "$PROMPT" > "$RESULTS_DIR/iteration_${i}.log" 2>&1
    exit_code=$?

    if [ $exit_code -eq 124 ]; then
        echo -e "${RED}✗ TIMEOUT after ${TIMEOUT}s${NC}"
        FAILED=$((FAILED + 1))
        echo "TIMEOUT" > "$RESULTS_DIR/iteration_${i}_result.txt"
        continue
    elif [ $exit_code -ne 0 ]; then
        echo -e "${RED}✗ FAILED with exit code $exit_code${NC}"
        FAILED=$((FAILED + 1))
        echo "FAILED: exit code $exit_code" > "$RESULTS_DIR/iteration_${i}_result.txt"
        continue
    fi

    # Find the latest session directory
    latest_session=$(ls -td debate_output/session_* | head -1)

    if [ -z "$latest_session" ]; then
        echo -e "${RED}✗ No session directory found${NC}"
        FAILED=$((FAILED + 1))
        echo "ERROR: No session directory" > "$RESULTS_DIR/iteration_${i}_result.txt"
        continue
    fi

    # Check format
    echo -n "Checking format... "
    format_check=$(check_format "$latest_session")
    format_result=$?

    if [ $format_result -eq 0 ]; then
        echo -e "${GREEN}✓ PASSED${NC}"
        echo "$format_check" >> "$RESULTS_DIR/iteration_${i}_result.txt"
        PASSED=$((PASSED + 1))

        # Copy final design to results
        cp "$latest_session/final_design.md" "$RESULTS_DIR/iteration_${i}_final_design.md"
    else
        echo -e "${RED}✗ FAILED${NC}"
        echo "$format_check"
        echo "$format_check" > "$RESULTS_DIR/iteration_${i}_result.txt"
        FAILED=$((FAILED + 1))

        # Copy problematic design for inspection
        cp "$latest_session/final_design.md" "$RESULTS_DIR/iteration_${i}_final_design.md" 2>/dev/null || true
    fi

    # Short pause between iterations
    sleep 2
done

# Summary
echo -e "\n${BOLD}${CYAN}================================${NC}"
echo -e "${BOLD}${CYAN}Test Summary${NC}"
echo -e "${BOLD}${CYAN}================================${NC}\n"

echo "Total iterations: $TOTAL"
echo -e "${GREEN}Passed: $PASSED${NC}"
echo -e "${RED}Failed: $FAILED${NC}"

if [ $FAILED -eq 0 ]; then
    echo -e "\n${BOLD}${GREEN}✓ All tests passed!${NC}\n"
    echo "Results saved to: $RESULTS_DIR"
    exit 0
else
    echo -e "\n${BOLD}${RED}✗ Some tests failed${NC}\n"
    echo "Results saved to: $RESULTS_DIR"
    echo "Check logs in $RESULTS_DIR/ for details"
    exit 1
fi
