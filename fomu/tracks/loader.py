"""Track loading and management."""

from __future__ import annotations

import contextlib
import os
import random
import sys
import threading
from pathlib import Path
from typing import Iterator

import numpy as np
import soundfile as sf
from numpy.typing import NDArray

from fomu.config import SAMPLE_RATE, get_tracks_dir
from fomu.tracks.catalog import Track, TrackCatalog, TrackPool


@contextlib.contextmanager
def suppress_stderr():
    """Suppress stderr output (e.g., audio library warnings)."""
    stderr_fd = sys.stderr.fileno()
    old_stderr = os.dup(stderr_fd)
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, stderr_fd)
    try:
        yield
    finally:
        os.dup2(old_stderr, stderr_fd)
        os.close(old_stderr)
        os.close(devnull)


class TrackLoader:
    """Loads and manages audio tracks."""

    def __init__(self, tracks_dir: Path | None = None) -> None:
        """Initialize the track loader.

        Args:
            tracks_dir: Directory containing audio files
        """
        self.tracks_dir = tracks_dir or get_tracks_dir()
        self.catalog = TrackCatalog()
        self._cache: dict[str, NDArray[np.float32]] = {}
        self._cache_lock = threading.Lock()
        self._preload_thread: threading.Thread | None = None

    def get_track_path(self, track: Track) -> Path:
        """Get the local path for a track."""
        return self.tracks_dir / track.filename

    def is_available(self, track: Track) -> bool:
        """Check if a track file exists and is readable."""
        path = self.get_track_path(track)
        return path.exists() and path.stat().st_size > 0

    def get_available_tracks(self, pools: list[TrackPool] | None = None) -> list[Track]:
        """Get list of available tracks, optionally filtered by pools."""
        if pools:
            tracks = self.catalog.get_tracks_by_pools(pools)
        else:
            tracks = self.catalog.get_all_tracks()

        return [t for t in tracks if self.is_available(t)]

    def load_track(self, track: Track) -> NDArray[np.float32] | None:
        """Load a track's audio data.

        Args:
            track: Track to load

        Returns:
            Audio array (samples, channels) or None if failed
        """
        # Check cache first
        with self._cache_lock:
            if track.slug in self._cache:
                return self._cache[track.slug]

        path = self.get_track_path(track)
        if not path.exists():
            return None

        try:
            # Load audio file (suppress library warnings)
            with suppress_stderr():
                audio, sr = sf.read(path, dtype=np.float32)

            # Resample if necessary
            if sr != SAMPLE_RATE:
                # Simple resampling (could use scipy for better quality)
                ratio = SAMPLE_RATE / sr
                new_length = int(len(audio) * ratio)
                indices = np.linspace(0, len(audio) - 1, new_length)
                if audio.ndim == 2:
                    audio = np.column_stack([
                        np.interp(indices, np.arange(len(audio)), audio[:, c])
                        for c in range(audio.shape[1])
                    ])
                else:
                    audio = np.interp(indices, np.arange(len(audio)), audio)

            # Ensure stereo
            if audio.ndim == 1:
                audio = np.column_stack((audio, audio))

            audio = audio.astype(np.float32)

            # Cache it
            with self._cache_lock:
                self._cache[track.slug] = audio

            return audio
        except Exception:
            return None

    def preload_track(self, track: Track) -> None:
        """Preload a track in the background.

        Args:
            track: Track to preload
        """
        def _preload():
            self.load_track(track)

        self._preload_thread = threading.Thread(target=_preload, daemon=True)
        self._preload_thread.start()

    def clear_cache(self) -> None:
        """Clear the audio cache."""
        with self._cache_lock:
            self._cache.clear()

    def create_playlist(
        self,
        pools: list[TrackPool],
        shuffle: bool = True,
    ) -> list[Track]:
        """Create a playlist from track pools.

        Args:
            pools: List of track pools to include
            shuffle: Whether to shuffle the playlist

        Returns:
            List of tracks
        """
        tracks = self.get_available_tracks(pools)
        if shuffle:
            random.shuffle(tracks)
        return tracks

    def playlist_iterator(
        self,
        pools: list[TrackPool],
        shuffle: bool = True,
        loop: bool = True,
    ) -> Iterator[tuple[Track, NDArray[np.float32]]]:
        """Create an infinite iterator over tracks.

        Args:
            pools: Track pools to include
            shuffle: Shuffle tracks
            loop: Loop playlist infinitely

        Yields:
            Tuples of (Track, audio_data)
        """
        while True:
            playlist = self.create_playlist(pools, shuffle)
            if not playlist:
                return

            for i, track in enumerate(playlist):
                audio = self.load_track(track)
                if audio is not None:
                    # Preload next track
                    if i + 1 < len(playlist):
                        self.preload_track(playlist[i + 1])

                    yield (track, audio)

            if not loop:
                break

    def get_track_duration(self, track: Track) -> float | None:
        """Get track duration in seconds.

        Args:
            track: Track to check

        Returns:
            Duration in seconds or None if not available
        """
        path = self.get_track_path(track)
        if not path.exists():
            return None

        try:
            info = sf.info(path)
            return info.duration
        except Exception:
            return None
