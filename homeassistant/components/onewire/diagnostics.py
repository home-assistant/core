"""Diagnostics support for 1-Wire."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import OneWireConfigEntry

TO_REDACT = {CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: OneWireConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    onewire_hub = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": {**entry.options},
        },
        "devices": [asdict(device_details) for device_details in onewire_hub.devices]
        if onewire_hub.devices
        else [],
    }
