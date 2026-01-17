---
description: "Run multi-turn planning to create a high-quality implementation design through agent collaboration"
allowed-tools:
  - Bash
  - Read
  - Glob
  - Grep
  - Edit
  - Write
arguments:
  - name: task
    description: "The task or feature to plan"
    required: false
  - name: max_rounds
    description: "Maximum planning rounds (default: 8)"
    required: false
  - name: model
    description: "Claude model to use: sonnet, opus, or haiku (default: sonnet)"
    required: false
---

# Multi-Turn Planning

You are about to run multi-turn planning to create a high-quality implementation design for a software engineering task.

## How It Works

The system uses two AI agents that iteratively refine a design:
- **Architect**: Creates and improves the design
- **Reviewer**: Critically analyzes and enhances the design

Each agent produces complete, improved designs until they reach consensus on an optimal solution.

## When to Use This

**Good for:**
- Tasks with multiple valid approaches
- Security/performance/architecture trade-offs
- Ambiguous requirements
- Changes affecting 3+ components

**Skip for:**
- Single obvious solution
- Trivial changes (typos, formatting)
- Well-established patterns

## Your Task

{{#if task}}
The user wants to plan: **{{task}}**
{{else}}
Ask the user what task or feature they want to plan. Once they provide the task, proceed with planning.
{{/if}}

## Instructions

1. **Run the planning session**:

```bash
"${CLAUDE_PLUGIN_ROOT}/debate" --working-dir "$(pwd)" {{#if max_rounds}}--max-rounds {{max_rounds}} {{/if}}{{#if model}}--model {{model}} {{/if}}"TASK_DESCRIPTION"
```

Replace `TASK_DESCRIPTION` with the actual task.

2. **Wait for consensus**: Planning runs through multiple rounds until both agents agree.

3. **Review the output**:
   - Final design: `debate_output/session_*/final_design.md`
   - Full history: `debate_output/session_*/debate_history.md`

4. **After completion**: Present the agreed-upon design to the user. Ask if they want you to implement it.

## CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--max-rounds N` | Maximum planning rounds | 8 |
| `--model MODEL` | Model: sonnet, opus, haiku | sonnet |
| `--timeout SECS` | Timeout per API call | 300 |
| `--resume latest` | Resume interrupted session | - |
| `--implement` | Auto-implement after consensus | - |
| `--verbose` | Show full agent outputs | - |
| `--no-color` | Disable colored output | - |
| `--self-test` | Run diagnostics | - |

## Examples

```bash
# Standard planning (most cases)
"${CLAUDE_PLUGIN_ROOT}/debate" --working-dir "$(pwd)" "Design API caching layer"

# Quick consensus for simpler tasks
"${CLAUDE_PLUGIN_ROOT}/debate" --working-dir "$(pwd)" --max-rounds 5 "Add rate limiting"

# Deep exploration for complex/critical tasks
"${CLAUDE_PLUGIN_ROOT}/debate" --working-dir "$(pwd)" --model opus --max-rounds 12 "Design payment processing"

# Resume an interrupted session
"${CLAUDE_PLUGIN_ROOT}/debate" --resume latest
```

## Notes

- Planning takes several minutes (typically 10-20 minutes for 4-8 rounds)
- You can safely interrupt with Ctrl+C - sessions are saved automatically
- Use `--resume latest` to continue an interrupted session

Now proceed to run planning for the user's task.
