"""Preset definitions for FocusMusic."""

from __future__ import annotations

from dataclasses import dataclass

from fomu.tracks.catalog import TrackPool


@dataclass
class Preset:
    """A focus preset with entrainment frequency and track pools."""
    name: str
    hz_min: float
    hz_max: float
    pools: list[TrackPool]
    description: str

    @property
    def hz_range(self) -> tuple[float, float]:
        """Get the frequency range."""
        return (self.hz_min, self.hz_max)

    @property
    def hz_center(self) -> float:
        """Get the center frequency."""
        return (self.hz_min + self.hz_max) / 2


# All presets from the spec
PRESETS: dict[str, Preset] = {
    "focus": Preset(
        name="focus",
        hz_min=14.0,
        hz_max=16.0,
        pools=[TrackPool.ATMOSPHERIC, TrackPool.CALM_FOCUS],
        description="Coding, writing",
    ),
    "deep": Preset(
        name="deep",
        hz_min=12.0,
        hz_max=14.0,
        pools=[TrackPool.CALM_FOCUS, TrackPool.ATMOSPHERIC],
        description="Reading, research",
    ),
    "creative": Preset(
        name="creative",
        hz_min=10.0,
        hz_max=12.0,
        pools=[TrackPool.ATMOSPHERIC, TrackPool.GENTLE_MOVEMENT],
        description="Brainstorming",
    ),
    "flow": Preset(
        name="flow",
        hz_min=8.0,
        hz_max=10.0,
        pools=[TrackPool.CALM_FOCUS, TrackPool.ATMOSPHERIC],
        description="Creative work",
    ),
    "relax": Preset(
        name="relax",
        hz_min=6.0,
        hz_max=8.0,
        pools=[TrackPool.CALM_FOCUS],
        description="Unwinding",
    ),
    "morning": Preset(
        name="morning",
        hz_min=16.0,
        hz_max=20.0,
        pools=[TrackPool.GENTLE_MOVEMENT, TrackPool.ATMOSPHERIC],
        description="Waking up",
    ),
}


def get_preset(name: str) -> Preset | None:
    """Get a preset by name."""
    return PRESETS.get(name)


def get_all_presets() -> list[Preset]:
    """Get all available presets."""
    return list(PRESETS.values())


def get_preset_names() -> list[str]:
    """Get all preset names."""
    return list(PRESETS.keys())
