"""Minimal single-line visualization."""

import numpy as np
from rich.console import RenderableType
from rich.text import Text

from fomu.visualization.base import BaseVisualizer, VisualizerRegistry


@VisualizerRegistry.register("minimal")
class MinimalVisualizer(BaseVisualizer):
    """Minimal single-line visualization with level meter."""

    # Block gradient characters
    BLOCKS = "░▒▓█"

    def __init__(
        self,
        width: int = 20,
        height: int = 1,
        theme: str = "cyan",
    ) -> None:
        super().__init__(width, height, theme)
        self._track_name = ""
        self._preset_name = ""
        self._elapsed_time = "00:00:00"

    def set_info(
        self,
        track_name: str = "",
        preset_name: str = "",
        elapsed_time: str = "",
    ) -> None:
        """Set display info.

        Args:
            track_name: Current track name
            preset_name: Current preset name
            elapsed_time: Elapsed time string
        """
        self._track_name = track_name
        self._preset_name = preset_name
        if elapsed_time:
            self._elapsed_time = elapsed_time

    def render(self) -> RenderableType:
        """Render the minimal visualization.

        Format: ♫ ░░▒▒▓▓████▓▓▒▒░░  Track Name — Artist  [preset] 00:00:00
        """
        # Build level meter (symmetric around center)
        meter_width = self.width
        half_width = meter_width // 2

        # Map RMS to meter level
        level = int(self._rms * half_width)

        meter_chars = []
        for i in range(half_width):
            # Distance from center
            dist_from_edge = half_width - i - 1

            if dist_from_edge < level:
                # Determine block type based on position
                intensity = (level - dist_from_edge) / max(1, level)
                block_idx = int(intensity * (len(self.BLOCKS) - 1))
                block_idx = max(0, min(len(self.BLOCKS) - 1, block_idx))
                meter_chars.append(self.BLOCKS[block_idx])
            else:
                meter_chars.append(self.BLOCKS[0])  # Empty

        # Mirror for right side
        left_half = "".join(meter_chars)
        right_half = "".join(reversed(meter_chars))
        meter = left_half + right_half

        return Text(meter, style=self.primary_color)

    def render_full(self) -> RenderableType:
        """Render full info line with track name and time.

        Format: ♫ ░░▒▒▓▓████▓▓▒▒░░  Track Name  [preset] 00:00:00
        """
        # Build meter
        meter = self.render()

        # Build full line
        parts = []
        parts.append(("♫ ", self.primary_color))
        parts.append((str(meter.plain), self.primary_color))
        parts.append(("  ", None))

        if self._track_name:
            parts.append((self._track_name, "white bold"))
            parts.append(("  ", None))

        if self._preset_name:
            parts.append((f"[{self._preset_name}]", self.secondary_color))
            parts.append((" ", None))

        parts.append((self._elapsed_time, "dim"))

        # Build Text object
        text = Text()
        for content, style in parts:
            if style:
                text.append(content, style=style)
            else:
                text.append(content)

        return text


@VisualizerRegistry.register("none")
class NoVisualizer(BaseVisualizer):
    """No visualization - just empty space."""

    def __init__(self, **kwargs) -> None:
        super().__init__(width=1, height=1, **kwargs)

    def render(self) -> RenderableType:
        return Text("")
