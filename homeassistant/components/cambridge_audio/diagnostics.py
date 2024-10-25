"""Diagnostics platform for Cambridge Audio."""

from typing import Any

from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from . import CambridgeAudioConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: CambridgeAudioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for the provided config entry."""
    client = entry.runtime_data
    return async_redact_data(
        {
            "display": client.display.to_dict(),
            "info": client.display.to_dict(),
            "now_playing": client.now_playing.to_dict(),
            "play_state": client.play_state.to_dict(),
            "presets_list": client.preset_list.to_dict(),
            "sources": {k: v.to_dict() for k, v in client.sources},
            "update": client.update.to_dict(),
        },
        TO_REDACT,
    )
