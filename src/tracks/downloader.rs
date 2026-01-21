//! Track downloading from scottbuckley.com.au

use std::fs::File;
use std::io::Write;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use std::thread;

use anyhow::{Context, Result};

use super::catalog::{Track, TrackPool};
use super::loader::{get_tracks_dir, TrackLoader};

#[derive(Clone, Default)]
pub struct DownloadProgress {
    pub track_name: String,
    pub progress: f32,
    pub completed: bool,
}

pub struct TrackDownloader {
    tracks_dir: PathBuf,
    loader: TrackLoader,
    should_stop: Arc<AtomicBool>,
    progress: Arc<Mutex<DownloadProgress>>,
    thread_handle: Option<thread::JoinHandle<()>>,
}

impl TrackDownloader {
    pub fn new() -> Self {
        Self {
            tracks_dir: get_tracks_dir(),
            loader: TrackLoader::new(),
            should_stop: Arc::new(AtomicBool::new(false)),
            progress: Arc::new(Mutex::new(DownloadProgress::default())),
            thread_handle: None,
        }
    }

    pub fn download_track(&self, track: &Track) -> Result<PathBuf> {
        let path = self.tracks_dir.join(track.filename());
        if path.exists() {
            return Ok(path);
        }

        let url = track.download_url;
        let response = reqwest::blocking::get(url)
            .with_context(|| format!("Failed to fetch {}", url))?;

        if !response.status().is_success() {
            anyhow::bail!("HTTP error: {}", response.status());
        }

        let bytes = response.bytes().context("Failed to read response bytes")?;
        let mut file = File::create(&path)
            .with_context(|| format!("Failed to create file {:?}", path))?;
        file.write_all(&bytes).context("Failed to write file")?;

        Ok(path)
    }

    pub fn download_one_track(&self, pools: &[TrackPool]) -> Result<Option<&'static Track>> {
        let missing = self.loader.get_missing_tracks_from_pools(pools);
        if let Some(track) = missing.first() {
            self.download_track(track)?;
            Ok(Some(*track))
        } else {
            Ok(None)
        }
    }

    pub fn start_background_download(&mut self, pools: Vec<TrackPool>) {
        self.stop_background_download();

        let should_stop = Arc::new(AtomicBool::new(false));
        self.should_stop = Arc::clone(&should_stop);

        let progress = Arc::clone(&self.progress);
        let tracks_dir = self.tracks_dir.clone();

        let missing: Vec<Track> = self
            .loader
            .get_missing_tracks_from_pools(&pools)
            .into_iter()
            .cloned()
            .collect();

        if missing.is_empty() {
            return;
        }

        let handle = thread::spawn(move || {
            for track in missing {
                if should_stop.load(Ordering::Relaxed) {
                    break;
                }

                {
                    let mut prog = progress.lock().unwrap();
                    prog.track_name = track.name.to_string();
                    prog.progress = 0.0;
                    prog.completed = false;
                }

                let path = tracks_dir.join(track.filename());
                if !path.exists() {
                    if let Ok(response) = reqwest::blocking::get(track.download_url) {
                        if response.status().is_success() {
                            if let Ok(bytes) = response.bytes() {
                                if let Ok(mut file) = File::create(&path) {
                                    let _ = file.write_all(&bytes);
                                }
                            }
                        }
                    }
                }

                {
                    let mut prog = progress.lock().unwrap();
                    prog.progress = 1.0;
                    prog.completed = true;
                }

                thread::sleep(std::time::Duration::from_millis(100));
            }
        });

        self.thread_handle = Some(handle);
    }

    pub fn stop_background_download(&mut self) {
        self.should_stop.store(true, Ordering::SeqCst);
        if let Some(handle) = self.thread_handle.take() {
            // Wait with timeout - HTTP requests can block
            let start = std::time::Instant::now();
            while !handle.is_finished() {
                if start.elapsed() > std::time::Duration::from_millis(500) {
                    break;
                }
                thread::sleep(std::time::Duration::from_millis(10));
            }
            if handle.is_finished() {
                let _ = handle.join();
            }
        }
    }

    pub fn get_progress(&self) -> DownloadProgress {
        self.progress.lock().unwrap().clone()
    }
}

impl Default for TrackDownloader {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for TrackDownloader {
    fn drop(&mut self) {
        self.stop_background_download();
    }
}
