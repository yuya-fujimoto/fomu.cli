//! Fomu - CLI ambient music player for focus.
//!
//! A Rust rewrite of the Python fomu player, designed for stable
//! real-time audio without GIL contention issues.

mod app;
mod audio;
mod presets;
mod tracks;
mod ui;

use anyhow::Result;
use clap::Parser;

use app::App;
use presets::get_preset_names;

/// Fomu - Ambient music for focus
///
/// Play curated ambient music from Scott Buckley's Creative Commons library.
#[derive(Parser, Debug)]
#[command(name = "fomu")]
#[command(author, version, about, long_about = None)]
struct Args {
    /// Music pool preset
    #[arg(short, long, default_value = "focus")]
    preset: String,

    /// Initial volume (0.0-1.0)
    #[arg(long, default_value = "0.8")]
    volume: f32,

    /// Delete all downloaded tracks and exit
    #[arg(long)]
    clear_tracks: bool,
}

fn main() -> Result<()> {
    // Set up panic hook to restore terminal on panic
    let original_hook = std::panic::take_hook();
    std::panic::set_hook(Box::new(move |panic_info| {
        // Restore terminal state
        let _ = crossterm::terminal::disable_raw_mode();
        let _ = crossterm::execute!(
            std::io::stdout(),
            crossterm::terminal::LeaveAlternateScreen,
            crossterm::event::DisableMouseCapture
        );
        // Call the original panic hook
        original_hook(panic_info);
    }));

    let args = Args::parse();

    // Handle --clear-tracks
    if args.clear_tracks {
        let tracks_dir = tracks::loader::get_tracks_dir();
        if tracks_dir.exists() {
            let mut count = 0;
            for entry in std::fs::read_dir(&tracks_dir)? {
                let entry = entry?;
                let path = entry.path();
                if path.extension().map(|e| e == "mp3").unwrap_or(false) {
                    std::fs::remove_file(&path)?;
                    count += 1;
                }
            }
            if count > 0 {
                println!("Deleted {} track(s)", count);
            } else {
                println!("No tracks to delete");
            }
        } else {
            println!("Tracks directory does not exist");
        }
        return Ok(());
    }

    // Validate preset
    let preset_names = get_preset_names();
    if !preset_names.contains(&args.preset.as_str()) {
        eprintln!(
            "Unknown preset '{}'. Available presets: {}",
            args.preset,
            preset_names.join(", ")
        );
        std::process::exit(1);
    }

    // Create and run app
    let mut app = App::new(&args.preset)?;
    app.set_volume(args.volume.clamp(0.0, 1.0));
    app.run()?;

    Ok(())
}
