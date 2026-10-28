"""Diagnostics support for Onkyo."""

from typing import Any

from homeassistant.core import HomeAssistant

from . import OnkyoConfigEntry
from .const import ZONES
from .media_player import DATA_MP_ENTITIES


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OnkyoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    manager = data.manager
    zones = hass.data[DATA_MP_ENTITIES][entry.entry_id]

    return {
        "model_name": manager.info.model_name,
        "connected": manager.connected,
        "zones": [ZONES[zone] for zone in zones],
        "options": dict(entry.options),
        "channel_muting": {
            channel.value: param.name
            for channel, param in data.channel_muting_coordinator.data.items()
        },
    }
