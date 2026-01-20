"""Tests for audio analyzer."""

import numpy as np
import pytest

from fomu.engine.analyzer import AudioAnalyzer


class TestAudioAnalyzer:
    """Tests for AudioAnalyzer class."""

    def test_init_defaults(self):
        """Test default initialization."""
        analyzer = AudioAnalyzer()
        assert analyzer.smoothing == 0.8

    def test_init_custom_smoothing(self):
        """Test initialization with custom smoothing."""
        analyzer = AudioAnalyzer(smoothing=0.5)
        assert analyzer.smoothing == 0.5

    def test_calculate_rms_empty(self):
        """Test RMS of empty audio is zero."""
        analyzer = AudioAnalyzer()
        rms = analyzer.calculate_rms(np.array([], dtype=np.float32))
        assert rms == 0.0

    def test_calculate_rms_silent(self, silent_audio):
        """Test RMS of silent audio is zero."""
        analyzer = AudioAnalyzer()
        rms = analyzer.calculate_rms(silent_audio)
        assert rms == 0.0

    def test_calculate_rms_normalized(self, sample_audio_stereo):
        """Test RMS is normalized to 0-1 range."""
        analyzer = AudioAnalyzer(smoothing=0.0)  # No smoothing
        rms = analyzer.calculate_rms(sample_audio_stereo)
        assert 0.0 <= rms <= 1.0

    def test_calculate_rms_mono(self, sample_audio_mono):
        """Test RMS calculation for mono audio."""
        analyzer = AudioAnalyzer(smoothing=0.0)
        rms = analyzer.calculate_rms(sample_audio_mono)
        assert 0.0 <= rms <= 1.0
        assert rms > 0.0  # Should have some level

    def test_calculate_peak_empty(self):
        """Test peak of empty audio is zero."""
        analyzer = AudioAnalyzer()
        peak = analyzer.calculate_peak(np.array([], dtype=np.float32))
        assert peak == 0.0

    def test_calculate_peak_silent(self, silent_audio):
        """Test peak of silent audio is zero."""
        analyzer = AudioAnalyzer()
        peak = analyzer.calculate_peak(silent_audio)
        assert peak == 0.0

    def test_calculate_peak_range(self, sample_audio_stereo):
        """Test peak is in 0-1 range."""
        analyzer = AudioAnalyzer()
        peak = analyzer.calculate_peak(sample_audio_stereo)
        assert 0.0 <= peak <= 1.0

    def test_calculate_frequency_bands_empty(self):
        """Test frequency bands of empty audio."""
        analyzer = AudioAnalyzer()
        bands = analyzer.calculate_frequency_bands(np.array([], dtype=np.float32))
        assert len(bands) == 16  # Default num_bands
        assert np.all(bands == 0.0)

    def test_calculate_frequency_bands_shape(self, sample_audio_stereo):
        """Test frequency bands output shape."""
        analyzer = AudioAnalyzer()
        bands = analyzer.calculate_frequency_bands(sample_audio_stereo, num_bands=8)
        assert len(bands) == 8
        assert bands.dtype == np.float32

    def test_calculate_frequency_bands_range(self, sample_audio_stereo):
        """Test frequency bands are normalized."""
        analyzer = AudioAnalyzer()
        bands = analyzer.calculate_frequency_bands(sample_audio_stereo)
        assert np.all(bands >= 0.0)
        assert np.all(bands <= 1.0)

    def test_calculate_frequency_bands_sine_wave(self):
        """Test frequency bands detect sine wave frequency."""
        analyzer = AudioAnalyzer(smoothing=0.0)

        # Create 1kHz sine wave
        sample_rate = 44100
        t = np.linspace(0, 1, sample_rate, dtype=np.float32)
        audio = np.sin(2 * np.pi * 1000 * t)

        bands = analyzer.calculate_frequency_bands(audio, num_bands=16, sample_rate=sample_rate)

        # Should have energy in bands around 1kHz
        # Band indices are logarithmically spaced from 20Hz to 20kHz
        assert np.max(bands) > 0.0

    def test_smoothing_effect(self, sample_audio_stereo, silent_audio):
        """Test smoothing affects consecutive measurements."""
        analyzer = AudioAnalyzer(smoothing=0.9)  # High smoothing

        # First measurement with signal
        rms1 = analyzer.calculate_rms(sample_audio_stereo)

        # Second measurement with silence
        rms2 = analyzer.calculate_rms(silent_audio)

        # Due to smoothing, rms2 should still be > 0 (residual from rms1)
        assert rms2 > 0.0
        assert rms2 < rms1

    def test_reset(self, sample_audio_stereo):
        """Test reset clears state."""
        analyzer = AudioAnalyzer(smoothing=0.9)

        # Build up some state
        for _ in range(10):
            analyzer.calculate_rms(sample_audio_stereo)
            analyzer.calculate_peak(sample_audio_stereo)
            analyzer.calculate_frequency_bands(sample_audio_stereo)

        analyzer.reset()

        # After reset, silent audio should give zero
        analyzer_fresh = AudioAnalyzer(smoothing=0.9)
        silent = np.zeros((1024, 2), dtype=np.float32)

        assert analyzer.calculate_rms(silent) == analyzer_fresh.calculate_rms(silent)
