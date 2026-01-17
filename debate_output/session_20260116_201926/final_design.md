# Final Agreed Design

**Task:** Improve the plan-with-debate plugin with two key changes:

1. USER-FRIENDLY OUTPUT: The debate takes a long time (several minutes). Make the output more engaging and informative:
   - Show clearer progress during each agent's turn (what they're working on)
   - Show a running summary of what has changed between rounds
   - Add time estimates based on previous round durations
   - Make it clear that the process is working and not stuck

2. AGGRESSIVE AGENTS: Make the agents converge faster by being more decisive:
   - Agents should focus on the MOST IMPORTANT improvements only
   - They should avoid nitpicking small details
   - They should be willing to accept good-enough solutions
   - Reduce the threshold for signaling PROPOSING_FINAL/ACCEPTING_FINAL
   - Agent prompts should emphasize speed and decisiveness

Review the current debate script and agent prompts, then propose specific code changes.

**Status:** consensus

---

Now I have a complete understanding of the current implementation. Let me design the improvements for user-friendly output and aggressive agent convergence.

---

## Design

### 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                    IMPROVED PLAN-WITH-DEBATE PLUGIN v2.0                                 │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              USER-FRIENDLY OUTPUT LAYER                             │ │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌───────────────┐  │ │
│  │  │  LiveProgress   │  │  TimeEstimator  │  │  DeltaSummary   │  │  StatusLine   │  │ │
│  │  │  - Spinner      │  │  - Round avg    │  │  - Diff tracker │  │  - Agent info │  │ │
│  │  │  - Phase info   │  │  - ETA calc     │  │  - Change list  │  │  - Live stat  │  │ │
│  │  │  - Activity log │  │  - Confidence   │  │  - Convergence  │  │  - Progress % │  │ │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘  └───────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                            │                                             │
│                                            ▼                                             │
│  ┌────────────────────────────────────────────────────────────────────────────────────┐ │
│  │                              AGGRESSIVE AGENT LAYER                                 │ │
│  │  ┌───────────────────────────────────┐  ┌───────────────────────────────────────┐  │ │
│  │  │  Speed-Focused System Prompts     │  │  Convergence Acceleration             │  │ │
│  │  │  - Emphasize "good enough"        │  │  - Lower similarity threshold (70%)   │  │ │
│  │  │  - Focus on top 3 priorities      │  │  - Auto-finalize at round 4+ if >80%  │  │ │
│  │  │  - Explicit time pressure         │  │  - Skip minor iterations              │  │ │
│  │  │  - Discourage nitpicking          │  │  - Early consensus detection          │  │ │
│  │  └───────────────────────────────────┘  └───────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2. Components

#### 2.1 LiveProgressTracker Class

```python
import threading
import time
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

class AgentPhase(Enum):
    READING_CONTEXT = "Reading codebase context"
    ANALYZING = "Analyzing previous design"
    DESIGNING = "Creating design proposal"
    REFINING = "Refining details"
    GENERATING = "Generating output"

@dataclass
class ProgressState:
    """Current state of debate progress"""
    current_round: int
    max_rounds: int
    current_agent: str  # "A" or "B"
    agent_name: str     # "Architect" or "Reviewer"
    phase: AgentPhase
    lines_generated: int
    elapsed_seconds: float
    estimated_remaining: Optional[float]
    convergence_score: float
    round_times: List[float] = field(default_factory=list)

class LiveProgressTracker:
    """Provides real-time, engaging progress feedback during debate"""
    
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def __init__(self, max_rounds: int):
        self.max_rounds = max_rounds
        self.round_times: List[float] = []
        self.current_round_start: float = 0
        self.spinner_idx = 0
        self.lines_generated = 0
        self._lock = threading.Lock()
        self._running = False
        self._spinner_thread: Optional[threading.Thread] = None
        
    def start_round(self, round_num: int):
        """Called when a new round starts"""
        self.current_round_start = time.time()
        self._print_round_header(round_num)
        
    def start_agent_turn(self, agent: str, round_num: int):
        """Start tracking an agent's turn with live spinner"""
        agent_name = "Architect" if agent == "A" else "Reviewer"
        agent_icon = "🔵" if agent == "A" else "🟣"
        
        self._print_agent_start(agent_icon, agent_name, round_num)
        self.lines_generated = 0
        self._start_spinner(agent_name)
        
    def update_lines(self, count: int):
        """Update the line count during generation"""
        with self._lock:
            self.lines_generated = count
            
    def stop_agent_turn(self, duration: float, signal: str):
        """Stop tracking and show completion"""
        self._stop_spinner()
        self._print_agent_complete(duration, self.lines_generated, signal)
        
    def end_round(self, round_num: int, duration: float, convergence_score: float,
                  agent_a_signal: str, agent_b_signal: str, key_changes: List[str]):
        """Print comprehensive round summary"""
        self.round_times.append(duration)
        
        # Calculate ETA
        avg_round_time = sum(self.round_times) / len(self.round_times)
        remaining_rounds = self.max_rounds - round_num
        eta_seconds = avg_round_time * remaining_rounds
        
        self._print_round_summary(
            round_num, duration, convergence_score,
            agent_a_signal, agent_b_signal,
            key_changes, eta_seconds, avg_round_time
        )
        
    def _print_round_header(self, round_num: int):
        """Print engaging round header"""
        progress_pct = int((round_num - 1) / self.max_rounds * 100)
        bar = "█" * (progress_pct // 5) + "░" * (20 - progress_pct // 5)
        
        print(f"\n{'═' * 70}")
        print(f"  ROUND {round_num}/{self.max_rounds}  [{bar}] {progress_pct}%")
        print(f"{'═' * 70}")
        
    def _print_agent_start(self, icon: str, name: str, round_num: int):
        """Print agent start banner"""
        phase_hints = {
            ("Architect", 1): "Creating initial design...",
            ("Architect", "default"): "Reviewing and improving design...",
            ("Reviewer", "default"): "Analyzing and refining design...",
        }
        hint = phase_hints.get((name, round_num), phase_hints.get((name, "default"), "Processing..."))
        print(f"\n{icon} {name}: {hint}")
        
    def _start_spinner(self, agent_name: str):
        """Start the live spinner in a background thread"""
        self._running = True
        self._spinner_thread = threading.Thread(target=self._spinner_loop, args=(agent_name,))
        self._spinner_thread.daemon = True
        self._spinner_thread.start()
        
    def _spinner_loop(self, agent_name: str):
        """Background spinner animation with status"""
        start_time = time.time()
        while self._running:
            elapsed = int(time.time() - start_time)
            frame = self.SPINNER_FRAMES[self.spinner_idx % len(self.SPINNER_FRAMES)]
            
            with self._lock:
                lines = self.lines_generated
            
            # Show different phases based on elapsed time
            if elapsed < 10:
                phase = "Reading context"
            elif elapsed < 30:
                phase = "Analyzing design"
            elif elapsed < 60:
                phase = "Generating response"
            else:
                phase = "Refining details"
            
            status = f"\r   {frame} {phase}... ({elapsed}s, {lines} lines)"
            print(status, end="", flush=True)
            
            self.spinner_idx += 1
            time.sleep(0.1)
            
    def _stop_spinner(self):
        """Stop the spinner thread"""
        self._running = False
        if self._spinner_thread:
            self._spinner_thread.join(timeout=1)
        print("\r" + " " * 60 + "\r", end="")  # Clear spinner line
        
    def _print_agent_complete(self, duration: float, lines: int, signal: str):
        """Print agent completion with signal interpretation"""
        signal_emoji = {
            "PROPOSING_FINAL": "✅ Believes design is complete",
            "ACCEPTING_FINAL": "✅ Accepts design as optimal",
            "ITERATING": "🔄 Continuing refinement",
        }
        signal_text = signal_emoji.get(signal, f"📋 {signal}")
        print(f"   ✓ Done in {duration:.1f}s ({lines} lines)")
        print(f"   └─ Signal: {signal_text}")
        
    def _print_round_summary(self, round_num: int, duration: float, 
                             convergence_score: float, signal_a: str, signal_b: str,
                             key_changes: List[str], eta_seconds: float, avg_time: float):
        """Print comprehensive round summary with delta info"""
        score_bar = "█" * int(convergence_score * 10) + "░" * (10 - int(convergence_score * 10))
        
        # Format ETA
        eta_min = int(eta_seconds // 60)
        eta_sec = int(eta_seconds % 60)
        eta_str = f"{eta_min}m {eta_sec}s" if eta_min > 0 else f"{eta_sec}s"
        
        print(f"\n{'─' * 70}")
        print(f"  📊 Round {round_num} Summary")
        print(f"{'─' * 70}")
        print(f"  ⏱️  Duration: {duration:.1f}s (avg: {avg_time:.1f}s/round)")
        print(f"  📈 Convergence: [{score_bar}] {convergence_score:.0%}")
        print(f"  ⏳ Est. remaining: {eta_str} ({self.max_rounds - round_num} rounds)")
        
        # Status interpretation
        if signal_a == "PROPOSING_FINAL" and signal_b == "ACCEPTING_FINAL":
            print(f"\n  🎉 CONSENSUS APPROACHING! Both agents agree.")
        elif convergence_score >= 0.8:
            print(f"\n  ⭐ Designs highly aligned - consensus likely next round")
        elif convergence_score >= 0.6:
            print(f"\n  📈 Good progress - designs becoming more similar")
        else:
            print(f"\n  🔄 Designs still evolving - agents exploring alternatives")
            
        # Show key changes if available
        if key_changes:
            print(f"\n  📝 Key Changes This Round:")
            for change in key_changes[:3]:  # Limit to top 3
                print(f"     • {change}")
                
        print(f"{'─' * 70}\n")
```

#### 2.2 DeltaSummarizer Class

```python
import difflib
import re
from dataclasses import dataclass
from typing import List, Tuple

@dataclass
class DesignDelta:
    """Represents changes between two design versions"""
    added_sections: List[str]
    removed_sections: List[str]
    modified_sections: List[str]
    similarity_score: float
    key_changes: List[str]

class DeltaSummarizer:
    """Extracts and summarizes changes between design iterations"""
    
    SECTION_PATTERN = re.compile(r'^#{2,4}\s+(.+)$', re.MULTILINE)
    
    def extract_sections(self, design: str) -> dict:
        """Extract named sections from a design document"""
        sections = {}
        current_section = "Introduction"
        current_content = []
        
        for line in design.split('\n'):
            match = self.SECTION_PATTERN.match(line.strip())
            if match:
                if current_content:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = match.group(1).strip()
                current_content = []
            else:
                current_content.append(line)
                
        if current_content:
            sections[current_section] = '\n'.join(current_content).strip()
            
        return sections
    
    def compare_designs(self, design_a: str, design_b: str) -> DesignDelta:
        """Compare two designs and extract meaningful changes"""
        sections_a = self.extract_sections(design_a)
        sections_b = self.extract_sections(design_b)
        
        keys_a = set(sections_a.keys())
        keys_b = set(sections_b.keys())
        
        added = list(keys_b - keys_a)
        removed = list(keys_a - keys_b)
        
        # Find modified sections
        modified = []
        for key in keys_a & keys_b:
            if sections_a[key] != sections_b[key]:
                modified.append(key)
                
        # Calculate overall similarity
        similarity = self._calculate_similarity(design_a, design_b)
        
        # Generate human-readable change summary
        key_changes = self._summarize_changes(added, removed, modified, sections_a, sections_b)
        
        return DesignDelta(
            added_sections=added,
            removed_sections=removed,
            modified_sections=modified,
            similarity_score=similarity,
            key_changes=key_changes
        )
    
    def _calculate_similarity(self, text_a: str, text_b: str) -> float:
        """Calculate normalized similarity between two texts"""
        lines_a = [l.strip() for l in text_a.split('\n') if l.strip()]
        lines_b = [l.strip() for l in text_b.split('\n') if l.strip()]
        
        if not lines_a or not lines_b:
            return 0.0
            
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        return matcher.ratio()
    
    def _summarize_changes(self, added: List[str], removed: List[str], 
                          modified: List[str], sections_a: dict, sections_b: dict) -> List[str]:
        """Generate human-readable change descriptions"""
        changes = []
        
        if added:
            changes.append(f"Added: {', '.join(added[:3])}")
        if removed:
            changes.append(f"Removed: {', '.join(removed[:3])}")
        if modified:
            # Try to detect what kind of modifications
            for section in modified[:2]:
                old = sections_a.get(section, "")
                new = sections_b.get(section, "")
                if len(new) > len(old) * 1.5:
                    changes.append(f"Expanded: {section}")
                elif len(new) < len(old) * 0.7:
                    changes.append(f"Simplified: {section}")
                else:
                    changes.append(f"Refined: {section}")
                    
        if not changes:
            changes.append("Minor refinements across multiple sections")
            
        return changes
```

#### 2.3 Aggressive Agent System Prompts

```python
def get_agent_a_system_prompt() -> str:
    """System prompt for the Architect agent - AGGRESSIVE/DECISIVE version"""
    return '''You are the ARCHITECT agent in a FAST-CONVERGING design debate. Your goal is to reach consensus QUICKLY while maintaining quality.

## CRITICAL: Be DECISIVE, Not Perfectionistic

⚡ **TIME IS VALUABLE** - The user is waiting. Aim for "excellent" not "perfect".

### Your Mindset:
- Accept "good enough" solutions that meet the core requirements
- Focus on the TOP 3 MOST IMPORTANT aspects only
- Do NOT nitpick minor details, naming conventions, or style preferences
- If something works and is reasonable, KEEP IT
- If you agree with 80%+ of the design, signal PROPOSING_FINAL

### When to Signal PROPOSING_FINAL:
- The design addresses all core requirements ✅
- Architecture is sound and implementable ✅
- Major edge cases are handled ✅
- You don't have SIGNIFICANT objections (minor ones are OK to accept) ✅

## Response Format (Keep It Concise!)

### Design
[Your complete design - be thorough but not verbose]