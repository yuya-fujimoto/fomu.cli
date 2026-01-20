"""Tests for presets."""

import pytest

from fomu.presets import (
    Preset,
    get_preset,
    get_all_presets,
    get_preset_names,
    PRESETS,
)
from fomu.tracks.catalog import TrackPool


class TestPreset:
    """Tests for Preset class."""

    def test_preset_attributes(self):
        """Test preset has required attributes."""
        preset = Preset(
            name="test",
            hz_min=10.0,
            hz_max=14.0,
            pools=[TrackPool.CALM_FOCUS],
            description="Test preset",
        )
        assert preset.name == "test"
        assert preset.hz_min == 10.0
        assert preset.hz_max == 14.0
        assert preset.pools == [TrackPool.CALM_FOCUS]
        assert preset.description == "Test preset"

    def test_hz_range(self):
        """Test hz_range property."""
        preset = Preset(
            name="test",
            hz_min=10.0,
            hz_max=14.0,
            pools=[TrackPool.CALM_FOCUS],
            description="Test",
        )
        assert preset.hz_range == (10.0, 14.0)

    def test_hz_center(self):
        """Test hz_center property."""
        preset = Preset(
            name="test",
            hz_min=10.0,
            hz_max=14.0,
            pools=[TrackPool.CALM_FOCUS],
            description="Test",
        )
        assert preset.hz_center == 12.0


class TestPresetFunctions:
    """Tests for preset utility functions."""

    def test_get_preset_exists(self):
        """Test getting an existing preset."""
        preset = get_preset("focus")
        assert preset is not None
        assert preset.name == "focus"

    def test_get_preset_not_exists(self):
        """Test getting a non-existent preset."""
        preset = get_preset("nonexistent")
        assert preset is None

    def test_get_all_presets(self):
        """Test getting all presets."""
        presets = get_all_presets()
        assert len(presets) == 6
        assert all(isinstance(p, Preset) for p in presets)

    def test_get_preset_names(self):
        """Test getting preset names."""
        names = get_preset_names()
        assert "focus" in names
        assert "deep" in names
        assert "creative" in names
        assert "flow" in names
        assert "relax" in names
        assert "morning" in names


class TestBuiltinPresets:
    """Tests for built-in preset definitions."""

    def test_focus_preset(self):
        """Test focus preset configuration."""
        preset = PRESETS["focus"]
        assert preset.hz_min == 14.0
        assert preset.hz_max == 16.0
        assert TrackPool.ATMOSPHERIC in preset.pools

    def test_deep_preset(self):
        """Test deep preset configuration."""
        preset = PRESETS["deep"]
        assert preset.hz_min == 12.0
        assert preset.hz_max == 14.0
        assert TrackPool.CALM_FOCUS in preset.pools

    def test_creative_preset(self):
        """Test creative preset configuration."""
        preset = PRESETS["creative"]
        assert preset.hz_min == 10.0
        assert preset.hz_max == 12.0
        assert TrackPool.GENTLE_MOVEMENT in preset.pools

    def test_flow_preset(self):
        """Test flow preset configuration."""
        preset = PRESETS["flow"]
        assert preset.hz_min == 8.0
        assert preset.hz_max == 10.0

    def test_relax_preset(self):
        """Test relax preset configuration."""
        preset = PRESETS["relax"]
        assert preset.hz_min == 6.0
        assert preset.hz_max == 8.0
        assert TrackPool.CALM_FOCUS in preset.pools

    def test_morning_preset(self):
        """Test morning preset configuration."""
        preset = PRESETS["morning"]
        assert preset.hz_min == 16.0
        assert preset.hz_max == 20.0
        assert TrackPool.GENTLE_MOVEMENT in preset.pools

    def test_all_presets_have_pools(self):
        """Test all presets have at least one pool."""
        for name, preset in PRESETS.items():
            assert len(preset.pools) > 0, f"Preset {name} has no pools"

    def test_all_presets_have_valid_hz_range(self):
        """Test all presets have valid Hz range."""
        for name, preset in PRESETS.items():
            assert preset.hz_min < preset.hz_max, f"Preset {name} has invalid Hz range"
            assert preset.hz_min >= 1.0, f"Preset {name} Hz too low"
            assert preset.hz_max <= 40.0, f"Preset {name} Hz too high"
