"""Wave visualization - scrolling wave based on audio amplitude."""

from __future__ import annotations

import math
from collections import deque

import numpy as np
from rich.console import RenderableType
from rich.text import Text

from fomu.visualization.base import BaseVisualizer, VisualizerRegistry


@VisualizerRegistry.register("wave")
class WaveVisualizer(BaseVisualizer):
    """Scrolling wave visualization using block characters."""

    # Block characters for vertical levels
    BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(
        self,
        width: int = 60,
        height: int = 5,
        theme: str = "cyan",
    ) -> None:
        super().__init__(width, height, theme)
        self._phase = 0.0
        self._history: deque[float] = deque([0.0] * width, maxlen=width)

    def update(self, rms: float, bands: np.ndarray) -> None:
        super().update(rms, bands)
        self._history.append(rms)  # deque auto-pops from left when maxlen reached
        self._phase += 0.1

    def render(self) -> RenderableType:
        """Render the wave visualization."""
        lines = []

        for row in range(self.height):
            row_chars = []
            # Row 0 is top, row height-1 is bottom
            # threshold: what level this row represents (1.0 at top, 0.0 at bottom)
            threshold = 1.0 - (row / (self.height - 1)) if self.height > 1 else 0.5

            for col in range(self.width):
                amp = self._history[col] if col < len(self._history) else 0.0

                # Add sine wave modulation
                phase = self._phase + col * 0.15
                wave_mod = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(phase))
                level = amp * wave_mod

                if level >= threshold:
                    row_chars.append("█")
                elif level >= threshold - 0.15:
                    # Partial block
                    partial = (level - (threshold - 0.15)) / 0.15
                    idx = int(partial * (len(self.BLOCKS) - 1))
                    idx = max(0, min(len(self.BLOCKS) - 1, idx))
                    row_chars.append(self.BLOCKS[idx])
                else:
                    row_chars.append(" ")

            lines.append("".join(row_chars))

        # Apply color
        wave_text = "\n".join(lines)
        return Text(wave_text, style=self.primary_color)


@VisualizerRegistry.register("wave-simple")
class SimpleWaveVisualizer(BaseVisualizer):
    """Single-line wave using block characters."""

    BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(
        self,
        width: int = 60,
        height: int = 1,
        theme: str = "cyan",
    ) -> None:
        super().__init__(width, height, theme)
        self._history: deque[float] = deque([0.0] * width, maxlen=width)

    def update(self, rms: float, bands: np.ndarray) -> None:
        super().update(rms, bands)
        self._history.append(rms)  # deque auto-pops from left when maxlen reached

    def render(self) -> RenderableType:
        """Render the simple wave."""
        chars = []
        for amp in self._history:
            idx = int(amp * (len(self.BLOCKS) - 1))
            idx = max(0, min(len(self.BLOCKS) - 1, idx))
            chars.append(self.BLOCKS[idx])

        return Text("".join(chars), style=self.primary_color)
