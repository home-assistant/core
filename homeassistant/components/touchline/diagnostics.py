"""Diagnostics for the Roth Touchline integration."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import TouchlineConfigEntry

TO_REDACT = {
    CONF_HOST,
    "hostname",
    "ip_address",
    "mac_address",
    "title",
    "unique_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TouchlineConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "controller": asdict(coordinator.controller_status),
            "rooms": {
                room_id: asdict(room) for room_id, room in coordinator.data.items()
            },
        },
        TO_REDACT,
    )
