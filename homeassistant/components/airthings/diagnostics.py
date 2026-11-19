"""Diagnostics support for Airthings."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AirthingsConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirthingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # The client ID and secret, device IDs (serial numbers), user-assigned
    # device names and location names are left out, as they are private.
    return {
        "last_update_success": coordinator.last_update_success,
        "devices": [
            {
                "device_type": device.device_type,
                "product_name": device.product_name,
                "is_active": device.is_active,
                "sensors": dict(device.sensors),
            }
            for device in coordinator.data.values()
        ],
    }
