#!/bin/bash
# Quick single test of the debate system

cd "$(dirname "$0")"

echo "Running single debate test..."
echo ""

# Clear old sessions to make it easier to find the new one
SESSION_BEFORE=$(ls -1 debate_output/session_* 2>/dev/null | wc -l)

# Run a quick debate
timeout 120 python3 debate "Design a REST API for a simple todo list with create, read, update, delete operations" --max-rounds 2 --no-color

# Find the newest session
SESSION_AFTER=$(ls -1 debate_output/session_* 2>/dev/null | wc -l)

if [ $SESSION_AFTER -gt $SESSION_BEFORE ]; then
    echo ""
    echo "New session created!"

    latest_session=$(ls -td debate_output/session_* 2>/dev/null | head -1)
    echo "Session: $latest_session"
    echo ""

    if [ -f "$latest_session/final_design.md" ]; then
        echo "Final design exists. Checking format..."
        echo ""

        # Show first 30 lines
        echo "=== First 30 lines of final_design.md ==="
        head -30 "$latest_session/final_design.md"
        echo ""
        echo "=== End of preview ==="
        echo ""

        # Check for violations
        if head -20 "$latest_session/final_design.md" | grep -E "^(You've caught|I appreciate|I disagree|Let me address|Your approach|Now I will|Let me create)"; then
            echo "❌ FORMAT VIOLATION DETECTED"
            exit 1
        else
            echo "✅ No obvious format violations found"
        fi

        # Check Design section location
        design_line=$(grep -n "^## Design" "$latest_session/final_design.md" | head -1 | cut -d: -f1)
        if [ ! -z "$design_line" ]; then
            echo "✅ ## Design found at line $design_line"
            if [ "$design_line" -le 10 ]; then
                echo "✅ Format looks good (Design section appears early)"
                exit 0
            else
                echo "⚠️  Warning: Design section is later than expected"
                exit 0
            fi
        else
            echo "❌ No ## Design section found"
            exit 1
        fi
    else
        echo "❌ No final_design.md produced"
        exit 1
    fi
else
    echo "❌ No new session was created"
    exit 1
fi
