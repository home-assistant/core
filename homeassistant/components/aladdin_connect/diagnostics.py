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
                "device_id": coordinator.data.device_id,
                "door_number": coordinator.data.door_number,
                "name": coordinator.data.name,
                "status": coordinator.data.status,
                "link_status": coordinator.data.link_status,
                "battery_level": coordinator.data.battery_level,
            }
            for uid, coordinator in config_entry.runtime_data.items()
        },
    }
