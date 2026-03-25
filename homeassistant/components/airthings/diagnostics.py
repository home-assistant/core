"""Diagnostics support for Airthings."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ID, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .const import CONF_SECRET
from .coordinator import AirthingsConfigEntry

REDACT_CONFIG = {CONF_SECRET, CONF_UNIQUE_ID, CONF_ID, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirthingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "config_entry": async_redact_data(entry.as_dict(), REDACT_CONFIG),
        "coordinator_data": {
            device_id: {
                "sensor_types": list(device.sensor_types),
                "product_name": device.product_name,
            }
            for device_id, device in coordinator.data.items()
        },
    }
