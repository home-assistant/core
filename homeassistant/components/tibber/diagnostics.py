"""Diagnostics support for Tibber."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .const import TibberConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: TibberConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    runtime = config_entry.runtime_data
    result: dict[str, Any] = {
        "homes": [
            {
                "last_data_timestamp": home.last_data_timestamp,
                "has_active_subscription": home.has_active_subscription,
                "has_real_time_consumption": home.has_real_time_consumption,
                "last_cons_data_timestamp": home.last_cons_data_timestamp,
                "country": home.country,
            }
            for home in runtime.tibber_connection.get_homes(only_active=False)
        ]
    }

    devices = (
        runtime.data_api_coordinator.data
        if runtime.data_api_coordinator is not None
        else {}
    ) or {}

    result["devices"] = [
        {
            "id": device.id,
            "name": device.name,
            "brand": device.brand,
            "model": device.model,
        }
        for device in devices.values()
    ]

    return result
