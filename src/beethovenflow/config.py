"""Configuration management for BeethovenFlow.

Handles loading/saving config and calibration data to platform-appropriate locations:
- macOS: ~/Library/Application Support/BeethovenFlow/
- Windows: %LOCALAPPDATA%/BeethovenFlow/
"""

import json
import platform
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List


def get_config_dir() -> Path:
    """Get the platform-appropriate config directory."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        config_dir = Path.home() / "Library" / "Application Support" / "BeethovenFlow"
    elif system == "Windows":
        # Use LOCALAPPDATA - always writable even on corp machines
        local_app_data = Path.home() / "AppData" / "Local"
        config_dir = local_app_data / "BeethovenFlow"
    else:
        # Linux/other - use XDG standard
        config_dir = Path.home() / ".config" / "beethovenflow"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@dataclass
class CalibrationData:
    """Stores calibration baseline values."""
    v_low: float = 0.0          # 25th percentile velocity
    v_high: float = 100.0       # 75th percentile velocity
    j_threshold: float = 10.0   # Median jitter
    calibrated: bool = False
    calibrated_at: str = ""
    samples_collected: int = 0


@dataclass
class Config:
    """Main configuration for BeethovenFlow."""
    # Timing
    cooldown_seconds: int = 300          # 5 minutes between state transitions
    sample_interval_seconds: int = 10    # How often to sample metrics
    window_seconds: int = 60             # Sliding window for metric calculation
    
    # Calibration
    calibration_duration_seconds: int = 120  # 2 minutes
    
    # Track history
    history_size: int = 20               # Number of video IDs to remember
    
    # Time-of-day scaling factors
    time_scaling: dict = field(default_factory=lambda: {
        "morning": 0.9,      # 05:00 - 11:59
        "afternoon": 1.0,    # 12:00 - 16:59
        "evening": 1.2,      # 17:00 - 21:59
        "night": 1.5         # 22:00 - 04:59
    })
    
    # Search query templates
    mood_modifiers: dict = field(default_factory=lambda: {
        "fatigued": "adagio slow peaceful",
        "focused": "piano sonata concentration",
        "energetic": "symphony allegro uplifting",
        "stressed": "dramatic powerful symphony"
    })
    
    time_tags: dict = field(default_factory=lambda: {
        "morning": "morning classical",
        "afternoon": "afternoon",
        "evening": "evening relaxing",
        "night": "late night calm"
    })
    
    generic_queries: dict = field(default_factory=lambda: {
        "morning": "Beethoven piano sonata morning",
        "afternoon": "Beethoven symphony",
        "evening": "Beethoven adagio evening",
        "night": "Beethoven moonlight sonata"
    })
    
    # Calibration data
    calibration: CalibrationData = field(default_factory=CalibrationData)
    
    # Track history (video IDs)
    track_history: List[str] = field(default_factory=list)


class ConfigManager:
    """Manages loading and saving configuration."""
    
    CONFIG_FILE = "config.json"
    
    def __init__(self):
        self.config_dir = get_config_dir()
        self.config_path = self.config_dir / self.CONFIG_FILE
        self.config = self._load()
    
    def _load(self) -> Config:
        """Load config from disk, or create default."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    data = json.load(f)
                
                # Handle nested calibration data
                if "calibration" in data and isinstance(data["calibration"], dict):
                    data["calibration"] = CalibrationData(**data["calibration"])
                else:
                    data["calibration"] = CalibrationData()
                
                # Create config with loaded data
                config = Config(**{k: v for k, v in data.items() if k in Config.__dataclass_fields__})
                return config
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                # Corrupted config, start fresh
                print(f"Warning: Could not load config ({e}), using defaults")
                return Config()
        return Config()
    
    def save(self) -> None:
        """Save current config to disk."""
        data = asdict(self.config)
        with open(self.config_path, "w") as f:
            json.dump(data, f, indent=2)
    
    def update_calibration(self, v_low: float, v_high: float, j_threshold: float, 
                          samples: int) -> None:
        """Update calibration data and save."""
        from datetime import datetime
        self.config.calibration = CalibrationData(
            v_low=v_low,
            v_high=v_high,
            j_threshold=j_threshold,
            calibrated=True,
            calibrated_at=datetime.now().isoformat(),
            samples_collected=samples
        )
        self.save()
    
    def add_to_history(self, video_id: str) -> None:
        """Add a video ID to track history, maintaining max size."""
        if video_id not in self.config.track_history:
            self.config.track_history.append(video_id)
            # Trim to max size
            if len(self.config.track_history) > self.config.history_size:
                self.config.track_history = self.config.track_history[-self.config.history_size:]
            self.save()
    
    def is_in_history(self, video_id: str) -> bool:
        """Check if a video ID is in the track history."""
        return video_id in self.config.track_history
    
    def clear_history(self) -> None:
        """Clear track history."""
        self.config.track_history = []
        self.save()
    
    def is_calibrated(self) -> bool:
        """Check if calibration has been completed."""
        return self.config.calibration.calibrated


# Global config instance
_config_manager: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Get the global config manager instance."""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager
