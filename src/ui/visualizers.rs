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
        let num_bars = bands.len();

        // Fixed 1-space gap between bars, bar width capped for tighter look
        let gap = 1;
        let total_gaps = (num_bars - 1) * gap;
        let bar_width = (width.saturating_sub(total_gaps) / num_bars).clamp(1, 2);

        let mut lines = Vec::with_capacity(height);

        let left_padding = 6;

        for row in 0..height {
            let mut row_chars = String::with_capacity(width);
            // Add left padding
            for _ in 0..left_padding {
                row_chars.push(' ');
            }
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
                    for _ in 0..gap {
                        row_chars.push(' ');
                    }
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
