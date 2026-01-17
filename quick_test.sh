#!/bin/bash
# Quick test to verify format compliance

cd "$(dirname "$0")"

echo "=========================================="
echo "Quick Format Compliance Test"
echo "=========================================="
echo ""

# Run a quick 2-round debate with haiku (fastest model)
timeout 180 ./debate "Create a user authentication system with login and logout" \
    --max-rounds 2 \
    --working-dir "$(pwd)" \
    --timeout 90 \
    --model haiku \
    2>&1 | tee /tmp/debate_test_$$.log

echo ""
echo "=========================================="
echo "Checking for format violations..."
echo "=========================================="

# Find the most recent session
latest_session=$(ls -td debate_output/session_* 2>/dev/null | head -1)

if [ -z "$latest_session" ]; then
    echo "ERROR: No session found"
    exit 1
fi

echo "Session: $latest_session"
echo ""

# Check debate history for preambles
if [ -f "$latest_session/debate_history.md" ]; then
    echo "Checking Agent A responses for preambles..."

    # Extract Agent A sections and check if they start with ## Design
    awk '/^### 🔵 Agent A/,/^### 🟠 Agent B|^## Round [0-9]/' "$latest_session/debate_history.md" | \
        grep -A 5 "^### 🔵 Agent A" | \
        grep -v "^###" | \
        grep -v "^--" | \
        grep -v "^$" | \
        head -10 > /tmp/agent_a_start_$$.txt

    first_content=$(grep -v "^$" /tmp/agent_a_start_$$.txt | head -1)

    if [[ "$first_content" == "## Design"* ]]; then
        echo "✓ Agent A: Format correct (starts with ## Design)"
    else
        echo "⚠️  Agent A: FORMAT VIOLATION - Preamble detected:"
        head -5 /tmp/agent_a_start_$$.txt
    fi

    echo ""
    echo "Checking Agent B responses for preambles..."

    # Extract Agent B sections
    awk '/^### 🟠 Agent B/,/^### 🔵 Agent A|^## Round [0-9]/' "$latest_session/debate_history.md" | \
        grep -A 5 "^### 🟠 Agent B" | \
        grep -v "^###" | \
        grep -v "^--" | \
        grep -v "^$" | \
        head -10 > /tmp/agent_b_start_$$.txt

    first_content=$(grep -v "^$" /tmp/agent_b_start_$$.txt | head -1)

    if [[ "$first_content" == "## Design"* ]]; then
        echo "✓ Agent B: Format correct (starts with ## Design)"
    else
        echo "⚠️  Agent B: FORMAT VIOLATION - Preamble detected:"
        head -5 /tmp/agent_b_start_$$.txt
    fi
else
    echo "WARNING: No debate_history.md found"
fi

echo ""

# Check final design
if [ -f "$latest_session/final_design.md" ]; then
    echo "Checking final design format..."

    # Find first non-header, non-metadata content line
    first_content=$(grep -v "^#\|^---\|^\*\*\|^$" "$latest_session/final_design.md" | head -1)

    if [[ "$first_content" == "## Design"* ]]; then
        echo "✓ Final design: Clean format"
    else
        echo "⚠️  Final design: Contains preamble:"
        echo "$first_content"
    fi
else
    echo "WARNING: No final_design.md found"
fi

echo ""
echo "=========================================="
echo "Test complete"
echo "=========================================="

# Cleanup
rm -f /tmp/agent_a_start_$$.txt /tmp/agent_b_start_$$.txt

# Return 0 if both agents followed format, 1 otherwise
if [ -f "$latest_session/debate_history.md" ]; then
    grep -q "FORMAT VIOLATION" /tmp/debate_test_$$.log && exit 1
fi

exit 0
