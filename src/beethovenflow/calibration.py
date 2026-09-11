"""Calibration module for BeethovenFlow.

Runs a 2-minute calibration period to establish personalized baselines
for velocity and jitter thresholds using percentile-based calculation.
"""

import time
from typing import Callable, Optional, List

import numpy as np

from .tracker import MouseTracker, MouseMetrics
from .config import get_config


class Calibrator:
    """Handles the calibration process to establish user baselines."""
    
    def __init__(
        self,
        duration_seconds: int = 120,
        sample_interval: float = 10.0,
        on_progress: Optional[Callable[[int, int], None]] = None,
        on_complete: Optional[Callable[[float, float, float], None]] = None
    ):
        """
        Initialize the calibrator.
        
        Args:
            duration_seconds: How long to calibrate (default 120s = 2 min)
            sample_interval: How often to sample metrics
            on_progress: Callback(elapsed_seconds, total_seconds)
            on_complete: Callback(v_low, v_high, j_threshold)
        """
        self.duration_seconds = duration_seconds
        self.sample_interval = sample_interval
        self.on_progress = on_progress
        self.on_complete = on_complete
        
        self._tracker: Optional[MouseTracker] = None
        self._samples: List[MouseMetrics] = []
        self._running = False
    
    def start(self, tracker: MouseTracker) -> None:
        """
        Start calibration using an existing tracker.
        
        Args:
            tracker: The MouseTracker instance to collect samples from
        """
        self._tracker = tracker
        self._samples = []
        self._running = True
    
    def stop(self) -> None:
        """Stop calibration early."""
        self._running = False
    
    def is_running(self) -> bool:
        """Check if calibration is in progress."""
        return self._running
    
    def update(self, metrics: MouseMetrics) -> bool:
        """
        Add a new sample during calibration.
        
        Args:
            metrics: The latest mouse metrics
            
        Returns:
            True if calibration is still in progress, False when complete
        """
        if not self._running:
            return False
        
        self._samples.append(metrics)
        
        elapsed = len(self._samples) * self.sample_interval
        
        # Report progress
        if self.on_progress:
            self.on_progress(int(elapsed), self.duration_seconds)
        
        # Check if we're done
        if elapsed >= self.duration_seconds:
            self._finish_calibration()
            return False
        
        return True
    
    def _finish_calibration(self) -> None:
        """Calculate thresholds from collected samples and save."""
        self._running = False
        
        if len(self._samples) < 3:
            # Not enough samples, use defaults
            v_low, v_high, j_threshold = 50.0, 150.0, 0.5
        else:
            velocities = [s.velocity for s in self._samples]
            jitters = [s.jitter for s in self._samples]
            
            # Calculate percentile-based thresholds
            v_low = float(np.percentile(velocities, 25))
            v_high = float(np.percentile(velocities, 75))
            j_threshold = float(np.median(jitters))
            
            # Ensure minimum separation between low and high
            if v_high - v_low < 20:
                mid = (v_low + v_high) / 2
                v_low = mid - 15
                v_high = mid + 15
        
        # Save to config
        config = get_config()
        config.update_calibration(
            v_low=v_low,
            v_high=v_high,
            j_threshold=j_threshold,
            samples=len(self._samples)
        )
        
        # Notify completion
        if self.on_complete:
            self.on_complete(v_low, v_high, j_threshold)
    
    def get_progress(self) -> tuple[int, int]:
        """Get current progress as (elapsed_seconds, total_seconds)."""
        elapsed = len(self._samples) * self.sample_interval
        return int(elapsed), self.duration_seconds
    
    def get_sample_count(self) -> int:
        """Get the number of samples collected so far."""
        return len(self._samples)


def needs_calibration() -> bool:
    """Check if calibration is needed."""
    config = get_config()
    return not config.is_calibrated()


def get_thresholds() -> tuple[float, float, float]:
    """
    Get the current calibration thresholds.
    
    Returns:
        (v_low, v_high, j_threshold)
    """
    config = get_config()
    cal = config.config.calibration
    return cal.v_low, cal.v_high, cal.j_threshold
