"""Diagnostics support for Aladdin Connect."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import AladdinConnectConfigEntry

TO_REDACT = {"access_token", "refresh_token"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AladdinConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "doors": {
            uid: {
                "device_id": door.device_id,
                "door_number": door.door_number,
                "name": door.name,
                "status": door.status,
                "link_status": door.link_status,
                "battery_level": door.battery_level,
            }
            for uid, door in config_entry.runtime_data.data.items()
        },
    }
