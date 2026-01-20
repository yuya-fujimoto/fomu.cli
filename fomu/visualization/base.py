"""Base visualizer class."""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray
from rich.console import Console, RenderableType

from fomu.config import COLOR_THEMES, DEFAULT_THEME


class BaseVisualizer(ABC):
    """Base class for audio visualizers."""

    def __init__(
        self,
        width: int = 60,
        height: int = 8,
        theme: str = DEFAULT_THEME,
    ) -> None:
        """Initialize the visualizer.

        Args:
            width: Width in characters
            height: Height in lines
            theme: Color theme name
        """
        self.width = width
        self.height = height
        self.theme = COLOR_THEMES.get(theme, COLOR_THEMES[DEFAULT_THEME])
        self._rms = 0.0
        self._bands: NDArray[np.float32] | None = None

    def update(self, rms: float, bands: NDArray[np.float32]) -> None:
        """Update visualization with new audio data.

        Args:
            rms: RMS level (0-1)
            bands: Frequency band levels
        """
        self._rms = rms
        self._bands = bands

    @abstractmethod
    def render(self) -> RenderableType:
        """Render the visualization.

        Returns:
            Rich renderable object
        """
        pass

    @property
    def primary_color(self) -> str:
        """Get primary theme color."""
        return self.theme["primary"]

    @property
    def secondary_color(self) -> str:
        """Get secondary theme color."""
        return self.theme["secondary"]

    def set_theme(self, theme: str) -> None:
        """Set the color theme.

        Args:
            theme: Theme name
        """
        if theme in COLOR_THEMES:
            self.theme = COLOR_THEMES[theme]


class VisualizerRegistry:
    """Registry of available visualizers."""

    _visualizers: dict[str, type[BaseVisualizer]] = {}

    @classmethod
    def register(cls, name: str):
        """Decorator to register a visualizer class."""
        def decorator(visualizer_cls: type[BaseVisualizer]):
            cls._visualizers[name] = visualizer_cls
            return visualizer_cls
        return decorator

    @classmethod
    def get(cls, name: str) -> type[BaseVisualizer] | None:
        """Get a visualizer class by name."""
        return cls._visualizers.get(name)

    @classmethod
    def get_names(cls) -> list[str]:
        """Get all registered visualizer names."""
        return list(cls._visualizers.keys())

    @classmethod
    def create(
        cls,
        name: str,
        **kwargs,
    ) -> BaseVisualizer | None:
        """Create a visualizer instance.

        Args:
            name: Visualizer name
            **kwargs: Arguments to pass to visualizer

        Returns:
            Visualizer instance or None if not found
        """
        visualizer_cls = cls.get(name)
        if visualizer_cls:
            return visualizer_cls(**kwargs)
        return None
