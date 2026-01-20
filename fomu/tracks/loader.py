"""Track loading and management."""

from __future__ import annotations

import contextlib
import os
import random
import sys
import threading
from collections import deque
from pathlib import Path
from typing import Iterator

import numpy as np
import soundfile as sf
from cachetools import LRUCache
from numpy.typing import NDArray

from fomu.config import MAX_CACHED_TRACKS, SAMPLE_RATE, STREAMING_CHUNK_SECONDS, get_tracks_dir
from fomu.tracks.catalog import Track, TrackCatalog, TrackPool


class StreamingAudioSource:
    """Memory-efficient streaming audio source.

    Instead of loading entire tracks into memory (~400MB per track),
    this class streams audio in chunks (~4MB per chunk at 10 seconds).
    """

    def __init__(
        self,
        path: Path,
        target_sample_rate: int = SAMPLE_RATE,
        chunk_seconds: float = STREAMING_CHUNK_SECONDS,
    ) -> None:
        """Initialize streaming audio source.

        Args:
            path: Path to audio file
            target_sample_rate: Target sample rate for resampling
            chunk_seconds: Seconds of audio per chunk
        """
        self._path = path
        self._target_sample_rate = target_sample_rate
        self._chunk_frames = int(target_sample_rate * chunk_seconds)

        # Open file for streaming
        self._file = sf.SoundFile(path)
        self._source_sample_rate = self._file.samplerate
        self._total_source_frames = self._file.frames
        self._channels = self._file.channels

        # Calculate total frames after resampling
        if self._source_sample_rate != target_sample_rate:
            self._resample_ratio = target_sample_rate / self._source_sample_rate
            self._total_frames = int(self._total_source_frames * self._resample_ratio)
        else:
            self._resample_ratio = 1.0
            self._total_frames = self._total_source_frames

        # Current position in target sample rate frames
        self._position = 0

        # Preloaded chunk buffer (stores next chunk for seamless playback)
        self._current_chunk: NDArray[np.float32] | None = None
        self._chunk_position = 0  # Position within current chunk

        # Lock for thread-safe access
        self._lock = threading.Lock()

        # Preload first chunk
        self._preload_next_chunk()

    @property
    def total_frames(self) -> int:
        """Total frames in target sample rate."""
        return self._total_frames

    @property
    def position(self) -> int:
        """Current position in frames."""
        return self._position

    @property
    def duration(self) -> float:
        """Duration in seconds."""
        return self._total_frames / self._target_sample_rate

    @property
    def progress(self) -> float:
        """Playback progress (0-1)."""
        if self._total_frames == 0:
            return 0.0
        return self._position / self._total_frames

    def _preload_next_chunk(self) -> None:
        """Load the next chunk of audio from file."""
        if self._file.tell() >= self._total_source_frames:
            # End of file
            self._current_chunk = None
            return

        # Calculate how many source frames to read
        source_chunk_frames = int(self._chunk_frames / self._resample_ratio) if self._resample_ratio != 1.0 else self._chunk_frames

        # Read from file
        audio = self._file.read(source_chunk_frames, dtype=np.float32)

        if len(audio) == 0:
            self._current_chunk = None
            return

        # Resample if needed
        if self._resample_ratio != 1.0:
            new_length = int(len(audio) * self._resample_ratio)
            if new_length > 0:
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

        self._current_chunk = audio.astype(np.float32)
        self._chunk_position = 0

    def read(self, frames: int) -> NDArray[np.float32]:
        """Read audio frames from the stream.

        Args:
            frames: Number of frames to read

        Returns:
            Audio array (frames, 2) in float32
        """
        with self._lock:
            if self._current_chunk is None:
                # End of stream
                return np.zeros((frames, 2), dtype=np.float32)

            output = np.zeros((frames, 2), dtype=np.float32)
            output_pos = 0

            while output_pos < frames:
                if self._current_chunk is None:
                    break

                # How much can we read from current chunk?
                available = len(self._current_chunk) - self._chunk_position
                needed = frames - output_pos
                to_read = min(available, needed)

                if to_read > 0:
                    output[output_pos:output_pos + to_read] = self._current_chunk[
                        self._chunk_position:self._chunk_position + to_read
                    ]
                    self._chunk_position += to_read
                    output_pos += to_read
                    self._position += to_read

                # Need more data?
                if self._chunk_position >= len(self._current_chunk):
                    self._preload_next_chunk()

            return output

    def is_finished(self) -> bool:
        """Check if stream has reached the end."""
        with self._lock:
            return self._current_chunk is None and self._position >= self._total_frames - 1

    def close(self) -> None:
        """Close the audio file."""
        with self._lock:
            if self._file is not None:
                self._file.close()
                self._file = None
                self._current_chunk = None

    def __del__(self) -> None:
        """Cleanup on deletion."""
        self.close()


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
        self._cache: LRUCache[str, NDArray[np.float32]] = LRUCache(maxsize=MAX_CACHED_TRACKS)
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

    def open_stream(self, track: Track) -> StreamingAudioSource | None:
        """Open a track as a streaming audio source.

        This is more memory-efficient than load_track() as it only keeps
        one chunk (~10 seconds) in memory at a time instead of the entire track.

        Args:
            track: Track to open

        Returns:
            StreamingAudioSource or None if failed
        """
        path = self.get_track_path(track)
        if not path.exists():
            return None

        try:
            with suppress_stderr():
                return StreamingAudioSource(path, target_sample_rate=SAMPLE_RATE)
        except Exception:
            return None

    def streaming_playlist_iterator(
        self,
        pools: list[TrackPool],
        shuffle: bool = True,
        loop: bool = True,
    ) -> Iterator[tuple[Track, StreamingAudioSource]]:
        """Create an infinite iterator over tracks using streaming.

        More memory-efficient than playlist_iterator() as tracks are streamed
        rather than fully loaded into memory.

        Args:
            pools: Track pools to include
            shuffle: Shuffle tracks
            loop: Loop playlist infinitely

        Yields:
            Tuples of (Track, StreamingAudioSource)
        """
        while True:
            playlist = self.create_playlist(pools, shuffle)
            if not playlist:
                return

            for track in playlist:
                stream = self.open_stream(track)
                if stream is not None:
                    yield (track, stream)

            if not loop:
                break
