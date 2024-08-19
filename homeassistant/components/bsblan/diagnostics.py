"""Diagnostics support for BSBLan."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .models import BSBLanData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: BSBLanData = hass.data[DOMAIN][entry.entry_id]

    # Helper function to safely get dict from potentially async methods
    async def safe_to_dict(obj):
        if callable(getattr(obj, "to_dict", None)):
            result = obj.to_dict()
            return await result if hasattr(result, "__await__") else result
        return obj

    # Process state and sensor data from the coordinator
    coordinator_data = data.coordinator.data
    state_dict = (
        await safe_to_dict(coordinator_data.state) if coordinator_data.state else {}
    )
    sensor_dict = (
        await safe_to_dict(coordinator_data.sensor) if coordinator_data.sensor else {}
    )

    return {
        "info": await safe_to_dict(data.info),
        "device": await safe_to_dict(data.device),
        "coordinator_data": {
            "state": state_dict,
            "sensor": sensor_dict,
        },
        "static": await safe_to_dict(data.static),
    }
