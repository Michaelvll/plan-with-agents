# Final Agreed Design

**Task:** Make the plan-with-debate plugin widely adoptable by other developers. Review the current implementation and design improvements for:

1. EASE OF INSTALLATION: Make it simple to install from GitHub with minimal setup
2. CONFIGURATION: Allow users to customize behavior (model, max rounds, verbosity, etc.)
3. DOCUMENTATION: Clear README, examples, and usage instructions
4. ROBUSTNESS: Handle edge cases, provide helpful error messages
5. INTEGRATION: Work seamlessly with Claude Code's plugin system

Current state:
- Plugin is at .claude/plugins/plan-with-debate/
- Has debate script, plugin.json, marketplace.json, commands/
- Works but may need polish for public release

Focus on what changes are needed to make this a production-quality plugin that developers would want to use.

**Status:** debating

---

Now I have the full context. Let me create my improved design addressing the critic's specific questions and the bugs found.

---

## Design

### Production-Ready Plan-with-Debate Plugin Design v5 (Architect)

---

## 1. Addressing the Critic's Specific Questions

### 1.1 Thread-Local Storage - My Decision: **DEFER to v1.1**

**Rationale:** The critic is technically correct that thread-local storage is more robust, but:

1. **This is a CLI tool** - It spawns subprocesses, not threads. The Python `signal` module only works in the main thread anyway.
2. **No async/threading in the codebase** - There's no `ThreadPoolExecutor`, no `asyncio`, no concurrent execution paths.
3. **YAGNI** - Adding thread-local complexity for a non-existent use case is over-engineering.

**However**, I agree the global variable is ugly. A simpler fix for v1.0:

```python
# Instead of global _current_session, embed session reference in handler closure
@contextmanager
def interrupt_handler(session: 'DebateSession'):
    """Context manager for graceful interrupt handling"""
    
    def handler(signum, frame):
        # session is captured in closure - no global needed
        sig_name = signal.Signals(signum).name
        print(f"\n{Colors.YELLOW}⚠ Received {sig_name}! Saving session...{Colors.NC}")
        
        if session and session.session_dir:
            try:
                save_session_state(session)
                print(f"{Colors.GREEN}✓ Session saved to {session.session_dir}{Colors.NC}")
                print(f"Resume: {Colors.CYAN}debate --resume {session.session_dir}{Colors.NC}")
            except Exception as e:
                print(f"{Colors.RED}✗ Save failed: {e}{Colors.NC}", file=sys.stderr)
        
        sys.exit(128 + signum)
    
    old_sigint = signal.signal(signal.SIGINT, handler)
    old_sigterm = signal.signal(signal.SIGTERM, handler)
    
    # SIGHUP only on Unix
    old_sighup = None
    if hasattr(signal, 'SIGHUP'):
        old_sighup = signal.signal(signal.SIGHUP, handler)
    
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        if old_sighup is not None:
            signal.signal(signal.SIGHUP, old_sighup)
```

**Why this works:**
- Closure captures `session` - no global state
- Properly restores all handlers
- Platform-aware SIGHUP handling
- Simple and correct for CLI use case

### 1.2 Global `_round_times` - My Decision: **FIX in v1.0**

The critic is right - this is sloppy and trivial to fix. Move it into the session:

```python
@dataclass
class DebateSession:
    """Tracks the entire debate session"""
    initial_prompt: str
    rounds: list = field(default_factory=list)
    final_design: str = ""
    status: ConvergenceStatus = ConvergenceStatus.DEBATING
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str = ""
    session_dir: str = ""  # Keep as str for JSON serialization
    max_rounds: int = 8
    working_dir: str = "."
    round_times: List[float] = field(default_factory=list)  # ADD THIS

# Update print_round_summary to take session
def print_round_summary(
    session: DebateSession,  # ADD
    round_num: int, 
    max_rounds: int, 
    duration: float,
    convergence_score: float, 
    agent_a_signal: str, 
    agent_b_signal: str
):
    """Print comprehensive summary after each round with ETA"""
    session.round_times.append(duration)  # USE SESSION
    
    # Calculate ETA
    avg_round_time = sum(session.round_times) / len(session.round_times)
    # ... rest unchanged
```

**Cost:** 3 lines changed. **Benefit:** Library-safe.

### 1.3 Atomic Writes - My Decision: **FIX in v1.0**

The critic is right - interrupted writes corrupt the session state, making `--resume` fail. This is a **real bug** that affects user experience.

```python
def save_session_state(session: DebateSession):
    """Save current session state atomically for resumption"""
    if not session.session_dir:
        return

    session_path = Path(session.session_dir)
    state_file = session_path / "session_state.json"
    temp_file = session_path / "session_state.json.tmp"

    # Build state dict
    state = {
        "initial_prompt": session.initial_prompt,
        "rounds": _serialize_rounds(session.rounds),
        "final_design": session.final_design,
        "status": session.status.value,
        "started_at": session.started_at,
        "ended_at": session.ended_at,
        "max_rounds": session.max_rounds,
        "working_dir": session.working_dir,
        "current_round": len(session.rounds),
        "round_times": session.round_times,  # Now in session
    }

    try:
        # Write to temp file first
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Ensure written to disk
        
        # Atomic rename (POSIX guarantees atomicity)
        temp_file.replace(state_file)
        
    except Exception as e:
        # Clean up temp file on failure
        if temp_file.exists():
            try:
                temp_file.unlink()
            except:
                pass
        raise

def _serialize_rounds(rounds: List[DebateRound]) -> List[dict]:
    """Serialize rounds to JSON-compatible format"""
    result = []
    for r in rounds:
        round_data = {"round_number": r.round_number}
        if r.agent_a_response:
            round_data["agent_a"] = {
                "content": r.agent_a_response.content,
                "prompt_for_other": r.agent_a_response.prompt_for_other,
                "convergence_signal": r.agent_a_response.convergence_signal,
                "raw_response": r.agent_a_response.raw_response
            }
        if r.agent_b_response:
            round_data["agent_b"] = {
                "content": r.agent_b_response.content,
                "prompt_for_other": r.agent_b_response.prompt_for_other,
                "convergence_signal": r.agent_b_response.convergence_signal,
                "raw_response": r.agent_b_response.raw_response
            }
        result.append(round_data)
    return result
```

**Cost:** ~20 lines. **Benefit:** Resume never corrupts.

### 1.4 Type Consistency (`session_dir` str vs Path) - My Decision: **KEEP str, FIX in v1.0**

I disagree with changing `session_dir` to `Path` throughout. Here's why:

1. **JSON serialization** - `DebateSession` is serialized to JSON. `Path` objects don't serialize cleanly.
2. **Dataclass immutability** - Changing the type breaks load_session_state compatibility.
3. **Current code works** - As the critic noted, Path has good `__str__` so `f"{session_dir}"` works.

**The real fix is simpler** - be consistent about conversion at usage sites:

```python
# FIXED: Always convert to Path at the start of functions that need it
def save_session(session: DebateSession, session_dir: Union[str, Path]):
    """Save the debate session to files"""
    session_path = Path(session_dir)  # Convert once at top
    
    history_file = session_path / "debate_history.md"
    # ... all usages are now Path operations
```

This is already mostly happening, just needs minor cleanup.

---

## 2. Complete Bug Fix List (Merged with Critic's Findings)

| Priority | Bug | Location | Fix | Effort |
|----------|-----|----------|-----|--------|
| **P0** | Missing `Dict` import | L23 | Add `Dict` to imports | 1 min |
| **P1** | Timeout not wired | L939-942 | Thread timeout through call chain | 30 min |
| **P1** | Model not wired | All claude calls | Add `--model` to CLI args and thread | 45 min |
| **P1** | No SIGINT handling | Global | Add context manager (see 1.1) | 45 min |
| **P1** | No `--model` flag | argparse | Add argument | 10 min |
| **P1** | No `--timeout` flag | argparse | Add argument | 5 min |
| **P1** | No `--no-color` flag | argparse | Add argument | 10 min |
| **P2** | Global `_round_times` | L478 | Move to session (see 1.2) | 10 min |
| **P2** | Non-atomic session save | L543-583 | Atomic write pattern (see 1.3) | 20 min |
| **P2** | Config file loading | New | Add `.debate.json` support | 30 min |
| **P3** | `session_dir` type cleanup | Multiple | Consistent Path conversion | 15 min |
| **P3** | Race in session_dir creation | L1119-1121 | Add exist_ok handling | 5 min |

---

## 3. Complete Implementation Design

### 3.1 Fix #1: Import Statement (P0)

```python
# Line 23 - ADD Dict to imports
from typing import Optional, Tuple, TypeVar, Generic, Union, Callable, List, Any, Dict
```

### 3.2 Fix #2: CLI Flags (P1)

```python
def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Debate System - Two AI agents debate to optimal designs"
    )
    
    # ... existing arguments ...
    
    # ADD these new arguments
    parser.add_argument(
        '--model',
        default=None,  # Will be resolved from config
        choices=['sonnet', 'opus', 'haiku'],
        help='Claude model to use (default: sonnet)'
    )
    parser.add_argument(
        '--timeout',
        type=int,
        default=None,  # Will be resolved from config
        help='Timeout per API call in seconds (default: 300)'
    )
    parser.add_argument(
        '--no-color',
        action='store_true',
        help='Disable colored output'
    )
    parser.add_argument(
        '--self-test',
        action='store_true',
        help='Run self-diagnostics and exit'
    )
```

### 3.3 Fix #3: Configuration System (P2)

```python
@dataclass
class DebateConfig:
    """Configuration with layered resolution"""
    max_rounds: int = 8
    model: str = 'sonnet'
    timeout: int = 300
    verbose: bool = False
    no_color: bool = False
    output_dir: str = './debate_output'
    working_dir: str = '.'


def load_config(working_dir: str = '.') -> DebateConfig:
    """Load configuration with 3-level precedence: defaults < file < env"""
    config = DebateConfig()
    
    # Level 1: File config (.debate.json in working dir or home)
    for config_path in [Path(working_dir) / '.debate.json', Path.home() / '.debate.json']:
        if not config_path.exists():
            continue
        
        try:
            with open(config_path) as f:
                raw = json.load(f)
            
            # Map JSON keys to config attributes
            KEY_MAP = {
                'maxRounds': 'max_rounds',
                'max_rounds': 'max_rounds',
                'model': 'model',
                'timeout': 'timeout',
                'verbose': 'verbose',
                'noColor': 'no_color',
                'no_color': 'no_color',
                'outputDir': 'output_dir',
                'output_dir': 'output_dir',
            }
            
            for json_key, attr in KEY_MAP.items():
                if json_key in raw:
                    setattr(config, attr, raw[json_key])
            
            # Warn about unknown keys
            known = set(KEY_MAP.keys())
            unknown = set(raw.keys()) - known
            if unknown:
                print(f"{Colors.YELLOW}⚠ Unknown config keys: {unknown}{Colors.NC}", 
                      file=sys.stderr)
            
            break  # Use first found config file
            
        except json.JSONDecodeError as e:
            print(f"{Colors.YELLOW}⚠ Invalid JSON in {config_path}: {e}{Colors.NC}",
                  file=sys.stderr)
        except Exception as e:
            print(f"{Colors.YELLOW}⚠ Error reading {config_path}: {e}{Colors.NC}",
                  file=sys.stderr)
    
    # Level 2: Environment variables (override file config)
    env_map = {
        'DEBATE_MAX_ROUNDS': ('max_rounds', int),
        'DEBATE_MODEL': ('model', str),
        'DEBATE_TIMEOUT': ('timeout', int),
        'DEBATE_VERBOSE': ('verbose', lambda x: x.lower() in ('1', 'true', 'yes')),
    }
    
    for env_var, (attr, converter) in env_map.items():
        value = os.environ.get(env_var)
        if value:
            try:
                setattr(config, attr, converter(value))
            except ValueError:
                print(f"{Colors.YELLOW}⚠ Invalid {env_var}: {value}{Colors.NC}",
                      file=sys.stderr)
    
    # NO_COLOR standard (https://no-color.org/)
    if os.environ.get('NO_COLOR'):
        config.no_color = True
    
    return config


def apply_cli_args(config: DebateConfig, args) -> DebateConfig:
    """Apply CLI arguments over config (highest precedence)"""
    if args.max_rounds is not None:
        config.max_rounds = args.max_rounds
    if args.model is not None:
        config.model = args.model
    if args.timeout is not None:
        config.timeout = args.timeout
    if args.verbose:
        config.verbose = True
    if args.no_color:
        config.no_color = True
    if args.output:
        config.output_dir = args.output
    if args.working_dir:
        config.working_dir = args.working_dir
    return config
```

### 3.4 Fix #4: SIGINT/SIGTERM Handler (P1)

```python
import signal
from contextlib import contextmanager

@contextmanager
def interrupt_handler(session: 'DebateSession'):
    """Context manager for graceful interrupt handling with session save"""
    
    def handler(signum, frame):
        sig_name = signal.Signals(signum).name
        print(f"\n{Colors.YELLOW}⚠ Received {sig_name}! Saving session...{Colors.NC}")
        
        if session and session.session_dir:
            try:
                save_session_state(session)
                print(f"{Colors.GREEN}✓ Session saved to {session.session_dir}{Colors.NC}")
                print(f"Resume with: {Colors.CYAN}debate --resume {session.session_dir}{Colors.NC}")
            except Exception as e:
                print(f"{Colors.RED}✗ Failed to save session: {e}{Colors.NC}", 
                      file=sys.stderr)
        
        # Exit with standard signal exit code
        sys.exit(128 + signum)
    
    # Save original handlers
    old_sigint = signal.signal(signal.SIGINT, handler)
    old_sigterm = signal.signal(signal.SIGTERM, handler)
    
    # SIGHUP only exists on Unix
    old_sighup = None
    if hasattr(signal, 'SIGHUP'):
        old_sighup = signal.signal(signal.SIGHUP, handler)
    
    try:
        yield
    finally:
        # Restore original handlers
        signal.signal(signal.SIGINT, old_sigint)
        signal.signal(signal.SIGTERM, old_sigterm)
        if old_sighup is not None:
            signal.signal(signal.SIGHUP, old_sighup)


# Usage in run_debate:
def run_debate(config: DebateConfig, ...) -> DebateSession:
    # ... setup session ...
    
    with interrupt_handler(session):
        for round_num in range(start_round, max_rounds + 1):
            # ... debate loop ...
            pass
    
    return session
```

### 3.5 Fix #5: Model & Timeout Threading (P1)

```python
def _single_claude_call(
    system_prompt: str,
    user_prompt: str,
    working_dir: str,
    timeout: int = 300,
    model: str = 'sonnet'  # ADD
) -> Result[str]:
    """Execute a single Claude CLI call"""
    start_time = time.time()
    process = None
    tracker = LiveProgressTracker()

    try:
        process = subprocess.Popen(
            [
                'claude',
                '--print',
                '--model', model,  # ADD
                '--system-prompt', system_prompt,
                '--output-format', 'text',
                '--dangerously-skip-permissions'
            ],
            # ... rest unchanged
        )
        # ... rest unchanged


def call_claude_with_retry(
    system_prompt: str,
    user_prompt: str,
    working_dir: str,
    timeout: int = 300,
    max_retries: int = 2,
    model: str = 'sonnet'  # ADD
) -> Result[str]:
    """Call Claude CLI with retry logic"""
    last_error: Optional[ErrorInfo] = None

    for attempt in range(1, max_retries + 1):
        result = _single_claude_call(
            system_prompt, user_prompt, working_dir, 
            timeout=timeout, 
            model=model  # PASS
        )
        # ... rest unchanged


def call_claude_streaming(
    system_prompt: str, 
    user_prompt: str, 
    working_dir: str,
    agent_color: str, 
    num_preview_lines: int = 6,
    timeout: int = 300,
    model: str = 'sonnet'  # ADD
) -> str:
    """Call Claude CLI with streaming output"""
    result = call_claude_with_retry(
        system_prompt, user_prompt, working_dir,
        timeout=timeout,
        model=model  # PASS
    )
    # ... rest unchanged


# In run_debate - update calls:
def run_debate(
    config: DebateConfig,  # CHANGE: Accept config object
    initial_prompt: str = "",
    resumed_session: Optional[DebateSession] = None
) -> DebateSession:
    
    # ... setup ...
    
    raw_response_a = call_claude_streaming(
        get_agent_a_system_prompt(),
        agent_a_prompt,
        config.working_dir,
        Colors.BLUE,
        timeout=config.timeout,  # USE CONFIG
        model=config.model       # USE CONFIG
    )
```

### 3.6 Fix #6: Self-Test Command (P1)

```python
def run_self_test() -> bool:
    """Run comprehensive self-diagnostics"""
    print(f"{Colors.BOLD}Running self-diagnostics...{Colors.NC}\n")
    
    all_passed = True
    
    tests = [
        ("Claude CLI installed", check_claude_cli),
        ("Output directory writable", check_output_writable),
        ("Disk space available", check_disk_space),
        ("Python version", check_python_version),
    ]
    
    for name, check_fn in tests:
        result = check_fn()
        if result.is_success:
            print(f"  {Colors.GREEN}✓{Colors.NC} {name}: {result.value}")
        else:
            if result.error.severity == ErrorSeverity.WARNING:
                print(f"  {Colors.YELLOW}⚠{Colors.NC} {name}: {result.error.message}")
            else:
                print(f"  {Colors.RED}✗{Colors.NC} {name}: {result.error.message}")
                all_passed = False
            if result.error.suggestion:
                print(f"    → {result.error.suggestion}")
    
    print()
    if all_passed:
        print(f"{Colors.GREEN}All checks passed!{Colors.NC}")
    else:
        print(f"{Colors.RED}Some checks failed. Please fix the issues above.{Colors.NC}")
    
    return all_passed


def check_output_writable() -> Result[str]:
    """Check if we can write to output directory"""
    try:
        test_dir = Path('./debate_output')
        test_dir.mkdir(parents=True, exist_ok=True)
        test_file = test_dir / '.write_test'
        test_file.write_text('test')
        test_file.unlink()
        return Success(str(test_dir.resolve()))
    except PermissionError:
        return Failure(ErrorInfo(
            code="OUTPUT_NOT_WRITABLE",
            message="Cannot write to output directory",
            severity=ErrorSeverity.FATAL,
            suggestion="Check permissions or use --output"
        ))
    except Exception as e:
        return Failure(ErrorInfo(
            code="OUTPUT_ERROR",
            message=str(e),
            severity=ErrorSeverity.FATAL
        ))


def check_disk_space() -> Result[str]:
    """Check for reasonable disk space"""
    try:
        total, used, free = shutil.disk_usage('.')
        free_mb = free // (1024 * 1024)
        if free_mb < 100:
            return Failure(ErrorInfo(
                code="LOW_DISK_SPACE",
                message=f"Only {free_mb}MB free",
                severity=ErrorSeverity.WARNING,
                suggestion="Free up disk space"
            ))
        return Success(f"{free_mb}MB free")
    except Exception:
        return Success("Unknown (check skipped)")


def check_python_version() -> Result[str]:
    """Check Python version"""
    version = sys.version_info
    if version < (3, 8):
        return Failure(ErrorInfo(
            code="PYTHON_VERSION",
            message=f"Python {version.major}.{version.minor} is too old",
            severity=ErrorSeverity.FATAL,
            suggestion="Upgrade to Python 3.8+"
        ))
    return Success(f"{version.major}.{version.minor}.{version.micro}")
```

### 3.7 Fix #7: Colors with Disable Support (P1)

```python
class Colors:
    """ANSI color codes with disable support"""
    _enabled = True
    _codes = {
        'RED': '\033[0;31m',
        'GREEN': '\033[0;32m',
        'BLUE': '\033[0;34m',
        'YELLOW': '\033[1;33m',
        'CYAN': '\033[0;36m',
        'MAGENTA': '\033[0;35m',
        'BOLD': '\033[1m',
        'DIM': '\033[2m',
        'NC': '\033[0m',
    }
    
    # Set attributes at class definition
    RED = _codes['RED']
    GREEN = _codes['GREEN']
    BLUE = _codes['BLUE']
    YELLOW = _codes['YELLOW']
    CYAN = _codes['CYAN']
    MAGENTA = _codes['MAGENTA']
    BOLD = _codes['BOLD']
    DIM = _codes['DIM']
    NC = _codes['NC']
    
    @classmethod
    def disable(cls):
        """Disable all color output"""
        cls._enabled = False
        for name in cls._codes:
            setattr(cls, name, '')
    
    @classmethod
    def enable(cls):
        """Re-enable color output"""
        cls._enabled = True
        for name, code in cls._codes.items():
            setattr(cls, name, code)
    
    @classmethod
    def is_enabled(cls) -> bool:
        return cls._enabled
```

---

## 4. Updated Main Function (Complete Integration)

```python
def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Debate System - Two AI agents debate to optimal designs"
    )
    parser.add_argument('prompt', nargs='?', help='Initial prompt')
    parser.add_argument('-f', '--file', help='Read prompt from file')
    parser.add_argument('-m', '--max-rounds', type=int, help='Max rounds')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('-w', '--working-dir', default='.', help='Working directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    parser.add_argument('-i', '--implement', action='store_true', help='Auto-implement')
    parser.add_argument('-r', '--resume', nargs='?', const='latest', help='Resume session')
    parser.add_argument('-l', '--list', action='store_true', help='List sessions')
    parser.add_argument('--model', choices=['sonnet', 'opus', 'haiku'], help='Model')
    parser.add_argument('--timeout', type=int, help='Timeout in seconds')
    parser.add_argument('--no-color', action='store_true', help='Disable colors')
    parser.add_argument('--self-test', action='store_true', help='Run diagnostics')
    
    args = parser.parse_args()
    
    # Load config with 3-level precedence
    config = load_config(args.working_dir)
    config = apply_cli_args(config, args)
    
    # Apply color setting early
    if config.no_color:
        Colors.disable()
    
    # Self-test mode
    if args.self_test:
        success = run_self_test()
        sys.exit(0 if success else 1)
    
    # List mode
    if args.list:
        list_sessions(config.output_dir)
        sys.exit(0)
    
    # Handle resume
    resumed_session = None
    if args.resume:
        resumed_session = handle_resume(args.resume, config.output_dir)
        if not resumed_session:
            sys.exit(1)
    
    # Get prompt
    initial_prompt = args.prompt
    if args.file:
        initial_prompt = Path(args.file).read_text().strip()
    
    if not initial_prompt and not resumed_session:
        parser.print_help()
        print(f"\n{Colors.RED}Error: No prompt provided{Colors.NC}")
        sys.exit(1)
    
    # Pre-flight checks
    cli_check = check_claude_cli()
    if not cli_check.is_success:
        report_error(cli_check.error)
        sys.exit(1)
    
    # Validate
    config_result = validate_config(
        max_rounds=config.max_rounds,
        timeout=config.timeout,
        working_dir=config.working_dir,
        output_dir=config.output_dir
    )
    if not config_result.is_success:
        report_error(config_result.error)
        sys.exit(1)
    
    if initial_prompt:
        prompt_result = validate_prompt(initial_prompt)
        if not prompt_result.is_success:
            report_error(prompt_result.error)
            sys.exit(1)
        initial_prompt = prompt_result.value
    
    # Run debate
    run_debate(
        config=config,
        initial_prompt=initial_prompt or "",
        implement=args.implement,
        resumed_session=resumed_session
    )
```

---

## 5. Implementation Priority & Timeline

| Phase | Tasks | Effort | When |
|-------|-------|--------|------|
| **v1.0 Critical** | P0 Dict import | 1 min | Now |
| **v1.0 Critical** | P1 Signal handler | 45 min | Now |
| **v1.0 Critical** | P1 Model/timeout threading | 45 min | Now |
| **v1.0 Critical** | P1 CLI flags | 15 min | Now |
| **v1.0 Critical** | P1 Self-test | 45 min | Now |
| **v1.0** | P2 Config file | 30 min | Now |
| **v1.0** | P2 Atomic writes | 20 min | Now |
| **v1.0** | P2 Move `_round_times` | 10 min | Now |
| **v1.0** | P3 Type cleanup | 15 min | Now |
| **v1.1** | Thread-local storage | 30 min | If needed |
| **v1.1** | Cost estimation | 20 min | Nice to have |
| **v1.1** | Response truncation | 15 min | If needed |

**Total v1.0: ~4 hours**

---