//! Track loading and playlist management.

use std::path::PathBuf;

use directories::ProjectDirs;
use rand::seq::SliceRandom;

use super::catalog::{get_tracks_by_pools, Track, TrackPool, TRACK_CATALOG};

pub fn get_tracks_dir() -> PathBuf {
    if let Some(proj_dirs) = ProjectDirs::from("", "", "fomu") {
        let tracks_dir = proj_dirs.data_dir().join("tracks").join("scott-buckley");
        std::fs::create_dir_all(&tracks_dir).ok();
        tracks_dir
    } else {
        let home = std::env::var("HOME")
            .map(PathBuf::from)
            .unwrap_or_else(|_| PathBuf::from("."));
        let tracks_dir = home.join(".fomu").join("tracks").join("scott-buckley");
        std::fs::create_dir_all(&tracks_dir).ok();
        tracks_dir
    }
}

pub struct TrackLoader {
    tracks_dir: PathBuf,
}

impl TrackLoader {
    pub fn new() -> Self {
        Self {
            tracks_dir: get_tracks_dir(),
        }
    }

    pub fn get_track_path(&self, track: &Track) -> PathBuf {
        self.tracks_dir.join(track.filename())
    }

    pub fn track_exists(&self, track: &Track) -> bool {
        self.get_track_path(track).exists()
    }

    pub fn get_available_tracks_from_pools(&self, pools: &[TrackPool]) -> Vec<&'static Track> {
        TRACK_CATALOG
            .iter()
            .filter(|t| pools.contains(&t.pool) && self.track_exists(t))
            .collect()
    }

    pub fn get_missing_tracks_from_pools(&self, pools: &[TrackPool]) -> Vec<&'static Track> {
        get_tracks_by_pools(pools)
            .into_iter()
            .filter(|t| !self.track_exists(t))
            .collect()
    }

    pub fn create_playlist(&self, pools: &[TrackPool], shuffle: bool) -> Vec<&'static Track> {
        let mut tracks = self.get_available_tracks_from_pools(pools);
        if shuffle {
            let mut rng = rand::thread_rng();
            tracks.shuffle(&mut rng);
        }
        tracks
    }
}

impl Default for TrackLoader {
    fn default() -> Self {
        Self::new()
    }
}
