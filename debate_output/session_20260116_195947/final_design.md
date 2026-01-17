# Final Agreed Design

**Task:** Improve this Claude Code plugin (plan-with-debate) to make it more robust and user-friendly. Focus on: 1) Better error handling when Claude CLI fails or times out, 2) Clearer user feedback when things go wrong, 3) Input validation, 4) Edge cases like empty prompts or interrupted sessions. Review the current code and propose specific improvements.

**Status:** consensus

---

Now I have a complete picture of the codebase. Let me provide my improved design as the ARCHITECT agent.

---

## Design

### 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    ROBUST PLAN-WITH-DEBATE PLUGIN                             │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    Validation Layer (Fail-Fast)                          │ │
│  │  - PromptValidator: sanitize, length check, quality warnings            │ │
│  │  - ConfigValidator: bounds, paths, permissions                          │ │
│  │  - Pre-flight check: Claude CLI availability + auth                     │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    Core Execution Layer                                  │ │
│  │  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐                  │ │
│  │  │ DebateRunner │◀──▶│ClaudeInvoker│◀──▶│StateManager │                  │ │
│  │  │ (Orchestrate)│    │(CLI Wrapper)│    │(Persistence)│                  │ │
│  │  └─────────────┘    └─────────────┘    └─────────────┘                  │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                    User Feedback Layer                                   │ │
│  │  - ProgressReporter: clear status, progress bars, timing                │ │
│  │  - ErrorPresenter: actionable messages with suggestions                 │ │
│  │  - SummaryFormatter: round/session summaries                            │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2. Core Data Types

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar, Generic, Optional, List, Union, Callable
from datetime import datetime
from pathlib import Path
import os
import re
import json

# ============================================================================
# Result Type - Explicit Error Handling
# ============================================================================

T = TypeVar('T')

class ErrorSeverity(Enum):
    """Classifies error severity for appropriate handling"""
    FATAL = "fatal"           # Must stop immediately
    RECOVERABLE = "recoverable"  # Can retry
    WARNING = "warning"       # Continue but inform user

@dataclass(frozen=True)
class ErrorInfo:
    """Immutable, actionable error information"""
    code: str                    # Machine-readable: "CLI_TIMEOUT", "INVALID_PROMPT"
    message: str                 # Human-readable description
    severity: ErrorSeverity
    suggestion: str = ""         # What the user should do
    context: dict = field(default_factory=dict)  # Debug info for verbose mode
    
    def __str__(self) -> str:
        s = f"[{self.code}] {self.message}"
        if self.suggestion:
            s += f"\n  → {self.suggestion}"
        return s

@dataclass
class Success(Generic[T]):
    """Successful operation with optional warnings"""
    value: T
    warnings: List[ErrorInfo] = field(default_factory=list)
    
    @property
    def is_success(self) -> bool:
        return True
    
    def map(self, fn: Callable[[T], 'U']) -> 'Success[U]':
        """Transform the success value"""
        return Success(value=fn(self.value), warnings=self.warnings)

@dataclass
class Failure:
    """Failed operation with error info and optional partial data"""
    error: ErrorInfo
    partial_value: Optional[any] = None  # Salvageable data
    
    @property
    def is_success(self) -> bool:
        return False

Result = Union[Success[T], Failure]

# ============================================================================
# Validated Input Types
# ============================================================================

@dataclass(frozen=True)
class ValidatedPrompt:
    """A prompt that has passed all validation - immutable guarantee"""
    text: str
    word_count: int
    
    @classmethod
    def validate(cls, raw_input: str) -> Result['ValidatedPrompt']:
        """Validate and sanitize user prompt"""
        if not raw_input:
            return Failure(ErrorInfo(
                code="EMPTY_PROMPT",
                message="Prompt cannot be empty",
                severity=ErrorSeverity.FATAL,
                suggestion="Provide a task description, e.g., 'Design a REST API for user management'"
            ))
        
        # Sanitize
        text = raw_input.strip()
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = ''.join(c for c in text if c == '\n' or c == '\t' or ord(c) >= 32)
        
        warnings = []
        
        # Length validation
        MIN_LENGTH, MAX_LENGTH = 10, 50000
        
        if len(text) < MIN_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_SHORT",
                message=f"Prompt is too short ({len(text)} chars, minimum {MIN_LENGTH})",
                severity=ErrorSeverity.FATAL,
                suggestion="Provide more detail about the task"
            ))
        
        if len(text) > MAX_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_LONG",
                message=f"Prompt exceeds maximum length ({len(text)} > {MAX_LENGTH} chars)",
                severity=ErrorSeverity.FATAL,
                suggestion="Summarize or split into multiple tasks"
            ))
        
        # Quality warnings (non-blocking)
        word_count = len(text.split())
        if word_count < 5:
            warnings.append(ErrorInfo(
                code="PROMPT_VAGUE",
                message="Prompt may be too vague for a detailed design",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider adding requirements, constraints, or context"
            ))
        
        # Check for design-oriented language
        design_words = {'design', 'create', 'build', 'implement', 'add', 'develop', 'refactor', 'improve'}
        has_design_intent = any(word in text.lower() for word in design_words)
        if not has_design_intent:
            warnings.append(ErrorInfo(
                code="PROMPT_NO_ACTION",
                message="Prompt doesn't contain clear design intent",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider starting with 'Design...', 'Implement...', or 'Create...'"
            ))
        
        return Success(value=cls(text=text, word_count=word_count), warnings=warnings)

@dataclass(frozen=True)
class ValidatedConfig:
    """Validated and normalized configuration"""
    max_rounds: int
    timeout_seconds: int
    working_dir: Path
    output_dir: Path
    verbose: bool
    quiet: bool
    
    @classmethod
    def validate(
        cls,
        max_rounds: int = 8,
        timeout: int = 300,
        working_dir: str = ".",
        output_dir: str = "./debate_output",
        verbose: bool = False,
        quiet: bool = False
    ) -> Result['ValidatedConfig']:
        """Validate all configuration parameters"""
        
        # max_rounds bounds
        if max_rounds < 1:
            return Failure(ErrorInfo(
                code="INVALID_ROUNDS",
                message=f"max_rounds must be at least 1 (got {max_rounds})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --max-rounds with a positive number"
            ))
        if max_rounds > 30:
            return Failure(ErrorInfo(
                code="ROUNDS_TOO_HIGH",
                message=f"max_rounds cannot exceed 30 (got {max_rounds})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use 30 or fewer rounds to avoid excessive API costs"
            ))
        
        # timeout bounds
        if timeout < 30:
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_LOW",
                message=f"Timeout must be at least 30 seconds (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --timeout 30 or higher"
            ))
        if timeout > 900:  # 15 minutes max
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_HIGH",
                message=f"Timeout cannot exceed 900 seconds (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --timeout 900 or lower"
            ))
        
        # Working directory validation
        wd = Path(working_dir).resolve()
        if not wd.exists():
            return Failure(ErrorInfo(
                code="WORKING_DIR_NOT_FOUND",
                message=f"Working directory does not exist: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Create the directory or specify an existing one with --working-dir"
            ))
        if not wd.is_dir():
            return Failure(ErrorInfo(
                code="WORKING_DIR_NOT_DIR",
                message=f"Path is not a directory: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Specify a directory path, not a file"
            ))
        if not os.access(wd, os.R_OK):
            return Failure(ErrorInfo(
                code="WORKING_DIR_NO_READ",
                message=f"Cannot read working directory: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check directory permissions"
            ))
        
        # Output directory - will create if needed
        od = Path(output_dir).resolve()
        if od.exists() and not od.is_dir():
            return Failure(ErrorInfo(
                code="OUTPUT_DIR_NOT_DIR",
                message=f"Output path exists but is not a directory: {od}",
                severity=ErrorSeverity.FATAL,
                suggestion="Remove the file or use a different --output path"
            ))
        
        warnings = []
        if max_rounds > 15:
            warnings.append(ErrorInfo(
                code="HIGH_ROUND_COUNT",
                message=f"High round count ({max_rounds}) may be slow and costly",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider starting with 8-10 rounds"
            ))
        
        if verbose and quiet:
            warnings.append(ErrorInfo(
                code="CONFLICTING_FLAGS",
                message="Both --verbose and --quiet specified; --verbose takes precedence",
                severity=ErrorSeverity.WARNING
            ))
        
        return Success(
            value=cls(
                max_rounds=max_rounds,
                timeout_seconds=timeout,
                working_dir=wd,
                output_dir=od,
                verbose=verbose,
                quiet=quiet and not verbose
            ),
            warnings=warnings
        )

# ============================================================================
# Session and Response Data Models
# ============================================================================

class ConvergenceStatus(Enum):
    DEBATING = "debating"
    CONVERGING = "converging"
    CONSENSUS = "consensus"
    INTERRUPTED = "interrupted"
    FAILED = "failed"

@dataclass
class AgentResponse:
    """Parsed response from an agent"""
    design_content: str        # The main design section
    prompt_for_other: str      # What they want the other agent to focus on
    convergence_signal: str    # ITERATING, PROPOSING_FINAL, ACCEPTING_FINAL
    raw_response: str          # Full unparsed response
    duration_seconds: float = 0.0
    parse_warnings: List[str] = field(default_factory=list)
    is_complete: bool = True   # False if response appears truncated

@dataclass
class DebateRound:
    """One complete round of debate"""
    round_number: int
    agent_a_response: Optional[AgentResponse] = None
    agent_b_response: Optional[AgentResponse] = None
    convergence_score: float = 0.0
    started_at: str = ""
    ended_at: str = ""
    duration_seconds: float = 0.0

@dataclass
class DebateSession:
    """Complete debate session state - fully serializable"""
    session_id: str
    initial_prompt: str
    config: dict                   # Serialized config for JSON
    rounds: List[DebateRound] = field(default_factory=list)
    status: ConvergenceStatus = ConvergenceStatus.DEBATING
    final_design: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str = ""
    error_log: List[str] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    
    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict"""
        return {
            'session_id': self.session_id,
            'initial_prompt': self.initial_prompt,
            'config': self.config,
            'rounds': [self._round_to_dict(r) for r in self.rounds],
            'status': self.status.value,
            'final_design': self.final_design,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'error_log': self.error_log,
            'total_duration_seconds': self.total_duration_seconds
        }
    
    def _round_to_dict(self, r: DebateRound) -> dict:
        d = {
            'round_number': r.round_number,
            'convergence_score': r.convergence_score,
            'started_at': r.started_at,
            'ended_at': r.ended_at,
            'duration_seconds': r.duration_seconds
        }
        if r.agent_a_response:
            d['agent_a'] = {
                'design_content': r.agent_a_response.design_content,
                'prompt_for_other': r.agent_a_response.prompt_for_other,
                'convergence_signal': r.agent_a_response.convergence_signal,
                'raw_response': r.agent_a_response.raw_response,
                'duration_seconds': r.agent_a_response.duration_seconds,
                'is_complete': r.agent_a_response.is_complete
            }
        if r.agent_b_response:
            d['agent_b'] = {
                'design_content': r.agent_b_response.design_content,
                'prompt_for_other': r.agent_b_response.prompt_for_other,
                'convergence_signal': r.agent_b_response.convergence_signal,
                'raw_response': r.agent_b_response.raw_response,
                'duration_seconds': r.agent_b_response.duration_seconds,
                'is_complete': r.agent_b_response.is_complete
            }
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DebateSession':
        """Deserialize with tolerance for missing/malformed data"""
        session = cls(
            session_id=data.get('session_id', 'unknown'),
            initial_prompt=data.get('initial_prompt', ''),
            config=data.get('config', {}),
            status=ConvergenceStatus(data.get('status', 'debating')),
            final_design=data.get('final_design', ''),
            started_at=data.get('started_at', ''),
            ended_at=data.get('ended_at', ''),
            error_log=data.get('error_log', []),
            total_duration_seconds=data.get('total_duration_seconds', 0.0)
        )
        
        for r_data in data.get('rounds', []):
            round_obj = DebateRound(
                round_number=r_data.get('round_number', 0),
                convergence_score=r_data.get('convergence_score', 0.0),
                started_at=r_data.get('started_at', ''),
                ended_at=r_data.get('ended_at', ''),
                duration_seconds=r_data.get('duration_seconds', 0.0)
            )
            if 'agent_a' in r_data:
                a = r_data['agent_a']
                round_obj.agent_a_response = AgentResponse(
                    design_content=a.get('design_content', ''),
                    prompt_for_other=a.get('prompt_for_other', ''),
                    convergence_signal=a.get('convergence_signal', 'ITERATING'),
                    raw_response=a.get('raw_response', ''),
                    duration_seconds=a.get('duration_seconds', 0.0),
                    is_complete=a.get('is_complete', True)
                )
            if 'agent_b' in r_data:
                b = r_data['agent_b']
                round_obj.agent_b_response = AgentResponse(
                    design_content=b.get('design_content', ''),
                    prompt_for_other=b.get('prompt_for_other', ''),
                    convergence_signal=b.get('convergence_signal', 'ITERATING'),
                    raw_response=b.get('raw_response', ''),
                    duration_seconds=b.get('duration_seconds', 0.0),
                    is_complete=b.get('is_complete', True)
                )
            session.rounds.append(round_obj)
        
        return session
```

### 3. ClaudeInvoker - Robust CLI Wrapper

```python
import subprocess
import time
import shutil

class ClaudeInvoker:
    """
    Robust wrapper for Claude CLI calls.
    
    Design decisions:
    - Retry with exponential backoff for transient failures
    - Clear error classification for appropriate recovery
    - Timeout monitoring with clean process termination
    - Response completeness detection
    - NO circuit breaker - agreed it's overkill for interactive CLI
    """
    
    # Error classification
    ERROR_CODES = {
        'timeout': 'CLI_TIMEOUT',
        'rate': 'RATE_LIMITED',
        'auth': 'AUTH_FAILED',
        'network': 'NETWORK_ERROR',
        'not_found': 'CLI_NOT_FOUND',
        'truncated': 'RESPONSE_TRUNCATED',
        'unknown': 'CLI_ERROR'
    }
    
    # Expected structural markers for completeness check
    COMPLETENESS_MARKERS = {
        'agent_a': ['### Design', 'PROMPT_FOR_CRITIC:'],
        'agent_b': ['### Design', 'PROMPT_FOR_ARCHITECT:']
    }
    
    def __init__(
        self,
        timeout: int = 300,
        max_retries: int = 2,
        on_progress: Optional[Callable[[str], None]] = None
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.on_progress = on_progress or (lambda x: None)
    
    def check_available(self) -> Result[str]:
        """Verify Claude CLI is installed, accessible, and authenticated"""
        # Check if claude is in PATH
        if not shutil.which('claude'):
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['not_found'],
                message="Claude CLI not found in PATH",
                severity=ErrorSeverity.FATAL,
                suggestion="Install Claude CLI: npm install -g @anthropic-ai/claude-code"
            ))
        
        try:
            result = subprocess.run(
                ['claude', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                version = result.stdout.strip()
                return Success(value=version)
            else:
                return Failure(ErrorInfo(
                    code=self.ERROR_CODES['unknown'],
                    message=f"Claude CLI error: {result.stderr.strip()}",
                    severity=ErrorSeverity.FATAL,
                    suggestion="Run 'claude --help' to verify installation"
                ))
        except subprocess.TimeoutExpired:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['timeout'],
                message="Claude CLI version check timed out",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Check your network connection"
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['unknown'],
                message=f"Unexpected error: {str(e)}",
                severity=ErrorSeverity.FATAL
            ))
    
    def invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: Path,
        agent_type: str = 'agent_a'
    ) -> Result[str]:
        """
        Call Claude CLI with retry logic.
        
        Returns Success with response, or Failure with classified error.
        Retries on transient failures with exponential backoff.
        """
        last_error: Optional[ErrorInfo] = None
        
        for attempt in range(1, self.max_retries + 1):
            result = self._single_invoke(system_prompt, user_prompt, working_dir, agent_type)
            
            if isinstance(result, Success):
                return result
            
            last_error = result.error
            
            # Don't retry fatal errors
            if last_error.severity == ErrorSeverity.FATAL:
                return result
            
            # Retry with exponential backoff
            if attempt < self.max_retries:
                wait_time = 5 * (2 ** (attempt - 1))  # 5s, 10s, 20s...
                self.on_progress(f"Retrying in {wait_time}s... ({last_error.message})")
                time.sleep(wait_time)
        
        return Failure(last_error)
    
    def _single_invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: Path,
        agent_type: str
    ) -> Result[str]:
        """Execute a single Claude CLI call with monitoring"""
        start_time = time.time()
        process = None
        
        try:
            process = subprocess.Popen(
                [
                    'claude',
                    '--print',
                    '--system-prompt', system_prompt,
                    '--output-format', 'text',
                    '--dangerously-skip-permissions'
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(working_dir),
                bufsize=1
            )
            
            # Send prompt and close stdin
            process.stdin.write(user_prompt)
            process.stdin.close()
            
            # Collect output with timeout monitoring
            output_lines = []
            last_progress_time = start_time
            progress_interval = 15  # seconds
            
            while True:
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > self.timeout:
                    process.kill()
                    process.wait(timeout=5)
                    return Failure(ErrorInfo(
                        code=self.ERROR_CODES['timeout'],
                        message=f"Request timed out after {int(elapsed)}s",
                        severity=ErrorSeverity.RECOVERABLE,
                        suggestion="Try increasing --timeout or simplifying the prompt",
                        context={'timeout': self.timeout, 'lines_received': len(output_lines)}
                    ))
                
                # Report progress periodically
                if time.time() - last_progress_time > progress_interval:
                    self.on_progress(f"Still working... ({int(elapsed)}s, {len(output_lines)} lines)")
                    last_progress_time = time.time()
                
                # Read output (non-blocking check via poll)
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line.rstrip('\n'))
            
            # Get any remaining stderr
            stderr = process.stderr.read()
            duration = time.time() - start_time
            
            # Check exit code
            if process.returncode != 0:
                return Failure(self._classify_error(stderr, process.returncode))
            
            content = '\n'.join(output_lines).strip()
            
            # Check for empty response
            if not content:
                return Failure(ErrorInfo(
                    code='EMPTY_RESPONSE',
                    message="Claude returned an empty response",
                    severity=ErrorSeverity.RECOVERABLE,
                    suggestion="Try rephrasing your prompt or check API status"
                ))
            
            # Check for response completeness
            warnings = []
            completeness = self._check_completeness(content, agent_type)
            if not completeness['is_complete']:
                warnings.append(ErrorInfo(
                    code=self.ERROR_CODES['truncated'],
                    message=f"Response may be truncated: missing {completeness['missing']}",
                    severity=ErrorSeverity.WARNING,
                    suggestion="Response will be used but may need follow-up"
                ))
            
            return Success(value=content, warnings=warnings)
            
        except FileNotFoundError:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['not_found'],
                message="Claude CLI not found",
                severity=ErrorSeverity.FATAL,
                suggestion="Install Claude CLI first"
            ))
        except Exception as e:
            if process:
                try:
                    process.kill()
                    process.wait(timeout=5)
                except:
                    pass
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['unknown'],
                message=str(e),
                severity=ErrorSeverity.RECOVERABLE
            ))
    
    def _classify_error(self, stderr: str, returncode: int) -> ErrorInfo:
        """Classify error based on stderr content"""
        stderr_lower = stderr.lower()
        
        if 'timeout' in stderr_lower or 'timed out' in stderr_lower:
            return ErrorInfo(
                code=self.ERROR_CODES['timeout'],
                message="Request timed out",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Try again or increase timeout"
            )
        
        if 'rate limit' in stderr_lower or '429' in stderr:
            return ErrorInfo(
                code=self.ERROR_CODES['rate'],
                message="API rate limit exceeded",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Wait a moment and try again"
            )
        
        if any(kw in stderr_lower for kw in ['unauthorized', 'authentication', 'api key', '401']):
            return ErrorInfo(
                code=self.ERROR_CODES['auth'],
                message="Authentication failed",
                severity=ErrorSeverity.FATAL,
                suggestion="Run 'claude login' to re-authenticate"
            )
        
        if any(kw in stderr_lower for kw in ['connection', 'network', 'dns', 'econnrefused']):
            return ErrorInfo(
                code=self.ERROR_CODES['network'],
                message="Network connection failed",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Check your internet connection"
            )
        
        return ErrorInfo(
            code=self.ERROR_CODES['unknown'],
            message=stderr.strip() or f"CLI exited with code {returncode}",
            severity=ErrorSeverity.RECOVERABLE,
            suggestion="Check Claude CLI logs or try again"
        )
    
    def _check_completeness(self, response: str, agent_type: str) -> dict:
        """Check if response contains expected structural markers"""
        markers = self.COMPLETENESS_MARKERS.get(agent_type, [])
        missing = [m for m in markers if m not in response]
        return {
            'is_complete': len(missing) == 0,
            'missing': missing
        }
```

### 4. StateManager - Atomic Persistence with atexit

```python
import atexit
import tempfile

class StateManager:
    """
    Manages session state with atomic writes and cleanup.
    
    Design decisions:
    - Atomic writes via write-to-temp-then-rename
    - atexit-based cleanup (simpler than signal handlers)
    - Auto-save after each agent turn
    - Graceful handling of save failures (warn, don't crash)
    """
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.state_file = session_dir / "session_state.json"
        self._cleanup_registered = False
        self._active_marker = session_dir / ".active"
    
    def initialize(self) -> Result[bool]:
        """Create session directory and register cleanup"""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            
            # Check for stale active marker (indicates crash)
            if self._active_marker.exists():
                try:
                    marker_content = self._active_marker.read_text()
                    # Could add warning about previous incomplete session
                except:
                    pass
            
            # Write active marker
            self._active_marker.write_text(
                f"pid={os.getpid()}\nstarted={datetime.now().isoformat()}"
            )
            
            # Register cleanup on exit
            if not self._cleanup_registered:
                atexit.register(self._cleanup)
                self._cleanup_registered = True
            
            return Success(value=True)
            
        except PermissionError as e:
            return Failure(ErrorInfo(
                code="STATE_PERMISSION_ERROR",
                message=f"Cannot write to session directory: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check directory permissions or use --output with a writable path"
            ))
        except OSError as e:
            return Failure(ErrorInfo(
                code="STATE_DISK_ERROR",
                message=f"Disk error creating session directory: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check available disk space"
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code="STATE_INIT_ERROR",
                message=f"Failed to initialize state: {e}",
                severity=ErrorSeverity.FATAL
            ))
    
    def save(self, session: DebateSession) -> Result[bool]:
        """
        Save session state atomically.
        Write to temp file, then rename for crash safety.
        """
        try:
            data = session.to_dict()
            
            # Create temp file in same directory (ensures same filesystem for rename)
            fd, temp_path = tempfile.mkstemp(
                dir=self.session_dir,
                prefix=".state_tmp_",
                suffix=".json"
            )
            
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Atomic rename (POSIX guarantees atomicity on same filesystem)
                os.replace(temp_path, self.state_file)
                return Success(value=True)
                
            except Exception as e:
                # Clean up temp file on failure
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
                
        except Exception as e:
            # Save failures are warnings - session continues
            return Failure(ErrorInfo(
                code="STATE_SAVE_ERROR",
                message=f"Failed to save state: {e}",
                severity=ErrorSeverity.WARNING,
                suggestion="Session will continue but may not be fully resumable"
            ))
    
    def load(self) -> Result[DebateSession]:
        """Load session state with error handling"""
        if not self.state_file.exists():
            return Failure(ErrorInfo(
                code="STATE_NOT_FOUND",
                message=f"No session state found at {self.state_file}",
                severity=ErrorSeverity.FATAL,
                suggestion="Start a new session or check the session path"
            ))
        
        try:
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            session = DebateSession.from_dict(data)
            return Success(value=session)
            
        except json.JSONDecodeError as e:
            return Failure(ErrorInfo(
                code="STATE_CORRUPT",
                message=f"Session state file is corrupted: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="The session cannot be recovered. Start a new session."
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code="STATE_LOAD_ERROR",
                message=f"Failed to load state: {e}",
                severity=ErrorSeverity.FATAL
            ))
    
    def can_resume(self) -> Result[dict]:
        """Check if session is resumable and return status"""
        load_result = self.load()
        if isinstance(load_result, Failure):
            return load_result
        
        session = load_result.value
        
        if session.status == ConvergenceStatus.CONSENSUS:
            return Failure(ErrorInfo(
                code="SESSION_COMPLETE",
                message="Session already reached consensus",
                severity=ErrorSeverity.WARNING,
                suggestion="View results in the session directory or start a new session"
            ))
        
        if session.status == ConvergenceStatus.FAILED:
            return Failure(ErrorInfo(
                code="SESSION_FAILED",
                message="Previous session failed",
                severity=ErrorSeverity.WARNING,
                suggestion="Check error_log in session state or start a new session"
            ))
        
        return Success(value={
            'session_id': session.session_id,
            'rounds_completed': len(session.rounds),
            'status': session.status.value,
            'last_round': session.rounds[-1].round_number if session.rounds else 0
        })
    
    def _cleanup(self):
        """Clean up on exit - remove active marker"""
        try:
            if self._active_marker.exists():
                self._active_marker.unlink()
        except:
            pass  # Best effort
```

### 5. UserReporter - Clear, Actionable Feedback

```python
import sys

class UserReporter:
    """
    Provides clear, actionable user feedback with consistent formatting.
    
    Principles:
    - Every error includes what to do about it
    - Progress is visible but not overwhelming
    - Verbose mode adds debug context
    - Quiet mode shows only errors and final result
    """
    
    ICONS = {
        'success': '✓',
        'error': '✗',
        'warning': '⚠',
        'info': 'ℹ',
        'progress': '→',
        'agent_a': '🔵',
        'agent_b': '🟣',
        'time': '⏱',
        'consensus': '🤝'
    }
    
    def __init__(self, verbose: bool = False, quiet: bool = False, use_color: bool = True):
        self.verbose = verbose
        self.quiet = quiet
        self.use_color = use_color and sys.stdout.isatty()
    
    def _c(self, color: str, text: str) -> str:
        """Colorize text if enabled"""
        if not self.use_color:
            return text
        return f"{color}{text}{Colors.NC}"
    
    def success(self, message: str):
        if not self.quiet:
            print(f"{self._c(Colors.GREEN, self.ICONS['success'])} {message}")
    
    def error(self, error: ErrorInfo):
        """Report error with actionable suggestion"""
        print(f"{self._c(Colors.RED, self.ICONS['error'])} {error.message}", file=sys.stderr)
        if error.suggestion:
            print(f"  {self._c(Colors.YELLOW, '→')} {error.suggestion}", file=sys.stderr)
        if self.verbose and error.context:
            print(f"  {self._c(Colors.CYAN, 'Debug:')} {error.context}", file=sys.stderr)
    
    def warning(self, warning: ErrorInfo):
        if not self.quiet:
            print(f"{self._c(Colors.YELLOW, self.ICONS['warning'])} {warning.message}")
            if warning.suggestion:
                print(f"  → {warning.suggestion}")
    
    def info(self, message: str):
        if not self.quiet:
            print(f"{self._c(Colors.CYAN, self.ICONS['info'])} {message}")
    
    def progress(self, message: str, agent: str = None, round_num: int = None):
        """Show progress update with optional agent/round context"""
        if self.quiet:
            return
        
        parts = []
        if round_num is not None:
            parts.append(f"[R{round_num}]")
        if agent:
            icon = self.ICONS['agent_a'] if agent == 'A' else self.ICONS['agent_b']
            parts.append(icon)
        parts.append(self.ICONS['progress'])
        parts.append(message)
        
        print(' '.join(parts))
        sys.stdout.flush()
    
    def debug(self, message: str):
        """Debug info - only in verbose mode"""
        if self.verbose:
            print(f"{self._c(Colors.CYAN, '·')} {message}")
    
    def report_result(self, result: Result, action: str = "Operation"):
        """Report any Result with appropriate handling"""
        if isinstance(result, Success):
            for w in result.warnings:
                self.warning(w)
        else:
            self.error(result.error)
    
    def show_validation_summary(self, prompt_result: Result, config_result: Result):
        """Show validation results before starting debate"""
        all_errors = []
        all_warnings = []
        
        for result in [prompt_result, config_result]:
            if isinstance(result, Failure):
                all_errors.append(result.error)
            elif isinstance(result, Success):
                all_warnings.extend(result.warnings)
        
        if all_errors:
            print(f"\n{self._c(Colors.RED, 'Validation failed:')}")
            for e in all_errors:
                self.error(e)
            return False
        
        if all_warnings and not self.quiet:
            print()
            for w in all_warnings:
                self.warning(w)
        
        return True
    
    def show_round_summary(
        self,
        round_num: int,
        max_rounds: int,
        duration: float,
        convergence_score: float,
        agent_a_signal: str,
        agent_b_signal: str
    ):
        """Show summary after completing a round"""
        if self.quiet:
            return
        
        # Progress bar
        bar = "█" * int(convergence_score * 10) + "░" * (10 - int(convergence_score * 10))
        
        print(f"\n{'─' * 60}")
        print(f"Round {round_num}/{max_rounds} │ {self.ICONS['time']} {duration:.0f}s │ Similarity [{bar}] {convergence_score:.0%}")
        print(f"  Architect: {agent_a_signal}")
        print(f"  Reviewer:  {agent_b_signal}")
        
        # Convergence hint
        if convergence_score > 0.8:
            print(f"  {self._c(Colors.GREEN, '↗')} Designs converging - consensus likely")
        elif convergence_score > 0.5:
            print(f"  → Designs becoming more similar")
        else:
            print(f"  ↻ Designs still diverging")
        print(f"{'─' * 60}\n")
    
    def show_final_summary(self, session: DebateSession, session_dir: Path):
        """Show final session summary"""
        print(f"\n{'═' * 60}")
        print(f"{self._c(Colors.BOLD, '  DEBATE COMPLETE')}")
        print(f"{'═' * 60}")
        
        # Status with color
        status_display = {
            ConvergenceStatus.CONSENSUS: (Colors.GREEN, "CONSENSUS REACHED 🤝"),
            ConvergenceStatus.INTERRUPTED: (Colors.YELLOW, "INTERRUPTED (resumable)"),
            ConvergenceStatus.FAILED: (Colors.RED, "FAILED"),
            ConvergenceStatus.DEBATING: (Colors.YELLOW, "MAX ROUNDS REACHED")
        }
        color, label = status_display.get(session.status, (Colors.NC, session.status.value))
        
        print(f"  Status:    {self._c(color, label)}")
        print(f"  Rounds:    {len(session.rounds)}")
        print(f"  Duration:  {session.total_duration_seconds:.0f}s")
        print(f"  Session:   {session_dir}")
        
        print(f"\n  Output files:")
        print(f"    • {session_dir / 'final_design.md'}")
        print(f"    • {session_dir / 'debate_history.md'}")
        
        if session.status == ConvergenceStatus.CONSENSUS:
            print(f"\n  {self._c(Colors.CYAN, 'To implement:')} claude \"Implement this design: $(cat {session_dir / 'final_design.md'})\"")
        elif session.status == ConvergenceStatus.INTERRUPTED:
            print(f"\n  {self._c(Colors.YELLOW, 'To resume:')} debate --resume {session_dir}")
        
        print(f"{'═' * 60}\n")
```

### 6. Response Parser with Completeness Detection

```python
class ResponseParser:
    """Parse agent responses with validation and fallbacks"""
    
    @staticmethod
    def parse(response: str, is_agent_a: bool) -> AgentResponse:
        """Parse an agent's response into structured components"""
        
        prompt_marker = "PROMPT_FOR_CRITIC:" if is_agent_a else "PROMPT_FOR_ARCHITECT:"
        parse_warnings = []
        
        # Extract prompt for other agent
        prompt_for_other = ""
        if prompt_marker in response:
            parts = response.split(prompt_marker, 1)
            if len(parts) > 1:
                prompt_section = parts[1].strip()
                # Take until next section or end
                if "###" in prompt_section:
                    prompt_for_other = prompt_section.split("###")[0].strip()
                else:
                    prompt_for_other = prompt_section.strip()
        
        if not prompt_for_other:
            prompt_for_other = "Please review my response and continue the discussion."
            parse_warnings.append(f"Could not extract {prompt_marker} section")
        
        # Extract convergence signal
        convergence_signal = "ITERATING"
        if is_agent_a:
            if "PROPOSING_FINAL" in response:
                convergence_signal = "PROPOSING_FINAL"
        else:
            if "ACCEPTING_FINAL" in response:
                convergence_signal = "ACCEPTING_FINAL"
            elif "MINOR_ISSUES" in response:
                convergence_signal = "MINOR_ISSUES"
        
        # Extract design content
        design_content = ResponseParser._extract_design_section(response)
        if not design_content:
            parse_warnings.append("Could not extract ### Design section")
            design_content = response.split(prompt_marker)[0].strip() if prompt_marker in response else response
        
        # Check completeness
        is_complete = ResponseParser._check_structural_completeness(response, is_agent_a)
        
        return AgentResponse(
            design_content=design_content,
            prompt_for_other=prompt_for_other,
            convergence_signal=convergence_signal,
            raw_response=response,
            parse_warnings=parse_warnings,
            is_complete=is_complete
        )
    
    @staticmethod
    def _extract_design_section(response: str) -> str:
        """Extract the Design section from response"""
        lines = response.split('\n')
        design_lines = []
        in_design = False
        
        for line in lines:
            if line.strip().startswith('### Design') or line.strip().startswith('## Design'):
                in_design = True
                continue
            if in_design and (line.strip().startswith('### ') or line.strip().startswith('## ')):
                break
            if in_design:
                design_lines.append(line)
        
        return '\n'.join(design_lines).strip()
    
    @staticmethod
    def _check_structural_completeness(response: str, is_agent_a: bool) -> bool:
        """Check if response has expected structural markers"""
        required_markers = ['### Design']
        if is_agent_a:
            required_markers.append('PROMPT_FOR_CRITIC:')
        else:
            required_markers.append('PROMPT_FOR_ARCHITECT:')
        
        # Also check for convergence section
        required_markers.append('