"""Diagnostics support for the Fresh-r integration."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import FreshrConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: FreshrConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "devices": [
            {"id": device.id, "device_type": str(device.device_type)}
            for device in (entry.runtime_data.devices.data or [])
        ],
        "readings": {
            device_id: dataclasses.asdict(readings)
            for device_id, readings in (entry.runtime_data.readings.data or {}).items()
        },
    }
