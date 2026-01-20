"""Audio analysis for visualization."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from fomu.config import BARS_COUNT


class AudioAnalyzer:
    """Analyzes audio for visualization purposes."""

    def __init__(
        self,
        smoothing: float = 0.8,
        fft_size: int = 512,
        num_bands: int = BARS_COUNT,
        sample_rate: int = 44100,
    ) -> None:
        """Initialize the analyzer.

        Args:
            smoothing: Smoothing factor for values (0-1, higher = smoother)
            fft_size: Size of FFT window (power of 2)
            num_bands: Number of frequency bands
            sample_rate: Sample rate for frequency calculations
        """
        self.smoothing = smoothing
        self._fft_size = fft_size
        self._num_bands = num_bands
        self._sample_rate = sample_rate
        self._last_rms = 0.0
        self._last_peak = 0.0
        self._last_bands: NDArray[np.float32] | None = None

        # Pre-allocated workspace buffers (avoid allocations in hot path)
        self._window = np.hanning(fft_size).astype(np.float32)
        self._mono_buffer = np.zeros(fft_size, dtype=np.float32)
        self._windowed = np.zeros(fft_size, dtype=np.float32)
        self._bands_buffer = np.zeros(num_bands, dtype=np.float32)

        # Pre-compute logarithmic band edges (constant for given sample rate)
        min_freq = 20
        max_freq = min(20000, sample_rate / 2)
        self._band_edges = np.logspace(
            np.log10(min_freq),
            np.log10(max_freq),
            num_bands + 1,
        )
        self._freq_resolution = sample_rate / fft_size

    def calculate_rms(self, audio: NDArray[np.float32]) -> float:
        """Calculate RMS (Root Mean Square) level of audio.

        Args:
            audio: Audio samples

        Returns:
            RMS level (0-1 range, normalized)
        """
        if len(audio) == 0:
            return 0.0

        # Convert to mono if stereo
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        # Calculate RMS
        rms = np.sqrt(np.mean(audio ** 2))

        # Normalize (typical music RMS is around 0.1-0.3)
        normalized = min(1.0, rms * 3.0)

        # Apply smoothing
        smoothed = self._last_rms * self.smoothing + normalized * (1 - self.smoothing)
        self._last_rms = smoothed

        return smoothed

    def calculate_peak(self, audio: NDArray[np.float32]) -> float:
        """Calculate peak level of audio.

        Args:
            audio: Audio samples

        Returns:
            Peak level (0-1 range)
        """
        if len(audio) == 0:
            return 0.0

        # Convert to mono if stereo
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        # Get peak
        peak = np.abs(audio).max()

        # Apply smoothing with faster attack, slower decay
        if peak > self._last_peak:
            # Fast attack
            smoothed = self._last_peak * 0.3 + peak * 0.7
        else:
            # Slow decay
            smoothed = self._last_peak * 0.95 + peak * 0.05

        self._last_peak = smoothed
        return smoothed

    def calculate_frequency_bands(
        self,
        audio: NDArray[np.float32],
        num_bands: int | None = None,
        sample_rate: int | None = None,
    ) -> NDArray[np.float32]:
        """Calculate frequency band levels using FFT.

        Uses pre-allocated buffers to minimize allocations in the hot path
        when using default parameters.

        Args:
            audio: Audio samples
            num_bands: Number of frequency bands (uses pre-configured if None)
            sample_rate: Sample rate (uses pre-configured if None)

        Returns:
            Array of band levels (0-1 range)
        """
        # Use pre-configured values if not specified
        use_prealloc = num_bands is None and sample_rate is None
        num_bands = num_bands if num_bands is not None else self._num_bands
        sample_rate = sample_rate if sample_rate is not None else self._sample_rate

        if len(audio) == 0:
            return np.zeros(num_bands, dtype=np.float32)

        # Convert to mono if stereo
        if audio.ndim == 2:
            audio_mono = audio.mean(axis=1)
        else:
            audio_mono = audio

        # Use pre-allocated buffers when possible (default path)
        if use_prealloc:
            n = min(len(audio_mono), self._fft_size)
            self._mono_buffer.fill(0)
            self._mono_buffer[:n] = audio_mono[:n]
            np.multiply(self._mono_buffer, self._window, out=self._windowed)
            fft = np.fft.rfft(self._windowed)
            magnitudes = np.abs(fft)
            band_edges = self._band_edges
            freq_resolution = self._freq_resolution
            bands_buffer = self._bands_buffer
            bands_buffer.fill(0)
        else:
            # Non-default path: allocate as needed (rare, for API compatibility)
            n = len(audio_mono)
            if n < 512:
                audio_mono = np.pad(audio_mono, (0, 512 - n))
                n = 512
            window = np.hanning(n)
            windowed = audio_mono * window
            fft = np.fft.rfft(windowed)
            magnitudes = np.abs(fft)
            freq_resolution = sample_rate / n
            min_freq = 20
            max_freq = min(20000, sample_rate / 2)
            band_edges = np.logspace(np.log10(min_freq), np.log10(max_freq), num_bands + 1)
            bands_buffer = np.zeros(num_bands, dtype=np.float32)

        # Calculate band levels
        for i in range(num_bands):
            low_bin = int(band_edges[i] / freq_resolution)
            high_bin = int(band_edges[i + 1] / freq_resolution)
            high_bin = max(low_bin + 1, high_bin)

            if high_bin <= len(magnitudes):
                bands_buffer[i] = magnitudes[low_bin:high_bin].mean()

        # Normalize
        max_val = bands_buffer.max()
        if max_val > 0:
            bands_buffer = bands_buffer / max_val

        # Apply smoothing (only for pre-allocated path with matching band count)
        if use_prealloc:
            if self._last_bands is None:
                self._last_bands = bands_buffer.copy()
            else:
                for i in range(num_bands):
                    if bands_buffer[i] > self._last_bands[i]:
                        self._last_bands[i] = self._last_bands[i] * 0.5 + bands_buffer[i] * 0.5
                    else:
                        self._last_bands[i] = self._last_bands[i] * 0.85 + bands_buffer[i] * 0.15
            return self._last_bands.copy()
        else:
            # For non-default path, return without persistent smoothing
            return bands_buffer

    def reset(self) -> None:
        """Reset analyzer state."""
        self._last_rms = 0.0
        self._last_peak = 0.0
        self._last_bands = None
        self._mono_buffer.fill(0)
        self._windowed.fill(0)
        self._bands_buffer.fill(0)
