//! Audio playback via cpal with real-time audio callback.
//!
//! This is the most critical module for audio stability. The audio callback
//! MUST NEVER allocate, lock mutexes, or block in any way.

use std::sync::atomic::{AtomicBool, AtomicU32, Ordering};
use std::sync::Arc;

use anyhow::Result;
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, SampleRate, Stream, StreamConfig};
use ringbuf::{traits::*, HeapRb};

/// Atomic f32 for lock-free volume control.
/// Stores f32 bits as u32 for atomic operations.
pub struct AtomicF32(AtomicU32);

impl AtomicF32 {
    pub fn new(val: f32) -> Self {
        Self(AtomicU32::new(val.to_bits()))
    }

    pub fn load(&self) -> f32 {
        f32::from_bits(self.0.load(Ordering::Relaxed))
    }

    pub fn store(&self, val: f32) {
        self.0.store(val.to_bits(), Ordering::Relaxed);
    }
}

/// Ring buffer size: ~500ms of stereo audio at 44100 Hz
pub const RING_BUFFER_SIZE: usize = 44100;

/// Audio configuration constants
pub const SAMPLE_RATE: u32 = 44100;
pub const CHANNELS: u16 = 2;
pub const BUFFER_SIZE: u32 = 512;

/// Audio player with real-time playback using cpal.
pub struct AudioPlayer {
    device: Device,
    config: StreamConfig,
    stream: Option<Stream>,
    volume: Arc<AtomicF32>,
    paused: Arc<AtomicBool>,
    finished: Arc<AtomicBool>,
}

impl AudioPlayer {
    /// Create a new audio player.
    pub fn new() -> Result<Self> {
        let host = cpal::default_host();
        let device = host
            .default_output_device()
            .ok_or_else(|| anyhow::anyhow!("No output device available"))?;

        let config = StreamConfig {
            channels: CHANNELS,
            sample_rate: SampleRate(SAMPLE_RATE),
            buffer_size: cpal::BufferSize::Fixed(BUFFER_SIZE),
        };

        Ok(Self {
            device,
            config,
            stream: None,
            volume: Arc::new(AtomicF32::new(0.8)),
            paused: Arc::new(AtomicBool::new(false)),
            finished: Arc::new(AtomicBool::new(false)),
        })
    }

    /// Initialize the ring buffer and return the producer.
    pub fn init_buffer(&mut self) -> ringbuf::HeapProd<f32> {
        let ring = HeapRb::<f32>::new(RING_BUFFER_SIZE);
        let (producer, consumer) = ring.split();

        self.finished.store(false, Ordering::SeqCst);
        self.paused.store(false, Ordering::SeqCst);

        self.start_stream(consumer);
        producer
    }

    /// Start the audio output stream.
    fn start_stream(&mut self, mut consumer: ringbuf::HeapCons<f32>) {
        let volume = Arc::clone(&self.volume);
        let paused = Arc::clone(&self.paused);

        // CRITICAL: This callback runs in a real-time audio thread.
        // It MUST NEVER: allocate, lock mutexes, println!, panic, or block.
        let stream = self
            .device
            .build_output_stream(
                &self.config,
                move |output: &mut [f32], _: &cpal::OutputCallbackInfo| {
                    let vol = volume.load();
                    let is_paused = paused.load(Ordering::Relaxed);

                    for sample in output.iter_mut() {
                        if is_paused {
                            *sample = 0.0;
                        } else {
                            *sample = consumer.try_pop().unwrap_or(0.0) * vol;
                        }
                    }
                },
                |err| eprintln!("Audio stream error: {}", err),
                None,
            )
            .expect("Failed to build output stream");

        stream.play().expect("Failed to start audio stream");
        self.stream = Some(stream);
    }

    pub fn volume(&self) -> f32 {
        self.volume.load()
    }

    pub fn set_volume(&self, vol: f32) {
        self.volume.store(vol.clamp(0.0, 1.0));
    }

    pub fn volume_up(&self) -> f32 {
        let new_vol = (self.volume() + 0.05).min(1.0);
        self.set_volume(new_vol);
        new_vol
    }

    pub fn volume_down(&self) -> f32 {
        let new_vol = (self.volume() - 0.05).max(0.0);
        self.set_volume(new_vol);
        new_vol
    }

    pub fn is_paused(&self) -> bool {
        self.paused.load(Ordering::Relaxed)
    }

    pub fn is_playing(&self) -> bool {
        !self.is_paused()
    }

    pub fn toggle_pause(&self) -> bool {
        let was_paused = self.paused.fetch_xor(true, Ordering::SeqCst);
        !was_paused
    }

    pub fn is_finished(&self) -> bool {
        self.finished.load(Ordering::Relaxed)
    }

    pub fn finished_flag(&self) -> Arc<AtomicBool> {
        Arc::clone(&self.finished)
    }

    pub fn stop(&mut self) {
        if let Some(stream) = self.stream.take() {
            drop(stream);
        }
    }
}

impl Default for AudioPlayer {
    fn default() -> Self {
        Self::new().expect("Failed to create audio player")
    }
}
