//! Main application state and event loop.

use std::io;
use std::time::{Duration, Instant};

use anyhow::Result;
use crossterm::{
    event::{self, DisableMouseCapture, EnableMouseCapture, Event, KeyCode, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use ratatui::{backend::CrosstermBackend, Terminal};

use crate::audio::{AudioAnalyzer, AudioDecoder, AudioPlayer};
use crate::presets::{get_preset, Preset, PRESETS};
use crate::tracks::{DownloadProgress, Track, TrackDownloader, TrackLoader};
use crate::ui::visualizers::Visualizer;
use crate::ui::render::{render_ui, open_support_url};

/// Main application state.
pub struct App {
    /// Audio player
    player: AudioPlayer,
    /// Audio decoder
    decoder: AudioDecoder,
    /// Audio analyzer for visualization
    analyzer: AudioAnalyzer,
    /// Track loader
    loader: TrackLoader,
    /// Track downloader
    downloader: TrackDownloader,
    /// Current preset
    preset: &'static Preset,
    /// Current track
    current_track: Option<&'static Track>,
    /// Playlist of tracks
    playlist: Vec<&'static Track>,
    /// Current index in playlist
    playlist_index: usize,
    /// Visualizer
    visualizer: Visualizer,
    /// Whether app is running
    running: bool,
    /// Start time
    start_time: Instant,
    /// Preset selection state
    selecting_preset: bool,
    selected_preset_idx: usize,
    /// Pending preset switch (waiting for download)
    pending_preset: Option<String>,
}

impl App {
    /// Create a new application.
    pub fn new(preset_name: &str) -> Result<Self> {
        let preset = get_preset(preset_name).unwrap_or(&PRESETS[0]);
        let loader = TrackLoader::new();
        let downloader = TrackDownloader::new();
        let player = AudioPlayer::new()?;
        let decoder = AudioDecoder::new();
        let analyzer = AudioAnalyzer::new();

        // Find initial preset index
        let selected_preset_idx = PRESETS
            .iter()
            .position(|p| p.name == preset.name)
            .unwrap_or(0);

        Ok(Self {
            player,
            decoder,
            analyzer,
            loader,
            downloader,
            preset,
            current_track: None,
            playlist: Vec::new(),
            playlist_index: 0,
            visualizer: Visualizer::new(),
            running: true,
            start_time: Instant::now(),
            selecting_preset: false,
            selected_preset_idx,
            pending_preset: None,
        })
    }

    /// Get current preset.
    pub fn preset(&self) -> &'static Preset {
        self.preset
    }

    /// Get all presets.
    pub fn all_presets(&self) -> &'static [Preset] {
        PRESETS
    }

    /// Get selected preset index.
    pub fn selected_preset_index(&self) -> usize {
        self.selected_preset_idx
    }

    /// Check if selecting preset.
    pub fn is_selecting_preset(&self) -> bool {
        self.selecting_preset
    }

    /// Get pending preset name.
    pub fn pending_preset(&self) -> Option<&str> {
        self.pending_preset.as_deref()
    }

    /// Get download progress.
    pub fn download_progress(&self) -> DownloadProgress {
        self.downloader.get_progress()
    }

    /// Check if preset has available tracks.
    pub fn preset_has_tracks(&self, preset: &Preset) -> bool {
        !self.loader.get_available_tracks_from_pools(preset.pools).is_empty()
    }

    /// Get current track.
    pub fn current_track(&self) -> Option<&'static Track> {
        self.current_track
    }

    /// Get visualizer.
    pub fn visualizer(&self) -> &Visualizer {
        &self.visualizer
    }

    /// Get RMS level.
    pub fn rms(&self) -> f32 {
        self.analyzer.rms()
    }

    /// Get frequency bands.
    pub fn bands(&self) -> &[f32] {
        self.analyzer.bands()
    }

    /// Get volume.
    pub fn volume(&self) -> f32 {
        self.player.volume()
    }

    /// Set volume.
    pub fn set_volume(&self, vol: f32) {
        self.player.set_volume(vol);
    }

    /// Check if playing.
    pub fn is_playing(&self) -> bool {
        self.player.is_playing()
    }

    /// Get elapsed time formatted.
    pub fn elapsed_time(&self) -> String {
        let elapsed = self.start_time.elapsed();
        let secs = elapsed.as_secs();
        let hours = secs / 3600;
        let mins = (secs % 3600) / 60;
        let secs = secs % 60;
        format!("{:02}:{:02}:{:02}", hours, mins, secs)
    }

    /// Ensure at least one track is available.
    fn ensure_tracks(&mut self) -> Result<bool> {
        let available = self.loader.get_available_tracks_from_pools(self.preset.pools);
        if !available.is_empty() {
            return Ok(true);
        }

        // Download one track
        println!("First run: downloading a track (only happens once)...");
        match self.downloader.download_one_track(self.preset.pools) {
            Ok(Some(_)) => Ok(true),
            Ok(None) => Ok(false),
            Err(e) => {
                eprintln!("Download error: {}", e);
                Ok(false)
            }
        }
    }

    /// Create playlist from current preset.
    fn create_playlist(&mut self) {
        self.playlist = self.loader.create_playlist(self.preset.pools, true);
        self.playlist_index = 0;
    }

    /// Load next track.
    fn load_next_track(&mut self) -> bool {
        if self.playlist.is_empty() {
            self.create_playlist();
        }

        if self.playlist.is_empty() {
            return false;
        }

        // Get next track
        let track = self.playlist[self.playlist_index];
        self.playlist_index = (self.playlist_index + 1) % self.playlist.len();

        // Reshuffle when we've played through all tracks
        if self.playlist_index == 0 {
            self.create_playlist();
        }

        self.current_track = Some(track);

        // Start decoding with analysis buffer
        let path = self.loader.get_track_path(track);
        let producer = self.player.init_buffer();
        let finished = self.player.finished_flag();
        let analysis_producer = self.analyzer.create_buffer();

        if let Err(e) = self.decoder.start(&path, producer, finished, Some(analysis_producer)) {
            eprintln!("Failed to start decoder: {}", e);
            return false;
        }

        true
    }

    /// Handle key events.
    fn handle_key(&mut self, code: KeyCode, modifiers: KeyModifiers) {
        if self.selecting_preset {
            match code {
                KeyCode::Esc | KeyCode::Char('q') => {
                    self.selecting_preset = false;
                    // Reset to current preset
                    self.selected_preset_idx = PRESETS
                        .iter()
                        .position(|p| p.name == self.preset.name)
                        .unwrap_or(0);
                }
                KeyCode::Enter => {
                    self.confirm_preset_selection();
                }
                KeyCode::Char('j') | KeyCode::Left => {
                    if self.selected_preset_idx > 0 {
                        self.selected_preset_idx -= 1;
                    } else {
                        self.selected_preset_idx = PRESETS.len() - 1;
                    }
                }
                KeyCode::Char('k') | KeyCode::Right | KeyCode::Char('p') => {
                    self.selected_preset_idx = (self.selected_preset_idx + 1) % PRESETS.len();
                }
                _ => {}
            }
        } else {
            match code {
                KeyCode::Char('q') | KeyCode::Esc => {
                    self.running = false;
                }
                KeyCode::Char('c') if modifiers.contains(KeyModifiers::CONTROL) => {
                    self.running = false;
                }
                KeyCode::Char(' ') => {
                    self.player.toggle_pause();
                }
                KeyCode::Char('p') => {
                    self.selecting_preset = true;
                }
                KeyCode::Char('n') => {
                    self.skip_track();
                }
                KeyCode::Char('s') => {
                    open_support_url();
                }
                KeyCode::Char('+') | KeyCode::Char('=') | KeyCode::Char(']') | KeyCode::Up => {
                    self.player.volume_up();
                }
                KeyCode::Char('-') | KeyCode::Char('_') | KeyCode::Char('[') | KeyCode::Down => {
                    self.player.volume_down();
                }
                _ => {}
            }
        }
    }

    /// Skip to next track.
    fn skip_track(&mut self) {
        self.decoder.stop();
        self.load_next_track();
    }

    /// Confirm preset selection.
    fn confirm_preset_selection(&mut self) {
        self.selecting_preset = false;
        let new_preset = &PRESETS[self.selected_preset_idx];

        if new_preset.name == self.preset.name {
            return; // No change
        }

        // Check if tracks are available
        let available = self.loader.get_available_tracks_from_pools(new_preset.pools);
        if available.is_empty() {
            // Start background download
            self.pending_preset = Some(new_preset.name.to_string());
            self.downloader.start_background_download(new_preset.pools.to_vec());
            return;
        }

        // Switch preset
        self.preset = new_preset;
        self.pending_preset = None;
        self.create_playlist();
        self.decoder.stop();
        self.load_next_track();

        // Start background download for remaining tracks
        self.downloader.start_background_download(self.preset.pools.to_vec());
    }

    /// Check for pending preset switch.
    fn check_pending_preset(&mut self) {
        if self.pending_preset.is_none() {
            return;
        }

        let pending_name = self.pending_preset.as_ref().unwrap().clone();
        if let Some(pending_preset) = get_preset(&pending_name) {
            let available = self.loader.get_available_tracks_from_pools(pending_preset.pools);
            if !available.is_empty() {
                // Switch to pending preset
                self.preset = pending_preset;
                self.pending_preset = None;
                self.selected_preset_idx = PRESETS
                    .iter()
                    .position(|p| p.name == self.preset.name)
                    .unwrap_or(0);
                self.create_playlist();
                self.decoder.stop();
                self.load_next_track();
            }
        }
    }

    /// Run the application.
    pub fn run(&mut self) -> Result<()> {
        // Ensure tracks are available
        if !self.ensure_tracks()? {
            eprintln!("No tracks available. Please check your internet connection.");
            return Ok(());
        }

        // Start background download
        self.downloader.start_background_download(self.preset.pools.to_vec());

        // Create playlist and load first track
        self.create_playlist();
        if !self.load_next_track() {
            eprintln!("Failed to load track.");
            return Ok(());
        }

        // Setup terminal with cleanup guard
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen, EnableMouseCapture)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;

        // Run the main loop, ensuring cleanup happens
        let result = self.run_loop(&mut terminal);

        // Cleanup audio (with timeouts to avoid blocking)
        self.decoder.stop();
        self.player.stop();
        self.downloader.stop_background_download();

        // Cleanup terminal (always do this, even if loop errored)
        let _ = disable_raw_mode();
        let _ = execute!(
            terminal.backend_mut(),
            LeaveAlternateScreen,
            DisableMouseCapture
        );
        let _ = terminal.show_cursor();

        result
    }

    /// Main event loop - separated for easier cleanup handling.
    fn run_loop(&mut self, terminal: &mut Terminal<CrosstermBackend<io::Stdout>>) -> Result<()> {
        let tick_rate = Duration::from_millis(1000 / 15); // 15 FPS

        while self.running {
            // Handle events
            if event::poll(tick_rate)? {
                if let Event::Key(key) = event::read()? {
                    self.handle_key(key.code, key.modifiers);
                }
            }

            // Update audio analysis
            self.analyzer.update();

            // Update visualizer
            self.visualizer.update(self.analyzer.rms(), self.analyzer.bands());

            // Check if track ended
            if self.player.is_finished() && !self.decoder.is_running() {
                if !self.load_next_track() {
                    // Restart playlist
                    self.create_playlist();
                    self.load_next_track();
                }
            }

            // Check for pending preset switch
            self.check_pending_preset();

            // Render
            terminal.draw(|f| render_ui(f, self))?;
        }

        Ok(())
    }
}
