# Final Agreed Design

**Task:** Improve this Claude Code plugin repository (plan-with-debate) to make it more production-ready. Key focus areas: 1) OBSERVABILITY - add progress indicators, status updates, and visibility into what the debate agents are doing (this is critical and currently missing), 2) Error handling and edge cases, 3) User experience improvements. The plugin should give users clear feedback about debate progress, which round they're on, what each agent is thinking, and estimated completion.

**Status:** consensus

---

Now I have a complete understanding of the current codebase. Let me create a comprehensive design to make this plugin production-ready with a focus on observability.

---

## Design

### 1. Architecture Overview

The enhanced plugin will follow a **layered architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        User Interface Layer                         │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────────────────────┐│
│  │ CLI Output  │  │ Progress Bar│  │ Status Dashboard (TUI)       ││
│  │ Formatter   │  │ Manager     │  │ - Live updates               ││
│  └─────────────┘  └─────────────┘  │ - Agent activity indicators  ││
│                                     │ - Round summaries            ││
│                                     └──────────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│                        Observability Layer                          │
│  ┌─────────────────┐  ┌───────────────┐  ┌────────────────────────┐│
│  │ Event Emitter   │  │ Metrics       │  │ Progress Tracker       ││
│  │ - Agent started │  │ Collector     │  │ - Estimated time       ││
│  │ - Agent thinking│  │ - Tokens used │  │ - Phase detection      ││
│  │ - Design ready  │  │ - Round times │  │ - Convergence scoring  ││
│  │ - Converging    │  │ - API latency │  │                        ││
│  └─────────────────┘  └───────────────┘  └────────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│                        Core Debate Engine                           │
│  ┌───────────────────┐  ┌─────────────────┐  ┌────────────────────┐│
│  │ Debate Orchestrator│  │ Agent Manager   │  │ Convergence        ││
│  │ - Round management │  │ - Claude calls  │  │ Detector           ││
│  │ - State machine    │  │ - Response parse│  │ - Similarity check ││
│  │ - Error recovery   │  │ - Retry logic   │  │ - Signal parsing   ││
│  └───────────────────┘  └─────────────────┘  └────────────────────┘│
├─────────────────────────────────────────────────────────────────────┤
│                        Persistence Layer                            │
│  ┌─────────────────┐  ┌───────────────┐  ┌────────────────────────┐│
│  │ Session Store   │  │ Checkpoint    │  │ Export Manager         ││
│  │ - JSON state    │  │ Manager       │  │ - Markdown             ││
│  │ - Recovery data │  │ - Auto-save   │  │ - JSON                 ││
│  └─────────────────┘  └───────────────┘  └────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### 2. Data Models

#### 2.1 Enhanced Core Models

```python
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
import time

class DebatePhase(Enum):
    """High-level phases of the debate for user understanding"""
    INITIALIZING = "initializing"
    FIRST_DESIGN = "first_design"          # Agent A's initial proposal
    REVIEWING = "reviewing"                 # Agent B reviewing
    ITERATING = "iterating"                # Back-and-forth improvement
    CONVERGING = "converging"              # Designs becoming similar
    FINALIZING = "finalizing"              # Final consensus check
    COMPLETED = "completed"
    FAILED = "failed"

class AgentState(Enum):
    """Current state of an individual agent"""
    IDLE = "idle"
    THINKING = "thinking"                   # API call in progress
    DESIGNING = "designing"                 # Generating design content
    ANALYZING = "analyzing"                 # Reviewing other agent's work
    WAITING = "waiting"                     # Waiting for other agent

@dataclass
class AgentActivity:
    """Real-time activity tracking for an agent"""
    agent_id: str                           # "architect" or "reviewer"
    state: AgentState = AgentState.IDLE
    current_action: str = ""                # Human-readable description
    started_at: Optional[float] = None      # Unix timestamp
    tokens_generated: int = 0
    lines_generated: int = 0
    last_output_preview: str = ""           # Last few lines of output

@dataclass
class RoundMetrics:
    """Metrics for a single debate round"""
    round_number: int
    agent_a_duration_seconds: float = 0.0
    agent_b_duration_seconds: float = 0.0
    agent_a_tokens: int = 0
    agent_b_tokens: int = 0
    convergence_score: float = 0.0          # 0.0 to 1.0, how similar designs are
    key_changes: List[str] = field(default_factory=list)

@dataclass
class ProgressEstimate:
    """Estimated progress and completion time"""
    current_round: int
    total_rounds_estimate: int              # Best guess at total rounds needed
    elapsed_seconds: float
    estimated_remaining_seconds: float
    estimated_completion_time: datetime
    confidence: float                       # 0.0 to 1.0

@dataclass 
class DebateEvent:
    """An observable event in the debate lifecycle"""
    event_type: str
    timestamp: float
    data: Dict[str, Any]
    round_number: Optional[int] = None
    agent_id: Optional[str] = None

# Event types
EVENT_DEBATE_STARTED = "debate_started"
EVENT_ROUND_STARTED = "round_started"
EVENT_ROUND_COMPLETED = "round_completed"
EVENT_AGENT_THINKING = "agent_thinking"
EVENT_AGENT_OUTPUT = "agent_output"
EVENT_AGENT_COMPLETED = "agent_completed"
EVENT_CONVERGENCE_UPDATE = "convergence_update"
EVENT_PHASE_CHANGE = "phase_change"
EVENT_ERROR = "error"
EVENT_DEBATE_COMPLETED = "debate_completed"

@dataclass
class AgentResponse:
    """Enhanced response from an agent"""
    content: str
    prompt_for_other: str
    convergence_signal: str
    raw_response: str
    # New fields for observability
    duration_seconds: float = 0.0
    token_count: int = 0
    design_sections: Dict[str, str] = field(default_factory=dict)  # Parsed sections
    key_decisions: List[str] = field(default_factory=list)

@dataclass
class DebateSession:
    """Enhanced debate session with full observability"""
    initial_prompt: str
    rounds: List['DebateRound'] = field(default_factory=list)
    final_design: str = ""
    status: 'ConvergenceStatus' = None      # Set at runtime
    phase: DebatePhase = DebatePhase.INITIALIZING
    started_at: str = ""
    ended_at: str = ""
    session_dir: str = ""
    max_rounds: int = 8
    working_dir: str = "."
    
    # Observability fields
    events: List[DebateEvent] = field(default_factory=list)
    round_metrics: List[RoundMetrics] = field(default_factory=list)
    agent_a_activity: AgentActivity = None
    agent_b_activity: AgentActivity = None
    current_progress: Optional[ProgressEstimate] = None
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
    def __post_init__(self):
        if self.agent_a_activity is None:
            self.agent_a_activity = AgentActivity(agent_id="architect")
        if self.agent_b_activity is None:
            self.agent_b_activity = AgentActivity(agent_id="reviewer")
```

### 3. Observability System

#### 3.1 Event Emitter

```python
from typing import Callable, List, Dict, Any
import threading
from queue import Queue

class EventEmitter:
    """Thread-safe event emitter for debate observability"""
    
    def __init__(self):
        self._listeners: Dict[str, List[Callable]] = {}
        self._global_listeners: List[Callable] = []
        self._event_queue: Queue = Queue()
        self._lock = threading.Lock()
    
    def on(self, event_type: str, callback: Callable[[DebateEvent], None]):
        """Register a listener for a specific event type"""
        with self._lock:
            if event_type not in self._listeners:
                self._listeners[event_type] = []
            self._listeners[event_type].append(callback)
    
    def on_all(self, callback: Callable[[DebateEvent], None]):
        """Register a listener for all events"""
        with self._lock:
            self._global_listeners.append(callback)
    
    def emit(self, event: DebateEvent):
        """Emit an event to all registered listeners"""
        with self._lock:
            listeners = self._listeners.get(event.event_type, []).copy()
            global_listeners = self._global_listeners.copy()
        
        for listener in listeners + global_listeners:
            try:
                listener(event)
            except Exception as e:
                # Log but don't crash on listener errors
                pass
    
    def emit_simple(self, event_type: str, data: Dict[str, Any], 
                    round_number: int = None, agent_id: str = None):
        """Convenience method to emit events"""
        event = DebateEvent(
            event_type=event_type,
            timestamp=time.time(),
            data=data,
            round_number=round_number,
            agent_id=agent_id
        )
        self.emit(event)
```

#### 3.2 Progress Tracker

```python
class ProgressTracker:
    """Tracks debate progress and estimates completion"""
    
    def __init__(self, max_rounds: int):
        self.max_rounds = max_rounds
        self.start_time: float = 0
        self.round_durations: List[float] = []
        self.convergence_scores: List[float] = []
    
    def start(self):
        self.start_time = time.time()
    
    def record_round(self, duration: float, convergence_score: float):
        self.round_durations.append(duration)
        self.convergence_scores.append(convergence_score)
    
    def get_estimate(self, current_round: int) -> ProgressEstimate:
        elapsed = time.time() - self.start_time
        
        # Estimate remaining rounds based on convergence trend
        if len(self.convergence_scores) >= 2:
            convergence_rate = self._calculate_convergence_rate()
            estimated_remaining = self._estimate_remaining_rounds(
                current_round, convergence_rate
            )
        else:
            estimated_remaining = self.max_rounds - current_round
        
        # Estimate time based on average round duration
        avg_round_time = sum(self.round_durations) / len(self.round_durations) if self.round_durations else 120
        estimated_remaining_time = estimated_remaining * avg_round_time
        
        # Confidence based on data we have
        confidence = min(1.0, len(self.round_durations) / 3)
        
        return ProgressEstimate(
            current_round=current_round,
            total_rounds_estimate=current_round + estimated_remaining,
            elapsed_seconds=elapsed,
            estimated_remaining_seconds=estimated_remaining_time,
            estimated_completion_time=datetime.now() + timedelta(seconds=estimated_remaining_time),
            confidence=confidence
        )
    
    def _calculate_convergence_rate(self) -> float:
        """Calculate rate at which designs are converging"""
        if len(self.convergence_scores) < 2:
            return 0.1
        
        # Linear regression on convergence scores
        n = len(self.convergence_scores)
        x_sum = sum(range(n))
        y_sum = sum(self.convergence_scores)
        xy_sum = sum(i * self.convergence_scores[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        if n * x2_sum - x_sum * x_sum == 0:
            return 0.1
            
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        return max(0.05, slope)  # Minimum 5% convergence per round
    
    def _estimate_remaining_rounds(self, current: int, rate: float) -> int:
        """Estimate rounds until convergence threshold (0.9)"""
        if not self.convergence_scores:
            return self.max_rounds - current
        
        current_score = self.convergence_scores[-1]
        if current_score >= 0.9:
            return 1
        
        remaining = (0.9 - current_score) / rate
        return min(int(remaining) + 1, self.max_rounds - current)
```

#### 3.3 Convergence Analyzer

```python
import difflib

class ConvergenceAnalyzer:
    """Analyzes design similarity and convergence"""
    
    def calculate_similarity(self, design_a: str, design_b: str) -> float:
        """Calculate structural similarity between two designs"""
        # Normalize designs
        lines_a = [l.strip() for l in design_a.split('\n') if l.strip()]
        lines_b = [l.strip() for l in design_b.split('\n') if l.strip()]
        
        # Use sequence matching
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b)
        return matcher.ratio()
    
    def extract_key_changes(self, old_design: str, new_design: str) -> List[str]:
        """Extract key changes between two design versions"""
        changes = []
        
        # Compare section by section
        old_sections = self._parse_sections(old_design)
        new_sections = self._parse_sections(new_design)
        
        # Find added sections
        for section in new_sections:
            if section not in old_sections:
                changes.append(f"Added: {section}")
            elif new_sections[section] != old_sections.get(section):
                changes.append(f"Modified: {section}")
        
        # Find removed sections
        for section in old_sections:
            if section not in new_sections:
                changes.append(f"Removed: {section}")
        
        return changes[:5]  # Limit to top 5 changes
    
    def _parse_sections(self, design: str) -> Dict[str, str]:
        """Parse design into sections"""
        sections = {}
        current_section = "intro"
        current_content = []
        
        for line in design.split('\n'):
            if line.startswith('##') or line.startswith('**'):
                if current_content:
                    sections[current_section] = '\n'.join(current_content)
                current_section = line.strip('#* ')
                current_content = []
            else:
                current_content.append(line)
        
        if current_content:
            sections[current_section] = '\n'.join(current_content)
        
        return sections
```

### 4. User Interface Layer

#### 4.1 Status Dashboard

```python
import sys
import shutil
from datetime import datetime, timedelta

class StatusDashboard:
    """Rich terminal UI for debate progress"""
    
    def __init__(self, session: DebateSession):
        self.session = session
        self.terminal_width = shutil.get_terminal_size().columns
        self._last_render_lines = 0
    
    def render(self):
        """Render the full status dashboard"""
        self._clear_previous()
        
        output = []
        output.extend(self._render_header())
        output.extend(self._render_progress_bar())
        output.extend(self._render_agent_status())
        output.extend(self._render_round_summary())
        output.extend(self._render_time_estimate())
        
        rendered = '\n'.join(output)
        print(rendered)
        self._last_render_lines = len(output)
    
    def _clear_previous(self):
        """Clear previous render for smooth updates"""
        if self._last_render_lines > 0:
            sys.stdout.write(f"\033[{self._last_render_lines}A")
            for _ in range(self._last_render_lines):
                sys.stdout.write("\033[2K\n")
            sys.stdout.write(f"\033[{self._last_render_lines}A")
    
    def _render_header(self) -> List[str]:
        """Render the header section"""
        phase_colors = {
            DebatePhase.INITIALIZING: Colors.YELLOW,
            DebatePhase.FIRST_DESIGN: Colors.BLUE,
            DebatePhase.REVIEWING: Colors.MAGENTA,
            DebatePhase.ITERATING: Colors.CYAN,
            DebatePhase.CONVERGING: Colors.GREEN,
            DebatePhase.FINALIZING: Colors.GREEN,
            DebatePhase.COMPLETED: Colors.GREEN,
            DebatePhase.FAILED: Colors.RED,
        }
        phase = self.session.phase
        color = phase_colors.get(phase, Colors.NC)
        
        return [
            f"{Colors.BOLD}╔{'═' * (self.terminal_width - 2)}╗{Colors.NC}",
            f"{Colors.BOLD}║{Colors.NC}  🎭 Debate: {self._truncate(self.session.initial_prompt, 40)}  "
            f"│  Phase: {color}{phase.value.upper()}{Colors.NC}  {Colors.BOLD}║{Colors.NC}",
            f"{Colors.BOLD}╚{'═' * (self.terminal_width - 2)}╝{Colors.NC}",
        ]
    
    def _render_progress_bar(self) -> List[str]:
        """Render progress bar with round indicator"""
        current = len(self.session.rounds)
        estimate = self.session.current_progress
        total = estimate.total_rounds_estimate if estimate else self.session.max_rounds
        
        bar_width = min(40, self.terminal_width - 30)
        filled = int(bar_width * current / total) if total > 0 else 0
        
        bar = f"{Colors.GREEN}{'█' * filled}{Colors.NC}{'░' * (bar_width - filled)}"
        
        return [
            f"",
            f"  Round {current}/{total}  [{bar}]  "
            f"{self._format_phase_indicator()}",
            f"",
        ]
    
    def _render_agent_status(self) -> List[str]:
        """Render status of both agents"""
        a = self.session.agent_a_activity
        b = self.session.agent_b_activity
        
        def agent_line(activity: AgentActivity, name: str, color: str) -> str:
            icon = self._get_state_icon(activity.state)
            elapsed = ""
            if activity.started_at and activity.state != AgentState.IDLE:
                secs = int(time.time() - activity.started_at)
                elapsed = f" ({secs}s)"
            
            preview = ""
            if activity.last_output_preview:
                preview = f"\n      {Colors.CYAN}└─ {self._truncate(activity.last_output_preview, 60)}{Colors.NC}"
            
            return (f"  {color}{icon} {name}{Colors.NC}: {activity.state.value}{elapsed}"
                   f"  {activity.current_action}{preview}")
        
        return [
            agent_line(a, "Architect", Colors.BLUE),
            agent_line(b, "Reviewer ", Colors.MAGENTA),
            "",
        ]
    
    def _render_round_summary(self) -> List[str]:
        """Render summary of recent rounds"""
        if not self.session.round_metrics:
            return ["  No rounds completed yet", ""]
        
        lines = ["  Recent rounds:"]
        for metrics in self.session.round_metrics[-3:]:  # Last 3 rounds
            conv_bar = self._mini_bar(metrics.convergence_score, 10)
            lines.append(
                f"    R{metrics.round_number}: {conv_bar} "
                f"({metrics.convergence_score:.0%} similar) "
                f"[{metrics.agent_a_duration_seconds:.0f}s + {metrics.agent_b_duration_seconds:.0f}s]"
            )
        
        return lines + [""]
    
    def _render_time_estimate(self) -> List[str]:
        """Render time estimate"""
        estimate = self.session.current_progress
        if not estimate:
            return []
        
        elapsed = timedelta(seconds=int(estimate.elapsed_seconds))
        remaining = timedelta(seconds=int(estimate.estimated_remaining_seconds))
        eta = estimate.estimated_completion_time.strftime("%H:%M:%S")
        
        confidence_indicator = "●" * int(estimate.confidence * 5) + "○" * (5 - int(estimate.confidence * 5))
        
        return [
            f"  ⏱  Elapsed: {elapsed}  │  Remaining: ~{remaining}  │  ETA: {eta}  "
            f"│  Confidence: {confidence_indicator}",
        ]
    
    def _get_state_icon(self, state: AgentState) -> str:
        icons = {
            AgentState.IDLE: "○",
            AgentState.THINKING: "◐",  # Animates: ◐ ◓ ◑ ◒
            AgentState.DESIGNING: "✎",
            AgentState.ANALYZING: "🔍",
            AgentState.WAITING: "⏸",
        }
        return icons.get(state, "?")
    
    def _format_phase_indicator(self) -> str:
        """Show convergence trend"""
        if len(self.session.round_metrics) < 2:
            return ""
        
        scores = [m.convergence_score for m in self.session.round_metrics[-3:]]
        if len(scores) >= 2:
            trend = scores[-1] - scores[-2]
            if trend > 0.05:
                return f"{Colors.GREEN}↗ Converging{Colors.NC}"
            elif trend < -0.05:
                return f"{Colors.YELLOW}↘ Diverging{Colors.NC}"
            else:
                return f"{Colors.CYAN}→ Stable{Colors.NC}"
        return ""
    
    def _mini_bar(self, value: float, width: int) -> str:
        filled = int(width * value)
        return f"[{'█' * filled}{'░' * (width - filled)}]"
    
    def _truncate(self, text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[:max_len - 3] + "..."
```

#### 4.2 Streaming Output Handler

```python
class StreamingOutputHandler:
    """Handles streaming output from Claude CLI with live preview"""
    
    def __init__(self, emitter: EventEmitter, agent_id: str, color: str):
        self.emitter = emitter
        self.agent_id = agent_id
        self.color = color
        self.lines_buffer: List[str] = []
        self.preview_lines = 6
        self._printed_lines = 0
        self._start_time: float = 0
    
    def start(self):
        self._start_time = time.time()
        self.lines_buffer = []
        self._printed_lines = 0
    
    def process_line(self, line: str):
        """Process a single line of output"""
        self.lines_buffer.append(line)
        
        # Emit event for observers
        self.emitter.emit_simple(
            EVENT_AGENT_OUTPUT,
            {
                "line": line,
                "line_number": len(self.lines_buffer),
                "elapsed": time.time() - self._start_time,
            },
            agent_id=self.agent_id
        )
        
        # Update live preview
        self._update_preview()
    
    def _update_preview(self):
        """Update the rolling preview in terminal"""
        preview = self.lines_buffer[-self.preview_lines:]
        
        # Clear previous preview
        if self._printed_lines > 0:
            sys.stdout.write(f"\033[{self._printed_lines}A")
            for _ in range(self._printed_lines):
                sys.stdout.write("\033[2K\n")
            sys.stdout.write(f"\033[{self._printed_lines}A")
        
        # Print new preview
        self._printed_lines = len(preview)
        for pl in preview:
            display = pl[:100] + "..." if len(pl) > 100 else pl
            sys.stdout.write(f"\033[2m{self.color}  │ {display}{Colors.NC}\033[0m\n")
        sys.stdout.flush()
    
    def finish(self) -> str:
        """Clear preview and return full output"""
        if self._printed_lines > 0:
            sys.stdout.write(f"\033[{self._printed_lines}A")
            for _ in range(self._printed_lines):
                sys.stdout.write("\033[2K\n")
            sys.stdout.write(f"\033[{self._printed_lines}A")
            sys.stdout.flush()
        
        return '\n'.join(self.lines_buffer).strip()
```

### 5. Error Handling

#### 5.1 Error Types and Recovery

```python
class DebateError(Exception):
    """Base exception for debate errors"""
    def __init__(self, message: str, recoverable: bool = True, 
                 context: Dict[str, Any] = None):
        super().__init__(message)
        self.recoverable = recoverable
        self.context = context or {}

class AgentTimeoutError(DebateError):
    """Agent took too long to respond"""
    def __init__(self, agent_id: str, timeout_seconds: int):
        super().__init__(
            f"Agent {agent_id} timed out after {timeout_seconds}s",
            recoverable=True,
            context={"agent_id": agent_id, "timeout": timeout_seconds}
        )

class AgentResponseError(DebateError):
    """Agent returned invalid/unparseable response"""
    pass

class CLIError(DebateError):
    """Claude CLI execution error"""
    pass

class ConvergenceFailureError(DebateError):
    """Agents failed to converge within max rounds"""
    def __init__(self, rounds_completed: int, final_score: float):
        super().__init__(
            f"Failed to converge after {rounds_completed} rounds (score: {final_score:.0%})",
            recoverable=False,
            context={"rounds": rounds_completed, "score": final_score}
        )

class ErrorHandler:
    """Centralized error handling with retry logic"""
    
    def __init__(self, emitter: EventEmitter, max_retries: int = 3):
        self.emitter = emitter
        self.max_retries = max_retries
        self.error_counts: Dict[str, int] = {}
    
    def handle_agent_error(self, error: DebateError, agent_id: str, 
                           round_num: int) -> bool:
        """Handle an agent error, returns True if should retry"""
        error_key = f"{agent_id}_{type(error).__name__}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Emit error event
        self.emitter.emit_simple(
            EVENT_ERROR,
            {
                "error_type": type(error).__name__,
                "message": str(error),
                "recoverable": error.recoverable,
                "retry_count": self.error_counts[error_key],
                "context": error.context,
            },
            round_number=round_num,
            agent_id=agent_id
        )
        
        if not error.recoverable:
            return False
        
        if self.error_counts[error_key] > self.max_retries:
            return False
        
        return True
    
    def wrap_agent_call(self, func: Callable, agent_id: str, 
                        round_num: int) -> Any:
        """Wrap an agent call with error handling and retries"""
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func()
            except subprocess.TimeoutExpired as e:
                last_error = AgentTimeoutError(agent_id, 300)
            except subprocess.CalledProcessError as e:
                last_error = CLIError(f"CLI error: {e.stderr}", 
                                      recoverable=attempt < self.max_retries)
            except Exception as e:
                last_error = DebateError(str(e), recoverable=attempt < self.max_retries)
            
            if not self.handle_agent_error(last_error, agent_id, round_num):
                raise last_error
            
            # Exponential backoff
            wait_time = 2 ** attempt
            time.sleep(wait_time)
        
        raise last_error
```

### 6. Enhanced Main Orchestrator

```python
class DebateOrchestrator:
    """Main orchestrator with full observability"""
    
    def __init__(self, config: Dict[str, Any]):
        self.emitter = EventEmitter()
        self.progress_tracker = ProgressTracker(config.get('max_rounds', 8))
        self.convergence_analyzer = ConvergenceAnalyzer()
        self.error_handler = ErrorHandler(self.emitter)
        self.dashboard = None
        self.session: Optional[DebateSession] = None
        self.config = config
    
    def run(self, initial_prompt: str) -> DebateSession:
        """Run the full debate with observability"""
        
        # Initialize session
        self.session = DebateSession(
            initial_prompt=initial_prompt,
            max_rounds=self.config.get('max_rounds', 8),
            working_dir=self.config.get('working_dir', '.'),
            phase=DebatePhase.INITIALIZING
        )
        
        # Setup dashboard
        self.dashboard = StatusDashboard(self.session)
        
        # Register default observers
        self._register_observers()
        
        # Emit start event
        self.emitter.emit_simple(EVENT_DEBATE_STARTED, {
            "prompt": initial_prompt,
            "max_rounds": self.session.max_rounds
        })
        
        self.progress_tracker.start()
        
        try:
            self._run_debate_loop()
        except DebateError as e:
            self.session.phase = DebatePhase.FAILED
            self.session.error_history.append({
                "type": type(e).__name__,
                "message": str(e),
                "timestamp": time.time()
            })
            raise
        finally:
            self._cleanup()
        
        return self.session
    
    def _run_debate_loop(self):
        """Main debate loop"""
        agent_a_response = None
        agent_b_response = None
        
        for round_num in range(1, self.session.max_rounds + 1):
            round_start = time.time()
            
            # Update phase
            if round_num == 1:
                self.session.phase = DebatePhase.FIRST_DESIGN
            elif len(self.session.round_metrics) > 0:
                last_score = self.session.round_metrics[-1].convergence_score
                if last_score > 0.8:
                    self.session.phase = DebatePhase.CONVERGING
                elif last_score > 0.9:
                    self.session.phase = DebatePhase.FINALIZING
                else:
                    self.session.phase = DebatePhase.ITERATING
            
            self.emitter.emit_simple(EVENT_ROUND_STARTED, {
                "round": round_num,
                "phase": self.session.phase.value
            }, round_number=round_num)
            
            # Run Agent A
            agent_a_response = self._run_agent_turn(
                "architect", round_num, agent_b_response
            )
            
            # Run Agent B
            self.session.phase = DebatePhase.REVIEWING
            agent_b_response = self._run_agent_turn(
                "reviewer", round_num, agent_a_response
            )
            
            # Calculate round metrics
            round_duration = time.time() - round_start
            similarity = self.convergence_analyzer.calculate_similarity(
                extract_design_section(agent_a_response.raw_response),
                extract_design_section(agent_b_response.raw_response)
            )
            
            metrics = RoundMetrics(
                round_number=round_num,
                agent_a_duration_seconds=agent_a_response.duration_seconds,
                agent_b_duration_seconds=agent_b_response.duration_seconds,
                convergence_score=similarity,
                key_changes=self.convergence_analyzer.extract_key_changes(
                    agent_a_response.content if round_num > 1 else "",
                    agent_b_response.content
                )
            )
            self.session.round_metrics.append(metrics)
            
            # Update progress estimate
            self.progress_tracker.record_round(round_duration, similarity)
            self.session.current_progress = self.progress_tracker.get_estimate(round_num)
            
            # Emit convergence update
            self.emitter.emit_simple(EVENT_CONVERGENCE_UPDATE, {
                "score": similarity,
                "trend": self._calculate_trend(),
                "estimate": self.session.current_progress
            }, round_number=round_num)
            
            # Check convergence
            if self._check_convergence(agent_a_response, agent_b_response):
                self.session.phase = DebatePhase.COMPLETED
                break
            
            # Save checkpoint
            save_session_state(self.session)
            
            # Refresh dashboard
            self.dashboard.render()
        
        # Finalize
        self.session.final_design = extract_design_section(agent_a_response.raw_response)
        self.session.ended_at = datetime.now().isoformat()
        
        self.emitter.emit_simple(EVENT_DEBATE_COMPLETED, {
            "rounds": len(self.session.rounds),
            "final_score": self.session.round_metrics[-1].convergence_score if self.session.round_metrics else 0,
            "phase": self.session.phase.value
        })
    
    def _run_agent_turn(self, agent_id: str, round_num: int, 
                        other_response: Optional[AgentResponse]) -> AgentResponse:
        """Run a single agent's turn with full observability"""
        is_architect = agent_id == "architect"
        activity = self.session.agent_a_activity if is_architect else self.session.agent_b_activity
        color = Colors.BLUE if is_architect else Colors.MAGENTA
        
        # Update activity state
        activity.state = AgentState.THINKING
        activity.current_action = "Preparing prompt..."
        activity.started_at = time.time()
        self.dashboard.render()
        
        # Build prompt
        prompt = self._build_prompt(agent_id, round_num, other_response)
        
        # Update state
        activity.state = AgentState.DESIGNING if is_architect else AgentState.ANALYZING
        activity.current_action = "Generating design..." if is_architect else "Analyzing design..."
        self.dashboard.render()
        
        # Setup streaming handler
        output_handler = StreamingOutputHandler(self.emitter, agent_id, color)
        output_handler.start()
        
        # Make the call with error handling
        def call_agent():
            return self._call_claude_with_streaming(
                get_agent_a_system_prompt() if is_architect else get_agent_b_system_prompt(),
                prompt,
                self.session.working_dir,
                output_handler
            )
        
        raw_response = self.error_handler.wrap_agent_call(
            call_agent, agent_id, round_num
        )
        
        # Parse response
        response = parse_agent_response(raw_response, is_architect)
        response.duration_seconds = time.time() - activity.started_at
        
        # Update activity
        activity.state = AgentState.IDLE
        activity.current_action = ""
        activity.last_output_preview = ""
        
        # Emit completion event
        self.emitter.emit_simple(EVENT_AGENT_COMPLETED, {
            "duration": response.duration_seconds,
            "signal": response.convergence_signal,
        }, round_number=round_num, agent_id=agent_id)
        
        return response
    
    def _register_observers(self):
        """Register default event observers"""
        
        # Log all events to session
        def log_event(event: DebateEvent):
            self.session.events.append(event)
        
        self.emitter.on_all(log_event)
        
        # Update dashboard on key events
        def update_dashboard(event: DebateEvent):
            if event.event_type in [EVENT_PHASE_CHANGE, EVENT_ROUND_STARTED, 
                                     EVENT_CONVERGENCE_UPDATE]:
                self.dashboard.render()
        
        self.emitter.on_all(update_dashboard)
```

### 7. File Structure

```
plan-with-debate/
├── .claude-plugin/
│   ├── plugin.json
│   └── marketplace.json
├── commands/
│   └── plan-with-debate.md
├── src/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── models.py               # Data models
│   ├── orchestrator.py         # Main debate orchestrator
│   ├── agents.py               # Agent calling logic
│   ├── observability/
│   │   ├── __init__.py
│   │   ├── events.py           # Event emitter
│   │   ├── progress.py         # Progress tracker
│   │   └── convergence.py      # Convergence analyzer
│   ├── ui/
│   │   ├── __init__.py
│   │   ├── dashboard.py        # Status dashboard
│   │   ├── colors.py           # ANSI colors
│   │   └── streaming.py        # Streaming output handler
│   ├── persistence/
│   │   ├── __init__.py
│   │   ├── session.py          # Session save/load
│   │   └── checkpoint.py       # Auto-checkpointing
│   └── errors.py               # Error types and handler
├── debate                      # CLI wrapper script
├── README.md
└── requirements.txt
```

### 8. Enhanced CLI Output Example

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║  🎭 Debate: Add user authentication with JWT tokens  │  Phase: ITERATING     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

  Round 3/5  [████████████████░░░░░░░░░░░░░░░░░░░░░░░░]  ↗ Converging

  🔵 Architect: designing (45s)  Generating improved token rotation design...
      └─ ### 4.2 Token Rotation Strategy
  🟣 Reviewer : idle

  Recent rounds:
    R1: [██████░░░░] (62% similar) [78s + 65s]
    R2: [███████░░░] (74% similar) [82s + 71s]
    R3: [in progress...]

  ⏱  Elapsed: 0:04:23  │  Remaining: ~0:02:45  │  ETA: 14:32:08  │  Confidence: ●●●○○
```

---

## Rationale

### Key Design Decisions

1. **Event-Driven Observability**: Using an event emitter pattern allows loose coupling between the core debate logic and the UI/logging systems. Any component can subscribe to events without modifying the core.

2. **Layered Architecture**: Clear separation between UI, observability, core logic, and persistence makes the code testable and maintainable. Each layer has a single responsibility.

3. **Convergence Analysis**: Rather than just relying on agent signals (which can be inconsistent), we calculate actual design similarity scores. This provides objective progress tracking.

4. **Progress Estimation**: Using historical round data and convergence trends to estimate completion gives users realistic expectations rather than just "round X of Y".

5. **Error Recovery with Retry**: Transient errors (timeouts, API issues) are retried with exponential backoff. Non-recoverable errors are surfaced clearly.

6. **Streaming with Preview**: The rolling preview of agent output gives users visibility into what's happening without overwhelming them with full output.

---

## What I Kept

- The core two-agent debate structure (Architect/Reviewer)
- The existing convergence signals (PROPOSING_FINAL, ACCEPTING_FINAL, ITERATING)
- Session persistence and resume capability
- The CLI interface and command structure
- ANSI color scheme for terminal output

---

## Convergence Status

- **ITERATING**: This is the initial design proposal, significant refinement expected

---

## Prompt for Other Agent