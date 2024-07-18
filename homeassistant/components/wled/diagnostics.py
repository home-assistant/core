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
        "info": async_redact_data(coordinator.data.info.to_dict(), "wifi"),
        "state": coordinator.data.state.to_dict(),
        "effects": {
            effect.effect_id: effect.name
            for effect in coordinator.data.effects.values()
        },
        "palettes": {
            palette.palette_id: palette.name
            for palette in coordinator.data.palettes.values()
        },
        "playlists": {
            playlist.playlist_id: playlist.name
            for playlist in coordinator.data.playlists.values()
        },
        "presets": {
            preset.preset_id: preset.name
            for preset in coordinator.data.presets.values()
        },
    }
    return data
