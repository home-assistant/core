"""Diagnostics support for Lunatone integration."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import LunatoneConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LunatoneConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    info_data = entry.runtime_data.coordinator_info.data
    devices_data = entry.runtime_data.coordinator_devices.data
    return {
        "info": info_data.model_dump(),
        "devices": [
            device.data.model_dump()
            for devices in devices_data.values()
            for device in devices.values()
        ],
    }
