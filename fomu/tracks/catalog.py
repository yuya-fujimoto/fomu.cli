"""Track catalog with all Scott Buckley tracks metadata."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrackPool(Enum):
    """Track pool categories."""
    CALM_FOCUS = "calm-focus"
    ATMOSPHERIC = "atmospheric"
    GENTLE_MOVEMENT = "gentle-movement"


@dataclass
class Track:
    """Track metadata."""
    name: str
    slug: str
    pool: TrackPool
    url: str
    character: str
    duration: Optional[float] = None  # Will be set after loading

    @property
    def filename(self) -> str:
        """Get the expected filename for this track."""
        return f"{self.slug}.mp3"

    @property
    def download_url(self) -> str:
        """Get the direct download URL for the track."""
        # Scott Buckley's site structure: /library/track-name/ contains the mp3
        return f"{self.url}{self.slug}.mp3"


# All 19 Scott Buckley tracks from the spec
TRACK_CATALOG: list[Track] = [
    # Pool: calm-focus (for: deep, flow, relax)
    Track(
        name="Permafrost",
        slug="permafrost",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/permafrost/",
        character="Meditative strings, synth",
    ),
    Track(
        name="Petrichor",
        slug="petrichor",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/petrichor/",
        character="Ambient synth pads, piano",
    ),
    Track(
        name="Borealis",
        slug="borealis",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/borealis/",
        character="Contemplative, slow",
    ),
    Track(
        name="She Moved Mountains",
        slug="she-moved-mountains",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/she-moved-mountains/",
        character="Minimal piano",
    ),
    Track(
        name="Reverie",
        slug="reverie",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/reverie/",
        character="Dreamy piano, strings",
    ),
    Track(
        name="Cobalt",
        slug="cobalt",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/cobalt/",
        character="Ambient piano, synths",
    ),
    Track(
        name="Life Is",
        slug="life-is",
        pool=TrackPool.CALM_FOCUS,
        url="https://www.scottbuckley.com.au/library/life-is/",
        character="Reflective piano, pads",
    ),
    # Pool: atmospheric (for: focus, creative)
    Track(
        name="Shadows and Dust",
        slug="shadows-and-dust",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/shadows-and-dust/",
        character="Ethereal synth drones",
    ),
    Track(
        name="Decoherence",
        slug="decoherence",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/decoherence/",
        character="Haunting, morphing",
    ),
    Track(
        name="Aurora",
        slug="aurora",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/aurora/",
        character="Warm, lush ambient",
    ),
    Track(
        name="Hymn to the Dawn",
        slug="hymn-to-the-dawn",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/hymn-to-the-dawn/",
        character="Floating synths",
    ),
    Track(
        name="Cirrus",
        slug="cirrus",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/cirrus/",
        character="Meditative neoclassical",
    ),
    Track(
        name="Meanwhile",
        slug="meanwhile",
        pool=TrackPool.ATMOSPHERIC,
        url="https://www.scottbuckley.com.au/library/meanwhile/",
        character="Ethereal piano, liquid",
    ),
    # Pool: gentle-movement (for: morning, creative)
    Track(
        name="Cicadas",
        slug="cicadas",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/cicadas/",
        character="Piano, nature sounds",
    ),
    Track(
        name="Effervescence",
        slug="effervescence",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/effervescence/",
        character="Calm piano, glitchy",
    ),
    Track(
        name="Golden Hour",
        slug="golden-hour",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/golden-hour/",
        character="Warm vocals, strings",
    ),
    Track(
        name="Castles in the Sky",
        slug="castles-in-the-sky",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/castles-in-the-sky/",
        character="Dreamy piano, vibes",
    ),
    Track(
        name="First Snow",
        slug="first-snow",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/first-snow/",
        character="Gentle piano, clarinet",
    ),
    Track(
        name="Snowfall",
        slug="snowfall",
        pool=TrackPool.GENTLE_MOVEMENT,
        url="https://www.scottbuckley.com.au/library/snowfall/",
        character="Layered pianos",
    ),
]


class TrackCatalog:
    """Manager for track catalog."""

    def __init__(self) -> None:
        self._tracks = {track.slug: track for track in TRACK_CATALOG}

    def get_track(self, slug: str) -> Track | None:
        """Get a track by slug."""
        return self._tracks.get(slug)

    def get_tracks_by_pool(self, pool: TrackPool) -> list[Track]:
        """Get all tracks in a pool."""
        return [t for t in TRACK_CATALOG if t.pool == pool]

    def get_tracks_by_pools(self, pools: list[TrackPool]) -> list[Track]:
        """Get all tracks from multiple pools."""
        return [t for t in TRACK_CATALOG if t.pool in pools]

    def get_all_tracks(self) -> list[Track]:
        """Get all tracks."""
        return list(TRACK_CATALOG)

    @property
    def track_count(self) -> int:
        """Get total number of tracks."""
        return len(TRACK_CATALOG)
