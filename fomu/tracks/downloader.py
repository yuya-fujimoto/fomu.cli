"""Track downloader for fetching Scott Buckley tracks."""

from __future__ import annotations

import asyncio
import re
import threading
from pathlib import Path
from typing import Callable, Optional

import httpx
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, DownloadColumn

from fomu.config import get_tracks_dir
from fomu.tracks.catalog import Track, TRACK_CATALOG, TrackPool


class TrackDownloader:
    """Downloads tracks from Scott Buckley's website."""

    def __init__(self, tracks_dir: Path | None = None) -> None:
        """Initialize the downloader.

        Args:
            tracks_dir: Directory to store downloaded tracks
        """
        self.tracks_dir = tracks_dir or get_tracks_dir()
        self.tracks_dir.mkdir(parents=True, exist_ok=True)
        self._background_thread: threading.Thread | None = None
        self._stop_background = False

        # Progress tracking for background downloads
        self._current_track_name: str | None = None
        self._download_progress: float = 0.0  # 0.0 to 1.0
        self._progress_lock = threading.Lock()

    def get_track_path(self, track: Track) -> Path:
        """Get the local path for a track."""
        return self.tracks_dir / track.filename

    def get_download_progress(self) -> tuple[str | None, float]:
        """Get current background download progress.

        Returns:
            Tuple of (track_name, progress_0_to_1) or (None, 0) if not downloading
        """
        with self._progress_lock:
            return (self._current_track_name, self._download_progress)

    def _set_download_progress(self, track_name: str | None, progress: float) -> None:
        """Update download progress (thread-safe)."""
        with self._progress_lock:
            self._current_track_name = track_name
            self._download_progress = progress

    def is_downloaded(self, track: Track) -> bool:
        """Check if a track is already downloaded."""
        path = self.get_track_path(track)
        return path.exists() and path.stat().st_size > 0

    def get_missing_tracks(self, pools: list[TrackPool] | None = None) -> list[Track]:
        """Get list of tracks that need to be downloaded.

        Args:
            pools: Optional list of pools to filter by
        """
        tracks = TRACK_CATALOG
        if pools:
            tracks = [t for t in tracks if t.pool in pools]
        return [t for t in tracks if not self.is_downloaded(t)]

    def get_available_tracks(self, pools: list[TrackPool] | None = None) -> list[Track]:
        """Get list of tracks that are downloaded.

        Args:
            pools: Optional list of pools to filter by
        """
        tracks = TRACK_CATALOG
        if pools:
            tracks = [t for t in tracks if t.pool in pools]
        return [t for t in tracks if self.is_downloaded(t)]

    async def _find_download_url(self, track: Track, client: httpx.AsyncClient) -> str | None:
        """Find the actual download URL from the track page."""
        try:
            response = await client.get(track.url, follow_redirects=True)
            response.raise_for_status()

            html = response.text

            patterns = [
                rf'href="([^"]*{re.escape(track.slug)}[^"]*\.mp3)"',
                r'href="([^"]*download[^"]*\.mp3)"',
                r'href="([^"]*\.mp3)"',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    url = match.group(1)
                    if url.startswith("/"):
                        url = f"https://www.scottbuckley.com.au{url}"
                    elif not url.startswith("http"):
                        url = f"{track.url}{url}"
                    return url

            return None
        except Exception:
            return None

    async def download_track(
        self,
        track: Track,
        client: httpx.AsyncClient,
        progress: Progress | None = None,
        task_id: int | None = None,
    ) -> bool:
        """Download a single track.

        Args:
            track: Track to download
            client: HTTP client
            progress: Rich progress bar
            task_id: Progress task ID

        Returns:
            True if successful
        """
        if self.is_downloaded(track):
            return True

        try:
            download_url = await self._find_download_url(track, client)
            if not download_url:
                download_url = f"https://www.scottbuckley.com.au/library/{track.slug}/{track.slug}.mp3"

            async with client.stream("GET", download_url, follow_redirects=True) as response:
                if response.status_code != 200:
                    return False

                total = int(response.headers.get("content-length", 0))

                if progress and task_id is not None:
                    progress.update(task_id, total=total)

                path = self.get_track_path(track)
                with open(path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        if progress and task_id is not None:
                            progress.update(task_id, advance=len(chunk))

            return True
        except Exception:
            return False

    async def download_one_track(
        self,
        pools: list[TrackPool] | None = None,
    ) -> Track | None:
        """Download a single track to get started quickly.

        Args:
            pools: Optional pools to prioritize

        Returns:
            The downloaded track, or None if failed
        """
        missing = self.get_missing_tracks(pools)
        if not missing:
            # Already have tracks
            available = self.get_available_tracks(pools)
            return available[0] if available else None

        track = missing[0]

        async with httpx.AsyncClient(timeout=120.0) as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
                transient=True,  # Auto-clear when done
            ) as progress:
                task_id = progress.add_task(
                    f"[cyan]Downloading {track.name}...",
                    total=None,
                )

                if await self.download_track(track, client, progress, task_id):
                    return track
                else:
                    return None

    def download_one_track_sync(
        self,
        pools: list[TrackPool] | None = None,
    ) -> Track | None:
        """Synchronous wrapper for download_one_track."""
        return asyncio.run(self.download_one_track(pools))

    async def _download_track_with_progress(
        self,
        track: Track,
        client: httpx.AsyncClient,
    ) -> bool:
        """Download a track while updating internal progress tracking."""
        if self.is_downloaded(track):
            return True

        self._set_download_progress(track.name, 0.0)

        try:
            download_url = await self._find_download_url(track, client)
            if not download_url:
                download_url = f"https://www.scottbuckley.com.au/library/{track.slug}/{track.slug}.mp3"

            async with client.stream("GET", download_url, follow_redirects=True) as response:
                if response.status_code != 200:
                    self._set_download_progress(None, 0.0)
                    return False

                total = int(response.headers.get("content-length", 0))
                downloaded = 0

                path = self.get_track_path(track)
                with open(path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            self._set_download_progress(track.name, downloaded / total)

            self._set_download_progress(None, 0.0)
            return True
        except Exception:
            self._set_download_progress(None, 0.0)
            return False

    async def _download_remaining_async(
        self,
        pools: list[TrackPool] | None = None,
        on_complete: Callable[[Track], None] | None = None,
    ) -> None:
        """Download remaining tracks (for background use)."""
        missing = self.get_missing_tracks(pools)
        if not missing:
            return

        async with httpx.AsyncClient(timeout=120.0) as client:
            for track in missing:
                if self._stop_background:
                    break
                if await self._download_track_with_progress(track, client):
                    if on_complete:
                        on_complete(track)

    def start_background_download(
        self,
        pools: list[TrackPool] | None = None,
        on_complete: Callable[[Track], None] | None = None,
    ) -> None:
        """Start downloading remaining tracks in background.

        Args:
            pools: Optional pools to prioritize
            on_complete: Callback when a track finishes downloading
        """
        if self._background_thread and self._background_thread.is_alive():
            return  # Already running

        self._stop_background = False

        def run_downloads():
            asyncio.run(self._download_remaining_async(pools, on_complete))

        self._background_thread = threading.Thread(target=run_downloads, daemon=True)
        self._background_thread.start()

    def stop_background_download(self) -> None:
        """Stop background downloading."""
        self._stop_background = True
        if self._background_thread:
            self._background_thread.join(timeout=1.0)

    async def download_all_missing(
        self,
        on_progress: Callable[[str, int, int], None] | None = None,
    ) -> tuple[int, int]:
        """Download all missing tracks with progress display.

        Args:
            on_progress: Callback(track_name, current, total)

        Returns:
            Tuple of (successful, failed) counts
        """
        missing = self.get_missing_tracks()
        if not missing:
            return (0, 0)

        successful = 0
        failed = 0

        async with httpx.AsyncClient(timeout=120.0) as client:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                DownloadColumn(),
            ) as progress:
                for i, track in enumerate(missing):
                    task_id = progress.add_task(
                        f"[cyan]Downloading {track.name}...",
                        total=None,
                    )

                    if on_progress:
                        on_progress(track.name, i + 1, len(missing))

                    if await self.download_track(track, client, progress, task_id):
                        successful += 1
                        progress.update(task_id, description=f"[green]Downloaded {track.name}")
                    else:
                        failed += 1
                        progress.update(task_id, description=f"[red]Failed: {track.name}")

                    progress.remove_task(task_id)

        return (successful, failed)

    def download_all_missing_sync(self) -> tuple[int, int]:
        """Synchronous wrapper for download_all_missing."""
        return asyncio.run(self.download_all_missing())
