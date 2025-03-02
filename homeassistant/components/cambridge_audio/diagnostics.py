"""Diagnostics platform for Cambridge Audio."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import CambridgeAudioConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the provided config entry."""
    client = entry.runtime_data
    return {
        "display": client.display.to_dict(),
        "info": client.info.to_dict(),
        "now_playing": client.now_playing.to_dict(),
        "play_state": client.play_state.to_dict(),
        "presets_list": client.preset_list.to_dict(),
        "sources": [s.to_dict() for s in client.sources],
        "update": client.update.to_dict(),
    }
