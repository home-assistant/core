"""Diagnostics support for Fresh-r."""

from __future__ import annotations

import dataclasses
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .coordinator import FreshrConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FreshrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    runtime_data = entry.runtime_data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "devices": [
            dataclasses.asdict(device) for device in runtime_data.devices.data.values()
        ],
        "readings": {
            device_id: dataclasses.asdict(coordinator.data)
            if coordinator.data is not None
            else None
            for device_id, coordinator in runtime_data.readings.items()
        },
    }
