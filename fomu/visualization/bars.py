"""Frequency bars visualization."""

import numpy as np
from rich.console import RenderableType
from rich.text import Text

from fomu.visualization.base import BaseVisualizer, VisualizerRegistry


@VisualizerRegistry.register("bars")
class BarsVisualizer(BaseVisualizer):
    """Frequency spectrum bars visualization."""

    BLOCKS = " ▁▂▃▄▅▆▇█"
    FULL_BLOCK = "█"

    def __init__(
        self,
        width: int = 60,
        height: int = 8,
        num_bars: int = 16,
        theme: str = "cyan",
    ) -> None:
        super().__init__(width, height, theme)
        self.num_bars = num_bars
        self._bar_width = max(1, (width - num_bars + 1) // num_bars)
        self._gap = 1

    def render(self) -> RenderableType:
        """Render the frequency bars."""
        if self._bands is None or len(self._bands) == 0:
            # Empty state
            return Text(" " * self.width)

        lines = []

        # Resample bands to match num_bars if needed
        bands = self._bands
        if len(bands) != self.num_bars:
            indices = np.linspace(0, len(bands) - 1, self.num_bars)
            bands = np.interp(indices, np.arange(len(bands)), bands)

        for row in range(self.height):
            line_parts = []
            # Threshold for this row (bottom = 0, top = 1)
            threshold = 1.0 - (row / self.height)

            for i, level in enumerate(bands):
                # Determine bar character for this cell
                if level >= threshold:
                    # Full block
                    char = self.FULL_BLOCK
                    # Gradient color based on height
                    if row < self.height // 3:
                        color = self.primary_color
                    elif row < 2 * self.height // 3:
                        color = self.secondary_color
                    else:
                        color = self.primary_color
                elif level >= threshold - (1.0 / self.height):
                    # Partial block at the top of the bar
                    partial_idx = int((level - threshold + (1.0 / self.height)) * self.height * (len(self.BLOCKS) - 1))
                    partial_idx = max(0, min(len(self.BLOCKS) - 1, partial_idx))
                    char = self.BLOCKS[partial_idx]
                    color = self.secondary_color
                else:
                    char = " "
                    color = None

                # Draw bar with width
                bar_str = char * self._bar_width

                if color:
                    line_parts.append(f"[{color}]{bar_str}[/{color}]")
                else:
                    line_parts.append(bar_str)

                # Add gap between bars (except last)
                if i < len(bands) - 1:
                    line_parts.append(" " * self._gap)

            lines.append("".join(line_parts))

        return Text.from_markup("\n".join(lines))


@VisualizerRegistry.register("bars-compact")
class CompactBarsVisualizer(BaseVisualizer):
    """Compact single-line frequency bars."""

    BLOCKS = " ▁▂▃▄▅▆▇█"

    def __init__(
        self,
        width: int = 60,
        height: int = 1,
        num_bars: int = 32,
        theme: str = "cyan",
    ) -> None:
        super().__init__(width, height, theme)
        self.num_bars = min(num_bars, width)

    def render(self) -> RenderableType:
        """Render compact bars."""
        if self._bands is None or len(self._bands) == 0:
            return Text(" " * self.num_bars)

        # Resample bands
        bands = self._bands
        if len(bands) != self.num_bars:
            indices = np.linspace(0, len(bands) - 1, self.num_bars)
            bands = np.interp(indices, np.arange(len(bands)), bands)

        chars = []
        for level in bands:
            idx = int(level * (len(self.BLOCKS) - 1))
            idx = max(0, min(len(self.BLOCKS) - 1, idx))
            chars.append(self.BLOCKS[idx])

        return Text("".join(chars), style=self.primary_color)
