# Fomu

CLI ambient music player for focus. Plays curated tracks from Scott Buckley's Creative Commons library.

![Fomu CLI](https://github.com/user-attachments/assets/5c1cbb8c-dab1-47b7-a5b0-9456360d4a8f)

## Installation

**Requirements:** Rust 1.70+

```bash
cargo install --path .
```

On first run, Fomu will automatically download one track to get started, then continue downloading the rest in the background.

## Usage

```bash
# Start with defaults
fomu

# Use a specific preset
fomu --preset deep
fomu --preset creative
fomu --preset morning

```

### Interactive Controls

| Key | Action |
|-----|--------|
| `Space` | Pause/Resume |
| `+/-` | Volume up/down |
| `n` | Skip track |
| `p` | Select preset |
| `q` | Quit |

## Presets

| Preset | Track Pools | Best For |
|--------|-------------|----------|
| `focus` | atmospheric, calm-focus | Coding, writing |
| `deep` | calm-focus, atmospheric | Reading, research |
| `creative` | atmospheric, gentle-movement | Brainstorming |
| `flow` | calm-focus, atmospheric | Creative work |
| `relax` | calm-focus | Unwinding |
| `morning` | gentle-movement, atmospheric | Waking up |

## Music Attribution

This project exists thanks to the generosity of **Scott Buckley**, who releases his beautiful cinematic music under **CC-BY 4.0** — free for anyone to use, just as long as you credit him.

> "Everyone has a story. I have a library of my own cinematic original music – released under CC-BY 4.0 – to help you tell that story, in whatever format you tell it. Oh, and it's free – just as long as you credit me."

- Website: https://www.scottbuckley.com.au
- Music Library: https://www.scottbuckley.com.au/library/
- **Support Scott**: https://www.scottbuckley.com.au/library/donate/

If you enjoy using Fomu, please consider donating to Scott to support his work.

## License

MIT License
