//! Track catalog with all Scott Buckley tracks metadata.

#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum TrackPool {
    CalmFocus,
    Atmospheric,
    GentleMovement,
}

#[derive(Debug, Clone)]
pub struct Track {
    pub name: &'static str,
    pub slug: &'static str,
    pub pool: TrackPool,
    pub download_url: &'static str,
}

impl Track {
    pub fn filename(&self) -> String {
        format!("{}.mp3", self.slug)
    }
}

pub static TRACK_CATALOG: &[Track] = &[
    // Pool: CalmFocus
    Track {
        name: "Permafrost",
        slug: "permafrost",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2022/08/Permafrost.mp3",
    },
    Track {
        name: "Petrichor",
        slug: "petrichor",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2019/05/sb_petrichor.mp3",
    },
    Track {
        name: "Borealis",
        slug: "borealis",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2019/09/sb_borealis.mp3",
    },
    Track {
        name: "She Moved Mountains",
        slug: "she-moved-mountains",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2014/07/sb_shemovedmountains.mp3",
    },
    Track {
        name: "Reverie",
        slug: "reverie",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2020/03/sb_reverie.mp3",
    },
    Track {
        name: "Cobalt",
        slug: "cobalt",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2017/11/sb_cobalt.mp3",
    },
    Track {
        name: "Life Is",
        slug: "life-is",
        pool: TrackPool::CalmFocus,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2017/10/sb_lifeis.mp3",
    },
    // Pool: Atmospheric
    Track {
        name: "Shadows and Dust",
        slug: "shadows-and-dust",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2023/11/ShadowsAndDust.mp3",
    },
    Track {
        name: "Decoherence",
        slug: "decoherence",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2022/03/sb_decoherence.mp3",
    },
    Track {
        name: "Aurora",
        slug: "aurora",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2021/10/Aurora.mp3",
    },
    Track {
        name: "Hymn to the Dawn",
        slug: "hymn-to-the-dawn",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2022/11/HymnToTheDawn.mp3",
    },
    Track {
        name: "Cirrus",
        slug: "cirrus",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2023/03/Cirrus.mp3",
    },
    Track {
        name: "Meanwhile",
        slug: "meanwhile",
        pool: TrackPool::Atmospheric,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2025/01/Meanwhile.mp3",
    },
    // Pool: GentleMovement
    Track {
        name: "Cicadas",
        slug: "cicadas",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2023/12/Cicadas.mp3",
    },
    Track {
        name: "Effervescence",
        slug: "effervescence",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2023/07/Effervescence.mp3",
    },
    Track {
        name: "Golden Hour",
        slug: "golden-hour",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2023/02/GoldenHour.mp3",
    },
    Track {
        name: "Castles in the Sky",
        slug: "castles-in-the-sky",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2021/11/sb_castlesinthesky.mp3",
    },
    Track {
        name: "First Snow",
        slug: "first-snow",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2022/12/FirstSnow.mp3",
    },
    Track {
        name: "Snowfall",
        slug: "snowfall",
        pool: TrackPool::GentleMovement,
        download_url: "https://www.scottbuckley.com.au/library/wp-content/uploads/2018/12/sb_snowfall.mp3",
    },
];

pub fn get_tracks_by_pools(pools: &[TrackPool]) -> Vec<&'static Track> {
    TRACK_CATALOG
        .iter()
        .filter(|t| pools.contains(&t.pool))
        .collect()
}
