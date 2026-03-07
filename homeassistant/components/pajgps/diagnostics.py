"""Diagnostics support for PAJ GPS."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PajGpsConfigEntry

TO_REDACT = {"email", "password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: PajGpsConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "coordinator_data": {
            "devices": [
                {
                    "id": device.id,
                    "name": device.name,
                    "model": (
                        device.device_models[0].get("model")
                        if device.device_models and isinstance(device.device_models[0], dict)
                        else None
                    ),
                }
                for device in data.devices
            ],
            "positions": {
                str(device_id): {
                    "latitude": tp.lat,
                    "longitude": tp.lng,
                    "speed": tp.speed,
                    "heading": tp.direction,
                    "timestamp": str(tp.dateunix) if tp.dateunix else None,
                }
                for device_id, tp in data.positions.items()
            },
        },
    }
