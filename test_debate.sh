#!/bin/bash
# Test script for debate system

cd "$(dirname "$0")"

echo "==================================="
echo "Testing Debate System - Run 1"
echo "==================================="

python3 debate "Design a simple user authentication API with login and logout endpoints" --max-rounds 3 --no-color

echo ""
echo "==================================="
echo "Checking output..."
echo "==================================="

# Find the most recent session
latest_session=$(ls -td debate_output/session_* | head -1)

if [ -d "$latest_session" ]; then
    echo "Latest session: $latest_session"

    if [ -f "$latest_session/final_design.md" ]; then
        echo ""
        echo "Final design exists. Checking for format violations..."

        # Check if there's any preamble before ## Design
        first_line=$(head -1 "$latest_session/final_design.md")
        if echo "$first_line" | grep -q "# Final Agreed Design"; then
            # Skip the header lines and check the first content line
            content_start=$(grep -n "^## Design" "$latest_session/final_design.md" | head -1 | cut -d: -f1)
            if [ ! -z "$content_start" ]; then
                echo "✓ Found ## Design at line $content_start"

                # Check for preamble between header and design
                between_lines=$(sed -n "1,${content_start}p" "$latest_session/final_design.md" | grep -v "^#" | grep -v "^\*\*" | grep -v "^---" | grep -v "^$" | wc -l)
                if [ "$between_lines" -gt 0 ]; then
                    echo "⚠️  WARNING: Found $between_lines lines of content before ## Design"
                    echo ""
                    echo "Preview:"
                    sed -n "1,${content_start}p" "$latest_session/final_design.md" | head -20
                else
                    echo "✓ No preamble found - format is clean"
                fi
            else
                echo "⚠️  WARNING: No ## Design section found"
            fi
        fi

        echo ""
        echo "First 30 lines of final design:"
        head -30 "$latest_session/final_design.md"
    else
        echo "⚠️  WARNING: No final_design.md found"
    fi

    if [ -f "$latest_session/session.json" ]; then
        echo ""
        echo "Session info:"
        cat "$latest_session/session.json"
    fi
else
    echo "⚠️  WARNING: No session directory found"
fi

echo ""
echo "==================================="
echo "Test complete"
echo "==================================="
