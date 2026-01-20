"""FocusMusic CLI - Command line interface."""

from __future__ import annotations

import os
import sys
import threading
import time
from datetime import timedelta

import click
import numpy as np
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

# Suppress audio library warnings (e.g., mpg123 Xing warnings)
os.environ["MPG123_QUIET"] = "1"

from fomu import __version__
from fomu.config import (
    COLOR_THEMES,
    DEFAULT_PRESET,
    DEFAULT_THEME,
    DEFAULT_VIZ_MODE,
    VOLUME_STEP,
)
from fomu.engine.player import AudioPlayer
from fomu.presets import get_preset, get_preset_names, get_all_presets
from fomu.tracks.catalog import Track
from fomu.tracks.downloader import TrackDownloader
from fomu.tracks.loader import TrackLoader
from fomu.visualization.base import VisualizerRegistry
from fomu.visualization.wave import WaveVisualizer, SimpleWaveVisualizer
from fomu.visualization.bars import BarsVisualizer, CompactBarsVisualizer
from fomu.visualization.minimal import MinimalVisualizer, NoVisualizer


console = Console()


class FomuApp:
    """Main application controller."""

    def __init__(
        self,
        preset_name: str = DEFAULT_PRESET,
        viz_mode: str = DEFAULT_VIZ_MODE,
        theme: str = DEFAULT_THEME,
    ) -> None:
        self.preset = get_preset(preset_name) or get_preset(DEFAULT_PRESET)
        self.viz_mode = viz_mode
        self.theme = theme

        self.player = AudioPlayer()
        self.loader = TrackLoader()
        self.downloader = TrackDownloader()

        self._current_track: Track | None = None
        self._playlist_iter = None
        self._running = False
        self._start_time = 0.0

        # Preset selection state
        self._selecting_preset = False
        self._all_presets = get_all_presets()
        self._selected_preset_idx = 0
        self._preset_switch_pending = None  # Name of preset waiting for tracks to download
        for i, p in enumerate(self._all_presets):
            if p.name == self.preset.name:
                self._selected_preset_idx = i
                break

        # Visualization state
        self._visualizer = self._create_visualizer()

        # Terminal focus state (for pausing UI when not visible)
        self._terminal_focused = True

        # Pre-cached static UI text elements (reduce allocations in render loop)
        self._cached_attribution = self._create_attribution_text()
        self._cached_controls_template = self._create_controls_template()


    def _create_visualizer(self):
        """Create visualizer based on mode."""
        viz_cls = VisualizerRegistry.get(self.viz_mode)
        if viz_cls:
            return viz_cls(theme=self.theme)
        return WaveVisualizer(theme=self.theme)

    def _create_attribution_text(self) -> Text:
        """Create cached attribution text (static, never changes)."""
        attribution = Text()
        attribution.append("  Music by Scott Buckley (CC-BY 4.0)", style="dim")
        attribution.append(" — ", style="dim")
        attribution.append(
            "support him",
            style="dim underline link https://www.scottbuckley.com.au/library/donate/",
        )
        return attribution

    def _create_controls_template(self) -> Text:
        """Create cached controls template (static parts only)."""
        controls = Text()
        controls.append("  │  ", style="dim")
        controls.append("[space]", style="bold")
        controls.append(" pause  ", style="dim")
        controls.append("[+/-]", style="bold")
        controls.append(" vol  ", style="dim")
        controls.append("[n]", style="bold")
        controls.append(" skip  ", style="dim")
        controls.append("[p]", style="bold")
        controls.append(" preset  ", style="dim")
        controls.append("[v]", style="bold")
        controls.append(" viz  ", style="dim")
        controls.append("[q]", style="bold")
        controls.append(" quit", style="dim")
        return controls

    def cycle_visualization(self) -> str:
        """Cycle to next visualization mode."""
        modes = VisualizerRegistry.get_names()
        if not modes:
            return self.viz_mode

        try:
            current_idx = modes.index(self.viz_mode)
            next_idx = (current_idx + 1) % len(modes)
        except ValueError:
            next_idx = 0

        self.viz_mode = modes[next_idx]
        self._visualizer = self._create_visualizer()
        return self.viz_mode

    def toggle_preset_selection(self) -> None:
        """Toggle preset selection mode."""
        if self._selecting_preset:
            # Cancel selection
            self._selecting_preset = False
            # Reset to current preset
            for i, p in enumerate(self._all_presets):
                if p.name == self.preset.name:
                    self._selected_preset_idx = i
                    break
        else:
            # Enter selection mode
            self._selecting_preset = True

    def preset_selection_next(self) -> None:
        """Move to next preset in selection."""
        self._selected_preset_idx = (self._selected_preset_idx + 1) % len(self._all_presets)

    def preset_selection_prev(self) -> None:
        """Move to previous preset in selection."""
        self._selected_preset_idx = (self._selected_preset_idx - 1) % len(self._all_presets)

    def confirm_preset_selection(self) -> str | None:
        """Confirm the selected preset and apply it.

        Returns:
            Preset name if switched, None if no tracks available.
        """
        self._selecting_preset = False
        new_preset = self._all_presets[self._selected_preset_idx]

        if new_preset.name == self.preset.name:
            return self.preset.name  # No change

        # Check if tracks are available for this preset
        available = self.loader.get_available_tracks(new_preset.pools)
        if not available:
            # No tracks downloaded for this preset yet
            # Start background download and show message
            self.downloader.start_background_download(
                pools=new_preset.pools,
                on_complete=self._on_track_downloaded,
            )
            self._preset_switch_pending = new_preset.name
            return None

        self.preset = new_preset
        self._preset_switch_pending = None

        # Restart playlist with new preset's pools
        self._playlist_iter = self.loader.streaming_playlist_iterator(self.preset.pools, shuffle=True)

        # Load a track from the new preset
        self._load_next_track()

        # Start background download for new preset's tracks
        self.downloader.start_background_download(
            pools=self.preset.pools,
            on_complete=self._on_track_downloaded,
        )

        return self.preset.name

    def volume_up(self) -> float:
        """Increase volume."""
        self.player.volume = min(1.0, self.player.volume + VOLUME_STEP)
        return self.player.volume

    def volume_down(self) -> float:
        """Decrease volume."""
        self.player.volume = max(0.0, self.player.volume - VOLUME_STEP)
        return self.player.volume

    def toggle_pause(self) -> bool:
        """Toggle pause. Returns True if now playing."""
        return self.player.toggle_pause()

    def skip_track(self) -> None:
        """Skip to next track."""
        self._load_next_track()

    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS."""
        td = timedelta(seconds=int(seconds))
        return str(td)

    def _get_elapsed_time(self) -> str:
        """Get elapsed time since start."""
        if self._start_time == 0:
            return "00:00:00"
        elapsed = time.time() - self._start_time
        return self._format_time(elapsed)

    def _render_ui(self) -> Panel:
        """Render the full UI."""
        # Get analysis from player (done in UI thread, not audio callback)
        rms, bands = self.player.get_analysis()

        # Update visualizer
        self._visualizer.update(rms, bands)

        # Build UI components
        track_name = self._current_track.name if self._current_track else "Loading..."
        status_icon = "▶" if self.player.is_playing else "⏸"
        volume_pct = int(self.player.volume * 100)

        # Header
        header = Text()
        header.append("  Fomu", style="bold white")
        header.append(f"  [{self.preset.name}]", style=f"{self._visualizer.primary_color}")
        if self._preset_switch_pending:
            track_name, progress = self.downloader.get_download_progress()
            if track_name and progress > 0:
                pct = int(progress * 100)
                header.append(f"  → [{self._preset_switch_pending}] {pct}%", style="yellow")
            else:
                header.append(f"  → [{self._preset_switch_pending}] downloading...", style="yellow")

        # Visualization
        viz_content = self._visualizer.render()

        # Track info
        track_info = Text()
        track_info.append(f"  {status_icon} ", style="bold")
        track_info.append(f"{track_name}", style="white")
        track_info.append(" — Scott Buckley", style="dim")
        track_info.append(f"  {self._get_elapsed_time()}", style="dim")

        # Controls or preset selection
        if self._selecting_preset:
            controls = Text()
            controls.append("  Select preset: ", style="bold")
            for i, preset in enumerate(self._all_presets):
                if i > 0:
                    controls.append(" ", style="dim")
                has_tracks = len(self.loader.get_available_tracks(preset.pools)) > 0
                if i == self._selected_preset_idx:
                    controls.append(f"[{preset.name}]", style="bold cyan reverse")
                elif has_tracks:
                    controls.append(preset.name, style="white")
                else:
                    controls.append(preset.name, style="dim italic")
            controls.append("\n  ", style="")
            controls.append("[j/k]", style="bold")
            controls.append(" navigate  ", style="dim")
            controls.append("[enter]", style="bold")
            controls.append(" select  ", style="dim")
            controls.append("[esc/q]", style="bold")
            controls.append(" cancel", style="dim")
        else:
            # Use cached template for static parts, only create dynamic volume text
            controls = Text()
            controls.append(f"  Vol: {volume_pct}%", style="cyan")
            controls.append_text(self._cached_controls_template)

        # Use cached attribution (completely static)
        attribution = self._cached_attribution

        # Combine into layout
        content = Text()
        content.append("\n")
        content.append_text(header)
        content.append("\n\n")
        content.append_text(viz_content)
        content.append("\n\n")
        content.append_text(track_info)
        content.append("\n")
        content.append_text(controls)
        content.append("\n\n")
        content.append_text(attribution)
        content.append("\n")

        return Panel(
            content,
            border_style=self._visualizer.primary_color,
            padding=(0, 1),
        )

    def _load_next_track(self) -> bool:
        """Load the next track from playlist using streaming."""
        if self._playlist_iter is None:
            return False

        try:
            track, stream = next(self._playlist_iter)
            self._current_track = track
            self.player.set_streaming_source(stream)
            return True
        except StopIteration:
            return False

    def _ensure_one_track(self) -> bool:
        """Ensure at least one track is available, downloading if needed.

        Returns:
            True if at least one track is available
        """
        # Check if we already have tracks for this preset
        available = self.loader.get_available_tracks(self.preset.pools)
        if available:
            return True

        # No tracks available - download one to get started
        missing = self.downloader.get_missing_tracks(self.preset.pools)
        if not missing:
            return False

        console.print("[dim]First run: downloading a track (only happens once)[/dim]")

        # Download just one track (progress bar is transient, auto-clears)
        track = self.downloader.download_one_track_sync(self.preset.pools)
        return track is not None

    def _on_track_downloaded(self, track: Track) -> None:
        """Callback when a background track download completes."""
        # Check if we're waiting to switch to a preset
        if self._preset_switch_pending:
            pending_preset = get_preset(self._preset_switch_pending)
            if pending_preset and track.pool in [p for p in pending_preset.pools]:
                # A track for the pending preset is now available, switch to it
                self.preset = pending_preset
                self._preset_switch_pending = None

                # Update selected index
                for i, p in enumerate(self._all_presets):
                    if p.name == self.preset.name:
                        self._selected_preset_idx = i
                        break

                # Restart playlist with new preset's pools
                self._playlist_iter = self.loader.streaming_playlist_iterator(self.preset.pools, shuffle=True)

                # Load a track from the new preset
                self._load_next_track()

    def run(self) -> None:
        """Run the main application loop."""
        # Ensure at least one track is available
        if not self._ensure_one_track():
            console.print("[red]No tracks available. Please check your internet connection.[/red]")
            return

        # Start background download of remaining tracks
        self.downloader.start_background_download(
            pools=self.preset.pools,
            on_complete=self._on_track_downloaded,
        )

        # Create playlist with available tracks
        self._playlist_iter = self.loader.streaming_playlist_iterator(self.preset.pools, shuffle=True)

        # Load first track
        if not self._load_next_track():
            console.print("[red]Failed to load track.[/red]")
            return

        # Start playback
        self.player.start()
        self._running = True
        self._start_time = time.time()

        # Start keyboard listener thread
        keyboard_thread = threading.Thread(target=self._keyboard_listener, daemon=True)
        keyboard_thread.start()

        # Main UI loop
        try:
            # Enable terminal focus reporting (supported by iTerm2, Kitty, etc.)
            sys.stdout.write("\x1b[?1004h")
            sys.stdout.flush()

            with Live(
                self._render_ui(),
                console=console,
                refresh_per_second=15,
                screen=True,  # Use alternate screen buffer for clean exit
            ) as live:
                while self._running:
                    # Only update UI if terminal is focused
                    if self._terminal_focused:
                        live.update(self._render_ui())

                    # Check if track ended (streaming or progress-based)
                    if self.player.is_stream_finished() or self.player.progress >= 0.99:
                        if not self._load_next_track():
                            # Restart playlist
                            self._playlist_iter = self.loader.streaming_playlist_iterator(
                                self.preset.pools, shuffle=True
                            )
                            self._load_next_track()

                    time.sleep(1 / 15)

        except KeyboardInterrupt:
            pass
        finally:
            # Disable terminal focus reporting
            sys.stdout.write("\x1b[?1004l")
            sys.stdout.flush()

            self.downloader.stop_background_download()
            self.player.stop()

    def _keyboard_listener(self) -> None:
        """Listen for keyboard input (runs in separate thread)."""
        try:
            import select
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)

            try:
                tty.setcbreak(fd)

                while self._running:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        ch = sys.stdin.read(1)

                        if ch == "q" or ch == "\x03":  # q or Ctrl+C
                            if self._selecting_preset:
                                self._selecting_preset = False
                            else:
                                self._running = False
                                break
                        elif ch == "\x1b":  # Escape sequence (arrow keys) or just Escape
                            # Read the rest of the escape sequence (arrow keys: ESC [ A/B/C/D)
                            seq = ""
                            for _ in range(2):  # Arrow keys need 2 more chars: [ and A/B/C/D
                                if select.select([sys.stdin], [], [], 0.05)[0]:
                                    seq += sys.stdin.read(1)
                                else:
                                    break
                            if seq == "":  # Just Escape key
                                if self._selecting_preset:
                                    self.toggle_preset_selection()
                            elif seq == "[I":  # Terminal gained focus
                                self._terminal_focused = True
                            elif seq == "[O":  # Terminal lost focus
                                self._terminal_focused = False
                            elif seq == "[A":  # Up arrow
                                if self._selecting_preset:
                                    self.preset_selection_prev()
                                else:
                                    self.volume_up()
                            elif seq == "[B":  # Down arrow
                                if self._selecting_preset:
                                    self.preset_selection_next()
                                else:
                                    self.volume_down()
                        elif ch == "\r" or ch == "\n":  # Enter
                            if self._selecting_preset:
                                self.confirm_preset_selection()
                        elif self._selecting_preset:
                            # In selection mode: p/k = next (right), j = prev (left)
                            if ch == "p" or ch == "k":
                                self.preset_selection_next()
                            elif ch == "j":
                                self.preset_selection_prev()
                        else:
                            # Normal mode
                            if ch == " ":
                                self.toggle_pause()
                            elif ch == "v":
                                self.cycle_visualization()
                            elif ch == "p":
                                self.toggle_preset_selection()
                            elif ch == "n":
                                self.skip_track()
                            elif ch in ("+", "=", "]"):  # Volume up
                                self.volume_up()
                            elif ch in ("-", "_", "["):  # Volume down
                                self.volume_down()
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

        except Exception:
            pass


@click.command()
@click.option(
    "--preset",
    "-p",
    type=click.Choice(get_preset_names()),
    default=DEFAULT_PRESET,
    help="Music pool preset",
)
@click.option(
    "--viz",
    "-v",
    type=click.Choice(["wave", "bars", "minimal", "none"]),
    default=DEFAULT_VIZ_MODE,
    help="Visualization mode",
)
@click.option(
    "--theme",
    "-t",
    type=click.Choice(list(COLOR_THEMES.keys())),
    default=DEFAULT_THEME,
    help="Color theme",
)
@click.option(
    "--volume",
    type=click.FloatRange(0.0, 1.0),
    default=0.8,
    help="Initial volume (0.0-1.0)",
)
@click.option(
    "--clear-tracks",
    is_flag=True,
    help="Delete all downloaded tracks and exit",
)
@click.version_option(version=__version__)
def main(preset: str, viz: str, theme: str, volume: float, clear_tracks: bool) -> None:
    """Fomu - Ambient music for focus.

    Play curated ambient music from Scott Buckley's Creative Commons library.

    \b
    Interactive Controls:
      Space     Pause/Resume
      +/-       Volume up/down
      n         Skip track
      p         Select preset (j/k to navigate, Enter to confirm)
      v         Cycle visualization
      q         Quit
    """
    # Handle --clear-tracks flag
    if clear_tracks:
        from fomu.config import get_tracks_dir
        tracks_dir = get_tracks_dir()
        if tracks_dir.exists():
            count = 0
            for f in tracks_dir.glob("*.mp3"):
                f.unlink()
                count += 1
            if count > 0:
                console.print(f"[green]Deleted {count} track(s)[/green]")
            else:
                console.print("[yellow]No tracks to delete[/yellow]")
        else:
            console.print("[yellow]Tracks directory does not exist[/yellow]")
        return

    app = FomuApp(preset_name=preset, viz_mode=viz, theme=theme)
    app.player.volume = volume
    app.run()


if __name__ == "__main__":
    main()
