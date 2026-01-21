//! MP3 decoder using symphonia.
//!
//! Decodes MP3 files to PCM samples and pushes them to a ring buffer
//! for the audio thread to consume.

use std::fs::File;
use std::path::Path;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;

use anyhow::{Context, Result};
use ringbuf::traits::*;
use symphonia::core::audio::{AudioBufferRef, Signal};
use symphonia::core::codecs::{DecoderOptions, CODEC_TYPE_NULL};
use symphonia::core::formats::FormatOptions;
use symphonia::core::io::MediaSourceStream;
use symphonia::core::meta::MetadataOptions;
use symphonia::core::probe::Hint;

use super::player::SAMPLE_RATE;

/// Audio decoder for MP3 files.
pub struct AudioDecoder {
    /// Flag to signal the decoder to stop
    should_stop: Arc<AtomicBool>,
    /// Decoder thread handle
    thread_handle: Option<thread::JoinHandle<()>>,
}

impl AudioDecoder {
    /// Create a new audio decoder.
    pub fn new() -> Self {
        Self {
            should_stop: Arc::new(AtomicBool::new(false)),
            thread_handle: None,
        }
    }

    /// Start decoding a file in a background thread.
    ///
    /// Samples are pushed to the provided ring buffer producer.
    /// Optionally, samples are also pushed to an analysis buffer for visualization.
    /// The decoder will signal `finished` when the file is complete.
    pub fn start(
        &mut self,
        path: &Path,
        mut producer: ringbuf::HeapProd<f32>,
        finished: Arc<AtomicBool>,
        analysis_producer: Option<ringbuf::HeapProd<f32>>,
    ) -> Result<()> {
        // Stop any existing decode
        self.stop();

        let should_stop = Arc::new(AtomicBool::new(false));
        self.should_stop = Arc::clone(&should_stop);

        let path = path.to_path_buf();

        let handle = thread::spawn(move || {
            if let Err(e) = decode_file(&path, &mut producer, &should_stop, analysis_producer) {
                eprintln!("Decoder error: {}", e);
            }
            finished.store(true, Ordering::SeqCst);
        });

        self.thread_handle = Some(handle);
        Ok(())
    }

    /// Stop the current decode operation.
    pub fn stop(&mut self) {
        self.should_stop.store(true, Ordering::SeqCst);

        if let Some(handle) = self.thread_handle.take() {
            // Wait for thread to finish with a reasonable timeout
            // If thread doesn't finish, just detach it (it will exit on its own)
            let start = std::time::Instant::now();
            while !handle.is_finished() {
                if start.elapsed() > Duration::from_millis(500) {
                    // Thread is taking too long, just let it detach
                    break;
                }
                thread::sleep(Duration::from_millis(10));
            }
            if handle.is_finished() {
                let _ = handle.join();
            }
            // If not finished, the handle will be dropped and thread detached
        }
    }

    /// Check if decoder is currently running.
    pub fn is_running(&self) -> bool {
        self.thread_handle
            .as_ref()
            .map(|h| !h.is_finished())
            .unwrap_or(false)
    }
}

impl Default for AudioDecoder {
    fn default() -> Self {
        Self::new()
    }
}

impl Drop for AudioDecoder {
    fn drop(&mut self) {
        self.stop();
    }
}

/// Decode an MP3 file and push samples to the ring buffer.
fn decode_file(
    path: &Path,
    producer: &mut ringbuf::HeapProd<f32>,
    should_stop: &AtomicBool,
    mut analysis_producer: Option<ringbuf::HeapProd<f32>>,
) -> Result<()> {
    let file = File::open(path).context("Failed to open audio file")?;
    let mss = MediaSourceStream::new(Box::new(file), Default::default());

    let mut hint = Hint::new();
    if let Some(ext) = path.extension().and_then(|e| e.to_str()) {
        hint.with_extension(ext);
    }

    let format_opts = FormatOptions::default();
    let metadata_opts = MetadataOptions::default();
    let decoder_opts = DecoderOptions::default();

    let probed = symphonia::default::get_probe()
        .format(&hint, mss, &format_opts, &metadata_opts)
        .context("Failed to probe audio format")?;

    let mut format = probed.format;

    // Find the first audio track
    let track = format
        .tracks()
        .iter()
        .find(|t| t.codec_params.codec != CODEC_TYPE_NULL)
        .ok_or_else(|| anyhow::anyhow!("No audio track found"))?;

    let track_id = track.id;

    // Create decoder for the track
    let mut decoder = symphonia::default::get_codecs()
        .make(&track.codec_params, &decoder_opts)
        .context("Failed to create decoder")?;

    // Get sample rate for potential resampling
    let source_sample_rate = track
        .codec_params
        .sample_rate
        .unwrap_or(SAMPLE_RATE);

    // Decode packets
    loop {
        if should_stop.load(Ordering::Relaxed) {
            break;
        }

        let packet = match format.next_packet() {
            Ok(packet) => packet,
            Err(symphonia::core::errors::Error::IoError(e))
                if e.kind() == std::io::ErrorKind::UnexpectedEof =>
            {
                // End of file
                break;
            }
            Err(e) => {
                eprintln!("Packet read error: {}", e);
                break;
            }
        };

        // Skip packets from other tracks
        if packet.track_id() != track_id {
            continue;
        }

        // Decode the packet
        let decoded = match decoder.decode(&packet) {
            Ok(decoded) => decoded,
            Err(symphonia::core::errors::Error::DecodeError(e)) => {
                eprintln!("Decode error: {}", e);
                continue;
            }
            Err(e) => {
                eprintln!("Decode error: {}", e);
                break;
            }
        };

        // Convert to f32 samples and push to ring buffer
        push_samples_to_buffer(decoded, producer, should_stop, source_sample_rate, &mut analysis_producer)?;
    }

    Ok(())
}

/// Convert decoded audio to f32 stereo and push to ring buffer.
fn push_samples_to_buffer(
    decoded: AudioBufferRef,
    producer: &mut ringbuf::HeapProd<f32>,
    should_stop: &AtomicBool,
    _source_sample_rate: u32,
    analysis_producer: &mut Option<ringbuf::HeapProd<f32>>,
) -> Result<()> {
    // Convert to f32 samples
    let samples: Vec<f32> = match decoded {
        AudioBufferRef::F32(buf) => {
            let channels = buf.spec().channels.count();
            let frames = buf.frames();

            let mut output = Vec::with_capacity(frames * 2);

            for frame in 0..frames {
                if channels == 1 {
                    // Mono -> stereo
                    let sample = buf.chan(0)[frame];
                    output.push(sample);
                    output.push(sample);
                } else if channels >= 2 {
                    // Stereo (or more, just take first two)
                    output.push(buf.chan(0)[frame]);
                    output.push(buf.chan(1)[frame]);
                }
            }
            output
        }
        AudioBufferRef::S16(buf) => {
            let channels = buf.spec().channels.count();
            let frames = buf.frames();

            let mut output = Vec::with_capacity(frames * 2);

            for frame in 0..frames {
                if channels == 1 {
                    let sample = buf.chan(0)[frame] as f32 / 32768.0;
                    output.push(sample);
                    output.push(sample);
                } else if channels >= 2 {
                    output.push(buf.chan(0)[frame] as f32 / 32768.0);
                    output.push(buf.chan(1)[frame] as f32 / 32768.0);
                }
            }
            output
        }
        AudioBufferRef::S32(buf) => {
            let channels = buf.spec().channels.count();
            let frames = buf.frames();

            let mut output = Vec::with_capacity(frames * 2);

            for frame in 0..frames {
                if channels == 1 {
                    let sample = buf.chan(0)[frame] as f32 / 2147483648.0;
                    output.push(sample);
                    output.push(sample);
                } else if channels >= 2 {
                    output.push(buf.chan(0)[frame] as f32 / 2147483648.0);
                    output.push(buf.chan(1)[frame] as f32 / 2147483648.0);
                }
            }
            output
        }
        AudioBufferRef::U8(buf) => {
            let channels = buf.spec().channels.count();
            let frames = buf.frames();

            let mut output = Vec::with_capacity(frames * 2);

            for frame in 0..frames {
                if channels == 1 {
                    let sample = (buf.chan(0)[frame] as f32 - 128.0) / 128.0;
                    output.push(sample);
                    output.push(sample);
                } else if channels >= 2 {
                    output.push((buf.chan(0)[frame] as f32 - 128.0) / 128.0);
                    output.push((buf.chan(1)[frame] as f32 - 128.0) / 128.0);
                }
            }
            output
        }
        _ => {
            // Unsupported format, skip
            return Ok(());
        }
    };

    // Push samples to ring buffer with backpressure
    let mut offset = 0;
    while offset < samples.len() {
        if should_stop.load(Ordering::Relaxed) {
            break;
        }

        let written = producer.push_slice(&samples[offset..]);
        offset += written;

        if written == 0 {
            // Buffer is full, wait a bit for consumer to catch up
            thread::sleep(Duration::from_millis(5));
        }
    }

    // Also push to analysis buffer (non-blocking, OK to drop samples)
    if let Some(ref mut analysis) = analysis_producer {
        // Just push what we can, don't wait - analysis is non-critical
        let _ = analysis.push_slice(&samples);
    }

    Ok(())
}
