---
name: planning-guide
description: Guide users through multi-turn planning tool usage, result interpretation, and quality validation
trigger_keywords:
  - "plan-with-agents"
  - "/plan-with-agents"
  - "planning tool"
  - "multi-turn planning"
  - "planning consensus"
  - "planning results"
  - "should I plan"
  - "when to plan"
trigger_context:
  - "when user asks about using the multi-turn planning tool"
  - "when user asks about planning output or consensus"
  - "when user questions planning quality or needs validation"
---

# Multi-Turn Planning Guide

**Context-aware sections:** Read ONLY the section matching user's context.

---

## Section 1: Deciding to Use Multi-Turn Planning

**When user is deciding whether to run planning** (no planning has run yet)

### Quick Decision Tree

**USE MULTI-TURN PLANNING when:**
- Multiple valid approaches exist
- Security/performance/architecture trade-offs matter
- Requirements are ambiguous
- Changes affect 3+ components

**SKIP MULTI-TURN PLANNING when:**
- Single obvious solution
- Trivial changes (typos, formatting)
- User specified exact approach
- Well-established pattern exists

### Configuration Examples

```bash
# Default (most cases)
/plan-with-agents "Design API caching layer"

# Quick consensus (simple multi-approach task)
/plan-with-agents --max-rounds 5 "Add rate limiting"

# Deep exploration (complex/critical)
/plan-with-agents --model opus --max-rounds 12 "Design payment processing"
```

### Response Templates

**User asks: "Should I use multi-turn planning for [task]?"**

**If task is straightforward:**
"No need for multi-turn planning - [task] has a standard approach. Just implement [specific guidance]."

**If task has trade-offs:**
"Yes, [task] involves trade-offs around [X vs Y]. Run: `/plan-with-agents '[specific task description]'`"

**STOP - Other sections are for post-planning analysis**

---

## Section 2: Interpreting Planning Output

**When user asks about planning results** (planning has already run)

### Output Files

```
debate_output/session_*/
├── final_design.md       # Consensus design (read this first)
├── debate_history.md     # Full agent conversation
├── session.json          # Metadata
└── session_state.json    # State for resumption
```

### How to Read Consensus

**Process:**
1. Read `final_design.md` - This is the agreed design
2. Skim `debate_history.md` - Look for "Round N" headers
3. Identify: What did agents disagree on? How was it resolved?

**Example interpretation:**

```
Agents converged on **Redis caching with 5min TTL** after 4 rounds.

Key decisions:
- Round 1: Proposed in-memory caching
- Round 2: Rejected (won't work with multiple instances)
- Round 3: Agreed on Redis, considered TTL (1min vs 10min)
- Round 4: Settled on 5min TTL (balance freshness/hit-rate)

Trade-offs documented:
- Redis adds operational complexity (vs in-memory)
- 5min TTL = 85% hit rate, 5min max staleness

Open questions (deferred):
- Cache warming strategy
- Redis clustering approach
```

**Give user this level of insight - surface key decision points.**

**STOP - Section 3 is for quality validation**

---

## Section 3: Validating Consensus Quality

**When user asks if consensus is good/ready/needs more work**

### Round Count Signals

| Rounds | Signal | Action |
|--------|--------|--------|
| 1-2 | Too fast | Resume: `--resume latest --max-rounds 8` |
| 3-6 | Healthy | Proceed confidently |
| 7-9 | Complex | Appropriate for hard problems |
| 10+ | Spinning | Task may be too vague |

### Design Quality Checklist

**Strong consensus has:**
- Code examples, schemas, or concrete specs
- Explicit trade-off comparisons (X vs Y because Z)
- Acknowledged open questions
- Specific numbers (timeouts, limits, sizes)

**Weak consensus has:**
- Only prose, no code
- No alternatives discussed
- Vague statements ("should be fast")
- No rationale for choices

### When to Resume Planning

**Resume if any:**
- Converged in 1-2 rounds with no code examples
- Design is vague or lacks specifics
- New constraint emerged after consensus
- User wants deeper exploration of alternative

```bash
# Add more rounds
/plan-with-agents --resume latest --max-rounds 10

# Inject new constraint
/plan-with-agents --resume latest "Consider: must support 10k req/sec"

# Request specific detail
/plan-with-agents --resume latest "Add concrete code examples"
```

---

## Quick Reference

**Before planning:** Section 1 (deciding to use)
**After planning:** Section 2 (interpreting results)
**Quality check:** Section 3 (validating consensus)
