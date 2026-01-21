//! Preset definitions for Fomu.

use crate::tracks::TrackPool;

#[derive(Debug, Clone)]
pub struct Preset {
    pub name: &'static str,
    pub pools: &'static [TrackPool],
}

pub static PRESETS: &[Preset] = &[
    Preset {
        name: "focus",
        pools: &[TrackPool::Atmospheric, TrackPool::CalmFocus],
    },
    Preset {
        name: "deep",
        pools: &[TrackPool::CalmFocus, TrackPool::Atmospheric],
    },
    Preset {
        name: "creative",
        pools: &[TrackPool::Atmospheric, TrackPool::GentleMovement],
    },
    Preset {
        name: "flow",
        pools: &[TrackPool::CalmFocus, TrackPool::Atmospheric],
    },
    Preset {
        name: "relax",
        pools: &[TrackPool::CalmFocus],
    },
    Preset {
        name: "morning",
        pools: &[TrackPool::GentleMovement, TrackPool::Atmospheric],
    },
];

pub fn get_preset(name: &str) -> Option<&'static Preset> {
    PRESETS.iter().find(|p| p.name == name)
}

pub fn get_preset_names() -> Vec<&'static str> {
    PRESETS.iter().map(|p| p.name).collect()
}
