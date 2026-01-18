# Plan with Agents

A Claude Code plugin that uses multi-turn planning with AI agent collaboration to create high-quality implementation designs.

## Project Overview

This plugin runs two AI agents (Architect and Reviewer) that iteratively refine a software design until they reach consensus. The process produces production-ready implementation plans with documented trade-offs.

## Key Files

- `plan` - Main executable script (Python) that orchestrates the planning process
- `commands/plan-with-agents.md` - Claude Code command definition
- `skills/planning-guide/SKILL.md` - Guidance for interpreting planning results
- `.claude-plugin/plugin.json` - Plugin metadata and configuration

## Directory Structure

```
plan-with-agents/
├── .claude-plugin/     # Plugin configuration
├── commands/           # Claude Code command definitions
├── examples/           # Sample planning sessions
├── skills/             # Skill definitions for Claude
└── plan                # Main executable
```

## Usage

The plugin exposes `/plan-with-agents` command:

```bash
# Basic usage
/plan-with-agents "Design API caching layer"

# With options
/plan-with-agents --max-rounds 5 --model opus "Design payment system"
```

## Configuration

Users can configure via:
- `.plan.json` in project root
- Environment variables (`PLAN_MAX_ROUNDS`, `PLAN_MODEL`, `PLAN_TIMEOUT`)
- CLI flags

## Output

Planning sessions output to `plan_output/session_*/`:
- `final_design.md` - Consensus design
- `planning_history.md` - Full agent conversation
- `session.json` - Session metadata

## Development Notes

- The `plan` script is a standalone Python executable
- Plugin follows Claude Code plugin conventions
- Examples in `examples/` demonstrate real planning sessions
