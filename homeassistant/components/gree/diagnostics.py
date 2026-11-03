"""Diagnostics support for Gree Climate."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import GreeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: GreeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "devices": [
            {
                "brand": coordinator.device.device_info.brand,
                "model": coordinator.device.device_info.model,
                "info_version": coordinator.device.device_info.version,
                "hid": coordinator.device.hid,
                "version": coordinator.device.version,
                "last_update_success": coordinator.last_update_success,
                "raw_properties": coordinator.data,
            }
            for coordinator in entry.runtime_data.coordinators
        ]
    }
