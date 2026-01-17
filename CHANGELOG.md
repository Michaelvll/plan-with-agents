# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-01-16

### Added
- **Skills**: `planning-guide` skill for contextual guidance on when and how to use multi-turn planning
- **Examples**: Three curated examples (api-design, auth-flow, database-schema) with curator notes
- **Configuration file support**: `.debate.json` for project-level configuration
- **CLI options**: `--model`, `--timeout`, `--no-color`, `--self-test` flags
- **Signal handling**: Graceful interrupt with session save (Ctrl+C safe)
- **Self-test command**: `debate --self-test` for pre-flight diagnostics
- **Atomic writes**: Session state saved atomically to prevent corruption
- **Live progress tracking**: Key point extraction during agent generation

### Changed
- Rebranded from "debate" to "multi-turn planning" in user-facing text
- Updated terminology to emphasize collaborative planning over adversarial debate
- Improved round summary with ETA and convergence indicators

### Fixed
- Added missing `Dict` type import
- Fixed indentation in main debate loop

## [1.0.0] - 2026-01-15

### Added
- Initial release
- Two-agent planning system (Architect and Reviewer)
- Session persistence and resume capability
- Configurable max rounds
- Verbose mode for full agent output
- Output directory customization

[1.1.0]: https://github.com/michaelvll/plan-with-debate/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/michaelvll/plan-with-debate/releases/tag/v1.0.0
