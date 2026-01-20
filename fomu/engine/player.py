"""Audio playback controller using sounddevice."""

from __future__ import annotations

import queue
import threading
from typing import Callable

import numpy as np
import sounddevice as sd
from numpy.typing import NDArray

from fomu.config import BUFFER_SIZE, CHANNELS, SAMPLE_RATE, DEFAULT_VOLUME
from fomu.engine.analyzer import AudioAnalyzer


class AudioPlayer:
    """Manages audio playback."""

    def __init__(
        self,
        sample_rate: int = SAMPLE_RATE,
        buffer_size: int = BUFFER_SIZE,
        channels: int = CHANNELS,
    ) -> None:
        """Initialize the audio player.

        Args:
            sample_rate: Audio sample rate
            buffer_size: Buffer size for playback
            channels: Number of audio channels
        """
        self.sample_rate = sample_rate
        self.buffer_size = buffer_size
        self.channels = channels

        self._volume = DEFAULT_VOLUME
        self.analyzer = AudioAnalyzer()

        self._stream: sd.OutputStream | None = None
        self._audio_queue: queue.Queue[NDArray[np.float32]] = queue.Queue(maxsize=32)
        self._current_audio: NDArray[np.float32] | None = None
        self._audio_position = 0
        self._is_playing = False
        self._is_paused = False
        self._lock = threading.Lock()

        # Callback for analysis data
        self._analysis_callback: Callable[[float, NDArray[np.float32]], None] | None = None
        self._last_buffer: NDArray[np.float32] | None = None

    @property
    def volume(self) -> float:
        """Get current volume."""
        return self._volume

    @volume.setter
    def volume(self, value: float) -> None:
        """Set volume (clamped to 0-1)."""
        self._volume = max(0.0, min(1.0, value))

    def set_audio(self, audio: NDArray[np.float32]) -> None:
        """Set the audio data to play.

        Args:
            audio: Audio array (samples, channels) or (samples,) for mono
        """
        with self._lock:
            # Ensure stereo
            if audio.ndim == 1:
                audio = np.column_stack((audio, audio))

            self._current_audio = audio.astype(np.float32)
            self._audio_position = 0

    def queue_audio(self, audio: NDArray[np.float32]) -> None:
        """Queue audio for seamless playback.

        Args:
            audio: Audio array to queue
        """
        # Ensure stereo
        if audio.ndim == 1:
            audio = np.column_stack((audio, audio))

        try:
            self._audio_queue.put_nowait(audio.astype(np.float32))
        except queue.Full:
            pass  # Drop if queue is full

    def _audio_callback(
        self,
        outdata: NDArray[np.float32],
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Sounddevice callback for audio output."""
        if status:
            pass  # Could log status issues

        if self._is_paused:
            outdata.fill(0)
            return

        with self._lock:
            if self._current_audio is None:
                outdata.fill(0)
                return

            # Get music frames
            start = self._audio_position
            end = start + frames

            if end <= len(self._current_audio):
                music = self._current_audio[start:end].copy()
                self._audio_position = end
            else:
                # End of current audio
                remaining = len(self._current_audio) - start
                if remaining > 0:
                    music = np.zeros((frames, 2), dtype=np.float32)
                    music[:remaining] = self._current_audio[start:]
                else:
                    music = np.zeros((frames, 2), dtype=np.float32)

                # Try to get next audio from queue
                try:
                    self._current_audio = self._audio_queue.get_nowait()
                    self._audio_position = frames - remaining
                    if remaining < frames and len(self._current_audio) > 0:
                        to_fill = min(frames - remaining, len(self._current_audio))
                        music[remaining:remaining + to_fill] = self._current_audio[:to_fill]
                except queue.Empty:
                    self._audio_position = len(self._current_audio)

        # Apply volume
        output = music * self._volume

        # Output
        outdata[:] = output

        # Store for analysis (will be processed outside the audio callback)
        self._last_buffer = output.copy()

    def start(self) -> None:
        """Start audio playback."""
        if self._stream is not None:
            return

        self._is_playing = True
        self._is_paused = False

        self._stream = sd.OutputStream(
            samplerate=self.sample_rate,
            blocksize=self.buffer_size,
            channels=self.channels,
            dtype=np.float32,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """Stop audio playback."""
        self._is_playing = False
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def pause(self) -> None:
        """Pause playback."""
        self._is_paused = True

    def resume(self) -> None:
        """Resume playback."""
        self._is_paused = False

    def toggle_pause(self) -> bool:
        """Toggle pause state.

        Returns:
            True if now playing, False if now paused
        """
        self._is_paused = not self._is_paused
        return not self._is_paused

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._is_playing and not self._is_paused

    @property
    def is_paused(self) -> bool:
        """Check if paused."""
        return self._is_paused

    @property
    def position(self) -> float:
        """Get current position in seconds."""
        return self._audio_position / self.sample_rate

    @property
    def duration(self) -> float:
        """Get total duration in seconds."""
        if self._current_audio is None:
            return 0.0
        return len(self._current_audio) / self.sample_rate

    @property
    def progress(self) -> float:
        """Get playback progress (0-1)."""
        if self._current_audio is None or len(self._current_audio) == 0:
            return 0.0
        return self._audio_position / len(self._current_audio)

    def set_analysis_callback(
        self,
        callback: Callable[[float, NDArray[np.float32]], None],
    ) -> None:
        """Set callback for audio analysis data.

        Args:
            callback: Function called with (rms, frequency_bands)
        """
        self._analysis_callback = callback

    def get_last_buffer(self) -> NDArray[np.float32] | None:
        """Get the last played audio buffer for analysis."""
        return self._last_buffer

    def get_analysis(self) -> tuple[float, NDArray[np.float32]]:
        """Get audio analysis data (call from UI thread, not audio callback).

        Returns:
            Tuple of (rms, frequency_bands)
        """
        buffer = self._last_buffer
        if buffer is None:
            return (0.0, np.zeros(16, dtype=np.float32))

        rms = self.analyzer.calculate_rms(buffer)
        bands = self.analyzer.calculate_frequency_bands(buffer, sample_rate=self.sample_rate)
        return (rms, bands)
