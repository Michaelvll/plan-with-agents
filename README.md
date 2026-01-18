# Plan with Agents

Two AI agents collaborate to converge on optimal designs before implementation begins.

## Why This Matters

> "Most sessions start in Plan mode... I will use Plan mode, and go back and forth with Claude until I like its plan. From there, I switch into auto-accept edits mode and Claude can usually 1-shot it. **A good plan is really important!**"
> — [Boris Cherny](https://x.com/bcherny/status/2007179845336527000), Claude Code creator

But why spend your time going back and forth with Claude on the plan? **Let two agents collaborate instead.**

This plugin automates that iterative refinement — two Claude instances critique and improve each other's designs until they converge on an optimal plan. You get a thoroughly vetted design without the manual back-and-forth.

**The result:** Better designs, fewer implementation issues, and you can grab a coffee while the agents collaborate.

## The GAN-Inspired Approach

This system draws inspiration from **Generative Adversarial Networks (GANs)** — the breakthrough ML technique where two neural networks improve each other through competition:

| GAN Training | Agent Planning |
|--------------|----------------|
| Generator creates images | Architect creates designs |
| Discriminator critiques | Reviewer analyzes and improves |
| Iterative refinement | Back-and-forth until convergence |
| Better outputs over time | Better designs through collaboration |

Just as GANs produce remarkable results by having two components push each other to improve, this system produces better software designs by having two Claude instances challenge and refine each other's thinking.

## How It Works

```
                        ┌─────────────────────────────────────┐
                        │           Your Task                 │
                        │  "Design a caching layer for..."    │
                        └──────────────────┬──────────────────┘
                                           │
                                           ▼
        ╔═══════════════════════════════════════════════════════════════╗
        ║                     PLANNING LOOP                             ║
        ╠═══════════════════════════════════════════════════════════════╣
        ║                                                               ║
        ║   ┌──────────────────┐         ┌──────────────────┐          ║
        ║   │   🔵 ARCHITECT   │         │   🟣 REVIEWER    │          ║
        ║   │                  │         │                  │          ║
        ║   │  Creates design  │ ──────► │  Reviews design  │          ║
        ║   │  Incorporates    │         │  Finds gaps      │          ║
        ║   │  feedback        │ ◄────── │  Improves design │          ║
        ║   │                  │         │                  │          ║
        ║   └──────────────────┘         └──────────────────┘          ║
        ║            │                           │                      ║
        ║            └───────────┬───────────────┘                      ║
        ║                        │                                      ║
        ║              ┌─────────▼─────────┐                            ║
        ║              │  Both agree?      │                            ║
        ║              │  PROPOSING_FINAL  │──── No ────┐               ║
        ║              │  ACCEPTING_FINAL  │            │               ║
        ║              └─────────┬─────────┘            │               ║
        ║                   Yes  │                      │               ║
        ╚════════════════════════╪══════════════════════╪═══════════════╝
                                 │                      │
                                 ▼                      └──► Next Round
                   ┌─────────────────────────┐
                   │   ✅ CONSENSUS REACHED   │
                   │                         │
                   │   final_design.md       │
                   │   Ready to implement    │
                   └─────────────────────────┘
```

Each agent doesn't just give feedback — they produce a **complete improved design** based on the other's version. This continues until neither agent can improve the design further.

## Real Example: Round 1 vs Round 4

**Task**: "Design a visual AI agent workflow builder"

After 4 rounds (26 minutes), watch a basic design evolve into production-ready architecture:

**Round 1** - Basic workflow builder:

![Round 1 - Basic](examples/agent-workflow-builder/round1-screenshot.png)

**Round 4** - Production UI with checkpoints, tiered storage, and stream resurrection:

![Round 4 - Production](examples/agent-workflow-builder/round4-screenshot.png)

**What the iteration caught:**
- ❌ Page refresh loses all execution state → ✅ Checkpoint-based stream resurrection
- ❌ Single storage layer → ✅ Three-tier storage (Memory → IndexedDB → SessionStorage)
- ❌ Basic properties → ✅ Composable expression system for data flows
- ❌ No observability → ✅ Execution logs, metrics, cost tracking

## When to Use This

**Good for:**
- Tasks with multiple valid approaches
- Security/performance/architecture trade-offs
- Ambiguous requirements needing exploration
- Changes affecting multiple components

**Skip for:**
- Single obvious solution
- Trivial changes (typos, formatting)
- Well-established patterns

## Quick Start

### Installation

```bash
# In Claude Code
/plugin marketplace add michaelvll/plan-with-agents
/plugin install plan-with-agents
```

Or clone directly:
```bash
git clone https://github.com/michaelvll/plan-with-agents ~/.claude/plugins/plan-with-agents
```

### Usage

```bash
# Basic usage
/plan-with-agents "Design a REST API for a task management system"

# Quick consensus for simpler tasks
/plan-with-agents --max-rounds 5 "Add rate limiting middleware"

# Deep exploration for complex/critical tasks
/plan-with-agents --model opus --max-rounds 12 "Design payment processing system"

# Resume an interrupted session
/plan-with-agents --resume latest
```

## CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--max-rounds N` | Maximum planning rounds | 8 |
| `--model MODEL` | Model: sonnet, opus, haiku | sonnet |
| `--timeout SECS` | Timeout per API call | 300 |
| `--resume latest` | Resume interrupted session | - |
| `--implement` | Auto-implement after consensus | - |
| `--verbose` | Show full agent outputs | - |
| `--list` | List available sessions | - |

## Configuration

Create `.plan.json` in your project root:

```json
{
  "maxRounds": 8,
  "model": "sonnet",
  "timeout": 300
}
```

Or use environment variables: `PLAN_MAX_ROUNDS`, `PLAN_MODEL`, `PLAN_TIMEOUT`

## Output

Each session saves to `plan_output/session_*/`:

```
plan_output/session_20260116_123456/
├── final_design.md         # The agreed-upon design
├── planning_history.md     # Full conversation transcript
├── improvements_summary.md # What changed from Round 1
└── session.json            # Metadata for resumption
```

## Using the Final Design

Once planning reaches consensus, implement with Claude Code:

```bash
# Pass design as argument
claude "Implement this design: $(cat plan_output/session_*/final_design.md)"

# Or pipe interactively
cat plan_output/session_*/final_design.md | claude

# Or auto-implement after consensus
/plan-with-agents --implement "Design a REST API for user management"
```

## Tips for Good Prompts

1. **Be specific**: "Design a REST API for user authentication with JWT tokens" > "Design an API"
2. **Include constraints**: "...that handles 10k requests/second"
3. **Mention technologies**: "...using Redis for caching"
4. **Specify scope**: "Focus on the data model and API endpoints"

## Troubleshooting

**Run self-test:**
```bash
./plan --self-test
```

**Low similarity scores?** If agents show < 30% similarity after several rounds:
- Task may be too vague — add specific constraints
- Task may be too complex — break into smaller pieces

## Requirements

- Claude Code CLI (2.0+)
- Python 3.8+

## License

MIT

## Contributing

Contributions welcome! See [CHANGELOG](CHANGELOG.md) for recent changes.
