"""Mouse tracking module for BeethovenFlow.

Tracks mouse movement using pynput to calculate:
- Velocity (px/sec): Total Euclidean distance / time
- Jitter: Standard deviation of movement vectors
"""

import time
import threading
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable, Tuple

import numpy as np
from pynput import mouse


@dataclass
class MouseMetrics:
    """Calculated metrics from mouse movement."""
    velocity: float      # Average velocity in px/sec
    jitter: float        # Standard deviation of direction vectors
    sample_time: float   # When this sample was taken


class MouseTracker:
    """Tracks mouse movement and calculates velocity/jitter metrics."""
    
    def __init__(self, sample_interval: float = 10.0, window_size: int = 6):
        """
        Initialize the mouse tracker.
        
        Args:
            sample_interval: How often to calculate metrics (seconds)
            window_size: Number of samples to keep for averaging
        """
        self.sample_interval = sample_interval
        self.window_size = window_size
        
        # Raw tracking data (cleared after each sample)
        self._positions: list[Tuple[float, float, float]] = []  # (x, y, timestamp)
        self._lock = threading.Lock()
        
        # Calculated samples for sliding window
        self._samples: deque[MouseMetrics] = deque(maxlen=window_size)
        
        # State
        self._running = False
        self._listener: Optional[mouse.Listener] = None
        self._sample_thread: Optional[threading.Thread] = None
        self._last_position: Optional[Tuple[float, float]] = None
        self._window_start: float = 0.0
        
        # Callbacks
        self._on_metrics: Optional[Callable[[MouseMetrics], None]] = None
    
    def start(self, on_metrics: Optional[Callable[[MouseMetrics], None]] = None) -> None:
        """Start tracking mouse movement."""
        if self._running:
            return
        
        self._running = True
        self._on_metrics = on_metrics
        self._window_start = time.time()
        self._positions = []
        self._last_position = None
        
        # Start mouse listener
        self._listener = mouse.Listener(on_move=self._on_move)
        self._listener.start()
        
        # Start sampling thread
        self._sample_thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._sample_thread.start()
    
    def stop(self) -> None:
        """Stop tracking."""
        self._running = False
        if self._listener:
            self._listener.stop()
            self._listener = None
    
    def _on_move(self, x: int, y: int) -> None:
        """Called on mouse movement."""
        if not self._running:
            return
        
        current_time = time.time()
        
        with self._lock:
            self._positions.append((float(x), float(y), current_time))
            self._last_position = (float(x), float(y))
    
    def _sample_loop(self) -> None:
        """Background thread that calculates metrics at regular intervals."""
        while self._running:
            time.sleep(self.sample_interval)
            
            if not self._running:
                break
            
            metrics = self._calculate_metrics()
            if metrics:
                self._samples.append(metrics)
                if self._on_metrics:
                    self._on_metrics(metrics)
    
    def _calculate_metrics(self) -> Optional[MouseMetrics]:
        """Calculate velocity and jitter from accumulated positions."""
        with self._lock:
            positions = self._positions.copy()
            self._positions = []  # Clear for next window
        
        if len(positions) < 2:
            # Not enough data points
            return MouseMetrics(velocity=0.0, jitter=0.0, sample_time=time.time())
        
        # Calculate distances and directions
        distances = []
        directions = []
        
        for i in range(1, len(positions)):
            x1, y1, t1 = positions[i - 1]
            x2, y2, t2 = positions[i]
            
            dx = x2 - x1
            dy = y2 - y1
            
            distance = math.sqrt(dx * dx + dy * dy)
            distances.append(distance)
            
            # Direction vector (normalized)
            if distance > 0:
                directions.append((dx / distance, dy / distance))
        
        # Calculate total distance and elapsed time
        total_distance = sum(distances)
        elapsed_time = positions[-1][2] - positions[0][2]
        
        # Velocity: total distance / time
        velocity = total_distance / elapsed_time if elapsed_time > 0 else 0.0
        
        # Jitter: standard deviation of direction changes
        if len(directions) >= 2:
            # Calculate angle changes between consecutive directions
            angle_changes = []
            for i in range(1, len(directions)):
                d1 = directions[i - 1]
                d2 = directions[i]
                # Dot product gives cosine of angle
                dot = d1[0] * d2[0] + d1[1] * d2[1]
                # Clamp to valid range for acos
                dot = max(-1.0, min(1.0, dot))
                angle = math.acos(dot)
                angle_changes.append(angle)
            
            jitter = float(np.std(angle_changes)) if angle_changes else 0.0
        else:
            jitter = 0.0
        
        return MouseMetrics(velocity=velocity, jitter=jitter, sample_time=time.time())
    
    def get_current_metrics(self) -> MouseMetrics:
        """Get the most recent metrics, or calculate from current data."""
        if self._samples:
            return self._samples[-1]
        return MouseMetrics(velocity=0.0, jitter=0.0, sample_time=time.time())
    
    def get_average_metrics(self) -> MouseMetrics:
        """Get averaged metrics over the sliding window."""
        if not self._samples:
            return MouseMetrics(velocity=0.0, jitter=0.0, sample_time=time.time())
        
        velocities = [s.velocity for s in self._samples]
        jitters = [s.jitter for s in self._samples]
        
        return MouseMetrics(
            velocity=float(np.mean(velocities)),
            jitter=float(np.mean(jitters)),
            sample_time=time.time()
        )
    
    def get_all_samples(self) -> list[MouseMetrics]:
        """Get all samples in the current window (for calibration)."""
        return list(self._samples)
    
    def clear_samples(self) -> None:
        """Clear accumulated samples."""
        self._samples.clear()
