"""State classification module for BeethovenFlow.

Classifies user state based on mouse metrics using a 2x2 grid:
- Velocity LOW  + Jitter LOW  = FATIGUED
- Velocity LOW  + Jitter HIGH = FOCUSED  
- Velocity HIGH + Jitter LOW  = ENERGETIC
- Velocity HIGH + Jitter HIGH = STRESSED

Time-of-day scaling adjusts thresholds based on the hour.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from .tracker import MouseMetrics
from .config import get_config


class UserState(Enum):
    """Possible user states based on interaction patterns."""
    FATIGUED = "fatigued"    # Slow, steady - calm/adagio music
    FOCUSED = "focused"      # Slow, precise - piano sonatas
    ENERGETIC = "energetic"  # Fast, smooth - symphony allegro
    STRESSED = "stressed"    # Fast, erratic - dramatic pieces


def get_time_period() -> str:
    """
    Get the current time period.
    
    Returns:
        One of: 'morning', 'afternoon', 'evening', 'night'
    """
    hour = datetime.now().hour
    
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:  # 22-4
        return "night"


def get_time_scale_factor() -> float:
    """
    Get the velocity scaling factor for the current time of day.
    
    Higher factor = higher threshold required to trigger high-energy states
    """
    config = get_config()
    period = get_time_period()
    return config.config.time_scaling.get(period, 1.0)


class StateClassifier:
    """Classifies user state from mouse metrics."""
    
    def __init__(
        self,
        v_low: float,
        v_high: float,
        j_threshold: float,
        cooldown_seconds: int = 300
    ):
        """
        Initialize the classifier.
        
        Args:
            v_low: Velocity threshold below which is considered "low"
            v_high: Velocity threshold above which is considered "high"
            j_threshold: Jitter threshold for low/high classification
            cooldown_seconds: Minimum time between state transitions
        """
        self.v_low = v_low
        self.v_high = v_high
        self.j_threshold = j_threshold
        self.cooldown_seconds = cooldown_seconds
        
        self._current_state: Optional[UserState] = None
        self._last_transition_time: float = 0.0
    
    def classify(self, metrics: MouseMetrics, apply_cooldown: bool = True) -> tuple[UserState, bool]:
        """
        Classify the current state from metrics.
        
        Args:
            metrics: Current mouse metrics
            apply_cooldown: Whether to enforce cooldown between transitions
            
        Returns:
            (state, changed): The classified state and whether it changed
        """
        import time
        
        # Apply time-of-day scaling to velocity thresholds
        scale = get_time_scale_factor()
        scaled_v_low = self.v_low * scale
        scaled_v_high = self.v_high * scale
        
        # Determine velocity category
        velocity = metrics.velocity
        jitter = metrics.jitter
        
        # Classify based on 2x2 grid
        if velocity < scaled_v_low:
            # Low velocity
            if jitter < self.j_threshold:
                new_state = UserState.FATIGUED
            else:
                new_state = UserState.FOCUSED
        else:
            # High velocity (using v_high as threshold for "definitely high")
            # Middle ground leans toward current state for stability
            if velocity >= scaled_v_high:
                if jitter < self.j_threshold:
                    new_state = UserState.ENERGETIC
                else:
                    new_state = UserState.STRESSED
            else:
                # In between v_low and v_high - mild activity
                # Lean toward less intense states
                if jitter < self.j_threshold:
                    new_state = UserState.FOCUSED  # Calm, moderate
                else:
                    new_state = UserState.ENERGETIC  # Active but not stressed
        
        # Check if state changed
        current_time = time.time()
        changed = False
        
        if self._current_state is None:
            # First classification
            self._current_state = new_state
            self._last_transition_time = current_time
            changed = True
        elif new_state != self._current_state:
            # State would change - check cooldown
            if apply_cooldown:
                time_since_last = current_time - self._last_transition_time
                if time_since_last >= self.cooldown_seconds:
                    self._current_state = new_state
                    self._last_transition_time = current_time
                    changed = True
                # else: cooldown not elapsed, keep current state
            else:
                self._current_state = new_state
                self._last_transition_time = current_time
                changed = True
        
        return self._current_state, changed
    
    def get_current_state(self) -> Optional[UserState]:
        """Get the current state without reclassifying."""
        return self._current_state
    
    def force_state(self, state: UserState) -> None:
        """Force a specific state (for manual override)."""
        import time
        self._current_state = state
        self._last_transition_time = time.time()
    
    def reset_cooldown(self) -> None:
        """Reset the cooldown timer (allows immediate transition)."""
        self._last_transition_time = 0.0
    
    def time_until_transition_allowed(self) -> float:
        """Get seconds until next state transition is allowed."""
        import time
        elapsed = time.time() - self._last_transition_time
        remaining = self.cooldown_seconds - elapsed
        return max(0.0, remaining)


def create_classifier_from_config() -> StateClassifier:
    """Create a StateClassifier using values from config."""
    config = get_config()
    cal = config.config.calibration
    
    return StateClassifier(
        v_low=cal.v_low,
        v_high=cal.v_high,
        j_threshold=cal.j_threshold,
        cooldown_seconds=config.config.cooldown_seconds
    )


def get_state_description(state: UserState) -> str:
    """Get a human-readable description of a state."""
    descriptions = {
        UserState.FATIGUED: "Slow, steady movement - playing calm, peaceful music",
        UserState.FOCUSED: "Precise, deliberate movement - playing piano sonatas",
        UserState.ENERGETIC: "Active, smooth movement - playing lively symphonies",
        UserState.STRESSED: "Fast, erratic movement - playing dramatic pieces"
    }
    return descriptions.get(state, "Unknown state")
