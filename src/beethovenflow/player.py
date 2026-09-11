"""Player and search module for BeethovenFlow.

Handles YouTube search via yt-dlp, track deduplication, and query construction.
"""

import re
import subprocess
import json
from dataclasses import dataclass
from typing import Optional, List

from .classifier import UserState, get_time_period
from .config import get_config
from .mpv_control import get_controller, MPVController


@dataclass
class SearchResult:
    """A YouTube search result."""
    video_id: str
    title: str
    url: str
    duration: int  # seconds
    channel: str


def is_ytdlp_installed() -> bool:
    """Check if yt-dlp is installed."""
    try:
        result = subprocess.run(
            ["yt-dlp", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def search_youtube(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    Search YouTube using yt-dlp.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of SearchResult objects
    """
    try:
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query}",
            "--dump-json",
            "--no-download",
            "--flat-playlist",
            "--no-warnings",
            "--quiet"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return []
        
        results = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                data = json.loads(line)
                results.append(SearchResult(
                    video_id=data.get("id", ""),
                    title=data.get("title", "Unknown"),
                    url=data.get("url", "") or f"https://www.youtube.com/watch?v={data.get('id', '')}",
                    duration=data.get("duration", 0) or 0,
                    channel=data.get("channel", "") or data.get("uploader", "Unknown")
                ))
            except json.JSONDecodeError:
                continue
        
        return results
        
    except subprocess.TimeoutExpired:
        return []
    except Exception:
        return []


def normalize_title(title: str) -> str:
    """
    Normalize a title to extract canonical work name.
    
    Strips:
    - Performance credits (artist names, orchestras)
    - Recording info (year, label)
    - Movement numbers (I., II., 1., 2.)
    - Common suffixes (Full, Complete, HQ, HD)
    
    Example:
        "Beethoven - Piano Sonata No. 14 'Moonlight' - I. Adagio (Horowitz)"
        -> "beethoven piano sonata 14 moonlight"
    """
    title = title.lower()
    
    # Remove common patterns
    patterns = [
        r"\([^)]*\)",           # (anything in parentheses)
        r"\[[^\]]*\]",          # [anything in brackets]
        r"\b(i{1,3}|iv|v|vi{0,3})\.",  # Roman numeral movements
        r"\b\d+\.",             # Numeric movements
        r"\b(op\.?\s*\d+)",     # Opus numbers
        r"\b(no\.?\s*\d+)",     # Number designations
        r"\b(woo\.?\s*\d+)",    # WoO numbers
        r"\b(full|complete|hq|hd|remaster(ed)?|live)\b",
        r"\b(adagio|allegro|andante|presto|largo|moderato|vivace)\b",
        r"\b(berlin|vienna|london|chicago|philharmonic|orchestra|symphony)\b",
        r"[-–—]",              # Dashes
        r"[''\"`,.]",          # Punctuation
    ]
    
    for pattern in patterns:
        title = re.sub(pattern, " ", title)
    
    # Collapse whitespace
    title = " ".join(title.split())
    
    return title


def is_duplicate_work(title1: str, title2: str) -> bool:
    """
    Check if two titles refer to the same musical work.
    
    Uses normalized titles to detect same piece by different performers.
    """
    norm1 = normalize_title(title1)
    norm2 = normalize_title(title2)
    
    # Check for substantial overlap
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    if not words1 or not words2:
        return False
    
    # Calculate Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    similarity = intersection / union if union > 0 else 0
    
    # High similarity = same work
    return similarity > 0.6


class Player:
    """Manages music playback with search and deduplication."""
    
    def __init__(self, mpv: Optional[MPVController] = None):
        self._mpv = mpv or get_controller()
        self._current_video_id: Optional[str] = None
        self._current_title: Optional[str] = None
        self._last_state: Optional[UserState] = None
    
    def build_query(self, state: Optional[UserState] = None) -> str:
        """
        Build a search query for the given state and time.
        
        Args:
            state: User state (if None, builds generic time-based query)
            
        Returns:
            Search query string
        """
        config = get_config()
        time_period = get_time_period()
        
        if state is None:
            # Generic query based on time of day (for calibration period)
            return config.config.generic_queries.get(
                time_period, 
                "Beethoven piano sonata"
            )
        
        # Build state + time query
        mood_mod = config.config.mood_modifiers.get(state.value, "")
        time_tag = config.config.time_tags.get(time_period, "")
        
        query = f"Beethoven {mood_mod} {time_tag}".strip()
        return query
    
    def find_track(self, state: Optional[UserState] = None) -> Optional[SearchResult]:
        """
        Find a suitable track for the given state.
        
        Handles deduplication against history and current track.
        
        Args:
            state: User state (if None, uses generic time-based query)
            
        Returns:
            SearchResult or None if no suitable track found
        """
        config = get_config()
        query = self.build_query(state)
        
        # Search YouTube
        results = search_youtube(query, max_results=5)
        
        if not results:
            # Try a simpler fallback query
            fallback_query = "Beethoven piano"
            results = search_youtube(fallback_query, max_results=5)
        
        if not results:
            return None
        
        # Filter out duplicates
        for result in results:
            # Check video ID history
            if config.is_in_history(result.video_id):
                continue
            
            # Check for same work as current track
            if self._current_title and is_duplicate_work(result.title, self._current_title):
                continue
            
            # Found a valid track
            return result
        
        # All results were duplicates - return the first one anyway
        # (better than silence)
        return results[0] if results else None
    
    def play_track(self, result: SearchResult) -> bool:
        """
        Play a track via MPV.
        
        Args:
            result: The search result to play
            
        Returns:
            True if playback started successfully
        """
        if not self._mpv.is_connected():
            if not self._mpv.start_mpv():
                return False
        
        # Build the URL for MPV/yt-dlp
        url = f"ytdl://ytsearch:{result.title}"
        # Or use direct URL if available
        if result.video_id:
            url = f"ytdl://https://www.youtube.com/watch?v={result.video_id}"
        
        # Load the track
        success = self._mpv.load_file(url, "replace")
        
        if success:
            # Update state
            self._current_video_id = result.video_id
            self._current_title = result.title
            
            # Add to history
            config = get_config()
            config.add_to_history(result.video_id)
        
        return success
    
    def play_for_state(self, state: Optional[UserState] = None) -> Optional[str]:
        """
        Find and play a track for the given state.
        
        Args:
            state: User state (None for generic)
            
        Returns:
            Track title if successful, None otherwise
        """
        result = self.find_track(state)
        
        if result and self.play_track(result):
            self._last_state = state
            return result.title
        
        return None
    
    def skip(self) -> Optional[str]:
        """
        Skip to a new track (same state).
        
        Returns:
            New track title if successful
        """
        return self.play_for_state(self._last_state)
    
    def pause(self) -> bool:
        """Pause playback."""
        return self._mpv.pause()
    
    def resume(self) -> bool:
        """Resume playback."""
        return self._mpv.resume()
    
    def toggle_pause(self) -> bool:
        """Toggle pause state."""
        return self._mpv.toggle_pause()
    
    def stop(self) -> bool:
        """Stop playback."""
        return self._mpv.stop()
    
    def get_current_title(self) -> Optional[str]:
        """Get the title of the currently playing track."""
        return self._current_title
    
    def is_playing(self) -> bool:
        """Check if music is currently playing."""
        return self._mpv.is_playing()
    
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._mpv.is_paused()


# Global player instance
_player: Optional[Player] = None


def get_player() -> Player:
    """Get the global player instance."""
    global _player
    if _player is None:
        _player = Player()
    return _player
