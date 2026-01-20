"""Audio analysis for visualization."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from fomu.config import BARS_COUNT


class AudioAnalyzer:
    """Analyzes audio for visualization purposes."""

    def __init__(self, smoothing: float = 0.8) -> None:
        """Initialize the analyzer.

        Args:
            smoothing: Smoothing factor for values (0-1, higher = smoother)
        """
        self.smoothing = smoothing
        self._last_rms = 0.0
        self._last_peak = 0.0
        self._last_bands: NDArray[np.float32] | None = None

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
        num_bands: int = BARS_COUNT,
        sample_rate: int = 44100,
    ) -> NDArray[np.float32]:
        """Calculate frequency band levels using FFT.

        Args:
            audio: Audio samples
            num_bands: Number of frequency bands
            sample_rate: Sample rate

        Returns:
            Array of band levels (0-1 range)
        """
        if len(audio) == 0:
            return np.zeros(num_bands, dtype=np.float32)

        # Convert to mono if stereo
        if audio.ndim == 2:
            audio = audio.mean(axis=1)

        # Ensure power of 2 for FFT
        n = len(audio)
        if n < 512:
            audio = np.pad(audio, (0, 512 - n))
            n = 512

        # Apply window
        window = np.hanning(n)
        windowed = audio * window

        # FFT
        fft = np.fft.rfft(windowed)
        magnitudes = np.abs(fft)

        # Frequency resolution
        freq_resolution = sample_rate / n

        # Define logarithmic frequency bands (20Hz to 20kHz)
        min_freq = 20
        max_freq = min(20000, sample_rate / 2)
        band_edges = np.logspace(
            np.log10(min_freq),
            np.log10(max_freq),
            num_bands + 1,
        )

        # Calculate band levels
        bands = np.zeros(num_bands, dtype=np.float32)
        for i in range(num_bands):
            low_bin = int(band_edges[i] / freq_resolution)
            high_bin = int(band_edges[i + 1] / freq_resolution)
            high_bin = max(low_bin + 1, high_bin)  # At least one bin

            if high_bin <= len(magnitudes):
                bands[i] = magnitudes[low_bin:high_bin].mean()

        # Normalize
        if bands.max() > 0:
            bands = bands / bands.max()

        # Apply smoothing
        if self._last_bands is None:
            self._last_bands = bands
        else:
            # Smooth with different attack/decay
            for i in range(num_bands):
                if bands[i] > self._last_bands[i]:
                    # Fast attack
                    self._last_bands[i] = self._last_bands[i] * 0.5 + bands[i] * 0.5
                else:
                    # Slow decay
                    self._last_bands[i] = self._last_bands[i] * 0.85 + bands[i] * 0.15

        return self._last_bands.copy()

    def reset(self) -> None:
        """Reset analyzer state."""
        self._last_rms = 0.0
        self._last_peak = 0.0
        self._last_bands = None
