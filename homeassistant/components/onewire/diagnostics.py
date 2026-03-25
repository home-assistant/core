"""Diagnostics support for 1-Wire."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .onewirehub import OneWireConfigEntry

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
        "devices": [asdict(device_details) for device_details in onewire_hub.devices],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: OneWireConfigEntry, device_entry: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""

    onewire_hub = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": {**entry.options},
        },
        "device": asdict(
            next(
                device_details
                for device_details in onewire_hub.devices
                if device_details.id[3:] == device_entry.serial_number
            )
        ),
    }
