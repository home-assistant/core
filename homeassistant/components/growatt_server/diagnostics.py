"""Diagnostics support for Growatt Server."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import GrowattConfigEntry

TO_REDACT = {"password", "token", "username"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: GrowattConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data

    return async_redact_data(
        {
            "config_entry": config_entry.as_dict(),
            "total_coordinator": data.total_coordinator.data,
            "devices": {
                device_sn: {
                    "device_type": coordinator.device_type,
                    "data": coordinator.data,
                }
                for device_sn, coordinator in data.devices.items()
            },
        },
        TO_REDACT,
    )
