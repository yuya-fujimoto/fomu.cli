"""Configuration constants for FocusMusic."""

from pathlib import Path

# Audio settings
SAMPLE_RATE = 44100
BUFFER_SIZE = 4096  # Larger buffer for stability
CHANNELS = 2

# Volume settings
DEFAULT_VOLUME = 0.8
VOLUME_STEP = 0.05
MIN_VOLUME = 0.0
MAX_VOLUME = 1.0

# Visualization settings
VIZ_FPS = 30
WAVE_WIDTH = 60
BARS_COUNT = 16

# Track settings
CROSSFADE_DURATION = 3.0  # Seconds for crossfade between tracks
TRACK_PRELOAD_TIME = 10.0  # Seconds before track end to start loading next

# Paths
def get_tracks_dir() -> Path:
    """Get the tracks directory, creating it if necessary."""
    # Look for tracks in package directory first, then current directory
    package_dir = Path(__file__).parent.parent.parent.parent / "tracks" / "scott-buckley"
    if package_dir.exists():
        return package_dir

    # Fallback to user's home directory
    home_tracks = Path.home() / ".fomu" / "tracks" / "scott-buckley"
    home_tracks.mkdir(parents=True, exist_ok=True)
    return home_tracks

# Color themes
COLOR_THEMES = {
    "cyan": {"primary": "cyan", "secondary": "blue"},
    "purple": {"primary": "magenta", "secondary": "purple"},
    "green": {"primary": "green", "secondary": "cyan"},
    "warm": {"primary": "yellow", "secondary": "orange3"},
    "mono": {"primary": "white", "secondary": "grey70"},
}

DEFAULT_THEME = "cyan"
DEFAULT_VIZ_MODE = "wave"
DEFAULT_PRESET = "focus"
