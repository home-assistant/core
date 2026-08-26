"""Diagnostics support for 1-Wire."""

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .model import OWDeviceDescription
from .onewirehub import OneWireConfigEntry

TO_REDACT = {CONF_HOST}


def _device_diagnostics(device_details: OWDeviceDescription) -> dict[str, Any]:
    """Return diagnostics for a device description."""
    # asdict recurses into the device info, which holds a field per key it can set
    return asdict(device_details) | {"device_info": dict(device_details.device_info)}


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
        "devices": [
            _device_diagnostics(device_details)
            for device_details in onewire_hub.devices
        ],
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
        "device": _device_diagnostics(
            next(
                device_details
                for device_details in onewire_hub.devices
                if device_details.id[3:] == device_entry.serial_number
            )
        ),
    }
