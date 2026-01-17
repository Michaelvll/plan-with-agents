#!/usr/bin/env python3
"""
Diagnose format violations in debate system responses
"""

import sys
import re
from pathlib import Path

def check_format_violation(response_text, agent_name):
    """Check if response violates format requirements"""

    # Strip leading whitespace
    stripped = response_text.lstrip()

    # Check if it starts with ## Design
    if not stripped.startswith('## Design'):
        # Find where ## Design actually appears
        lines = response_text.split('\n')
        design_line_num = None
        preamble_lines = []

        for i, line in enumerate(lines):
            if line.strip().startswith('## Design'):
                design_line_num = i
                break
            if line.strip():  # Non-empty line
                preamble_lines.append(f"  Line {i+1}: {line[:80]}")

        if design_line_num is not None:
            print(f"\n❌ {agent_name} FORMAT VIOLATION")
            print(f"   '## Design' found at line {design_line_num + 1}")
            print(f"   Forbidden preamble detected:\n")
            for line in preamble_lines[:10]:
                print(line)
            return True, design_line_num
        else:
            print(f"\n❌ {agent_name} MISSING ## Design SECTION")
            return True, None

    print(f"✅ {agent_name} format is correct")
    return False, None

def extract_and_clean_design(response_text):
    """Extract design section, removing any preamble"""

    # Find ## Design and start from there
    design_patterns = ['## Design\n', '### Design\n', '## Design\r\n']

    for pattern in design_patterns:
        if pattern in response_text:
            # Start from the Design section
            parts = response_text.split(pattern, 1)
            if len(parts) > 1:
                return pattern + parts[1]

    return response_text

def main():
    # Find the most recent session
    output_dir = Path("debate_output")
    if not output_dir.exists():
        print("No debate_output directory found")
        sys.exit(1)

    sessions = sorted(output_dir.glob("session_*"),
                     key=lambda p: p.stat().st_mtime,
                     reverse=True)

    if not sessions:
        print("No sessions found")
        sys.exit(1)

    # Check the most recent session that has a history file
    for session_dir in sessions[:5]:
        history_file = session_dir / "debate_history.md"
        if history_file.exists():
            print(f"\n📁 Analyzing session: {session_dir.name}")

            content = history_file.read_text()

            # Extract rounds
            rounds = re.split(r'## Round \d+', content)

            for i, round_text in enumerate(rounds[1:], 1):  # Skip first split (header)
                print(f"\n--- Round {i} ---")

                # Find Agent A and Agent B responses
                agent_a_match = re.search(r'### 🔵 Agent A\n\n(.*?)(?=### 🟣 Agent B|\*\*Convergence Signal|\Z)',
                                         round_text, re.DOTALL)
                agent_b_match = re.search(r'### 🟣 Agent B\n\n(.*?)(?=\*\*Convergence Signal|\Z)',
                                         round_text, re.DOTALL)

                if agent_a_match:
                    agent_a_response = agent_a_match.group(1).strip()
                    check_format_violation(agent_a_response, "Agent A (Architect)")

                if agent_b_match:
                    agent_b_response = agent_b_match.group(1).strip()
                    check_format_violation(agent_b_response, "Agent B (Reviewer)")

            # Only analyze the first session with history
            break
    else:
        print("No sessions with debate_history.md found")
        sys.exit(1)

if __name__ == "__main__":
    main()
