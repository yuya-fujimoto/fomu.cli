"""Pytest fixtures for FocusMusic tests."""

import numpy as np
import pytest


@pytest.fixture
def sample_audio_mono():
    """Create sample mono audio data."""
    # 1 second of 440Hz sine wave at 44100Hz
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    return audio


@pytest.fixture
def sample_audio_stereo():
    """Create sample stereo audio data."""
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration), dtype=np.float32)
    left = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    right = np.sin(2 * np.pi * 550 * t).astype(np.float32)
    return np.column_stack((left, right))


@pytest.fixture
def silent_audio():
    """Create silent audio data."""
    return np.zeros((44100, 2), dtype=np.float32)
