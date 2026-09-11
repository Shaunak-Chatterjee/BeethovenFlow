"""MPV IPC controller for BeethovenFlow.

Handles cross-platform communication with MPV:
- Windows: Named Pipe (\\.\pipe\mpvsocket)
- macOS/Linux: Unix Domain Socket (/tmp/mpvsocket)
"""

import json
import os
import platform
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Optional, Callable, Any


@dataclass
class TrackInfo:
    """Information about the currently playing track."""
    title: str = ""
    url: str = ""
    duration: float = 0.0
    position: float = 0.0
    paused: bool = False


def get_socket_path() -> str:
    """Get the platform-appropriate socket/pipe path."""
    if platform.system() == "Windows":
        return r"\\.\pipe\mpvsocket"
    else:
        return "/tmp/mpvsocket"


def is_mpv_installed() -> bool:
    """Check if MPV is installed and accessible."""
    try:
        result = subprocess.run(
            ["mpv", "--version"],
            capture_output=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_mpv_path() -> Optional[str]:
    """Get the path to the MPV executable."""
    import shutil
    return shutil.which("mpv")


class MPVController:
    """Controls MPV player via IPC."""
    
    def __init__(self):
        self._socket_path = get_socket_path()
        self._process: Optional[subprocess.Popen] = None
        self._socket: Optional[socket.socket] = None
        self._connected = False
        self._lock = threading.Lock()
        self._request_id = 0
        
        # Windows named pipe handle
        self._pipe_handle = None
        
        # Callbacks
        self._on_track_end: Optional[Callable[[], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
        # Track info
        self._current_track = TrackInfo()
    
    def start_mpv(self) -> bool:
        """
        Start MPV in headless mode if not already running.
        
        Returns:
            True if MPV is running (started or already was), False on failure
        """
        if self._is_mpv_running():
            return True
        
        if not is_mpv_installed():
            return False
        
        try:
            socket_path = self._socket_path
            
            # Build command
            cmd = [
                "mpv",
                "--idle=yes",
                "--no-video",
                f"--input-ipc-server={socket_path}",
                "--really-quiet"
            ]
            
            # On Unix, remove old socket if it exists
            if platform.system() != "Windows" and os.path.exists(socket_path):
                os.remove(socket_path)
            
            # Start MPV
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL
            )
            
            # Wait for socket to be available
            for _ in range(50):  # 5 second timeout
                time.sleep(0.1)
                if self._try_connect():
                    return True
            
            return False
            
        except Exception as e:
            if self._on_error:
                self._on_error(f"Failed to start MPV: {e}")
            return False
    
    def _is_mpv_running(self) -> bool:
        """Check if our MPV process is running."""
        if self._process:
            return self._process.poll() is None
        return False
    
    def _try_connect(self) -> bool:
        """Try to connect to MPV's IPC socket."""
        try:
            if platform.system() == "Windows":
                return self._connect_windows()
            else:
                return self._connect_unix()
        except Exception:
            return False
    
    def _connect_unix(self) -> bool:
        """Connect via Unix domain socket."""
        if not os.path.exists(self._socket_path):
            return False
        
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self._socket_path)
            sock.setblocking(True)
            sock.settimeout(5.0)
            self._socket = sock
            self._connected = True
            return True
        except Exception:
            return False
    
    def _connect_windows(self) -> bool:
        """Connect via Windows named pipe."""
        try:
            # On Windows, we use file I/O for named pipes
            # Try to open the pipe
            pipe_path = self._socket_path
            
            # Windows named pipes are accessed as files
            self._pipe_handle = open(pipe_path, "r+b", buffering=0)
            self._connected = True
            return True
        except Exception:
            return False
    
    def _send_command(self, command: list[Any]) -> Optional[dict]:
        """
        Send a command to MPV and wait for response.
        
        Args:
            command: MPV command as a list (e.g., ["loadfile", "url"])
            
        Returns:
            Response dict or None on failure
        """
        with self._lock:
            self._request_id += 1
            request = {
                "command": command,
                "request_id": self._request_id
            }
            
            try:
                message = json.dumps(request) + "\n"
                
                if platform.system() == "Windows":
                    if self._pipe_handle:
                        self._pipe_handle.write(message.encode("utf-8"))
                        self._pipe_handle.flush()
                        # Read response
                        response_line = self._pipe_handle.readline()
                        if response_line:
                            return json.loads(response_line.decode("utf-8"))
                else:
                    if self._socket:
                        self._socket.sendall(message.encode("utf-8"))
                        # Read response
                        response_data = b""
                        while b"\n" not in response_data:
                            chunk = self._socket.recv(4096)
                            if not chunk:
                                break
                            response_data += chunk
                        
                        if response_data:
                            # Parse first line (response to our command)
                            first_line = response_data.split(b"\n")[0]
                            return json.loads(first_line.decode("utf-8"))
                
            except Exception as e:
                if self._on_error:
                    self._on_error(f"IPC error: {e}")
                self._connected = False
                return None
        
        return None
    
    def _get_property(self, prop: str) -> Any:
        """Get a property value from MPV."""
        result = self._send_command(["get_property", prop])
        if result and "data" in result:
            return result["data"]
        return None
    
    def connect(self) -> bool:
        """
        Connect to an existing MPV instance.
        
        Returns:
            True if connected, False otherwise
        """
        return self._try_connect()
    
    def disconnect(self) -> None:
        """Disconnect from MPV."""
        with self._lock:
            self._connected = False
            
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            
            if self._pipe_handle:
                try:
                    self._pipe_handle.close()
                except Exception:
                    pass
                self._pipe_handle = None
    
    def stop_mpv(self) -> None:
        """Stop MPV and disconnect."""
        self._send_command(["quit"])
        self.disconnect()
        
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                self._process.kill()
            self._process = None
    
    def is_connected(self) -> bool:
        """Check if connected to MPV."""
        return self._connected
    
    def load_file(self, url: str, mode: str = "replace") -> bool:
        """
        Load a file/URL into MPV.
        
        Args:
            url: The URL or file path to load
            mode: 'replace' (stop current), 'append' (add to playlist)
            
        Returns:
            True if command succeeded
        """
        result = self._send_command(["loadfile", url, mode])
        return result is not None and result.get("error") == "success"
    
    def pause(self) -> bool:
        """Pause playback."""
        result = self._send_command(["set_property", "pause", True])
        return result is not None
    
    def resume(self) -> bool:
        """Resume playback."""
        result = self._send_command(["set_property", "pause", False])
        return result is not None
    
    def toggle_pause(self) -> bool:
        """Toggle pause state."""
        current = self._get_property("pause")
        if current is not None:
            return self.resume() if current else self.pause()
        return False
    
    def stop(self) -> bool:
        """Stop playback."""
        result = self._send_command(["stop"])
        return result is not None
    
    def set_volume(self, volume: int) -> bool:
        """Set volume (0-100)."""
        result = self._send_command(["set_property", "volume", max(0, min(100, volume))])
        return result is not None
    
    def get_volume(self) -> int:
        """Get current volume."""
        vol = self._get_property("volume")
        return int(vol) if vol is not None else 100
    
    def get_track_info(self) -> TrackInfo:
        """Get information about the current track."""
        info = TrackInfo()
        
        info.title = self._get_property("media-title") or ""
        info.url = self._get_property("path") or ""
        info.duration = self._get_property("duration") or 0.0
        info.position = self._get_property("time-pos") or 0.0
        info.paused = self._get_property("pause") or False
        
        return info
    
    def is_playing(self) -> bool:
        """Check if something is currently playing."""
        idle = self._get_property("idle-active")
        return idle is False
    
    def is_paused(self) -> bool:
        """Check if playback is paused."""
        return self._get_property("pause") or False
    
    def set_on_track_end(self, callback: Callable[[], None]) -> None:
        """Set callback for when a track ends."""
        self._on_track_end = callback
    
    def set_on_error(self, callback: Callable[[str], None]) -> None:
        """Set callback for errors."""
        self._on_error = callback


# Global controller instance
_controller: Optional[MPVController] = None


def get_controller() -> MPVController:
    """Get the global MPV controller instance."""
    global _controller
    if _controller is None:
        _controller = MPVController()
    return _controller
