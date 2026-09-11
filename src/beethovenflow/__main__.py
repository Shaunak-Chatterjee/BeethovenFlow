"""Main CLI application for BeethovenFlow.

Entry point that orchestrates all components:
- Mouse tracking
- Calibration (if needed)
- State classification
- Music playback
"""

import sys
import time
import threading
import select
from typing import Optional

from . import __version__
from .config import get_config
from .tracker import MouseTracker, MouseMetrics
from .calibration import Calibrator, needs_calibration, get_thresholds
from .classifier import StateClassifier, UserState, get_time_period, create_classifier_from_config
from .player import get_player, is_ytdlp_installed
from .mpv_control import is_mpv_installed, get_controller


# ANSI color codes
class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"


def print_header():
    """Print the application header."""
    print(f"""
{Colors.CYAN}{Colors.BOLD}🎵 BeethovenFlow v{__version__}{Colors.RESET}
{Colors.DIM}───────────────────────────────────{Colors.RESET}
""")


def print_status(state: UserState, title: Optional[str] = None, calibrating: bool = False):
    """Print current status."""
    state_colors = {
        UserState.FATIGUED: Colors.BLUE,
        UserState.FOCUSED: Colors.GREEN,
        UserState.ENERGETIC: Colors.YELLOW,
        UserState.STRESSED: Colors.MAGENTA
    }
    
    time_str = time.strftime("%H:%M")
    state_color = state_colors.get(state, Colors.RESET)
    
    if calibrating:
        print(f"\r{Colors.DIM}[{time_str}]{Colors.RESET} {Colors.YELLOW}Calibrating...{Colors.RESET}", end="", flush=True)
    else:
        state_name = state.value.upper()
        print(f"\n{Colors.DIM}[{time_str}]{Colors.RESET} State: {state_color}{Colors.BOLD}{state_name}{Colors.RESET}")
        if title:
            # Truncate long titles
            if len(title) > 60:
                title = title[:57] + "..."
            print(f"        Playing: {Colors.CYAN}{title}{Colors.RESET}")


def print_progress_bar(current: int, total: int, width: int = 30):
    """Print a progress bar."""
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    percent = int(100 * current / total)
    print(f"\r{Colors.DIM}Calibrating:{Colors.RESET} [{Colors.GREEN}{bar}{Colors.RESET}] {percent}%", end="", flush=True)


def print_commands():
    """Print available commands."""
    print(f"""
{Colors.DIM}Commands:{Colors.RESET} [s]kip  [p]ause  [r]ecalibrate  [i]nfo  [q]uit
""")


def check_dependencies() -> bool:
    """Check that all dependencies are installed."""
    missing = []
    
    if not is_mpv_installed():
        missing.append("mpv")
    
    if not is_ytdlp_installed():
        missing.append("yt-dlp")
    
    if missing:
        print(f"{Colors.RED}Error: Missing dependencies: {', '.join(missing)}{Colors.RESET}")
        print()
        print("Please run the installer script:")
        print(f"  {Colors.CYAN}./install.sh{Colors.RESET} (macOS)")
        print(f"  {Colors.CYAN}.\\install.ps1{Colors.RESET} (Windows)")
        return False
    
    return True


class BeethovenFlow:
    """Main application class."""
    
    def __init__(self):
        self.config = get_config()
        self.tracker = MouseTracker(
            sample_interval=self.config.config.sample_interval_seconds
        )
        self.player = get_player()
        self.mpv = get_controller()
        
        self.classifier: Optional[StateClassifier] = None
        self.calibrator: Optional[Calibrator] = None
        
        self._running = False
        self._paused = False
        self._current_state: Optional[UserState] = None
        self._current_title: Optional[str] = None
    
    def start(self):
        """Start the application."""
        print_header()
        
        # Check dependencies
        if not check_dependencies():
            return 1
        
        # Start MPV
        print(f"{Colors.DIM}Starting MPV...{Colors.RESET}", end=" ", flush=True)
        if not self.mpv.start_mpv():
            print(f"{Colors.RED}Failed{Colors.RESET}")
            print("Could not start MPV. Make sure it's installed correctly.")
            return 1
        print(f"{Colors.GREEN}✓{Colors.RESET}")
        
        self._running = True
        
        # Check if calibration is needed
        if needs_calibration():
            self._run_calibration_phase()
        else:
            # Load existing calibration
            v_low, v_high, j_threshold = get_thresholds()
            self.classifier = StateClassifier(
                v_low=v_low,
                v_high=v_high,
                j_threshold=j_threshold,
                cooldown_seconds=self.config.config.cooldown_seconds
            )
            print(f"{Colors.GREEN}✓ Calibration loaded{Colors.RESET}")
            print(f"  V_low: {v_low:.1f} | V_high: {v_high:.1f} | J_threshold: {j_threshold:.2f}")
        
        # Start tracking
        self.tracker.start(on_metrics=self._on_metrics)
        
        print_commands()
        
        # Main loop
        self._main_loop()
        
        # Cleanup
        self.tracker.stop()
        self.mpv.stop_mpv()
        
        print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
        return 0
    
    def _run_calibration_phase(self):
        """Run the calibration phase with generic music playing."""
        print()
        print(f"{Colors.YELLOW}Calibrating...{Colors.RESET} Move your mouse normally for 2 minutes.")
        print(f"{Colors.DIM}Playing generic {get_time_period()} music while calibrating.{Colors.RESET}")
        print()
        
        # Play generic music based on time of day
        title = self.player.play_for_state(None)
        if title:
            self._current_title = title
            print(f"Playing: {Colors.CYAN}{title}{Colors.RESET}")
        
        # Set up calibrator
        self.calibrator = Calibrator(
            duration_seconds=self.config.config.calibration_duration_seconds,
            sample_interval=self.config.config.sample_interval_seconds,
            on_progress=self._on_calibration_progress,
            on_complete=self._on_calibration_complete
        )
        
        # Start tracking for calibration
        self.tracker.start(on_metrics=self._on_calibration_metrics)
        self.calibrator.start(self.tracker)
        
        # Wait for calibration to complete
        while self.calibrator.is_running() and self._running:
            self._handle_input(timeout=0.5)
        
        self.tracker.stop()
        self.tracker.clear_samples()
        print()  # Clear progress line
    
    def _on_calibration_metrics(self, metrics: MouseMetrics):
        """Handle metrics during calibration."""
        if self.calibrator and self.calibrator.is_running():
            self.calibrator.update(metrics)
    
    def _on_calibration_progress(self, elapsed: int, total: int):
        """Handle calibration progress updates."""
        print_progress_bar(elapsed, total)
    
    def _on_calibration_complete(self, v_low: float, v_high: float, j_threshold: float):
        """Handle calibration completion."""
        print()
        print(f"\n{Colors.GREEN}✓ Calibration complete{Colors.RESET}")
        print(f"  V_low: {v_low:.1f} px/s | V_high: {v_high:.1f} px/s | J_threshold: {j_threshold:.2f}")
        
        # Create classifier with new thresholds
        self.classifier = StateClassifier(
            v_low=v_low,
            v_high=v_high,
            j_threshold=j_threshold,
            cooldown_seconds=self.config.config.cooldown_seconds
        )
    
    def _on_metrics(self, metrics: MouseMetrics):
        """Handle new metrics from the tracker."""
        if not self.classifier or not self._running:
            return
        
        # Classify the state
        state, changed = self.classifier.classify(metrics)
        
        if changed and state:
            self._current_state = state
            
            # Play appropriate music
            title = self.player.play_for_state(state)
            if title:
                self._current_title = title
            
            print_status(state, self._current_title)
    
    def _main_loop(self):
        """Main application loop."""
        # Do initial classification and play
        if self.classifier:
            metrics = self.tracker.get_current_metrics()
            state, _ = self.classifier.classify(metrics, apply_cooldown=False)
            self._current_state = state
            
            title = self.player.play_for_state(state)
            if title:
                self._current_title = title
            
            print_status(state, self._current_title)
        
        while self._running:
            self._handle_input(timeout=1.0)
    
    def _handle_input(self, timeout: float = 1.0):
        """Handle user input (non-blocking)."""
        import sys
        import os
        
        # Platform-specific non-blocking input
        if sys.platform == "win32":
            self._handle_input_windows(timeout)
        else:
            self._handle_input_unix(timeout)
    
    def _handle_input_unix(self, timeout: float):
        """Handle input on Unix systems."""
        import tty
        import termios
        
        old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())
            rlist, _, _ = select.select([sys.stdin], [], [], timeout)
            if rlist:
                char = sys.stdin.read(1)
                self._process_command(char)
        except Exception:
            pass
        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    def _handle_input_windows(self, timeout: float):
        """Handle input on Windows."""
        try:
            import msvcrt
            start = time.time()
            while time.time() - start < timeout:
                if msvcrt.kbhit():
                    char = msvcrt.getch().decode("utf-8", errors="ignore")
                    self._process_command(char)
                    break
                time.sleep(0.05)
        except Exception:
            time.sleep(timeout)
    
    def _process_command(self, char: str):
        """Process a single-character command."""
        char = char.lower()
        
        if char == "q":
            self._running = False
            print(f"\n{Colors.YELLOW}Quitting...{Colors.RESET}")
        
        elif char == "s":
            print(f"\n{Colors.DIM}Skipping...{Colors.RESET}", end=" ", flush=True)
            title = self.player.skip()
            if title:
                self._current_title = title
                print(f"{Colors.GREEN}✓{Colors.RESET}")
                if self._current_state:
                    print_status(self._current_state, self._current_title)
            else:
                print(f"{Colors.RED}Failed{Colors.RESET}")
        
        elif char == "p":
            if self.player.is_paused():
                self.player.resume()
                print(f"\n{Colors.GREEN}▶ Resumed{Colors.RESET}")
            else:
                self.player.pause()
                print(f"\n{Colors.YELLOW}⏸ Paused{Colors.RESET}")
        
        elif char == "r":
            print(f"\n{Colors.YELLOW}Recalibrating...{Colors.RESET}")
            # Clear old calibration
            self.config.config.calibration.calibrated = False
            self.config.save()
            self.tracker.stop()
            self._run_calibration_phase()
            self.tracker.start(on_metrics=self._on_metrics)
            print_commands()
        
        elif char == "i":
            self._print_info()
    
    def _print_info(self):
        """Print detailed status information."""
        print()
        print(f"{Colors.BOLD}Current Status:{Colors.RESET}")
        print(f"  State: {self._current_state.value if self._current_state else 'Unknown'}")
        print(f"  Time Period: {get_time_period()}")
        print(f"  Track: {self._current_title or 'None'}")
        print()
        
        # Show calibration values
        if self.classifier:
            print(f"{Colors.BOLD}Calibration:{Colors.RESET}")
            print(f"  V_low: {self.classifier.v_low:.1f} px/s")
            print(f"  V_high: {self.classifier.v_high:.1f} px/s")
            print(f"  J_threshold: {self.classifier.j_threshold:.2f}")
            cooldown_remaining = self.classifier.time_until_transition_allowed()
            if cooldown_remaining > 0:
                print(f"  Cooldown: {int(cooldown_remaining)}s remaining")
        print()
        
        # Show recent metrics
        metrics = self.tracker.get_average_metrics()
        print(f"{Colors.BOLD}Current Metrics:{Colors.RESET}")
        print(f"  Velocity: {metrics.velocity:.1f} px/s")
        print(f"  Jitter: {metrics.jitter:.2f}")
        print()


def main():
    """Main entry point."""
    try:
        app = BeethovenFlow()
        sys.exit(app.start())
    except KeyboardInterrupt:
        print(f"\n{Colors.DIM}Interrupted{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
