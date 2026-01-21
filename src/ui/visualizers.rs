//! Bar visualization for the audio player.

const BLOCKS: &[char] = &[' ', '▁', '▂', '▃', '▄', '▅', '▆', '▇', '█'];

pub struct Visualizer {
    _placeholder: (),
}

impl Visualizer {
    pub fn new() -> Self {
        Self { _placeholder: () }
    }

    pub fn update(&mut self, _rms: f32, _bands: &[f32]) {
        // No state needed for bars visualization
    }

    /// Render bar visualization with dynamic sizing.
    pub fn render_sized(&self, _rms: f32, bands: &[f32], width: usize, height: usize) -> Vec<String> {
        let num_bars = bands.len().min(16);
        let bar_width = if num_bars > 0 {
            (width.saturating_sub(num_bars - 1)) / num_bars
        } else {
            1
        }.max(1);

        let mut lines = Vec::with_capacity(height);

        for row in 0..height {
            let mut row_chars = String::with_capacity(width);
            let threshold = 1.0 - (row as f32 / height as f32);

            for (i, &level) in bands.iter().take(num_bars).enumerate() {
                let ch = if level >= threshold {
                    '█'
                } else if level >= threshold - (1.0 / height as f32) {
                    let partial_idx = ((level - threshold + (1.0 / height as f32))
                        * height as f32 * (BLOCKS.len() - 1) as f32) as usize;
                    BLOCKS[partial_idx.min(BLOCKS.len() - 1)]
                } else {
                    ' '
                };

                for _ in 0..bar_width {
                    row_chars.push(ch);
                }
                if i < num_bars - 1 {
                    row_chars.push(' ');
                }
            }
            lines.push(row_chars);
        }
        lines
    }
}

impl Default for Visualizer {
    fn default() -> Self {
        Self::new()
    }
}
