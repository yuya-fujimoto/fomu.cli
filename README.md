# Fomu

CLI ambient music player for focus. Plays curated tracks from Scott Buckley's Creative Commons library.

## Installation

**Requirements:** Python 3.9+

### From source

```bash
git clone https://github.com/yuya-fujimoto/fomu.cli.git
cd fomu
pip install .
```

On first run, Fomu will automatically download one track to get started, then continue downloading the rest in the background.

### For development

```bash
git clone https://github.com/yuya-fujimoto/fomu.cli.git
cd fomu
pip install -e ".[dev]"
```

## Usage

```bash
# Start with defaults
fomu

# Use a specific preset (different track pools)
fomu --preset deep
fomu --preset creative
fomu --preset morning

# Change visualization
fomu --viz bars
fomu --viz minimal

# Set color theme
fomu --theme purple
fomu --theme warm
```

### Interactive Controls

| Key | Action |
|-----|--------|
| `Space` | Pause/Resume |
| `+/-` | Volume up/down |
| `n` | Skip track |
| `v` | Cycle visualization |
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
