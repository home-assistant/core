"""Diagnostics support for the Yoto integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import YotoConfigEntry

TO_REDACT = {
    "access_token",
    "refresh_token",
    "mac",
    "network_ssid",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: YotoConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "players": async_redact_data(
            {
                player_id: asdict(player)
                for player_id, player in coordinator.data.items()
            },
            TO_REDACT,
        ),
    }
