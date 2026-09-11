# 🎵 BeethovenFlow

A motion-aware Beethoven music player that adapts to your interaction patterns. BeethovenFlow monitors your mouse movement to detect your state (Focused, Energetic, Stressed, Fatigued) and plays appropriate Beethoven music to match your mood.

**No AI, no cloud, no tracking of what you type** — just simple statistics from your mouse movement.

## How It Works

```
Your Mouse Movement → State Classification → Beethoven Music
      ↓                       ↓                    ↓
  Velocity + Jitter    2×2 Decision Grid      YouTube via MPV
```

BeethovenFlow measures two things:
1. **Velocity**: How fast your mouse moves (px/sec)
2. **Jitter**: How erratic your movements are (directional changes)

These map to four states:

| | Jitter LOW | Jitter HIGH |
|---|---|---|
| **Velocity LOW** | 😴 Fatigued (calm adagios) | 🎯 Focused (piano sonatas) |
| **Velocity HIGH** | ⚡ Energetic (symphonies) | 😰 Stressed (dramatic pieces) |

## Features

- **Privacy-first**: Only tracks mouse movement. No keyboard content, no screenshots, no data leaves your machine.
- **Personalized calibration**: 2-minute calibration learns your baseline activity patterns.
- **Time-aware**: Adjusts thresholds based on time of day (calmer music at night).
- **Zero playlists**: Dynamically searches YouTube for Beethoven, avoiding recently played tracks.
- **Cross-platform**: Works on macOS and Windows.

## Installation

### macOS

```bash
# Clone the repo
git clone https://github.com/yourusername/beethovenflow.git
cd beethovenflow

# Run installer
./install.sh
```

The installer will:
1. Install Homebrew (if needed)
2. Install MPV and yt-dlp
3. Install BeethovenFlow
4. Remind you to grant Accessibility permissions

**Important**: After first run, go to **System Settings → Privacy & Security → Accessibility** and enable your terminal app.

### Windows

```powershell
# Clone the repo
git clone https://github.com/yourusername/beethovenflow.git
cd beethovenflow

# Run installer (in PowerShell)
.\install.ps1
```

The installer will use winget (Windows 11) or Chocolatey to install dependencies.

### Manual Installation

If you prefer to install manually:

```bash
# Install system dependencies
# macOS:
brew install mpv yt-dlp

# Windows (with winget):
winget install mpv yt-dlp

# Install BeethovenFlow
pip install -e .
```

## Usage

```bash
beethovenflow
```

### First Run

On first run, BeethovenFlow will:
1. Start MPV in headless mode
2. Play generic Beethoven music based on time of day
3. Calibrate for 2 minutes while you work normally
4. Switch to mood-based music selection

### Controls

While running, press these keys:

| Key | Action |
|-----|--------|
| `s` | Skip to next track |
| `p` | Pause/Resume playback |
| `r` | Recalibrate (2 minutes) |
| `i` | Show current state info |
| `q` | Quit |

### Example Session

```
🎵 BeethovenFlow v1.0.0
───────────────────────────────────
Starting MPV... ✓

Calibrating... Move your mouse normally for 2 minutes.
Playing generic evening music while calibrating.
Playing: Beethoven Piano Sonata No. 14 "Moonlight"

Calibrating: [████████████████████████████░░] 93%

✓ Calibration complete
  V_low: 42.3 px/s | V_high: 138.7 px/s | J_threshold: 0.45

Commands: [s]kip  [p]ause  [r]ecalibrate  [i]nfo  [q]uit

[18:34] State: FOCUSED
        Playing: Beethoven Piano Sonata No. 8 "Pathétique" - II. Adagio

[18:42] State: ENERGETIC
        Playing: Beethoven Symphony No. 7 - IV. Allegro con brio
```

## Configuration

Config is stored in:
- **macOS**: `~/Library/Application Support/BeethovenFlow/config.json`
- **Windows**: `%LOCALAPPDATA%\BeethovenFlow\config.json`

### Default Settings

```json
{
  "cooldown_seconds": 300,
  "sample_interval_seconds": 10,
  "calibration_duration_seconds": 120,
  "history_size": 20,
  "time_scaling": {
    "morning": 0.9,
    "afternoon": 1.0,
    "evening": 1.2,
    "night": 1.5
  }
}
```

- **cooldown_seconds**: Minimum time between automatic track changes (5 min default)
- **history_size**: Number of recent videos to avoid replaying
- **time_scaling**: Multiplier for velocity thresholds by time of day (higher = harder to trigger energetic states)

## Time of Day

BeethovenFlow adjusts behavior based on the time:

| Period | Hours | Behavior |
|--------|-------|----------|
| Morning | 05:00 - 11:59 | Slightly more sensitive to energetic states |
| Afternoon | 12:00 - 16:59 | Standard baseline |
| Evening | 17:00 - 21:59 | Higher threshold for high-energy music |
| Night | 22:00 - 04:59 | Heavily biased toward calm tracks |

## Troubleshooting

### "Could not start MPV"

Make sure MPV is installed and in your PATH:
```bash
mpv --version
```

### "Missing dependencies: yt-dlp"

Install yt-dlp:
```bash
# macOS
brew install yt-dlp

# Windows
winget install yt-dlp
```

### macOS: "No mouse events detected"

Grant Accessibility permissions:
1. Go to **System Settings → Privacy & Security → Accessibility**
2. Find your terminal app (Terminal, iTerm2, VS Code, etc.)
3. Toggle it ON

### Music doesn't change

- The cooldown between state changes is 5 minutes by default
- Press `i` to see current state and cooldown remaining
- Press `r` to recalibrate if your baseline has changed

### Search returns irrelevant results

YouTube search is imperfect. Press `s` to skip to the next track. The deduplication system will avoid replaying the same video.

## Architecture

```
beethovenflow/
├── __main__.py      # CLI entry point, main loop
├── config.py        # Configuration management
├── tracker.py       # Mouse movement tracking (pynput)
├── calibration.py   # Baseline calibration
├── classifier.py    # State classification (2×2 grid)
├── player.py        # YouTube search, deduplication
└── mpv_control.py   # MPV IPC (Unix socket / Windows pipe)
```

## Privacy

BeethovenFlow:
- ✅ Tracks mouse position changes (not absolute position)
- ✅ Calculates velocity and jitter statistics
- ✅ Stores calibration data locally
- ✅ Searches YouTube for music
- ❌ Does NOT log keystrokes or text content
- ❌ Does NOT send any data to external servers
- ❌ Does NOT record or store mouse paths

## Requirements

- Python 3.8+
- MPV media player
- yt-dlp
- Internet connection (for YouTube)

## License

MIT License - see LICENSE file.

## Contributing

Contributions welcome! Please open an issue or PR.

Ideas for improvement:
- [ ] System tray UI option
- [ ] Spotify integration (for Premium users)
- [ ] Custom composer/genre selection
- [ ] Volume normalization
- [ ] Idle detection to pause
