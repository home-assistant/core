"""Diagnostics support for the Yoto integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import YotoConfigEntry

TO_REDACT = {
    "token",
    "mac",
    "network_ssid",
    "pop_code",
    "activation_pop_code",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YotoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "players": {
            player_id: async_redact_data(asdict(player), TO_REDACT)
            for player_id, player in coordinator.data.items()
        },
    }
