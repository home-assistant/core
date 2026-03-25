"""Diagnostics support for Airthings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .coordinator import AirthingsConfigEntry

TO_REDACT = {"device_id", "location_name"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: AirthingsConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    devices = {
        device.name: {
            "device_type": device.device_type,
            "product_name": device.product_name,
            "is_active": device.is_active,
            "sensor_types": device.sensor_types,
            "sensors": device.sensors,
        }
        for device in coordinator.data.values()
    }

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "devices": async_redact_data(devices, TO_REDACT),
    }
