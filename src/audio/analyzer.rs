//! Audio analysis for visualization using FFT.
//!
//! Computes RMS level and frequency bands from audio samples.

use ringbuf::{traits::*, HeapRb};
use rustfft::{num_complex::Complex, FftPlanner};

/// FFT window size - must be power of 2
const FFT_SIZE: usize = 2048;

/// Number of frequency bands for visualization
const NUM_BANDS: usize = 16;

/// Analysis ring buffer size - enough for a few FFT windows
pub const ANALYSIS_BUFFER_SIZE: usize = FFT_SIZE * 4;

/// Audio analyzer for computing RMS and frequency bands.
pub struct AudioAnalyzer {
    /// Ring buffer consumer for analysis samples
    consumer: Option<ringbuf::HeapCons<f32>>,
    /// Sample buffer for FFT
    sample_buffer: Vec<f32>,
    /// FFT input buffer
    fft_input: Vec<Complex<f32>>,
    /// FFT output buffer
    fft_output: Vec<Complex<f32>>,
    /// FFT planner
    fft: std::sync::Arc<dyn rustfft::Fft<f32>>,
    /// Current RMS level
    rms: f32,
    /// Current frequency bands
    bands: Vec<f32>,
    /// Smoothing factor for values (higher = smoother)
    smoothing: f32,
}

impl AudioAnalyzer {
    /// Create a new analyzer without a consumer.
    /// Use `create_buffer()` to get a producer/consumer pair for each track.
    pub fn new() -> Self {
        let mut planner = FftPlanner::new();
        let fft = planner.plan_fft_forward(FFT_SIZE);

        Self {
            consumer: None,
            sample_buffer: Vec::with_capacity(FFT_SIZE),
            fft_input: vec![Complex::new(0.0, 0.0); FFT_SIZE],
            fft_output: vec![Complex::new(0.0, 0.0); FFT_SIZE],
            fft,
            rms: 0.0,
            bands: vec![0.0; NUM_BANDS],
            smoothing: 0.7,
        }
    }

    /// Create a new analysis buffer and return the producer.
    /// The analyzer will consume from the new buffer.
    pub fn create_buffer(&mut self) -> ringbuf::HeapProd<f32> {
        let ring = HeapRb::<f32>::new(ANALYSIS_BUFFER_SIZE);
        let (producer, consumer) = ring.split();
        self.consumer = Some(consumer);
        self.sample_buffer.clear();
        producer
    }

    /// Process available samples and update analysis.
    pub fn update(&mut self) {
        // Drain available samples from ring buffer (limit to avoid blocking event loop)
        const MAX_SAMPLES_PER_UPDATE: usize = 8192;
        let mut samples_read = 0;

        if let Some(ref mut consumer) = self.consumer {
            while samples_read < MAX_SAMPLES_PER_UPDATE {
                if let Some(sample) = consumer.try_pop() {
                    // Convert stereo to mono by averaging pairs
                    if samples_read % 2 == 1 {
                        // This is the right channel, average with previous left
                        if let Some(last) = self.sample_buffer.last_mut() {
                            *last = (*last + sample) * 0.5;
                        }
                    } else {
                        // This is the left channel
                        self.sample_buffer.push(sample);
                    }
                    samples_read += 1;
                } else {
                    break;
                }
            }
        }

        if samples_read == 0 {
            // Decay values when no new samples
            self.rms *= 0.95;
            for band in &mut self.bands {
                *band *= 0.95;
            }
            return;
        }

        // Process if we have enough samples (only do one FFT per update)
        if self.sample_buffer.len() >= FFT_SIZE {
            self.process_fft();
            // Keep last quarter for overlap
            let keep_from = self.sample_buffer.len() - FFT_SIZE / 4;
            self.sample_buffer = self.sample_buffer[keep_from..].to_vec();
        }
    }

    /// Perform FFT analysis on the sample buffer.
    fn process_fft(&mut self) {
        let samples = &self.sample_buffer[..FFT_SIZE];

        // Compute RMS
        let sum_squares: f32 = samples.iter().map(|s| s * s).sum();
        let new_rms = (sum_squares / FFT_SIZE as f32).sqrt();

        // Apply Hann window and copy to FFT input
        for (i, &sample) in samples.iter().enumerate() {
            let window = 0.5 * (1.0 - (2.0 * std::f32::consts::PI * i as f32 / (FFT_SIZE - 1) as f32).cos());
            self.fft_input[i] = Complex::new(sample * window, 0.0);
        }

        // Perform FFT
        self.fft_output.copy_from_slice(&self.fft_input);
        self.fft.process(&mut self.fft_output);

        // Extract frequency bands
        let new_bands = self.extract_bands();

        // Smooth values
        self.rms = self.rms * self.smoothing + new_rms * (1.0 - self.smoothing);
        for (i, &new_band) in new_bands.iter().enumerate() {
            self.bands[i] = self.bands[i] * self.smoothing + new_band * (1.0 - self.smoothing);
        }
    }

    /// Extract frequency bands from FFT output.
    fn extract_bands(&self) -> Vec<f32> {
        let mut bands = vec![0.0; NUM_BANDS];

        // Only use first half of FFT output (positive frequencies)
        let useful_bins = FFT_SIZE / 2;

        // Logarithmic band distribution for better visual representation
        // Each band covers a range of FFT bins, with higher bands covering more bins
        for band_idx in 0..NUM_BANDS {
            // Logarithmic frequency mapping
            let low_freq = (band_idx as f32 / NUM_BANDS as f32).powf(2.0);
            let high_freq = ((band_idx + 1) as f32 / NUM_BANDS as f32).powf(2.0);

            let low_bin = (low_freq * useful_bins as f32) as usize;
            let high_bin = ((high_freq * useful_bins as f32) as usize).max(low_bin + 1);

            // Average magnitude in this frequency range
            let mut sum = 0.0;
            let mut count = 0;
            for bin in low_bin..high_bin.min(useful_bins) {
                let magnitude = self.fft_output[bin].norm();
                sum += magnitude;
                count += 1;
            }

            if count > 0 {
                // Normalize and scale for visualization
                let avg = sum / count as f32;
                // Scale to roughly 0-1 range (adjust multiplier as needed)
                bands[band_idx] = (avg / FFT_SIZE as f32 * 40.0).min(1.0);
            }
        }

        bands
    }

    /// Get current RMS level (0.0 - 1.0).
    pub fn rms(&self) -> f32 {
        // Scale RMS for better visualization (music is often quieter than peak)
        (self.rms * 3.0).min(1.0)
    }

    /// Get current frequency bands.
    pub fn bands(&self) -> &[f32] {
        &self.bands
    }
}

impl Default for AudioAnalyzer {
    fn default() -> Self {
        Self::new()
    }
}
