"""Diagnostics support for WLED."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import WLEDConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WLEDConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    data: dict[str, Any] = {
        "info": async_redact_data(coordinator.data.info.__dict__, "wifi"),
        "state": coordinator.data.state.__dict__,
        "effects": {
            effect.effect_id: effect.name for effect in coordinator.data.effects
        },
        "palettes": {
            palette.palette_id: palette.name for palette in coordinator.data.palettes
        },
        "playlists": {
            playlist.playlist_id: {
                "name": playlist.name,
                "repeat": playlist.repeat,
                "shuffle": playlist.shuffle,
                "end": playlist.end.preset_id if playlist.end else None,
            }
            for playlist in coordinator.data.playlists
        },
        "presets": {
            preset.preset_id: {
                "name": preset.name,
                "quick_label": preset.quick_label,
                "on": preset.on,
                "transition": preset.transition,
            }
            for preset in coordinator.data.presets
        },
    }
    return data
