# Final Agreed Design

**Task:** Improve the UX of plan-with-debate during long debates. The problem: debates take 5-10 minutes and users just see 'generating...' with no insight into what's happening.

REQUIREMENTS:
1. Show a LIVE SUMMARY of what each agent is producing as they generate (extract key points from the streaming output)
2. Show what aspects of the design are being debated/changed
3. Make the wait feel shorter and more informative
4. Users should understand the debate progress without reading full outputs

CONSTRAINTS:
- Output is streaming line-by-line from Claude CLI
- Can't modify Claude CLI itself
- Must work in terminal (no GUI)

Review the current debate script, especially call_claude_with_retry and the main loop, then propose specific UX improvements with code.

**Status:** consensus

---

Now I have a complete understanding of the codebase. Let me create a comprehensive design for improving the UX during long debates.

---

## Design: Live Debate Progress UX

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    DEBATE PROGRESS DASHBOARD                     │
├─────────────────────────────────────────────────────────────────┤
│  [████████████░░░░░░░] Round 2/8 (25%) │ ⏱️ 3:42 │ ETA: 11:06    │
├─────────────────────────────────────────────────────────────────┤
│  🔵 ARCHITECT (Generating...)                                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Key Points Being Discussed:                                 ││
│  │  • Proposing REST API with pagination                       ││
│  │  • Adding rate limiting middleware                          ││
│  │  • Reconsidering database schema from last round            ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
│  📊 Design Aspects:                                              │
│  ├── Architecture:    ████████░░ 80% stable (changed: caching)  │
│  ├── Data Model:      ██████░░░░ 60% stable (debating: indexes) │
│  ├── Error Handling:  ████████████ 100% agreed                  │
│  └── Security:        ██░░░░░░░░ 20% (new topic this round)     │
│                                                                  │
│  🔄 Changes This Round:                                          │
│  - [KEPT] REST over GraphQL approach                            │
│  - [CHANGED] Switched to Redis caching (was: in-memory)         │
│  - [NEW] Added rate limiting discussion                         │
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. StreamingKeyPointExtractor

A real-time text analyzer that extracts key points from streaming output.

```python
@dataclass
class KeyPoint:
    """A key point extracted from streaming output"""
    category: str           # "architecture", "data_model", "error_handling", etc.
    summary: str            # Short 10-15 word summary
    change_type: str        # "new", "kept", "changed", "debating"
    confidence: float       # 0.0-1.0 how confident we are in extraction
    line_number: int        # Where in the output this was found
    timestamp: float        # When extracted

@dataclass
class LiveSummary:
    """Current state of live extraction"""
    current_section: str                    # "Design", "Rationale", etc.
    key_points: List[KeyPoint]              # Extracted points
    aspects_status: Dict[str, AspectStatus] # Per-aspect stability
    change_summary: List[str]               # What changed/kept this round
    convergence_hint: Optional[str]         # "PROPOSING_FINAL" if detected

class StreamingKeyPointExtractor:
    """Extracts key points from Claude output in real-time"""
    
    SECTION_MARKERS = {
        "### Design": "design",
        "