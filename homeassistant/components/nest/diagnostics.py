"""Diagnostics support for Nest."""

from __future__ import annotations

from typing import Any

from google_nest_sdm import diagnostics
from google_nest_sdm.device_traits import InfoTrait

from homeassistant.components.camera import diagnostics as camera_diagnostics
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .types import NestConfigEntry

REDACT_DEVICE_TRAITS = {InfoTrait.NAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: NestConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if (
        not hasattr(config_entry, "runtime_data")
        or not config_entry.runtime_data
        or not (nest_devices := config_entry.runtime_data.device_manager.devices)
    ):
        return {}
    data: dict[str, Any] = {
        **diagnostics.get_diagnostics(),
        "devices": [
            nest_device.get_diagnostics() for nest_device in nest_devices.values()
        ],
    }
    camera_data = await camera_diagnostics.async_get_config_entry_diagnostics(
        hass, config_entry
    )
    if camera_data:
        data["camera"] = camera_data
    return data


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: NestConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    nest_devices = config_entry.runtime_data.device_manager.devices
    nest_device_id = next(iter(device.identifiers))[1]
    nest_device = nest_devices.get(nest_device_id)
    return nest_device.get_diagnostics() if nest_device else {}
