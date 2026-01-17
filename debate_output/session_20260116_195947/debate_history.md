# Claude Code Debate Session

**Started:** 2026-01-16T19:59:47.224950
**Ended:** 2026-01-16T20:14:15.509539
**Status:** consensus
**Rounds:** 2

## Initial Prompt

Improve this Claude Code plugin (plan-with-debate) to make it more robust and user-friendly. Focus on: 1) Better error handling when Claude CLI fails or times out, 2) Clearer user feedback when things go wrong, 3) Input validation, 4) Edge cases like empty prompts or interrupted sessions. Review the current code and propose specific improvements.

---

## Round 1

### 🔵 Agent A

Now I have a complete picture of the codebase. Let me create a comprehensive design for improving this plugin's robustness and user experience.

---

## Design

### 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                       IMPROVED PLAN-WITH-DEBATE PLUGIN                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  Input Layer    │    │  Orchestration  │    │  Output Layer   │          │
│  │  - Validator    │───▶│  - Debate Loop  │───▶│  - Reporter     │          │
│  │  - Sanitizer    │    │  - State Mgr    │    │  - File Writer  │          │
│  │  - CLI Parser   │    │  - Error Recov. │    │  - Progress UI  │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│           │                     │                     │                      │
│           ▼                     ▼                     ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                     Claude CLI Adapter                           │        │
│  │  - Retry Logic    - Timeout Handler    - Health Check           │        │
│  │  - Circuit Breaker - Connection Pool   - Response Validator     │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                     Error & Recovery Layer                       │        │
│  │  - Graceful Degradation  - Auto-Save  - User Notification       │        │
│  │  - Signal Handlers       - Cleanup    - Recovery Strategies     │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2. Components

#### 2.1 Input Validator (`InputValidator`)

```python
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
import re

class ValidationError(Exception):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: str, suggestion: str = ""):
        self.message = message
        self.field = field
        self.suggestion = suggestion
        super().__init__(f"{field}: {message}")

class ValidationSeverity(Enum):
    ERROR = "error"      # Cannot proceed
    WARNING = "warning"  # Can proceed with caution
    INFO = "info"        # Informational

@dataclass
class ValidationResult:
    is_valid: bool
    severity: ValidationSeverity
    message: str
    field: str
    suggestion: str = ""

class InputValidator:
    """Validates and sanitizes all user inputs"""
    
    MIN_PROMPT_LENGTH = 10
    MAX_PROMPT_LENGTH = 50000
    MIN_ROUNDS = 1
    MAX_ROUNDS = 50
    DANGEROUS_PATTERNS = [
        r'rm\s+-rf\s+/',         # Dangerous file deletion
        r'>\s*/dev/sd',          # Direct disk writes
        r':\(\)\{:|:&\};:',      # Fork bomb
    ]
    
    def validate_prompt(self, prompt: str) -> List[ValidationResult]:
        """Validate the initial debate prompt"""
        results = []
        
        # Check for empty/whitespace-only
        if not prompt or not prompt.strip():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="Prompt cannot be empty",
                field="prompt",
                suggestion="Provide a clear design task description"
            ))
            return results
            
        prompt = prompt.strip()
        
        # Check minimum length
        if len(prompt) < self.MIN_PROMPT_LENGTH:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Prompt too short ({len(prompt)} chars, minimum {self.MIN_PROMPT_LENGTH})",
                field="prompt",
                suggestion="Provide more detail about the design task"
            ))
            
        # Check maximum length
        if len(prompt) > self.MAX_PROMPT_LENGTH:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Prompt too long ({len(prompt)} chars, maximum {self.MAX_PROMPT_LENGTH})",
                field="prompt",
                suggestion="Consider splitting into smaller tasks or summarizing"
            ))
            
        # Check for dangerous patterns (warning only)
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, prompt, re.IGNORECASE):
                results.append(ValidationResult(
                    is_valid=True,  # Allow but warn
                    severity=ValidationSeverity.WARNING,
                    message="Prompt contains potentially dangerous commands",
                    field="prompt",
                    suggestion="Review prompt to ensure it's safe for AI execution"
                ))
                break
                
        # Check for clarity indicators (info)
        clarity_keywords = ['design', 'create', 'build', 'implement', 'develop', 'plan']
        has_clarity = any(kw in prompt.lower() for kw in clarity_keywords)
        if not has_clarity:
            results.append(ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.INFO,
                message="Prompt may lack clear action words",
                field="prompt",
                suggestion="Consider starting with: 'Design...', 'Create...', or 'Build...'"
            ))
            
        # If no errors found, mark as valid
        if not any(r.severity == ValidationSeverity.ERROR for r in results):
            if not results:
                results.append(ValidationResult(
                    is_valid=True,
                    severity=ValidationSeverity.INFO,
                    message="Prompt validation passed",
                    field="prompt"
                ))
                
        return results
    
    def validate_rounds(self, max_rounds: int) -> List[ValidationResult]:
        """Validate max_rounds parameter"""
        results = []
        
        if max_rounds < self.MIN_ROUNDS:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"max_rounds must be at least {self.MIN_ROUNDS}",
                field="max_rounds",
                suggestion=f"Use --max-rounds {self.MIN_ROUNDS} or higher"
            ))
        elif max_rounds > self.MAX_ROUNDS:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"max_rounds cannot exceed {self.MAX_ROUNDS}",
                field="max_rounds",
                suggestion=f"Use --max-rounds {self.MAX_ROUNDS} or lower"
            ))
        elif max_rounds > 15:
            results.append(ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                message=f"High round count ({max_rounds}) may take a long time",
                field="max_rounds",
                suggestion="Consider starting with 5-10 rounds"
            ))
            
        return results
    
    def validate_working_dir(self, path: str) -> List[ValidationResult]:
        """Validate working directory exists and is accessible"""
        from pathlib import Path
        import os
        
        results = []
        p = Path(path)
        
        if not p.exists():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Working directory does not exist: {path}",
                field="working_dir",
                suggestion="Create the directory or specify an existing one"
            ))
        elif not p.is_dir():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Path is not a directory: {path}",
                field="working_dir",
                suggestion="Specify a directory, not a file"
            ))
        elif not os.access(path, os.R_OK | os.W_OK):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Insufficient permissions for directory: {path}",
                field="working_dir",
                suggestion="Check read/write permissions"
            ))
            
        return results
    
    def validate_file(self, path: str) -> List[ValidationResult]:
        """Validate prompt file exists and is readable"""
        from pathlib import Path
        import os
        
        results = []
        p = Path(path)
        
        if not p.exists():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"File does not exist: {path}",
                field="file",
                suggestion="Check the file path and try again"
            ))
        elif not p.is_file():
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Path is not a file: {path}",
                field="file",
                suggestion="Specify a file, not a directory"
            ))
        elif not os.access(path, os.R_OK):
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"Cannot read file: {path}",
                field="file",
                suggestion="Check file permissions"
            ))
        elif p.stat().st_size == 0:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message=f"File is empty: {path}",
                field="file",
                suggestion="Add content to the prompt file"
            ))
        elif p.stat().st_size > 1_000_000:  # 1MB
            results.append(ValidationResult(
                is_valid=True,
                severity=ValidationSeverity.WARNING,
                message=f"File is very large ({p.stat().st_size} bytes)",
                field="file",
                suggestion="Large prompts may cause issues; consider summarizing"
            ))
            
        return results
    
    def sanitize_prompt(self, prompt: str) -> str:
        """Clean and normalize the prompt"""
        if not prompt:
            return ""
            
        # Strip leading/trailing whitespace
        prompt = prompt.strip()
        
        # Normalize line endings
        prompt = prompt.replace('\r\n', '\n').replace('\r', '\n')
        
        # Remove excessive whitespace (more than 2 consecutive newlines)
        import re
        prompt = re.sub(r'\n{3,}', '\n\n', prompt)
        
        # Remove null bytes and other control characters (except newline, tab)
        prompt = ''.join(c for c in prompt if c == '\n' or c == '\t' or (ord(c) >= 32))
        
        return prompt
```

#### 2.2 Claude CLI Adapter (`ClaudeCLIAdapter`)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Callable
import subprocess
import time
import os

class CLIErrorType(Enum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    INVALID_RESPONSE = "invalid_response"
    PROCESS_CRASH = "process_crash"
    UNKNOWN = "unknown"

@dataclass
class CLIError:
    error_type: CLIErrorType
    message: str
    is_retryable: bool
    suggested_action: str
    raw_error: str = ""

@dataclass
class CLIResponse:
    success: bool
    content: str
    error: Optional[CLIError] = None
    duration_seconds: float = 0.0
    retry_count: int = 0

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered

@dataclass
class CircuitBreaker:
    """Prevents cascading failures when Claude CLI is consistently failing"""
    failure_threshold: int = 3
    recovery_timeout: int = 60  # seconds
    
    _failure_count: int = 0
    _last_failure_time: float = 0
    _state: CircuitState = CircuitState.CLOSED
    
    def record_success(self):
        self._failure_count = 0
        self._state = CircuitState.CLOSED
        
    def record_failure(self):
        self._failure_count += 1
        self._last_failure_time = time.time()
        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            
    def can_execute(self) -> bool:
        if self._state == CircuitState.CLOSED:
            return True
        elif self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if time.time() - self._last_failure_time >= self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                return True
            return False
        else:  # HALF_OPEN
            return True
            
    def get_wait_time(self) -> int:
        """Returns seconds until circuit breaker might allow execution"""
        if self._state != CircuitState.OPEN:
            return 0
        elapsed = time.time() - self._last_failure_time
        return max(0, int(self.recovery_timeout - elapsed))

class ClaudeCLIAdapter:
    """Robust wrapper for Claude CLI with retry logic and error handling"""
    
    DEFAULT_TIMEOUT = 300  # 5 minutes
    MAX_RETRIES = 3
    RETRY_DELAYS = [5, 15, 30]  # Exponential backoff
    
    def __init__(
        self,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        on_progress: Optional[Callable[[str], None]] = None
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.on_progress = on_progress
        self.circuit_breaker = CircuitBreaker()
        
    def health_check(self) -> CLIResponse:
        """Verify Claude CLI is installed and authenticated"""
        try:
            # Check if claude command exists
            result = subprocess.run(
                ['which', 'claude'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                return CLIResponse(
                    success=False,
                    content="",
                    error=CLIError(
                        error_type=CLIErrorType.CONNECTION,
                        message="Claude CLI not found",
                        is_retryable=False,
                        suggested_action="Install Claude CLI: https://docs.anthropic.com/claude-code/getting-started"
                    )
                )
            
            # Check authentication with a minimal call
            result = subprocess.run(
                ['claude', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return CLIResponse(
                success=True,
                content=result.stdout.strip()
            )
            
        except subprocess.TimeoutExpired:
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.TIMEOUT,
                    message="Health check timed out",
                    is_retryable=True,
                    suggested_action="Check your network connection"
                )
            )
        except Exception as e:
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.UNKNOWN,
                    message=str(e),
                    is_retryable=False,
                    suggested_action="Check Claude CLI installation"
                )
            )
    
    def _classify_error(self, stderr: str, returncode: int) -> CLIError:
        """Classify error from Claude CLI output"""
        stderr_lower = stderr.lower()
        
        if 'timeout' in stderr_lower or 'timed out' in stderr_lower:
            return CLIError(
                error_type=CLIErrorType.TIMEOUT,
                message="Request timed out",
                is_retryable=True,
                suggested_action="The request took too long. It will be retried automatically.",
                raw_error=stderr
            )
        elif 'rate limit' in stderr_lower or '429' in stderr:
            return CLIError(
                error_type=CLIErrorType.RATE_LIMIT,
                message="Rate limit exceeded",
                is_retryable=True,
                suggested_action="Too many requests. Waiting before retry.",
                raw_error=stderr
            )
        elif 'unauthorized' in stderr_lower or 'authentication' in stderr_lower or '401' in stderr:
            return CLIError(
                error_type=CLIErrorType.AUTHENTICATION,
                message="Authentication failed",
                is_retryable=False,
                suggested_action="Run 'claude login' to re-authenticate",
                raw_error=stderr
            )
        elif 'connection' in stderr_lower or 'network' in stderr_lower or 'econnrefused' in stderr_lower:
            return CLIError(
                error_type=CLIErrorType.CONNECTION,
                message="Connection failed",
                is_retryable=True,
                suggested_action="Check your network connection",
                raw_error=stderr
            )
        elif returncode == -9 or returncode == -15 or 'killed' in stderr_lower:
            return CLIError(
                error_type=CLIErrorType.PROCESS_CRASH,
                message="Process was terminated",
                is_retryable=True,
                suggested_action="The process crashed. Retrying.",
                raw_error=stderr
            )
        else:
            return CLIError(
                error_type=CLIErrorType.UNKNOWN,
                message=stderr or f"Unknown error (exit code {returncode})",
                is_retryable=True,  # Assume retryable for unknown errors
                suggested_action="An unexpected error occurred. Retrying.",
                raw_error=stderr
            )
    
    def call(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> CLIResponse:
        """Call Claude CLI with full error handling and retry logic"""
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            wait_time = self.circuit_breaker.get_wait_time()
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.CONNECTION,
                    message=f"Circuit breaker open. Too many recent failures.",
                    is_retryable=False,
                    suggested_action=f"Wait {wait_time}s before retrying, or check Claude CLI status"
                )
            )
        
        last_error: Optional[CLIError] = None
        start_time = time.time()
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self._execute_call(
                    system_prompt, user_prompt, working_dir, stream_callback
                )
                
                if response.success:
                    self.circuit_breaker.record_success()
                    response.duration_seconds = time.time() - start_time
                    response.retry_count = attempt
                    return response
                    
                last_error = response.error
                
                # Don't retry non-retryable errors
                if not last_error.is_retryable:
                    self.circuit_breaker.record_failure()
                    return response
                
                # Wait before retry
                if attempt < self.max_retries:
                    delay = self.RETRY_DELAYS[min(attempt, len(self.RETRY_DELAYS) - 1)]
                    if self.on_progress:
                        self.on_progress(f"Retry {attempt + 1}/{self.max_retries} in {delay}s: {last_error.message}")
                    time.sleep(delay)
                    
            except KeyboardInterrupt:
                return CLIResponse(
                    success=False,
                    content="",
                    error=CLIError(
                        error_type=CLIErrorType.PROCESS_CRASH,
                        message="Interrupted by user",
                        is_retryable=False,
                        suggested_action="Use --resume to continue later"
                    ),
                    duration_seconds=time.time() - start_time
                )
        
        self.circuit_breaker.record_failure()
        return CLIResponse(
            success=False,
            content="",
            error=last_error or CLIError(
                error_type=CLIErrorType.UNKNOWN,
                message="All retries exhausted",
                is_retryable=False,
                suggested_action="Check Claude CLI status and try again"
            ),
            duration_seconds=time.time() - start_time,
            retry_count=self.max_retries
        )
    
    def _execute_call(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: str,
        stream_callback: Optional[Callable[[str], None]] = None
    ) -> CLIResponse:
        """Execute a single call to Claude CLI"""
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
                cwd=working_dir,
                bufsize=1
            )
            
            # Send prompt
            process.stdin.write(user_prompt)
            process.stdin.close()
            
            # Collect output with streaming
            output_lines = []
            start_time = time.time()
            
            while True:
                # Check timeout
                if time.time() - start_time > self.timeout:
                    process.kill()
                    return CLIResponse(
                        success=False,
                        content='\n'.join(output_lines),
                        error=CLIError(
                            error_type=CLIErrorType.TIMEOUT,
                            message=f"Request timed out after {self.timeout}s",
                            is_retryable=True,
                            suggested_action="Consider increasing timeout with longer prompts"
                        )
                    )
                
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line.rstrip('\n'))
                    if stream_callback:
                        stream_callback(line.rstrip('\n'))
            
            stderr = process.stderr.read()
            
            if process.returncode != 0:
                return CLIResponse(
                    success=False,
                    content='\n'.join(output_lines),
                    error=self._classify_error(stderr, process.returncode)
                )
            
            content = '\n'.join(output_lines).strip()
            
            # Validate response isn't empty
            if not content:
                return CLIResponse(
                    success=False,
                    content="",
                    error=CLIError(
                        error_type=CLIErrorType.INVALID_RESPONSE,
                        message="Empty response from Claude",
                        is_retryable=True,
                        suggested_action="Retrying request"
                    )
                )
            
            return CLIResponse(success=True, content=content)
            
        except subprocess.TimeoutExpired:
            process.kill()
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.TIMEOUT,
                    message=f"Process timed out after {self.timeout}s",
                    is_retryable=True,
                    suggested_action="The request is taking too long"
                )
            )
        except FileNotFoundError:
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.CONNECTION,
                    message="Claude CLI not found",
                    is_retryable=False,
                    suggested_action="Install Claude CLI first"
                )
            )
        except Exception as e:
            return CLIResponse(
                success=False,
                content="",
                error=CLIError(
                    error_type=CLIErrorType.UNKNOWN,
                    message=str(e),
                    is_retryable=True,
                    suggested_action="Unexpected error occurred"
                )
            )
```

#### 2.3 Session Manager with Auto-Recovery (`SessionManager`)

```python
import signal
import atexit
from pathlib import Path
from datetime import datetime
import json
import os
from typing import Optional
from enum import Enum

class SessionState(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"

@dataclass  
class CheckpointData:
    """Data saved at each checkpoint for recovery"""
    round_number: int
    agent_turn: str  # "agent_a" or "agent_b"
    completed: bool
    response_data: Optional[dict]
    timestamp: str

class SessionManager:
    """Manages session lifecycle with auto-save and recovery"""
    
    CHECKPOINT_INTERVAL = 1  # Save after every agent turn
    LOCK_FILE_NAME = ".debate_lock"
    
    def __init__(self, session_dir: Path, auto_save: bool = True):
        self.session_dir = Path(session_dir)
        self.auto_save = auto_save
        self.state = SessionState.INITIALIZING
        self._lock_file: Optional[Path] = None
        self._cleanup_registered = False
        self._original_sigint = None
        self._original_sigterm = None
        
    def initialize(self) -> bool:
        """Initialize session with proper locking and signal handling"""
        # Create session directory
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Check for existing lock (another session running in this dir)
        self._lock_file = self.session_dir / self.LOCK_FILE_NAME
        if self._lock_file.exists():
            try:
                with open(self._lock_file, 'r') as f:
                    lock_data = json.load(f)
                pid = lock_data.get('pid')
                # Check if process is still running
                if pid and self._is_process_running(pid):
                    return False  # Another session is active
            except (json.JSONDecodeError, IOError):
                pass  # Stale lock file, remove it
            self._lock_file.unlink(missing_ok=True)
        
        # Create lock file
        with open(self._lock_file, 'w') as f:
            json.dump({
                'pid': os.getpid(),
                'started_at': datetime.now().isoformat()
            }, f)
        
        # Register cleanup
        self._register_cleanup()
        
        self.state = SessionState.RUNNING
        return True
    
    def _is_process_running(self, pid: int) -> bool:
        """Check if a process is still running"""
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False
    
    def _register_cleanup(self):
        """Register signal handlers and atexit for cleanup"""
        if self._cleanup_registered:
            return
            
        # Save original handlers
        self._original_sigint = signal.getsignal(signal.SIGINT)
        self._original_sigterm = signal.getsignal(signal.SIGTERM)
        
        # Register our handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        atexit.register(self._cleanup)
        
        self._cleanup_registered = True
    
    def _signal_handler(self, signum, frame):
        """Handle interruption signals gracefully"""
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        print(f"\n\n{Colors.YELLOW}⚠ Received {signal_name}. Saving session state...{Colors.NC}")
        
        self.state = SessionState.INTERRUPTED
        self._save_interrupt_state()
        self._cleanup()
        
        # Call original handler or exit
        if signum == signal.SIGINT and self._original_sigint:
            if callable(self._original_sigint):
                self._original_sigint(signum, frame)
        
        print(f"{Colors.GREEN}Session saved. Use --resume to continue.{Colors.NC}\n")
        raise SystemExit(130)  # Standard exit code for SIGINT
    
    def _save_interrupt_state(self):
        """Save state when interrupted"""
        state_file = self.session_dir / "session_state.json"
        if state_file.exists():
            with open(state_file, 'r') as f:
                state = json.load(f)
            state['status'] = SessionState.INTERRUPTED.value
            state['interrupted_at'] = datetime.now().isoformat()
            with open(state_file, 'w') as f:
                json.dump(state, f, indent=2)
    
    def _cleanup(self):
        """Clean up resources"""
        # Remove lock file
        if self._lock_file and self._lock_file.exists():
            try:
                self._lock_file.unlink()
            except IOError:
                pass
        
        # Restore signal handlers
        if self._original_sigint:
            signal.signal(signal.SIGINT, self._original_sigint)
        if self._original_sigterm:
            signal.signal(signal.SIGTERM, self._original_sigterm)
    
    def checkpoint(self, checkpoint_data: CheckpointData):
        """Save a checkpoint for recovery"""
        if not self.auto_save:
            return
            
        checkpoint_file = self.session_dir / "checkpoint.json"
        with open(checkpoint_file, 'w') as f:
            json.dump({
                'round_number': checkpoint_data.round_number,
                'agent_turn': checkpoint_data.agent_turn,
                'completed': checkpoint_data.completed,
                'response_data': checkpoint_data.response_data,
                'timestamp': checkpoint_data.timestamp
            }, f, indent=2)
    
    def get_last_checkpoint(self) -> Optional[CheckpointData]:
        """Retrieve the last checkpoint for recovery"""
        checkpoint_file = self.session_dir / "checkpoint.json"
        if not checkpoint_file.exists():
            return None
            
        try:
            with open(checkpoint_file, 'r') as f:
                data = json.load(f)
            return CheckpointData(**data)
        except (json.JSONDecodeError, IOError, TypeError):
            return None
    
    def mark_completed(self, success: bool = True):
        """Mark session as completed"""
        self.state = SessionState.COMPLETED if success else SessionState.FAILED
        self._cleanup()
    
    def get_recovery_info(self) -> dict:
        """Get information about what can be recovered"""
        checkpoint = self.get_last_checkpoint()
        state_file = self.session_dir / "session_state.json"
        
        info = {
            'can_resume': False,
            'last_round': 0,
            'last_agent': None,
            'status': None
        }
        
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                info['status'] = state.get('status')
                info['last_round'] = state.get('current_round', 0)
                info['can_resume'] = state.get('status') not in ['consensus', 'completed']
            except (json.JSONDecodeError, IOError):
                pass
        
        if checkpoint:
            info['last_agent'] = checkpoint.agent_turn
            info['can_resume'] = not checkpoint.completed or info['can_resume']
            
        return info
```

#### 2.4 Progress Reporter (`ProgressReporter`)

```python
import sys
from enum import Enum
from typing import Optional, List
from dataclasses import dataclass

class MessageType(Enum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    PROGRESS = "progress"
    DEBUG = "debug"

@dataclass
class ProgressUpdate:
    message: str
    message_type: MessageType
    agent: Optional[str] = None
    round_number: Optional[int] = None
    percentage: Optional[float] = None

class ProgressReporter:
    """Provides clear, consistent user feedback"""
    
    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.verbose = verbose
        self.quiet = quiet
        self._spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
        self._spinner_index = 0
        self._current_status_line = ""
        
    def _get_color(self, msg_type: MessageType) -> str:
        colors = {
            MessageType.INFO: Colors.CYAN,
            MessageType.SUCCESS: Colors.GREEN,
            MessageType.WARNING: Colors.YELLOW,
            MessageType.ERROR: Colors.RED,
            MessageType.PROGRESS: Colors.BLUE,
            MessageType.DEBUG: '\033[90m'  # Gray
        }
        return colors.get(msg_type, Colors.NC)
    
    def _get_icon(self, msg_type: MessageType) -> str:
        icons = {
            MessageType.INFO: 'ℹ',
            MessageType.SUCCESS: '✓',
            MessageType.WARNING: '⚠',
            MessageType.ERROR: '✗',
            MessageType.PROGRESS: '→',
            MessageType.DEBUG: '·'
        }
        return icons.get(msg_type, '')
    
    def report(self, update: ProgressUpdate):
        """Report a progress update to the user"""
        if self.quiet and update.message_type not in [MessageType.ERROR, MessageType.WARNING]:
            return
        if update.message_type == MessageType.DEBUG and not self.verbose:
            return
            
        color = self._get_color(update.message_type)
        icon = self._get_icon(update.message_type)
        
        prefix = ""
        if update.agent:
            agent_icon = "🔵" if update.agent == "Agent A" else "🟣"
            prefix = f"{agent_icon} "
        if update.round_number:
            prefix += f"[R{update.round_number}] "
            
        message = f"{color}{icon} {prefix}{update.message}{Colors.NC}"
        print(message)
    
    def start_spinner(self, message: str):
        """Start a spinner for long-running operations"""
        self._current_status_line = message
        self._update_spinner()
    
    def _update_spinner(self):
        """Update spinner animation"""
        if not self._current_status_line:
            return
        frame = self._spinner_frames[self._spinner_index]
        self._spinner_index = (self._spinner_index + 1) % len(self._spinner_frames)
        sys.stdout.write(f"\r{Colors.CYAN}{frame} {self._current_status_line}{Colors.NC}")
        sys.stdout.flush()
    
    def stop_spinner(self, final_message: str = "", success: bool = True):
        """Stop spinner and show final message"""
        sys.stdout.write("\r" + " " * (len(self._current_status_line) + 5) + "\r")
        self._current_status_line = ""
        if final_message:
            msg_type = MessageType.SUCCESS if success else MessageType.ERROR
            self.report(ProgressUpdate(message=final_message, message_type=msg_type))
    
    def report_error(self, error: CLIError, context: str = ""):
        """Report a CLI error with helpful context"""
        self.report(ProgressUpdate(
            message=f"{context}: {error.message}" if context else error.message,
            message_type=MessageType.ERROR
        ))
        
        if error.suggested_action:
            self.report(ProgressUpdate(
                message=f"💡 {error.suggested_action}",
                message_type=MessageType.INFO
            ))
        
        if self.verbose and error.raw_error:
            self.report(ProgressUpdate(
                message=f"Raw error: {error.raw_error[:200]}",
                message_type=MessageType.DEBUG
            ))
    
    def report_validation_results(self, results: List[ValidationResult]):
        """Report validation results in a user-friendly way"""
        errors = [r for r in results if r.severity == ValidationSeverity.ERROR]
        warnings = [r for r in results if r.severity == ValidationSeverity.WARNING]
        
        for error in errors:
            self.report(ProgressUpdate(
                message=error.message,
                message_type=MessageType.ERROR
            ))
            if error.suggestion:
                self.report(ProgressUpdate(
                    message=f"💡 {error.suggestion}",
                    message_type=MessageType.INFO
                ))
        
        for warning in warnings:
            self.report(ProgressUpdate(
                message=warning.message,
                message_type=MessageType.WARNING
            ))
            if warning.suggestion:
                self.report(ProgressUpdate(
                    message=f"💡 {warning.suggestion}",
                    message_type=MessageType.INFO
                ))
    
    def show_summary(self, session: 'DebateSession'):
        """Show a summary of the debate session"""
        print(f"\n{Colors.BOLD}{'═' * 60}{Colors.NC}")
        print(f"{Colors.BOLD}DEBATE SUMMARY{Colors.NC}")
        print(f"{'═' * 60}")
        
        status_color = Colors.GREEN if session.status == ConvergenceStatus.CONSENSUS else Colors.YELLOW
        print(f"Status:      {status_color}{session.status.value.upper()}{Colors.NC}")
        print(f"Rounds:      {len(session.rounds)}")
        print(f"Duration:    {self._format_duration(session.started_at, session.ended_at)}")
        print(f"Session:     {session.session_dir}")
        print(f"{'═' * 60}\n")
    
    def _format_duration(self, start: str, end: str) -> str:
        """Format duration between two ISO timestamps"""
        try:
            from datetime import datetime
            start_dt = datetime.fromisoformat(start)
            end_dt = datetime.fromisoformat(end) if end else datetime.now()
            delta = end_dt - start_dt
            minutes, seconds = divmod(int(delta.total_seconds()), 60)
            return f"{minutes}m {seconds}s"
        except:
            return "unknown"
```

#### 2.5 Updated Main Entry Point

```python
def run_debate_improved(
    initial_prompt: str = "",
    max_rounds: int = 8,
    working_dir: str = ".",
    output_dir: str = "./debate_output",
    verbose: bool = False,
    quiet: bool = False,
    implement: bool = False,
    resumed_session: Optional[DebateSession] = None,
    timeout: int = 300
) -> DebateSession:
    """Improved debate runner with robust error handling"""
    
    # Initialize components
    validator = InputValidator()
    reporter = ProgressReporter(verbose=verbose, quiet=quiet)
    
    # Validate inputs (if not resuming)
    if not resumed_session:
        # Validate prompt
        prompt_results = validator.validate_prompt(initial_prompt)
        if any(r.severity == ValidationSeverity.ERROR for r in prompt_results):
            reporter.report_validation_results(prompt_results)
            raise ValueError("Invalid prompt")
        reporter.report_validation_results(prompt_results)
        
        # Validate rounds
        rounds_results = validator.validate_rounds(max_rounds)
        if any(r.severity == ValidationSeverity.ERROR for r in rounds_results):
            reporter.report_validation_results(rounds_results)
            raise ValueError("Invalid max_rounds")
        
        # Validate working directory
        dir_results = validator.validate_working_dir(working_dir)
        if any(r.severity == ValidationSeverity.ERROR for r in dir_results):
            reporter.report_validation_results(dir_results)
            raise ValueError("Invalid working directory")
        
        # Sanitize prompt
        initial_prompt = validator.sanitize_prompt(initial_prompt)
    
    # Initialize CLI adapter
    cli = ClaudeCLIAdapter(
        timeout=timeout,
        on_progress=lambda msg: reporter.report(ProgressUpdate(
            message=msg, message_type=MessageType.PROGRESS
        ))
    )
    
    # Health check
    reporter.report(ProgressUpdate(
        message="Checking Claude CLI...",
        message_type=MessageType.PROGRESS
    ))
    health = cli.health_check()
    if not health.success:
        reporter.report_error(health.error, "Pre-flight check failed")
        raise RuntimeError("Claude CLI is not available")
    reporter.report(ProgressUpdate(
        message="Claude CLI ready",
        message_type=MessageType.SUCCESS
    ))
    
    # Setup session
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    if resumed_session:
        session = resumed_session
        session_dir = Path(session.session_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = output_path / f"session_{timestamp}"
        session = DebateSession(
            initial_prompt=initial_prompt,
            session_dir=str(session_dir),
            max_rounds=max_rounds,
            working_dir=working_dir
        )
    
    # Initialize session manager
    session_mgr = SessionManager(session_dir)
    if not session_mgr.initialize():
        reporter.report(ProgressUpdate(
            message="Another debate session is running in this directory",
            message_type=MessageType.ERROR
        ))
        raise RuntimeError("Session lock conflict")
    
    print_header()
    
    try:
        # Run debate loop
        start_round = len(session.rounds) + 1 if resumed_session else 1
        
        for round_num in range(start_round, max_rounds + 1):
            debate_round = DebateRound(round_number=round_num)
            
            # Agent A turn
            reporter.report(ProgressUpdate(
                message="Designing...",
                message_type=MessageType.PROGRESS,
                agent="Agent A",
                round_number=round_num
            ))
            
            agent_a_prompt = _build_agent_a_prompt(
                round_num, initial_prompt, 
                session.rounds[-1].agent_b_response if session.rounds else None
            )
            
            response_a = cli.call(
                get_agent_a_system_prompt(),
                agent_a_prompt,
                working_dir,
                stream_callback=lambda line: _stream_preview(line, reporter) if verbose else None
            )
            
            if not response_a.success:
                reporter.report_error(response_a.error, "Agent A failed")
                session_mgr.checkpoint(CheckpointData(
                    round_number=round_num,
                    agent_turn="agent_a",
                    completed=False,
                    response_data=None,
                    timestamp=datetime.now().isoformat()
                ))
                raise RuntimeError(f"Agent A failed: {response_a.error.message}")
            
            agent_a_response = parse_agent_response(response_a.content, is_agent_a=True)
            debate_round.agent_a_response = agent_a_response
            
            reporter.report(ProgressUpdate(
                message=f"Design complete ({response_a.duration_seconds:.1f}s)",
                message_type=MessageType.SUCCESS,
                agent="Agent A",
                round_number=round_num
            ))
            
            # Checkpoint after Agent A
            session_mgr.checkpoint(CheckpointData(
                round_number=round_num,
                agent_turn="agent_a",
                completed=True,
                response_data={"raw": agent_a_response.raw_response},
                timestamp=datetime.now().isoformat()
            ))
            
            # Agent B turn (similar pattern)
            # ... [similar code for Agent B] ...
            
            session.rounds.append(debate_round)
            save_session_state(session)
            
            # Check convergence
            if check_convergence(agent_a_response, agent_b_response) == ConvergenceStatus.CONSENSUS:
                reporter.report(ProgressUpdate(
                    message="CONSENSUS REACHED",
                    message_type=MessageType.SUCCESS
                ))
                session.status = ConvergenceStatus.CONSENSUS
                break
        
        session.ended_at = datetime.now().isoformat()
        session_mgr.mark_completed(success=True)
        save_session(session, session_dir)
        reporter.show_summary(session)
        
        return session
        
    except KeyboardInterrupt:
        reporter.report(ProgressUpdate(
            message="Interrupted. Session saved for resume.",
            message_type=MessageType.WARNING
        ))
        raise
    except Exception as e:
        session_mgr.mark_completed(success=False)
        reporter.report(ProgressUpdate(
            message=f"Debate failed: {str(e)}",
            message_type=MessageType.ERROR
        ))
        raise
```

### 3. Data Models

```python
# Enhanced data models with validation

@dataclass
class DebateConfig:
    """Configuration for a debate session"""
    max_rounds: int = 8
    timeout_per_call: int = 300
    convergence_threshold: int = 1
    auto_save: bool = True
    verbose: bool = False
    quiet: bool = False
    implement_after: bool = False
    
    def validate(self) -> List[ValidationResult]:
        results = []
        if self.max_rounds < 1 or self.max_rounds > 50:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="max_rounds must be between 1 and 50",
                field="max_rounds"
            ))
        if self.timeout_per_call < 30 or self.timeout_per_call > 600:
            results.append(ValidationResult(
                is_valid=False,
                severity=ValidationSeverity.ERROR,
                message="timeout must be between 30 and 600 seconds",
                field="timeout"
            ))
        return results

@dataclass
class AgentResponse:
    """Enhanced agent response with metadata"""
    content: str
    prompt_for_other: str
    convergence_signal: str
    raw_response: str
    parse_errors: List[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    duration_seconds: float = 0.0
    
    @property
    def is_valid(self) -> bool:
        return bool(self.content) and not self.parse_errors

@dataclass
class DebateSession:
    """Enhanced session with recovery metadata"""
    initial_prompt: str
    config: DebateConfig = field(default_factory=DebateConfig)
    rounds: List[DebateRound] = field(default_factory=list)
    final_design: str = ""
    status: ConvergenceStatus = ConvergenceStatus.DEBATING
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str = ""
    session_dir: str = ""
    error_history: List[str] = field(default_factory=list)
    total_retries: int = 0
```

### 4. Error Handling Strategy

| Error Type | Detection | Recovery Strategy | User Feedback |
|------------|-----------|-------------------|---------------|
| Empty prompt | Validation | Block execution | "Prompt cannot be empty. Provide a design task." |
| CLI not found | Health check | Fail fast | "Claude CLI not installed. See installation guide." |
| Auth failure | CLI response | Fail fast | "Authentication failed. Run 'claude login'." |
| Timeout | Process monitor | Retry (3x) | "Request timed out. Retrying (1/3)..." |
| Rate limit | CLI response | Backoff + retry | "Rate limited. Waiting 30s..." |
| Network error | CLI response | Retry (3x) | "Connection failed. Retrying..." |
| SIGINT | Signal handler | Save + exit | "Interrupted. Session saved. Use --resume." |
| Parse error | Response parser | Use raw response | "Warning: Response format unexpected." |
| Disk full | File write | Warn + continue | "Warning: Could not save checkpoint." |

### 5. New CLI Options

```
--timeout SECONDS     Timeout per Claude call (default: 300)
--retries N           Max retry attempts (default: 3)
--quiet               Only show errors and final result
--no-auto-save        Disable automatic checkpointing
--health-check        Just verify Claude CLI is working
--validate            Validate inputs without running debate
```

---

## Rationale

### Key Design Decisions

1. **Layered Architecture**: Separating concerns (validation, CLI interaction, session management, reporting) makes each component testable and maintainable independently.

2. **Circuit Breaker Pattern**: Prevents the system from hammering a failing Claude CLI, giving it time to recover while providing clear feedback to users.

3. **Checkpoint-based Recovery**: Saving state after each agent turn (not just each round) means users lose minimal work on interruption.

4. **Validation-First Approach**: Failing fast on invalid inputs saves time and provides clear guidance.

5. **Rich Error Classification**: Different error types (timeout, auth, rate limit) need different recovery strategies and user messaging.

### What I Changed

*First round - no prior version to compare against*

### What I Kept

The core debate loop structure and convergence logic from the original design, as these work well.

### Convergence Status

- **ITERATING**: This is an initial comprehensive design proposal that needs review.

---

PROMPT_FOR_CRITIC:

Please focus your review on:

1. **Complexity vs. Value**: Is the circuit breaker pattern overkill for this use case, or is it justified given real-world Claude CLI behavior?

2. **Signal Handling**: The SIGINT/SIGTERM handling adds complexity. Is this the right approach, or would simpler "save on exit" logic suffice?

3. **Missing Edge Cases**: What scenarios have I not addressed? Consider: partial responses, malformed JSON in state files, concurrent resume attempts, etc.

4. **User Experience**: Are the error messages and recovery suggestions actually helpful? Could they be clearer?

5. **Testing Strategy**: How would you approach testing these components, especially the error handling paths?

**Convergence Signal:** ITERATING

### 🟣 Agent B

Now I have a complete picture of the codebase. Let me provide my improved design as the REVIEWER agent.

---

## Design

### 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                     IMPROVED PLAN-WITH-DEBATE PLUGIN                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        Error Envelope Pattern                           │  │
│  │  Result[T] = Success[T] | Failure[ErrorInfo]                           │  │
│  │  - All operations return Result types                                   │  │
│  │  - No exceptions cross component boundaries                             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐          │
│  │  CLI Interface  │───▶│  DebateRunner   │───▶│  OutputManager  │          │
│  │  - ArgParser    │    │  - Orchestrator │    │  - FileWriter   │          │
│  │  - Validator    │    │  - Recovery     │    │  - Reporter     │          │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘          │
│           │                     │                     │                      │
│           ▼                     ▼                     ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                     ClaudeInvoker (Simplified)                   │        │
│  │  - Single retry with exponential backoff                         │        │
│  │  - Simple timeout handling                                       │        │
│  │  - Clear error classification (no circuit breaker)              │        │
│  └─────────────────────────────────────────────────────────────────┘        │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐        │
│  │                     StateManager (Lightweight)                   │        │
│  │  - JSON state files with atomic writes                          │        │
│  │  - atexit-based cleanup (no complex signal handling)            │        │
│  │  - Graceful partial save on failure                             │        │
│  └─────────────────────────────────────────────────────────────────┘        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 2. Core Data Types with Validation Built-In

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeVar, Generic, Union, Optional, List, Callable
from datetime import datetime
from pathlib import Path
import os
import re
import json

# ============================================================================
# Result Type - Functional Error Handling
# ============================================================================

T = TypeVar('T')

class ErrorSeverity(Enum):
    """How bad is this error?"""
    FATAL = "fatal"       # Cannot continue, must stop
    RECOVERABLE = "recoverable"  # Can retry or work around
    WARNING = "warning"   # Continue but user should know

@dataclass(frozen=True)
class ErrorInfo:
    """Immutable error information with actionable guidance"""
    code: str                    # Machine-readable: "CLI_TIMEOUT", "INVALID_PROMPT"
    message: str                 # Human-readable: "Claude CLI timed out after 300s"
    severity: ErrorSeverity
    suggestion: str = ""         # "Try increasing --timeout or simplifying the prompt"
    context: dict = field(default_factory=dict)  # Additional debug info
    
    def __str__(self) -> str:
        s = f"[{self.code}] {self.message}"
        if self.suggestion:
            s += f"\n  → {self.suggestion}"
        return s

@dataclass
class Success(Generic[T]):
    """Successful result wrapper"""
    value: T
    warnings: List[ErrorInfo] = field(default_factory=list)
    
    @property
    def is_success(self) -> bool:
        return True

@dataclass  
class Failure:
    """Failed result wrapper"""
    error: ErrorInfo
    partial_value: Optional[any] = None  # Any salvageable data
    
    @property
    def is_success(self) -> bool:
        return False

Result = Union[Success[T], Failure]

def collect_warnings(results: List[Result]) -> List[ErrorInfo]:
    """Gather all warnings from multiple results"""
    warnings = []
    for r in results:
        if isinstance(r, Success) and r.warnings:
            warnings.extend(r.warnings)
    return warnings

# ============================================================================
# Input Validation - Simpler, More Focused
# ============================================================================

@dataclass
class ValidatedPrompt:
    """A prompt that has passed validation - guarantees certain properties"""
    text: str
    word_count: int
    
    @classmethod
    def validate(cls, raw_input: str) -> Result['ValidatedPrompt']:
        """
        Validate and sanitize a prompt.
        Returns Success with warnings for non-fatal issues.
        """
        if not raw_input:
            return Failure(ErrorInfo(
                code="EMPTY_PROMPT",
                message="Prompt cannot be empty",
                severity=ErrorSeverity.FATAL,
                suggestion="Provide a task description, e.g., 'Design a user authentication system'"
            ))
        
        # Sanitize
        text = raw_input.strip()
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = ''.join(c for c in text if c == '\n' or c == '\t' or ord(c) >= 32)
        
        warnings = []
        
        # Length checks
        MIN_LENGTH = 10
        MAX_LENGTH = 50000
        
        if len(text) < MIN_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_SHORT",
                message=f"Prompt is too short ({len(text)} chars, need at least {MIN_LENGTH})",
                severity=ErrorSeverity.FATAL,
                suggestion="Describe the task in more detail"
            ))
        
        if len(text) > MAX_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_LONG",
                message=f"Prompt is too long ({len(text)} chars, max {MAX_LENGTH})",
                severity=ErrorSeverity.FATAL,
                suggestion="Summarize or split into multiple tasks"
            ))
        
        # Quality warnings (non-blocking)
        word_count = len(text.split())
        
        if word_count < 5:
            warnings.append(ErrorInfo(
                code="PROMPT_VAGUE",
                message="Prompt may be too vague",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider adding more context about requirements"
            ))
        
        # Check for actionable language
        action_words = {'design', 'create', 'build', 'implement', 'add', 'develop', 'refactor'}
        has_action = any(word in text.lower() for word in action_words)
        if not has_action:
            warnings.append(ErrorInfo(
                code="PROMPT_NO_ACTION",
                message="Prompt doesn't contain clear action words",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider starting with 'Design...', 'Implement...', or 'Create...'"
            ))
        
        return Success(
            value=cls(text=text, word_count=word_count),
            warnings=warnings
        )

@dataclass
class ValidatedConfig:
    """Validated configuration for a debate session"""
    max_rounds: int
    timeout_seconds: int
    working_dir: Path
    output_dir: Path
    
    @classmethod
    def validate(
        cls,
        max_rounds: int = 8,
        timeout: int = 300,
        working_dir: str = ".",
        output_dir: str = "./debate_output"
    ) -> Result['ValidatedConfig']:
        """Validate all configuration parameters"""
        
        # Validate max_rounds
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
                suggestion="Use 30 or fewer rounds to avoid excessive costs"
            ))
        
        # Validate timeout
        if timeout < 30:
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_LOW",
                message=f"Timeout must be at least 30s (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --timeout 30 or higher"
            ))
        if timeout > 600:
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_HIGH",
                message=f"Timeout cannot exceed 600s (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --timeout 600 or lower"
            ))
        
        # Validate working directory
        wd = Path(working_dir).resolve()
        if not wd.exists():
            return Failure(ErrorInfo(
                code="WORKING_DIR_NOT_FOUND",
                message=f"Working directory does not exist: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Create the directory or specify an existing one"
            ))
        if not wd.is_dir():
            return Failure(ErrorInfo(
                code="WORKING_DIR_NOT_DIR",
                message=f"Path is not a directory: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Specify a directory, not a file"
            ))
        if not os.access(wd, os.R_OK):
            return Failure(ErrorInfo(
                code="WORKING_DIR_NO_READ",
                message=f"Cannot read working directory: {wd}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check directory permissions"
            ))
        
        # Output directory - create if needed
        od = Path(output_dir).resolve()
        if od.exists() and not od.is_dir():
            return Failure(ErrorInfo(
                code="OUTPUT_DIR_NOT_DIR",
                message=f"Output path exists but is not a directory: {od}",
                severity=ErrorSeverity.FATAL,
                suggestion="Remove the file or specify a different output path"
            ))
        
        warnings = []
        if max_rounds > 15:
            warnings.append(ErrorInfo(
                code="HIGH_ROUND_COUNT",
                message=f"High round count ({max_rounds}) may be slow and costly",
                severity=ErrorSeverity.WARNING,
                suggestion="Consider starting with 8-10 rounds"
            ))
        
        return Success(
            value=cls(
                max_rounds=max_rounds,
                timeout_seconds=timeout,
                working_dir=wd,
                output_dir=od
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
    parse_warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

@dataclass
class DebateRound:
    """One complete round of debate"""
    round_number: int
    agent_a_response: Optional[AgentResponse] = None
    agent_b_response: Optional[AgentResponse] = None
    convergence_score: float = 0.0
    started_at: Optional[str] = None
    ended_at: Optional[str] = None

@dataclass
class DebateSession:
    """Complete debate session state - serializable to JSON"""
    session_id: str
    initial_prompt: str
    config: dict                   # Serialized ValidatedConfig
    rounds: List[DebateRound] = field(default_factory=list)
    status: ConvergenceStatus = ConvergenceStatus.DEBATING
    final_design: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    ended_at: str = ""
    error_log: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict"""
        return {
            'session_id': self.session_id,
            'initial_prompt': self.initial_prompt,
            'config': self.config,
            'rounds': [self._round_to_dict(r) for r in self.rounds],
            'status': self.status.value,
            'final_design': self.final_design,
            'started_at': self.started_at,
            'ended_at': self.ended_at,
            'error_log': self.error_log
        }
    
    def _round_to_dict(self, r: DebateRound) -> dict:
        d = {'round_number': r.round_number, 'convergence_score': r.convergence_score}
        if r.agent_a_response:
            d['agent_a'] = {
                'design_content': r.agent_a_response.design_content,
                'prompt_for_other': r.agent_a_response.prompt_for_other,
                'convergence_signal': r.agent_a_response.convergence_signal,
                'raw_response': r.agent_a_response.raw_response,
                'duration_seconds': r.agent_a_response.duration_seconds
            }
        if r.agent_b_response:
            d['agent_b'] = {
                'design_content': r.agent_b_response.design_content,
                'prompt_for_other': r.agent_b_response.prompt_for_other,
                'convergence_signal': r.agent_b_response.convergence_signal,
                'raw_response': r.agent_b_response.raw_response,
                'duration_seconds': r.agent_b_response.duration_seconds
            }
        return d
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DebateSession':
        """Deserialize from JSON dict with error tolerance"""
        session = cls(
            session_id=data.get('session_id', 'unknown'),
            initial_prompt=data.get('initial_prompt', ''),
            config=data.get('config', {}),
            status=ConvergenceStatus(data.get('status', 'debating')),
            final_design=data.get('final_design', ''),
            started_at=data.get('started_at', ''),
            ended_at=data.get('ended_at', ''),
            error_log=data.get('error_log', [])
        )
        
        for r_data in data.get('rounds', []):
            round_obj = DebateRound(
                round_number=r_data.get('round_number', 0),
                convergence_score=r_data.get('convergence_score', 0.0)
            )
            if 'agent_a' in r_data:
                a = r_data['agent_a']
                round_obj.agent_a_response = AgentResponse(
                    design_content=a.get('design_content', ''),
                    prompt_for_other=a.get('prompt_for_other', ''),
                    convergence_signal=a.get('convergence_signal', 'ITERATING'),
                    raw_response=a.get('raw_response', ''),
                    duration_seconds=a.get('duration_seconds', 0.0)
                )
            if 'agent_b' in r_data:
                b = r_data['agent_b']
                round_obj.agent_b_response = AgentResponse(
                    design_content=b.get('design_content', ''),
                    prompt_for_other=b.get('prompt_for_other', ''),
                    convergence_signal=b.get('convergence_signal', 'ITERATING'),
                    raw_response=b.get('raw_response', ''),
                    duration_seconds=b.get('duration_seconds', 0.0)
                )
            session.rounds.append(round_obj)
        
        return session
```

### 3. ClaudeInvoker - Simplified, No Circuit Breaker

```python
import subprocess
import time
from typing import Callable, Optional

class ClaudeInvoker:
    """
    Simple, robust wrapper for Claude CLI calls.
    
    Design decisions:
    - NO circuit breaker: overkill for a CLI tool used interactively
    - Single retry with backoff: handles transient failures without complexity
    - Clear timeout handling: kills process cleanly
    - Streaming support: shows progress during long operations
    """
    
    # Error codes for classification
    ERROR_CODES = {
        'timeout': 'CLI_TIMEOUT',
        'rate': 'RATE_LIMITED', 
        'auth': 'AUTH_FAILED',
        'network': 'NETWORK_ERROR',
        'not_found': 'CLI_NOT_FOUND',
        'unknown': 'CLI_ERROR'
    }
    
    def __init__(self, timeout: int = 300, on_progress: Optional[Callable[[str], None]] = None):
        self.timeout = timeout
        self.on_progress = on_progress or (lambda x: None)
    
    def check_available(self) -> Result[str]:
        """Verify Claude CLI is installed and accessible"""
        try:
            result = subprocess.run(
                ['claude', '--version'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return Success(value=result.stdout.strip())
            else:
                return Failure(ErrorInfo(
                    code=self.ERROR_CODES['not_found'],
                    message="Claude CLI returned an error",
                    severity=ErrorSeverity.FATAL,
                    suggestion="Run 'claude --help' to verify installation"
                ))
        except FileNotFoundError:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['not_found'],
                message="Claude CLI not found in PATH",
                severity=ErrorSeverity.FATAL,
                suggestion="Install Claude CLI: https://docs.anthropic.com/claude-code"
            ))
        except subprocess.TimeoutExpired:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['timeout'],
                message="Claude CLI check timed out",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Check your network connection"
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['unknown'],
                message=f"Unexpected error: {str(e)}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check Claude CLI installation"
            ))
    
    def invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: Path,
        retry_on_failure: bool = True
    ) -> Result[str]:
        """
        Call Claude CLI with the given prompts.
        
        Returns Success with response text, or Failure with error info.
        Optionally retries once on transient failures.
        """
        attempt = 0
        max_attempts = 2 if retry_on_failure else 1
        last_error: Optional[ErrorInfo] = None
        
        while attempt < max_attempts:
            attempt += 1
            result = self._single_invoke(system_prompt, user_prompt, working_dir)
            
            if isinstance(result, Success):
                return result
            
            last_error = result.error
            
            # Don't retry fatal errors
            if last_error.severity == ErrorSeverity.FATAL:
                return result
            
            # Retry with backoff
            if attempt < max_attempts:
                wait_time = 5 * attempt  # 5s, then 10s
                self.on_progress(f"Retrying in {wait_time}s... ({last_error.message})")
                time.sleep(wait_time)
        
        return Failure(last_error)
    
    def _single_invoke(
        self,
        system_prompt: str,
        user_prompt: str,
        working_dir: Path
    ) -> Result[str]:
        """Execute a single Claude CLI call"""
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
            
            # Send prompt
            process.stdin.write(user_prompt)
            process.stdin.close()
            
            # Collect output with timeout monitoring
            output_lines = []
            last_progress = start_time
            
            while True:
                elapsed = time.time() - start_time
                
                # Check timeout
                if elapsed > self.timeout:
                    process.kill()
                    process.wait()
                    return Failure(ErrorInfo(
                        code=self.ERROR_CODES['timeout'],
                        message=f"Request timed out after {int(elapsed)}s",
                        severity=ErrorSeverity.RECOVERABLE,
                        suggestion="Try increasing --timeout or simplifying the prompt",
                        context={'timeout': self.timeout, 'elapsed': elapsed}
                    ))
                
                # Show progress every 15 seconds
                if elapsed - (last_progress - start_time) > 15:
                    self.on_progress(f"Still working... ({int(elapsed)}s)")
                    last_progress = time.time()
                
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                if line:
                    output_lines.append(line.rstrip('\n'))
            
            stderr = process.stderr.read()
            duration = time.time() - start_time
            
            if process.returncode != 0:
                return Failure(self._classify_error(stderr, process.returncode))
            
            content = '\n'.join(output_lines).strip()
            
            if not content:
                return Failure(ErrorInfo(
                    code='EMPTY_RESPONSE',
                    message="Claude returned an empty response",
                    severity=ErrorSeverity.RECOVERABLE,
                    suggestion="Try rephrasing your prompt"
                ))
            
            return Success(value=content)
            
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
                except:
                    pass
            return Failure(ErrorInfo(
                code=self.ERROR_CODES['unknown'],
                message=str(e),
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="An unexpected error occurred"
            ))
    
    def _classify_error(self, stderr: str, returncode: int) -> ErrorInfo:
        """Classify an error based on stderr output"""
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
                message="Rate limit exceeded",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Wait a moment and try again"
            )
        
        if 'unauthorized' in stderr_lower or 'authentication' in stderr_lower or '401' in stderr:
            return ErrorInfo(
                code=self.ERROR_CODES['auth'],
                message="Authentication failed",
                severity=ErrorSeverity.FATAL,
                suggestion="Run 'claude login' to re-authenticate"
            )
        
        if 'connection' in stderr_lower or 'network' in stderr_lower:
            return ErrorInfo(
                code=self.ERROR_CODES['network'],
                message="Network connection failed",
                severity=ErrorSeverity.RECOVERABLE,
                suggestion="Check your internet connection"
            )
        
        return ErrorInfo(
            code=self.ERROR_CODES['unknown'],
            message=stderr or f"CLI exited with code {returncode}",
            severity=ErrorSeverity.RECOVERABLE,
            suggestion="Check Claude CLI logs for details"
        )
```

### 4. StateManager - Simplified, atexit-based

```python
import atexit
import tempfile
import shutil

class StateManager:
    """
    Manages session state with atomic writes and automatic cleanup.
    
    Design decisions:
    - NO complex signal handling: atexit is sufficient for cleanup
    - Atomic writes: write to temp file, then rename
    - No file locking: single-user CLI tool doesn't need it
    - Graceful degradation: failures to save state don't crash the debate
    """
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.state_file = session_dir / "session_state.json"
        self._cleanup_registered = False
    
    def initialize(self) -> Result[bool]:
        """Initialize the session directory and register cleanup"""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            
            # Write a marker file to indicate session is active
            marker = self.session_dir / ".active"
            marker.write_text(f"pid={os.getpid()}\nstarted={datetime.now().isoformat()}")
            
            # Register cleanup
            if not self._cleanup_registered:
                atexit.register(self._cleanup)
                self._cleanup_registered = True
            
            return Success(value=True)
            
        except PermissionError as e:
            return Failure(ErrorInfo(
                code="STATE_PERMISSION_ERROR",
                message=f"Cannot write to session directory: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check directory permissions"
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code="STATE_INIT_ERROR",
                message=f"Failed to initialize state: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check disk space and permissions"
            ))
    
    def save(self, session: DebateSession) -> Result[bool]:
        """
        Save session state atomically.
        Uses write-to-temp-then-rename for crash safety.
        """
        try:
            data = session.to_dict()
            
            # Write to temp file first
            temp_fd, temp_path = tempfile.mkstemp(
                dir=self.session_dir,
                prefix=".state_",
                suffix=".json"
            )
            
            try:
                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(data, f, indent=2)
                
                # Atomic rename
                shutil.move(temp_path, self.state_file)
                return Success(value=True)
                
            except Exception as e:
                # Clean up temp file on failure
                try:
                    os.unlink(temp_path)
                except:
                    pass
                raise e
                
        except Exception as e:
            # Save failures are warnings, not fatal
            return Failure(ErrorInfo(
                code="STATE_SAVE_ERROR",
                message=f"Failed to save state: {e}",
                severity=ErrorSeverity.WARNING,
                suggestion="Session will continue but may not be resumable"
            ))
    
    def load(self) -> Result[DebateSession]:
        """Load session state from disk with error tolerance"""
        if not self.state_file.exists():
            return Failure(ErrorInfo(
                code="STATE_NOT_FOUND",
                message=f"No session state found at {self.state_file}",
                severity=ErrorSeverity.FATAL,
                suggestion="Start a new session or specify a valid session path"
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
                suggestion="The session cannot be resumed. Start a new session."
            ))
        except Exception as e:
            return Failure(ErrorInfo(
                code="STATE_LOAD_ERROR",
                message=f"Failed to load state: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check file permissions or start a new session"
            ))
    
    def can_resume(self) -> Result[dict]:
        """Check if this session can be resumed and return status info"""
        load_result = self.load()
        
        if isinstance(load_result, Failure):
            return load_result
        
        session = load_result.value
        
        if session.status == ConvergenceStatus.CONSENSUS:
            return Failure(ErrorInfo(
                code="SESSION_COMPLETE",
                message="Session already reached consensus",
                severity=ErrorSeverity.WARNING,
                suggestion="Nothing to resume. View results with --list"
            ))
        
        if session.status == ConvergenceStatus.FAILED:
            return Failure(ErrorInfo(
                code="SESSION_FAILED",
                message="Previous session failed",
                severity=ErrorSeverity.WARNING,
                suggestion="Review error log or start a new session"
            ))
        
        return Success(value={
            'session_id': session.session_id,
            'rounds_completed': len(session.rounds),
            'status': session.status.value,
            'last_activity': session.ended_at or session.started_at
        })
    
    def _cleanup(self):
        """Clean up on exit - remove active marker"""
        try:
            marker = self.session_dir / ".active"
            if marker.exists():
                marker.unlink()
        except:
            pass  # Best effort cleanup
```

### 5. UserReporter - Clean, Actionable Feedback

```python
import sys

class UserReporter:
    """
    Provides clear, actionable user feedback.
    
    Design principles:
    - Always include what went wrong AND what to do about it
    - Use consistent icons/colors for quick scanning
    - Verbose mode shows debug info, quiet mode shows only errors
    """
    
    ICONS = {
        'success': '✓',
        'error': '✗',
        'warning': '⚠',
        'info': 'ℹ',
        'progress': '→',
        'agent_a': '🔵',
        'agent_b': '🟣'
    }
    
    def __init__(self, verbose: bool = False, quiet: bool = False):
        self.verbose = verbose
        self.quiet = quiet
    
    def success(self, message: str):
        """Report a success"""
        if not self.quiet:
            print(f"{Colors.GREEN}{self.ICONS['success']} {message}{Colors.NC}")
    
    def error(self, error: ErrorInfo):
        """Report an error with suggestion"""
        print(f"{Colors.RED}{self.ICONS['error']} {error.message}{Colors.NC}")
        if error.suggestion:
            print(f"  {Colors.YELLOW}→ {error.suggestion}{Colors.NC}")
        if self.verbose and error.context:
            print(f"  {Colors.CYAN}Debug: {error.context}{Colors.NC}")
    
    def warning(self, message: str, suggestion: str = ""):
        """Report a warning"""
        print(f"{Colors.YELLOW}{self.ICONS['warning']} {message}{Colors.NC}")
        if suggestion:
            print(f"  → {suggestion}")
    
    def info(self, message: str):
        """Report info (respects quiet mode)"""
        if not self.quiet:
            print(f"{Colors.CYAN}{self.ICONS['info']} {message}{Colors.NC}")
    
    def progress(self, message: str, agent: str = None, round_num: int = None):
        """Report progress (respects quiet mode)"""
        if self.quiet:
            return
        
        prefix = ""
        if agent:
            icon = self.ICONS['agent_a'] if agent == 'A' else self.ICONS['agent_b']
            prefix = f"{icon} "
        if round_num:
            prefix += f"[R{round_num}] "
        
        print(f"{prefix}{self.ICONS['progress']} {message}")
        sys.stdout.flush()
    
    def debug(self, message: str):
        """Report debug info (only in verbose mode)"""
        if self.verbose:
            print(f"\033[90m· {message}{Colors.NC}")
    
    def report_result(self, result: Result, context: str = ""):
        """Report any Result type appropriately"""
        if isinstance(result, Success):
            if result.warnings:
                for w in result.warnings:
                    self.warning(w.message, w.suggestion)
        else:
            self.error(result.error)
    
    def show_validation_results(self, results: List[Result]):
        """Show all validation results in a clear format"""
        errors = [r.error for r in results if isinstance(r, Failure)]
        warnings = []
        for r in results:
            if isinstance(r, Success):
                warnings.extend(r.warnings)
        
        if errors:
            print(f"\n{Colors.RED}Validation failed:{Colors.NC}")
            for e in errors:
                self.error(e)
        
        if warnings and not self.quiet:
            if errors:
                print()
            for w in warnings:
                self.warning(w.message, w.suggestion)
    
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
        
        bar = "█" * int(convergence_score * 10) + "░" * (10 - int(convergence_score * 10))
        
        print(f"\n{'─' * 60}")
        print(f"Round {round_num}/{max_rounds} | {duration:.0f}s | Similarity [{bar}] {convergence_score:.0%}")
        print(f"  Architect: {agent_a_signal} | Reviewer: {agent_b_signal}")
        
        if convergence_score > 0.8:
            print(f"  {Colors.GREEN}↗ Designs converging - consensus likely{Colors.NC}")
        elif convergence_score > 0.5:
            print(f"  → Designs becoming more similar")
        print(f"{'─' * 60}\n")
    
    def show_final_summary(self, session: DebateSession, session_dir: Path):
        """Show final debate summary"""
        print(f"\n{'═' * 60}")
        print(f"{Colors.BOLD}DEBATE COMPLETE{Colors.NC}")
        print(f"{'═' * 60}")
        
        status_colors = {
            ConvergenceStatus.CONSENSUS: Colors.GREEN,
            ConvergenceStatus.INTERRUPTED: Colors.YELLOW,
            ConvergenceStatus.FAILED: Colors.RED
        }
        color = status_colors.get(session.status, Colors.NC)
        
        print(f"Status:   {color}{session.status.value.upper()}{Colors.NC}")
        print(f"Rounds:   {len(session.rounds)}")
        print(f"Session:  {session_dir}")
        print(f"\nOutput files:")
        print(f"  • {session_dir / 'final_design.md'}")
        print(f"  • {session_dir / 'debate_history.md'}")
        print(f"{'═' * 60}\n")
```

### 6. Main Entry Point - Clean Flow

```python
def run_debate(
    prompt: ValidatedPrompt,
    config: ValidatedConfig,
    reporter: UserReporter,
    resumed_session: Optional[DebateSession] = None
) -> Result[DebateSession]:
    """
    Main debate orchestration function.
    
    Accepts only validated inputs - validation happens at CLI layer.
    Returns Result type for consistent error handling.
    """
    
    # Setup
    invoker = ClaudeInvoker(
        timeout=config.timeout_seconds,
        on_progress=lambda msg: reporter.debug(msg)
    )
    
    # Health check
    reporter.info("Checking Claude CLI...")
    health = invoker.check_available()
    if isinstance(health, Failure):
        reporter.error(health.error)
        return health
    reporter.success(f"Claude CLI ready ({health.value})")
    
    # Initialize session
    if resumed_session:
        session = resumed_session
        session_dir = Path(resumed_session.config.get('session_dir', config.output_dir))
        start_round = len(session.rounds) + 1
        reporter.info(f"Resuming from round {start_round}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = config.output_dir / f"session_{timestamp}"
        session = DebateSession(
            session_id=timestamp,
            initial_prompt=prompt.text,
            config={
                'max_rounds': config.max_rounds,
                'timeout': config.timeout_seconds,
                'working_dir': str(config.working_dir),
                'session_dir': str(session_dir)
            }
        )
        start_round = 1
    
    # Initialize state manager
    state_mgr = StateManager(session_dir)
    init_result = state_mgr.initialize()
    if isinstance(init_result, Failure):
        return init_result
    
    # Print header
    print_header()
    reporter.info(f"Task: {prompt.text[:100]}...")
    reporter.info(f"Session: {session_dir}")
    
    # Track responses
    last_agent_a: Optional[AgentResponse] = None
    last_agent_b: Optional[AgentResponse] = None
    
    if resumed_session and session.rounds:
        last_round = session.rounds[-1]
        last_agent_a = last_round.agent_a_response
        last_agent_b = last_round.agent_b_response
    
    try:
        for round_num in range(start_round, config.max_rounds + 1):
            round_start = time.time()
            debate_round = DebateRound(
                round_number=round_num,
                started_at=datetime.now().isoformat()
            )
            
            # === Agent A Turn ===
            reporter.progress("Designing...", agent='A', round_num=round_num)
            
            agent_a_prompt = build_agent_a_prompt(
                round_num, prompt.text, last_agent_b
            )
            
            response_a = invoker.invoke(
                get_agent_a_system_prompt(),
                agent_a_prompt,
                config.working_dir
            )
            
            if isinstance(response_a, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(str(response_a.error))
                state_mgr.save(session)
                return response_a
            
            last_agent_a = parse_agent_response(response_a.value, is_agent_a=True)
            debate_round.agent_a_response = last_agent_a
            reporter.success(f"Design complete ({last_agent_a.duration_seconds:.0f}s)")
            
            # Save checkpoint after Agent A
            state_mgr.save(session)
            
            # === Agent B Turn ===
            reporter.progress("Reviewing...", agent='B', round_num=round_num)
            
            agent_b_prompt = build_agent_b_prompt(
                prompt.text, last_agent_a
            )
            
            response_b = invoker.invoke(
                get_agent_b_system_prompt(),
                agent_b_prompt,
                config.working_dir
            )
            
            if isinstance(response_b, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(str(response_b.error))
                state_mgr.save(session)
                return response_b
            
            last_agent_b = parse_agent_response(response_b.value, is_agent_a=False)
            debate_round.agent_b_response = last_agent_b
            reporter.success(f"Review complete ({last_agent_b.duration_seconds:.0f}s)")
            
            # Calculate metrics
            round_duration = time.time() - round_start
            convergence_score = calculate_similarity(
                last_agent_a.design_content,
                last_agent_b.design_content
            )
            debate_round.convergence_score = convergence_score
            debate_round.ended_at = datetime.now().isoformat()
            
            session.rounds.append(debate_round)
            state_mgr.save(session)
            
            # Show round summary
            reporter.show_round_summary(
                round_num, config.max_rounds, round_duration,
                convergence_score,
                last_agent_a.convergence_signal,
                last_agent_b.convergence_signal
            )
            
            # Check convergence
            if check_convergence(last_agent_a, last_agent_b) == ConvergenceStatus.CONSENSUS:
                session.status = ConvergenceStatus.CONSENSUS
                session.final_design = last_agent_a.design_content
                reporter.success("CONSENSUS REACHED!")
                break
        
        session.ended_at = datetime.now().isoformat()
        save_final_outputs(session, session_dir)
        state_mgr.save(session)
        
        reporter.show_final_summary(session, session_dir)
        return Success(value=session)
        
    except KeyboardInterrupt:
        session.status = ConvergenceStatus.INTERRUPTED
        session.ended_at = datetime.now().isoformat()
        state_mgr.save(session)
        reporter.warning("Interrupted. Session saved.", "Use --resume to continue")
        return Failure(ErrorInfo(
            code="INTERRUPTED",
            message="Debate interrupted by user",
            severity=ErrorSeverity.WARNING,
            suggestion=f"Resume with: debate --resume {session_dir}"
        ))
```

### 7. Error Handling Strategy (Simplified)

| Error Type | Detection | Recovery | User Message |
|------------|-----------|----------|--------------|
| Empty prompt | Validation | Block immediately | "Prompt cannot be empty. Example: 'Design a REST API...'" |
| CLI not found | Health check | Stop | "Claude CLI not found. Install: https://docs.anthropic.com/..." |
| Auth failed | CLI stderr | Stop | "Authentication failed. Run 'claude login'" |
| Timeout | Process monitor | Retry once | "Timed out after 300s. Retrying..." |
| Rate limit | CLI stderr | Retry with backoff | "Rate limited. Waiting 10s..." |
| Network error | CLI stderr | Retry once | "Network error. Retrying..." |
| Ctrl+C | KeyboardInterrupt | Save & exit | "Interrupted. Resume with --resume" |
| Parse error | Response parser | Use fallback | (warning) "Could not parse response format" |
| Disk full | File write | Warn, continue | (warning) "Could not save checkpoint" |

### 8. New CLI Options

```
--timeout SECONDS     Timeout per Claude call (default: 300, max: 600)
--quiet               Only show errors and final result  
--validate            Validate inputs without running debate
--health-check        Verify Claude CLI works and exit
```

---

## Rationale

### Key Design Decisions

1. **Result Type Over Exceptions**: Using `Success`/`Failure` wrappers makes error handling explicit. Every function documents what can go wrong, and callers must handle both cases. This prevents silent failures.

2. **No Circuit Breaker**: The architect's circuit breaker pattern is overkill for this use case. This is a CLI tool run interactively by a single user. If Claude CLI is down, the user will see retry failures and can decide what to do. Adding circuit breaker complexity gains us nothing.

3. **Simplified Signal Handling**: Complex SIGINT/SIGTERM handlers with state restoration are fragile. Instead, we use `atexit` for cleanup and save state after every agent turn. If interrupted, the user runs `--resume` and picks up where they left off.

4. **Atomic State Writes**: Write to temp file, then rename. This ensures we never have a half-written state file. Simple and reliable.

5. **Validated Types**: `ValidatedPrompt` and `ValidatedConfig` guarantee that by the time we start the debate, all inputs are valid. No need to check again deeper in the code.

---

## What I Improved

1. **Removed Circuit Breaker**: This added ~100 lines of complexity for a pattern designed for distributed systems, not CLI tools. A simple "retry once with backoff" handles the same cases with far less code.

2. **Simplified Signal Handling**: Replaced complex signal handlers with atexit + save-after-every-turn. Same reliability, much simpler.

3. **Added Result Type**: The architect used exceptions and error dataclasses but didn't have a consistent pattern for "operation succeeded with warnings." The `Success`/`Failure` types make this explicit.

4. **Validated Types as Guarantees**: Rather than running validation and then passing raw types around, I create `ValidatedPrompt` and `ValidatedConfig` types that encode the validation as a type guarantee.

5. **Atomic State Writes**: The architect's design wrote directly to the state file. If the process dies mid-write, the file is corrupt. Write-to-temp-then-rename prevents this.

6. **Clearer Error Messages**: Every error now has: (1) what went wrong, (2) what to do about it, and optionally (3) debug context. No more cryptic failures.

---

## What I Kept

1. **Core Architecture**: The layered design with validation → CLI adapter → session management → reporting is sound.

2. **Error Classification**: Distinguishing timeout vs auth vs rate limit is important for choosing the right recovery strategy.

3. **Checkpoint After Each Agent Turn**: This granularity ensures minimal lost work on interruption.

4. **Progress Reporting Structure**: The reporter abstraction with verbose/quiet modes is clean.

5. **Health Check on Startup**: Failing fast when Claude CLI isn't available saves time.

---

## Remaining Concerns

1. **Partial Response Handling**: If Claude returns a response that's truncated mid-design, we should detect this (look for missing expected sections) and either retry or warn the user. Neither design fully addresses this.

2. **Concurrent Resume Attempts**: Two users could try to resume the same session simultaneously. The "active marker" file helps but isn't foolproof without true file locking.

3. **Large State Files**: If prompts or responses are very large, JSON state files could grow unwieldy. Might need compression or separate files for raw responses.

4. **Testing**: Both designs would benefit from a mock `ClaudeInvoker` interface for testing error paths without real API calls.

---

## Convergence Status

**ITERATING**: I made significant simplifications while preserving the core ideas. The architect should review whether the circuit breaker removal loses important protection, and whether the Result type adds value over their exception-based approach.

---

PROMPT_FOR_ARCHITECT:

Please focus your review on:

1. **Circuit Breaker Removal**: I removed it as overkill. But consider: if a user runs 8 rounds and Claude CLI starts failing on round 5, would a circuit breaker help them? Or would "retry once then fail with clear message" be just as good?

2. **Result Type vs Exceptions**: I added `Success`/`Failure` wrappers for explicit error handling. Is this better than Python's natural exception model, or is it over-engineering for a CLI tool?

3. **Partial Response Detection**: Neither of us fully addressed: what if Claude returns a truncated response (e.g., network hiccup mid-stream)? How would we detect and handle this?

4. **State File Atomicity**: I added write-to-temp-then-rename. Is this necessary, or is the probability of corruption during write low enough to ignore?

5. **Simplicity vs Robustness Tradeoff**: I prioritized simplicity over the architect's more defensive design. Did I cut too much? Too little?

**Convergence Signal:** ACCEPTING_FINAL

---

## Round 2

### 🔵 Agent A

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
        required_markers.append('### Convergence Status')
        
        return all(marker in response for marker in required_markers)
```

### 7. Main Entry Point

```python
def run_debate(
    prompt: ValidatedPrompt,
    config: ValidatedConfig,
    reporter: UserReporter,
    resumed_session: Optional[DebateSession] = None
) -> Result[DebateSession]:
    """
    Main debate orchestration.
    
    Accepts only validated inputs - validation happens at CLI layer.
    Returns Result for consistent error handling throughout.
    """
    
    # Create invoker with progress callback
    invoker = ClaudeInvoker(
        timeout=config.timeout_seconds,
        on_progress=lambda msg: reporter.debug(msg)
    )
    
    # Pre-flight check
    reporter.info("Checking Claude CLI...")
    health = invoker.check_available()
    if isinstance(health, Failure):
        reporter.error(health.error)
        return health
    reporter.success(f"Claude CLI ready ({health.value})")
    
    # Setup session
    if resumed_session:
        session = resumed_session
        session_dir = Path(session.config.get('session_dir', config.output_dir))
        start_round = len(session.rounds) + 1
        reporter.info(f"Resuming session from round {start_round}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = config.output_dir / f"session_{timestamp}"
        session = DebateSession(
            session_id=timestamp,
            initial_prompt=prompt.text,
            config={
                'max_rounds': config.max_rounds,
                'timeout': config.timeout_seconds,
                'working_dir': str(config.working_dir),
                'session_dir': str(session_dir)
            }
        )
        start_round = 1
    
    # Initialize state manager
    state_mgr = StateManager(session_dir)
    init_result = state_mgr.initialize()
    if isinstance(init_result, Failure):
        reporter.error(init_result.error)
        return init_result
    
    # Print header
    print_header()
    reporter.info(f"Task: {prompt.text[:100]}{'...' if len(prompt.text) > 100 else ''}")
    reporter.info(f"Session: {session_dir}")
    
    # Track last responses for context
    last_agent_a: Optional[AgentResponse] = None
    last_agent_b: Optional[AgentResponse] = None
    
    if resumed_session and session.rounds:
        last_round = session.rounds[-1]
        last_agent_a = last_round.agent_a_response
        last_agent_b = last_round.agent_b_response
    
    session_start_time = time.time()
    
    try:
        for round_num in range(start_round, config.max_rounds + 1):
            round_start = time.time()
            debate_round = DebateRound(
                round_number=round_num,
                started_at=datetime.now().isoformat()
            )
            
            # === Agent A (Architect) Turn ===
            reporter.progress(
                "Creating design..." if round_num == 1 else "Improving design...",
                agent='A', round_num=round_num
            )
            
            agent_a_prompt = build_agent_a_prompt(round_num, prompt.text, last_agent_b)
            
            agent_a_start = time.time()
            response_a = invoker.invoke(
                get_agent_a_system_prompt(),
                agent_a_prompt,
                config.working_dir,
                agent_type='agent_a'
            )
            
            if isinstance(response_a, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(f"Agent A failed: {response_a.error}")
                state_mgr.save(session)
                reporter.error(response_a.error)
                return response_a
            
            # Report any warnings
            for w in response_a.warnings:
                reporter.warning(w)
            
            last_agent_a = ResponseParser.parse(response_a.value, is_agent_a=True)
            last_agent_a.duration_seconds = time.time() - agent_a_start
            debate_round.agent_a_response = last_agent_a
            
            reporter.success(f"Design complete ({last_agent_a.duration_seconds:.0f}s)")
            
            # Checkpoint after Agent A
            state_mgr.save(session)
            
            # === Agent B (Reviewer) Turn ===
            reporter.progress("Reviewing design...", agent='B', round_num=round_num)
            
            agent_b_prompt = build_agent_b_prompt(prompt.text, last_agent_a)
            
            agent_b_start = time.time()
            response_b = invoker.invoke(
                get_agent_b_system_prompt(),
                agent_b_prompt,
                config.working_dir,
                agent_type='agent_b'
            )
            
            if isinstance(response_b, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(f"Agent B failed: {response_b.error}")
                state_mgr.save(session)
                reporter.error(response_b.error)
                return response_b
            
            for w in response_b.warnings:
                reporter.warning(w)
            
            last_agent_b = ResponseParser.parse(response_b.value, is_agent_a=False)
            last_agent_b.duration_seconds = time.time() - agent_b_start
            debate_round.agent_b_response = last_agent_b
            
            reporter.success(f"Review complete ({last_agent_b.duration_seconds:.0f}s)")
            
            # Complete round metrics
            debate_round.duration_seconds = time.time() - round_start
            debate_round.ended_at = datetime.now().isoformat()
            debate_round.convergence_score = calculate_similarity(
                last_agent_a.design_content,
                last_agent_b.design_content
            )
            
            session.rounds.append(debate_round)
            state_mgr.save(session)
            
            # Show round summary
            reporter.show_round_summary(
                round_num, config.max_rounds,
                debate_round.duration_seconds,
                debate_round.convergence_score,
                last_agent_a.convergence_signal,
                last_agent_b.convergence_signal
            )
            
            # Check for consensus
            if check_convergence(last_agent_a, last_agent_b) == ConvergenceStatus.CONSENSUS:
                session.status = ConvergenceStatus.CONSENSUS
                session.final_design = last_agent_a.design_content
                reporter.success("CONSENSUS REACHED! 🤝")
                break
        
        # Finalize session
        session.ended_at = datetime.now().isoformat()
        session.total_duration_seconds = time.time() - session_start_time
        
        if session.status == ConvergenceStatus.DEBATING:
            # Max rounds reached without consensus
            session.final_design = last_agent_a.design_content if last_agent_a else ""
        
        save_final_outputs(session, session_dir)
        state_mgr.save(session)
        
        reporter.show_final_summary(session, session_dir)
        return Success(value=session)
        
    except KeyboardInterrupt:
        session.status = ConvergenceStatus.INTERRUPTED
        session.ended_at = datetime.now().isoformat()
        session.total_duration_seconds = time.time() - session_start_time
        state_mgr.save(session)
        
        reporter.warning(ErrorInfo(
            code="INTERRUPTED",
            message="Debate interrupted by user",
            severity=ErrorSeverity.WARNING,
            suggestion=f"Resume with: debate --resume {session_dir}"
        ))
        
        return Failure(ErrorInfo(
            code="INTERRUPTED",
            message="Session interrupted",
            severity=ErrorSeverity.WARNING
        ))


def build_agent_a_prompt(round_num: int, initial_prompt: str, last_agent_b: Optional[AgentResponse]) -> str:
    """Build the prompt for Agent A based on round"""
    if round_num == 1:
        return f"""## Design Task

{initial_prompt}

Create a complete, detailed design for this task.
Include: architecture, components, data models, interfaces, and error handling.
End with "PROMPT_FOR_CRITIC:" followed by what you want the reviewer to focus on."""
    else:
        return f"""## Other Agent's Design (Previous Round)

{last_agent_b.raw_response}

---

## Their Focus Question for You:

{last_agent_b.prompt_for_other}

---

## Original Task (for reference)
{initial_prompt}

---

Review their design and create YOUR improved version. Keep what works, improve what doesn't.
Output a COMPLETE design, not just feedback. End with "PROMPT_FOR_CRITIC:" for what they should focus on."""


def build_agent_b_prompt(initial_prompt: str, last_agent_a: AgentResponse) -> str:
    """Build the prompt for Agent B"""
    return f"""## Other Agent's Design

{last_agent_a.raw_response}

---

## Their Focus Question for You:

{last_agent_a.prompt_for_other}

---

## Original Task (for reference)
{initial_prompt}

---

Review their design and create YOUR improved version. Keep what works, improve what doesn't.
Output a COMPLETE design, not just feedback. End with "PROMPT_FOR_ARCHITECT:" for what they should focus on.
If their design is already optimal, signal ACCEPTING_FINAL."""
```

### 8. CLI Entry Point with Validation

```python
def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Debate System - Two AI agents debate to optimal designs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  debate "Design a REST API for user management"
  debate -f requirements.txt --max-rounds 10
  debate --resume latest
  debate --health-check
        """
    )
    parser.add_argument('prompt', nargs='?', help='Task description for the debate')
    parser.add_argument('-f', '--file', help='Read prompt from file')
    parser.add_argument('-m', '--max-rounds', type=int, default=8, help='Maximum rounds (default: 8)')
    parser.add_argument('-o', '--output', default='./debate_output', help='Output directory')
    parser.add_argument('-w', '--working-dir', default='.', help='Working directory for agents')
    parser.add_argument('-t', '--timeout', type=int, default=300, help='Timeout per agent call in seconds (default: 300)')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show debug output')
    parser.add_argument('-q', '--quiet', action='store_true', help='Only show errors and final result')
    parser.add_argument('-r', '--resume', nargs='?', const='latest', help='Resume session (path or "latest")')
    parser.add_argument('-l', '--list', action='store_true', help='List resumable sessions')
    parser.add_argument('--health-check', action='store_true', help='Verify Claude CLI and exit')
    parser.add_argument('--validate', action='store_true', help='Validate inputs without running')
    parser.add_argument('-i', '--implement', action='store_true', help='Run implementation after consensus')
    
    args = parser.parse_args()
    
    # Create reporter early for consistent output
    reporter = UserReporter(verbose=args.verbose, quiet=args.quiet)
    
    # Health check mode
    if args.health_check:
        invoker = ClaudeInvoker()
        result = invoker.check_available()
        if isinstance(result, Success):
            reporter.success(f"Claude CLI is available: {result.value}")
            sys.exit(0)
        else:
            reporter.error(result.error)
            sys.exit(1)
    
    # List sessions mode
    if args.list:
        list_sessions(args.output, reporter)
        sys.exit(0)
    
    # Resume mode
    resumed_session = None
    if args.resume:
        resumed_session = load_resumed_session(args.resume, args.output, reporter)
        if not resumed_session:
            sys.exit(1)
    
    # Get prompt (required if not resuming)
    raw_prompt = args.prompt
    if args.file:
        try:
            with open(args.file, 'r') as f:
                raw_prompt = f.read().strip()
        except Exception as e:
            reporter.error(ErrorInfo(
                code="FILE_READ_ERROR",
                message=f"Cannot read prompt file: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check file path and permissions"
            ))
            sys.exit(1)
    
    if not raw_prompt and not resumed_session:
        parser.print_help()
        print(f"\n{Colors.RED}Error: No prompt provided (use --resume to continue a session){Colors.NC}")
        sys.exit(1)
    
    # Validate inputs
    prompt_result = ValidatedPrompt.validate(raw_prompt) if raw_prompt else Success(value=None)
    config_result = ValidatedConfig.validate(
        max_rounds=args.max_rounds,
        timeout=args.timeout,
        working_dir=args.working_dir,
        output_dir=args.output,
        verbose=args.verbose,
        quiet=args.quiet
    )
    
    # Show validation results
    if not reporter.show_validation_summary(prompt_result, config_result):
        sys.exit(1)
    
    # Validate-only mode
    if args.validate:
        reporter.success("Validation passed")
        sys.exit(0)
    
    # Extract validated values
    prompt = prompt_result.value if isinstance(prompt_result, Success) else None
    config = config_result.value
    
    # Run the debate
    result = run_debate(
        prompt=prompt or ValidatedPrompt(text=resumed_session.initial_prompt, word_count=0) if resumed_session else prompt,
        config=config,
        reporter=reporter,
        resumed_session=resumed_session
    )
    
    if isinstance(result, Failure):
        sys.exit(1 if result.error.severity == ErrorSeverity.FATAL else 0)
    
    # Implementation phase
    if args.implement and result.value.status == ConvergenceStatus.CONSENSUS:
        reporter.info("Starting implementation phase...")
        run_implementation(result.value.final_design, result.value.initial_prompt, config.working_dir)


if __name__ == "__main__":
    main()
```

### 9. Error Handling Matrix

| Error Type | Code | Detection | Recovery | User Message |
|------------|------|-----------|----------|--------------|
| Empty prompt | `EMPTY_PROMPT` | Validation | Block | "Prompt cannot be empty. Example: 'Design...'" |
| Prompt too short | `PROMPT_TOO_SHORT` | Validation | Block | "Prompt too short (N chars, need 10+)" |
| Prompt too long | `PROMPT_TOO_LONG` | Validation | Block | "Prompt exceeds max (N > 50000)" |
| CLI not found | `CLI_NOT_FOUND` | Health check | Stop | "Install Claude CLI: npm install -g..." |
| Auth failed | `AUTH_FAILED` | CLI stderr | Stop | "Run 'claude login' to authenticate" |
| Timeout | `CLI_TIMEOUT` | Process monitor | Retry (2x) | "Timed out after Ns. Retrying..." |
| Rate limit | `RATE_LIMITED` | CLI stderr | Retry with backoff | "Rate limited. Waiting 10s..." |
| Network error | `NETWORK_ERROR` | CLI stderr | Retry (2x) | "Network error. Check connection." |
| Truncated response | `RESPONSE_TRUNCATED` | Marker check | Warn, continue | "Response may be incomplete" |
| State save failed | `STATE_SAVE_ERROR` | File write | Warn, continue | "Checkpoint failed (session continues)" |
| Ctrl+C | `INTERRUPTED` | KeyboardInterrupt | Save & exit | "Interrupted. Resume with --resume" |

---

## Rationale

### Key Design Decisions

1. **Result Type with Warnings**: I kept the reviewer's `Success`/`Failure` pattern because it makes error handling explicit and allows for non-fatal warnings. This is cleaner than exceptions for a multi-step orchestration where we need fine-grained control.

2. **Atomic State Writes**: I kept the write-to-temp-then-rename pattern. The cost is minimal (one extra file operation) and it completely prevents corrupted state files from incomplete writes.

3. **No Circuit Breaker**: I agree with the reviewer - it's overkill. Simple retry with exponential backoff handles transient failures without the complexity. A user running 8 rounds interactively will notice repeated failures and can decide what to do.

4. **Completeness Detection**: I added explicit checking for expected response markers (`### Design`, `PROMPT_FOR_*`). This addresses the truncated response concern - we now detect it and warn the user while still using whatever we got.

5. **Pre-flight Health Check**: Validating Claude CLI availability before starting saves the user from discovering auth issues mid-debate.

6. **Checkpoint After Every Agent Turn**: Not just after every round. If the process dies after Agent A but before Agent B, we preserve Agent A's work.

---

## What I Changed

1. **Added Response Completeness Detection**: The `_check_completeness` method looks for expected structural markers. If missing, we warn but continue - the response may still be usable.

2. **Simplified Signal Handling**: Kept atexit for cleanup (from reviewer), removed any complex signal handler ideas.

3. **Added `--timeout` CLI Flag**: Users can now tune timeout per their needs (30-900s range).

4. **Added `--validate` Mode**: Run validation without executing the debate - useful for CI/scripts.

5. **Improved Error Classification**: Added more network-related keywords and the `truncated` error code.

6. **Richer Round Metrics**: Each round now tracks `started_at`, `ended_at`, `duration_seconds` for better debugging.

---

## What I Kept

1. **Result Type Pattern**: From reviewer - explicit `Success`/`Failure` with warnings is cleaner than exceptions for this use case.

2. **Atomic State Writes**: From reviewer - write-to-temp-then-rename prevents corruption.

3. **atexit Cleanup**: From reviewer - simpler than signal handlers, sufficient for this use case.

4. **ValidatedPrompt/ValidatedConfig Types**: From reviewer - encoding validation as types provides guarantees downstream.

5. **Error Severity Classification**: From both - distinguishing FATAL/RECOVERABLE/WARNING drives appropriate handling.

6. **Progress Reporting Structure**: From original - the reporter abstraction with verbose/quiet modes is clean.

---

## Convergence Status

**PROPOSING_FINAL**: I believe this design is complete and addresses all the key concerns:
- Robust error handling with retries and classification
- Clear user feedback with actionable suggestions  
- Input validation with warnings for quality issues
- Atomic state persistence for crash safety
- Response completeness detection
- Clean resumption support

The design is concrete, implementable, and appropriately complex for a CLI tool (no over-engineering like circuit breakers).

---

PROMPT_FOR_CRITIC:

Please review for final consensus on:

1. **Response Completeness Detection**: I added checking for structural markers (`### Design`, `PROMPT_FOR_*`). Is this sufficient, or do we need more sophisticated truncation detection (e.g., looking for incomplete sentences at the end)?

2. **Timeout Range**: I set 30-900s. Is 900s (15 min) reasonable as a maximum, or should we allow longer for very complex prompts?

3. **Retry Count**: I have `max_retries=2` (so up to 2 attempts). Should this be configurable via CLI, or is hardcoding appropriate?

4. **Active Marker File**: I kept the `.active` marker for crash detection. Do you agree this is useful, or is it unnecessary complexity?

5. **Convergence Agreement**: Do you accept this design as final, or are there remaining issues that need iteration?

**Convergence Signal:** PROPOSING_FINAL

### 🟣 Agent B

Now I have the full context - I can see both the current implementation and the Architect's proposed design. Let me provide my review and improved design.

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
│  │  - InputValidator: sanitize, length check, quality warnings             │ │
│  │  - ConfigValidator: bounds, paths, permissions                          │ │
│  │  - HealthCheck: CLI availability + basic auth verification              │ │
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
│  │  - ProgressReporter: status, progress bars, timing estimates            │ │
│  │  - ErrorPresenter: actionable messages with recovery steps              │ │
│  │  - SummaryFormatter: round/session summaries with next steps            │ │
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
    """Error severity classification"""
    FATAL = "fatal"           # Must stop - unrecoverable
    RECOVERABLE = "recoverable"  # Can retry - transient failure
    WARNING = "warning"       # Continue but inform user

@dataclass(frozen=True)
class ErrorInfo:
    """Immutable error information with actionable guidance"""
    code: str                    # Machine-readable: "CLI_TIMEOUT", "INVALID_PROMPT"
    message: str                 # Human-readable description
    severity: ErrorSeverity
    suggestion: str = ""         # Actionable recovery step
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

# Validation constants - centralized for easy tuning
PROMPT_MIN_LENGTH = 10
PROMPT_MAX_LENGTH = 50000
ROUNDS_MIN = 1
ROUNDS_MAX = 30
TIMEOUT_MIN_SECONDS = 30
TIMEOUT_MAX_SECONDS = 900
TIMEOUT_DEFAULT_SECONDS = 300
DEFAULT_MAX_RETRIES = 2

@dataclass(frozen=True)
class ValidatedPrompt:
    """A prompt that has passed validation - immutable guarantee"""
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
        
        # Sanitize: normalize whitespace, remove control characters
        text = raw_input.strip()
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = ''.join(c for c in text if c == '\n' or c == '\t' or ord(c) >= 32)
        
        warnings = []
        
        # Length validation
        if len(text) < PROMPT_MIN_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_SHORT",
                message=f"Prompt is too short ({len(text)} chars, minimum {PROMPT_MIN_LENGTH})",
                severity=ErrorSeverity.FATAL,
                suggestion="Provide more detail about the task"
            ))
        
        if len(text) > PROMPT_MAX_LENGTH:
            return Failure(ErrorInfo(
                code="PROMPT_TOO_LONG",
                message=f"Prompt exceeds maximum length ({len(text)} > {PROMPT_MAX_LENGTH} chars)",
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
        timeout: int = TIMEOUT_DEFAULT_SECONDS,
        working_dir: str = ".",
        output_dir: str = "./debate_output",
        verbose: bool = False,
        quiet: bool = False
    ) -> Result['ValidatedConfig']:
        """Validate all configuration parameters"""
        
        # max_rounds bounds
        if max_rounds < ROUNDS_MIN:
            return Failure(ErrorInfo(
                code="INVALID_ROUNDS",
                message=f"max_rounds must be at least {ROUNDS_MIN} (got {max_rounds})",
                severity=ErrorSeverity.FATAL,
                suggestion="Use --max-rounds with a positive number"
            ))
        if max_rounds > ROUNDS_MAX:
            return Failure(ErrorInfo(
                code="ROUNDS_TOO_HIGH",
                message=f"max_rounds cannot exceed {ROUNDS_MAX} (got {max_rounds})",
                severity=ErrorSeverity.FATAL,
                suggestion=f"Use {ROUNDS_MAX} or fewer rounds to avoid excessive API costs"
            ))
        
        # timeout bounds
        if timeout < TIMEOUT_MIN_SECONDS:
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_LOW",
                message=f"Timeout must be at least {TIMEOUT_MIN_SECONDS} seconds (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion=f"Use --timeout {TIMEOUT_MIN_SECONDS} or higher"
            ))
        if timeout > TIMEOUT_MAX_SECONDS:
            return Failure(ErrorInfo(
                code="TIMEOUT_TOO_HIGH",
                message=f"Timeout cannot exceed {TIMEOUT_MAX_SECONDS} seconds (got {timeout})",
                severity=ErrorSeverity.FATAL,
                suggestion=f"Use --timeout {TIMEOUT_MAX_SECONDS} or lower"
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
            # Resolve conflict: verbose wins
            quiet = False
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
                quiet=quiet
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
                'is_complete': r.agent_a_response.is_complete,
                'parse_warnings': r.agent_a_response.parse_warnings
            }
        if r.agent_b_response:
            d['agent_b'] = {
                'design_content': r.agent_b_response.design_content,
                'prompt_for_other': r.agent_b_response.prompt_for_other,
                'convergence_signal': r.agent_b_response.convergence_signal,
                'raw_response': r.agent_b_response.raw_response,
                'duration_seconds': r.agent_b_response.duration_seconds,
                'is_complete': r.agent_b_response.is_complete,
                'parse_warnings': r.agent_b_response.parse_warnings
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
                    is_complete=a.get('is_complete', True),
                    parse_warnings=a.get('parse_warnings', [])
                )
            if 'agent_b' in r_data:
                b = r_data['agent_b']
                round_obj.agent_b_response = AgentResponse(
                    design_content=b.get('design_content', ''),
                    prompt_for_other=b.get('prompt_for_other', ''),
                    convergence_signal=b.get('convergence_signal', 'ITERATING'),
                    raw_response=b.get('raw_response', ''),
                    duration_seconds=b.get('duration_seconds', 0.0),
                    is_complete=b.get('is_complete', True),
                    parse_warnings=b.get('parse_warnings', [])
                )
            session.rounds.append(round_obj)
        
        return session
```

### 3. ClaudeInvoker - Robust CLI Wrapper

```python
import subprocess
import time
import shutil
import select
import os

class ClaudeInvoker:
    """
    Robust wrapper for Claude CLI calls.
    
    Design:
    - Retry with exponential backoff for transient failures
    - Clear error classification for appropriate recovery
    - Timeout monitoring with clean process termination
    - Response completeness detection via structural markers
    """
    
    # Error classification codes
    ERROR_CODES = {
        'timeout': 'CLI_TIMEOUT',
        'rate': 'RATE_LIMITED',
        'auth': 'AUTH_FAILED',
        'network': 'NETWORK_ERROR',
        'not_found': 'CLI_NOT_FOUND',
        'truncated': 'RESPONSE_TRUNCATED',
        'empty': 'EMPTY_RESPONSE',
        'unknown': 'CLI_ERROR'
    }
    
    def __init__(
        self,
        timeout: int = TIMEOUT_DEFAULT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        on_progress: Optional[Callable[[str], None]] = None
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.on_progress = on_progress or (lambda x: None)
    
    def check_available(self) -> Result[str]:
        """Verify Claude CLI is installed and accessible"""
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
                wait_time = 5 * (2 ** (attempt - 1))  # 5s, 10s
                self.on_progress(f"Retrying in {wait_time}s... (attempt {attempt+1}/{self.max_retries})")
                time.sleep(wait_time)
        
        # All retries exhausted
        return Failure(ErrorInfo(
            code=last_error.code,
            message=f"{last_error.message} (after {self.max_retries} attempts)",
            severity=ErrorSeverity.FATAL,  # Escalate to fatal after all retries
            suggestion=last_error.suggestion,
            context={'attempts': self.max_retries, 'last_error': str(last_error)}
        ))
    
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
                    code=self.ERROR_CODES['empty'],
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
                    message=f"Response may be incomplete: missing {', '.join(completeness['missing'])}",
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
        
        if any(kw in stderr_lower for kw in ['unauthorized', 'authentication', 'api key', '401', 'not logged in']):
            return ErrorInfo(
                code=self.ERROR_CODES['auth'],
                message="Authentication failed",
                severity=ErrorSeverity.FATAL,
                suggestion="Run 'claude login' to authenticate"
            )
        
        if any(kw in stderr_lower for kw in ['connection', 'network', 'dns', 'econnrefused', 'enotfound', 'socket']):
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
        # Required markers for each agent type
        if agent_type == 'agent_a':
            required = ['### Design', 'PROMPT_FOR_CRITIC:']
            optional = ['### Convergence Status']  # Should be present but not fatal
        else:
            required = ['### Design', 'PROMPT_FOR_ARCHITECT:']
            optional = ['### Convergence Status']
        
        missing = [m for m in required if m not in response]
        
        # Also check for abrupt endings (indicates possible truncation)
        lines = response.strip().split('\n')
        if lines:
            last_line = lines[-1].strip()
            # Suspicious endings that suggest truncation
            if last_line.endswith(('...', '```', '---')) and len(last_line) < 10:
                if 'abrupt_ending' not in missing:
                    missing.append('(response appears truncated)')
        
        return {
            'is_complete': len(missing) == 0,
            'missing': missing
        }
```

### 4. StateManager - Atomic Persistence

```python
import atexit
import tempfile

class StateManager:
    """
    Manages session state with atomic writes and cleanup.
    
    Design:
    - Atomic writes via write-to-temp-then-rename
    - atexit-based cleanup for graceful termination
    - Auto-checkpoint after each agent turn
    - Graceful handling of save failures (warn, don't crash)
    """
    
    def __init__(self, session_dir: Path):
        self.session_dir = session_dir
        self.state_file = session_dir / "session_state.json"
        self._cleanup_registered = False
        self._current_session: Optional[DebateSession] = None
    
    def initialize(self) -> Result[bool]:
        """Create session directory and register cleanup"""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            
            # Verify write permission by creating a test file
            test_file = self.session_dir / ".write_test"
            try:
                test_file.write_text("test")
                test_file.unlink()
            except Exception as e:
                return Failure(ErrorInfo(
                    code="STATE_PERMISSION_ERROR",
                    message=f"Cannot write to session directory: {e}",
                    severity=ErrorSeverity.FATAL,
                    suggestion="Check directory permissions or use --output with a writable path"
                ))
            
            # Register cleanup on exit
            if not self._cleanup_registered:
                atexit.register(self._cleanup)
                self._cleanup_registered = True
            
            return Success(value=True)
            
        except PermissionError as e:
            return Failure(ErrorInfo(
                code="STATE_PERMISSION_ERROR",
                message=f"Cannot create session directory: {e}",
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
    
    def save(self, session: DebateSession) -> Result[bool]:
        """
        Save session state atomically.
        Write to temp file, then rename for crash safety.
        """
        self._current_session = session
        
        try:
            data = session.to_dict()
            
            # Create temp file in same directory (ensures same filesystem for atomic rename)
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
        """Clean up on exit - save final state if we have one"""
        if self._current_session and self._current_session.status == ConvergenceStatus.DEBATING:
            # Mark as interrupted if we're exiting mid-debate
            self._current_session.status = ConvergenceStatus.INTERRUPTED
            self._current_session.ended_at = datetime.now().isoformat()
            try:
                self.save(self._current_session)
            except:
                pass  # Best effort
```

### 5. UserReporter - Clear, Actionable Feedback

```python
import sys

class Colors:
    """ANSI color codes"""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    BLUE = '\033[0;34m'
    YELLOW = '\033[1;33m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'
    BOLD = '\033[1m'
    NC = '\033[0m'  # No Color

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
            print(f"  {self._c(Colors.CYAN, 'Debug:')} {json.dumps(error.context)}", file=sys.stderr)
    
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
    
    def show_validation_summary(self, prompt_result: Result, config_result: Result) -> bool:
        """Show validation results before starting debate. Returns True if valid."""
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
        
        # Progress bar for convergence
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
        """Show final session summary with next steps"""
        print(f"\n{'═' * 60}")
        print(f"{self._c(Colors.BOLD, '  DEBATE COMPLETE')}")
        print(f"{'═' * 60}")
        
        # Status with appropriate color
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
        
        # Next steps based on status
        if session.status == ConvergenceStatus.CONSENSUS:
            print(f"\n  {self._c(Colors.CYAN, 'To implement:')} claude \"Implement this design: $(cat {session_dir / 'final_design.md'})\"")
        elif session.status == ConvergenceStatus.INTERRUPTED:
            print(f"\n  {self._c(Colors.YELLOW, 'To resume:')} debate --resume {session_dir}")
        elif session.status == ConvergenceStatus.DEBATING:
            print(f"\n  {self._c(Colors.YELLOW, 'To continue:')} debate --resume {session_dir} --max-rounds {session.config.get('max_rounds', 8) + 5}")
        
        print(f"{'═' * 60}\n")
```

### 6. Response Parser

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
            # Fallback: use content before prompt marker
            design_content = response.split(prompt_marker)[0].strip() if prompt_marker in response else response
        
        # Check completeness
        is_complete = len(parse_warnings) == 0
        
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
```

### 7. Main Orchestration

```python
import difflib

def calculate_similarity(text_a: str, text_b: str) -> float:
    """Calculate similarity between two design texts (0.0 to 1.0)"""
    lines_a = [l.strip() for l in text_a.split('\n') if l.strip()]
    lines_b = [l.strip() for l in text_b.split('\n') if l.strip()]
    if not lines_a or not lines_b:
        return 0.0
    return difflib.SequenceMatcher(None, lines_a, lines_b).ratio()

def check_convergence(agent_a: AgentResponse, agent_b: AgentResponse) -> ConvergenceStatus:
    """Check if the agents have reached consensus"""
    a_ready = agent_a.convergence_signal == "PROPOSING_FINAL"
    b_accepts = agent_b.convergence_signal == "ACCEPTING_FINAL"
    b_minor = agent_b.convergence_signal == "MINOR_ISSUES"
    
    if a_ready and b_accepts:
        return ConvergenceStatus.CONSENSUS
    elif a_ready or b_minor:
        return ConvergenceStatus.CONVERGING
    return ConvergenceStatus.DEBATING

def run_debate(
    prompt: ValidatedPrompt,
    config: ValidatedConfig,
    reporter: UserReporter,
    resumed_session: Optional[DebateSession] = None
) -> Result[DebateSession]:
    """
    Main debate orchestration.
    Accepts only validated inputs - validation happens at CLI layer.
    """
    
    # Create invoker with progress callback
    invoker = ClaudeInvoker(
        timeout=config.timeout_seconds,
        on_progress=lambda msg: reporter.debug(msg)
    )
    
    # Pre-flight check
    reporter.info("Checking Claude CLI...")
    health = invoker.check_available()
    if isinstance(health, Failure):
        reporter.error(health.error)
        return health
    reporter.success(f"Claude CLI ready ({health.value})")
    
    # Setup session
    if resumed_session:
        session = resumed_session
        session_dir = Path(session.config.get('session_dir', str(config.output_dir)))
        start_round = len(session.rounds) + 1
        reporter.info(f"Resuming session from round {start_round}")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = config.output_dir / f"session_{timestamp}"
        session = DebateSession(
            session_id=timestamp,
            initial_prompt=prompt.text,
            config={
                'max_rounds': config.max_rounds,
                'timeout': config.timeout_seconds,
                'working_dir': str(config.working_dir),
                'session_dir': str(session_dir)
            }
        )
        start_round = 1
    
    # Initialize state manager
    state_mgr = StateManager(session_dir)
    init_result = state_mgr.initialize()
    if isinstance(init_result, Failure):
        reporter.error(init_result.error)
        return init_result
    
    # Print header and session info
    reporter.info(f"Task: {prompt.text[:100]}{'...' if len(prompt.text) > 100 else ''}")
    reporter.info(f"Session: {session_dir}")
    
    # Track responses for context
    last_agent_a: Optional[AgentResponse] = None
    last_agent_b: Optional[AgentResponse] = None
    
    if resumed_session and session.rounds:
        last_round = session.rounds[-1]
        last_agent_a = last_round.agent_a_response
        last_agent_b = last_round.agent_b_response
    
    session_start_time = time.time()
    
    try:
        for round_num in range(start_round, config.max_rounds + 1):
            round_start = time.time()
            debate_round = DebateRound(
                round_number=round_num,
                started_at=datetime.now().isoformat()
            )
            
            # === Agent A (Architect) Turn ===
            reporter.progress(
                "Creating design..." if round_num == 1 else "Improving design...",
                agent='A', round_num=round_num
            )
            
            agent_a_prompt = build_agent_a_prompt(round_num, prompt.text, last_agent_b)
            
            agent_a_start = time.time()
            response_a = invoker.invoke(
                get_agent_a_system_prompt(),
                agent_a_prompt,
                config.working_dir,
                agent_type='agent_a'
            )
            
            if isinstance(response_a, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(f"Agent A failed: {response_a.error}")
                state_mgr.save(session)
                reporter.error(response_a.error)
                return response_a
            
            # Report any warnings
            for w in response_a.warnings:
                reporter.warning(w)
            
            last_agent_a = ResponseParser.parse(response_a.value, is_agent_a=True)
            last_agent_a.duration_seconds = time.time() - agent_a_start
            debate_round.agent_a_response = last_agent_a
            
            reporter.success(f"Design complete ({last_agent_a.duration_seconds:.0f}s)")
            
            # Checkpoint after Agent A
            session.rounds.append(debate_round)  # Add incomplete round for checkpoint
            state_mgr.save(session)
            session.rounds.pop()  # Remove for proper completion below
            
            # === Agent B (Reviewer) Turn ===
            reporter.progress("Reviewing design...", agent='B', round_num=round_num)
            
            agent_b_prompt = build_agent_b_prompt(prompt.text, last_agent_a)
            
            agent_b_start = time.time()
            response_b = invoker.invoke(
                get_agent_b_system_prompt(),
                agent_b_prompt,
                config.working_dir,
                agent_type='agent_b'
            )
            
            if isinstance(response_b, Failure):
                session.status = ConvergenceStatus.FAILED
                session.error_log.append(f"Agent B failed: {response_b.error}")
                state_mgr.save(session)
                reporter.error(response_b.error)
                return response_b
            
            for w in response_b.warnings:
                reporter.warning(w)
            
            last_agent_b = ResponseParser.parse(response_b.value, is_agent_a=False)
            last_agent_b.duration_seconds = time.time() - agent_b_start
            debate_round.agent_b_response = last_agent_b
            
            reporter.success(f"Review complete ({last_agent_b.duration_seconds:.0f}s)")
            
            # Complete round metrics
            debate_round.duration_seconds = time.time() - round_start
            debate_round.ended_at = datetime.now().isoformat()
            debate_round.convergence_score = calculate_similarity(
                last_agent_a.design_content,
                last_agent_b.design_content
            )
            
            session.rounds.append(debate_round)
            state_mgr.save(session)
            
            # Show round summary
            reporter.show_round_summary(
                round_num, config.max_rounds,
                debate_round.duration_seconds,
                debate_round.convergence_score,
                last_agent_a.convergence_signal,
                last_agent_b.convergence_signal
            )
            
            # Check for consensus
            if check_convergence(last_agent_a, last_agent_b) == ConvergenceStatus.CONSENSUS:
                session.status = ConvergenceStatus.CONSENSUS
                session.final_design = last_agent_a.design_content
                reporter.success("CONSENSUS REACHED! 🤝")
                break
        
        # Finalize session
        session.ended_at = datetime.now().isoformat()
        session.total_duration_seconds = time.time() - session_start_time
        
        if session.status == ConvergenceStatus.DEBATING:
            # Max rounds reached without consensus - use latest design
            session.final_design = last_agent_a.design_content if last_agent_a else ""
        
        save_final_outputs(session, session_dir)
        state_mgr.save(session)
        
        reporter.show_final_summary(session, session_dir)
        return Success(value=session)
        
    except KeyboardInterrupt:
        session.status = ConvergenceStatus.INTERRUPTED
        session.ended_at = datetime.now().isoformat()
        session.total_duration_seconds = time.time() - session_start_time
        state_mgr.save(session)
        
        reporter.warning(ErrorInfo(
            code="INTERRUPTED",
            message="Debate interrupted by user",
            severity=ErrorSeverity.WARNING,
            suggestion=f"Resume with: debate --resume {session_dir}"
        ))
        
        return Failure(ErrorInfo(
            code="INTERRUPTED",
            message="Session interrupted",
            severity=ErrorSeverity.WARNING
        ))

def save_final_outputs(session: DebateSession, session_dir: Path):
    """Save final design and history files"""
    # Save final design
    final_design_file = session_dir / "final_design.md"
    with open(final_design_file, 'w') as f:
        f.write(f"# Final Design\n\n")
        f.write(f"**Task:** {session.initial_prompt}\n\n")
        f.write(f"**Status:** {session.status.value}\n\n")
        f.write("---\n\n")
        f.write(session.final_design)
    
    # Save debate history
    history_file = session_dir / "debate_history.md"
    with open(history_file, 'w') as f:
        f.write(f"# Debate History\n\n")
        f.write(f"**Started:** {session.started_at}\n")
        f.write(f"**Ended:** {session.ended_at}\n")
        f.write(f"**Status:** {session.status.value}\n")
        f.write(f"**Rounds:** {len(session.rounds)}\n\n")
        f.write(f"## Initial Prompt\n\n{session.initial_prompt}\n\n---\n\n")
        
        for r in session.rounds:
            f.write(f"## Round {r.round_number}\n\n")
            if r.agent_a_response:
                f.write(f"### 🔵 Architect\n\n{r.agent_a_response.raw_response}\n\n")
            if r.agent_b_response:
                f.write(f"### 🟣 Reviewer\n\n{r.agent_b_response.raw_response}\n\n")
            f.write("---\n\n")
```

### 8. CLI Entry Point

```python
def main():
    parser = argparse.ArgumentParser(
        description="Claude Code Debate System - Two AI agents debate to optimal designs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  debate "Design a REST API for user management"
  debate -f requirements.txt --max-rounds 10
  debate --resume latest
  debate --health-check
        """
    )
    parser.add_argument('prompt', nargs='?', help='Task description')
    parser.add_argument('-f', '--file', help='Read prompt from file')
    parser.add_argument('-m', '--max-rounds', type=int, default=8)
    parser.add_argument('-o', '--output', default='./debate_output')
    parser.add_argument('-w', '--working-dir', default='.')
    parser.add_argument('-t', '--timeout', type=int, default=TIMEOUT_DEFAULT_SECONDS,
                        help=f'Timeout per agent call ({TIMEOUT_MIN_SECONDS}-{TIMEOUT_MAX_SECONDS}s, default: {TIMEOUT_DEFAULT_SECONDS})')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-q', '--quiet', action='store_true')
    parser.add_argument('-r', '--resume', nargs='?', const='latest')
    parser.add_argument('-l', '--list', action='store_true', help='List resumable sessions')
    parser.add_argument('--health-check', action='store_true', help='Verify CLI and exit')
    parser.add_argument('-i', '--implement', action='store_true')
    
    args = parser.parse_args()
    
    # Create reporter early
    reporter = UserReporter(verbose=args.verbose, quiet=args.quiet)
    
    # Health check mode
    if args.health_check:
        invoker = ClaudeInvoker()
        result = invoker.check_available()
        if isinstance(result, Success):
            reporter.success(f"Claude CLI available: {result.value}")
            sys.exit(0)
        else:
            reporter.error(result.error)
            sys.exit(1)
    
    # List sessions mode  
    if args.list:
        list_sessions(args.output, reporter)
        sys.exit(0)
    
    # Resume mode
    resumed_session = None
    if args.resume:
        resumed_session = load_resumed_session(args.resume, args.output, reporter)
        if not resumed_session:
            sys.exit(1)
    
    # Get prompt
    raw_prompt = args.prompt
    if args.file:
        try:
            with open(args.file, 'r') as f:
                raw_prompt = f.read().strip()
        except Exception as e:
            reporter.error(ErrorInfo(
                code="FILE_READ_ERROR",
                message=f"Cannot read prompt file: {e}",
                severity=ErrorSeverity.FATAL,
                suggestion="Check file path and permissions"
            ))
            sys.exit(1)
    
    if not raw_prompt and not resumed_session:
        parser.print_help()
        print(f"\n{Colors.RED}Error: No prompt provided{Colors.NC}")
        sys.exit(1)
    
    # Validate inputs
    prompt_result = ValidatedPrompt.validate(raw_prompt) if raw_prompt else Success(value=None)
    config_result = ValidatedConfig.validate(
        max_rounds=args.max_rounds,
        timeout=args.timeout,
        working_dir=args.working_dir,
        output_dir=args.output,
        verbose=args.verbose,
        quiet=args.quiet
    )
    
    if not reporter.show_validation_summary(prompt_result, config_result):
        sys.exit(1)
    
    prompt = prompt_result.value if isinstance(prompt_result, Success) else None
    config = config_result.value
    
    # Handle resumed session prompt
    if resumed_session and not prompt:
        prompt = ValidatedPrompt(text=resumed_session.initial_prompt, word_count=len(resumed_session.initial_prompt.split()))
    
    result = run_debate(
        prompt=prompt,
        config=config,
        reporter=reporter,
        resumed_session=resumed_session
    )
    
    if isinstance(result, Failure):
        sys.exit(1 if result.error.severity == ErrorSeverity.FATAL else 0)
    
    # Implementation phase
    if args.implement and result.value.status == ConvergenceStatus.CONSENSUS:
        reporter.info("Starting implementation...")
        run_implementation(result.value.final_design, result.value.initial_prompt, config.working_dir)

if __name__ == "__main__":
    main()
```

---

## Rationale

### Key Design Decisions

1. **Result Type Pattern**: The explicit `Success`/`Failure` union with typed errors provides compile-time (via type hints) and runtime clarity about what can go wrong. This is superior to exceptions for an orchestration layer where we need fine-grained control over error recovery.

2. **Centralized Constants**: I extracted all magic numbers (`PROMPT_MIN_LENGTH`, `TIMEOUT_MAX_SECONDS`, etc.) to module-level constants. This makes tuning easier and keeps validation logic clean.

3. **Atomic State Writes**: The write-to-temp-then-rename pattern is essential for crash safety. The overhead is negligible compared to the risk of corrupted state files.

4. **Escalating Retry Failures to Fatal**: After exhausting retries, I escalate RECOVERABLE errors to FATAL with a message indicating all attempts failed. This prevents infinite loops and gives users a clear signal.

5. **Checkpoint After Each Agent Turn**: This preserves work even if the process dies between Agent A and Agent B responses.

---

## What I Improved

1. **Removed `.active` Marker File**: The Architect proposed an active marker for crash detection, but this adds complexity without clear benefit. The `atexit` cleanup already marks sessions as INTERRUPTED if they exit mid-debate. The marker file requires additional logic to handle stale markers from hard crashes and doesn't provide actionable information to the user.

2. **Simplified Truncation Detection**: The Architect's completeness check is good, but I improved it by:
   - Checking for abrupt endings (lines ending with `...`, `\`\`\``, `---` that suggest mid-output cutoff)
   - Making parse warnings feed directly into `is_complete` flag
   - Combining ClaudeInvoker's marker check with ResponseParser's structural parsing

3. **Better State Manager Cleanup**: Instead of an active marker, the StateManager now:
   - Tracks current session internally
   - On atexit, if session is still DEBATING, marks it as INTERRUPTED
   - This is simpler and more reliable than marker files

4. **Retry Exhaustion Handling**: After all retries fail, I escalate the error to FATAL with context about how many attempts were made. The Architect's version would keep the error as RECOVERABLE, which doesn't give the main loop a clear signal to stop.

5. **Cleaner Checkpoint Logic**: Fixed a subtle bug in the checkpoint-after-Agent-A logic. The Architect's version saves after adding the round, but the round isn't complete yet. I add/save/pop to preserve Agent A's work without leaving an incomplete round in the session.

---

## What I Kept

1. **Result Type with Warnings**: Perfect for this use case - errors are explicit, warnings don't block progress.

2. **ValidatedPrompt/ValidatedConfig Types**: Encoding validation as types provides guarantees downstream.

3. **Error Severity Classification**: FATAL/RECOVERABLE/WARNING drives appropriate handling.

4. **Atomic File Writes**: Essential for reliability.

5. **Pre-flight Health Check**: Catching auth issues early saves frustration.

6. **Timeout CLI Flag**: User-configurable timeout is important for complex prompts.

---

## Remaining Concerns

1. **Timeout Range (30-900s)**: 900s (15 min) seems reasonable. Very complex design tasks might need this. Users who need longer can run multiple sessions or break tasks down.

2. **Retry Count Not Configurable**: Hardcoding `max_retries=2` is appropriate. Making it configurable adds CLI complexity for minimal benefit. If someone is seeing frequent failures, the underlying issue (network, auth, rate limits) should be fixed rather than masked with more retries.

3. **No Convergence Detection Enhancement**: The similarity-based convergence score is simplistic but effective. More sophisticated NLP-based comparison would add dependencies and complexity without clear benefit for a CLI tool.

---

## Convergence Status

**ACCEPTING_FINAL**: The Architect's design is fundamentally sound. My changes are refinements rather than architectural shifts:
- Removed unnecessary `.active` marker complexity
- Improved retry exhaustion handling  
- Fixed checkpoint ordering
- Centralized constants

The core architecture (Result types, validation layer, ClaudeInvoker, StateManager, UserReporter) is correct and complete. I accept this design as final.

---

PROMPT_FOR_ARCHITECT:

I've accepted your design as final with minor refinements:

1. **Removed `.active` marker** - I believe atexit cleanup is sufficient. If you feel strongly that crash detection needs the marker, please explain the scenario where atexit fails but the marker would help.

2. **Centralized constants** - I moved magic numbers to module-level constants. This is a style preference but I think it improves maintainability.

3. **Fixed checkpoint ordering** - The add/save/pop pattern for mid-round checkpoints ensures we don't leave incomplete rounds in the session.

Do you accept these refinements, or do you have concerns about any of them?

**Convergence Signal:** ACCEPTING_FINAL

---

