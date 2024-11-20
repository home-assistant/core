"""Diagnostics support for Home Connect Diagnostics."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import HomeConnectConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: HomeConnectConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        device.appliance.haId: device.appliance.status
        for device in entry.runtime_data.devices
    }
