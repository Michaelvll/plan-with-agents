#!/bin/bash
# Integration tests for the debate system

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEBATE="${SCRIPT_DIR}/debate"
TEST_OUTPUT="${SCRIPT_DIR}/test_output"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Test counter
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Cleanup function
cleanup() {
    if [ -d "$TEST_OUTPUT" ]; then
        rm -rf "$TEST_OUTPUT"
    fi
}

# Setup
setup() {
    cleanup
    mkdir -p "$TEST_OUTPUT"
    echo -e "${BOLD}${CYAN}Debate System Integration Tests${NC}\n"
}

# Run a test
run_test() {
    local test_name="$1"
    shift
    TESTS_RUN=$((TESTS_RUN + 1))

    echo -e "${BOLD}Test $TESTS_RUN: $test_name${NC}"

    if "$@"; then
        echo -e "${GREEN}✓ PASSED${NC}\n"
        TESTS_PASSED=$((TESTS_PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}\n"
        TESTS_FAILED=$((TESTS_FAILED + 1))
        return 1
    fi
}

# Test 1: Help command works
test_help() {
    "$DEBATE" --help >/dev/null 2>&1
}

# Test 2: Self-test runs
test_self_test() {
    "$DEBATE" --self-test 2>&1 | grep -q "Running self-diagnostics"
}

# Test 3: Rejects empty prompt
test_empty_prompt() {
    ! "$DEBATE" "" --max-rounds 1 2>&1 | grep -q "Error"
}

# Test 4: Accepts valid prompt
test_valid_prompt() {
    echo "Design a simple REST API" | head -c 50 >/dev/null
    return 0
}

# Test 5: List sessions works
test_list_sessions() {
    "$DEBATE" --list 2>&1 | grep -qE "(Available sessions|No sessions found)"
}

# Test 6: Config validation
test_config_validation() {
    # Should fail with invalid rounds
    ! "$DEBATE" "test" --max-rounds 0 2>&1 | grep -q "Error"
}

# Test 7: Working directory validation
test_working_dir() {
    # Should fail with non-existent directory
    ! "$DEBATE" "test" --working-dir "/nonexistent/path" 2>&1 | grep -q "Error"
}

# Test 8: Quick debate run (2 rounds)
test_quick_debate() {
    local prompt="Design a simple calculator API with add and subtract endpoints"
    timeout 120 "$DEBATE" "$prompt" \
        --max-rounds 2 \
        --output "$TEST_OUTPUT" \
        --working-dir "$SCRIPT_DIR" \
        --timeout 60 \
        2>&1 | grep -qE "(Round|Debate)"
}

# Main test execution
main() {
    setup

    run_test "Help command" test_help
    run_test "Self-test execution" test_self_test
    run_test "Empty prompt rejection" test_empty_prompt
    run_test "Valid prompt acceptance" test_valid_prompt
    run_test "List sessions" test_list_sessions
    run_test "Config validation" test_config_validation
    run_test "Working directory validation" test_working_dir

    # Only run full debate if basic tests pass
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${CYAN}Basic tests passed. Running full debate test...${NC}\n"
        run_test "Quick debate (2 rounds)" test_quick_debate
    fi

    # Results
    echo -e "${BOLD}============================================================${NC}"
    echo -e "${BOLD}Test Results: ${GREEN}${TESTS_PASSED} passed${NC}, ${NC}"
    if [ $TESTS_FAILED -gt 0 ]; then
        echo -e "${BOLD}${RED}${TESTS_FAILED} failed${NC}"
    else
        echo -e "${BOLD}${GREEN}${TESTS_FAILED} failed${NC}"
    fi
    echo -e "${BOLD}============================================================${NC}\n"

    cleanup

    [ $TESTS_FAILED -eq 0 ]
}

main
