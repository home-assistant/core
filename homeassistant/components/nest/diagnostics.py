"""Diagnostics support for Nest."""

from __future__ import annotations

from typing import Any

from google_nest_sdm import diagnostics
from google_nest_sdm.device import Device
from google_nest_sdm.device_manager import DeviceManager
from google_nest_sdm.device_traits import InfoTrait

from homeassistant.components.camera import diagnostics as camera_diagnostics
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DATA_DEVICE_MANAGER, DATA_SDM, DOMAIN

REDACT_DEVICE_TRAITS = {InfoTrait.NAME}


@callback
def _async_get_nest_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Device]:
    """Return dict of available devices."""
    if DATA_SDM not in config_entry.data:
        return {}

    if (
        config_entry.entry_id not in hass.data[DOMAIN]
        or DATA_DEVICE_MANAGER not in hass.data[DOMAIN][config_entry.entry_id]
    ):
        return {}

    device_manager: DeviceManager = hass.data[DOMAIN][config_entry.entry_id][
        DATA_DEVICE_MANAGER
    ]
    return device_manager.devices


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    nest_devices = _async_get_nest_devices(hass, config_entry)
    if not nest_devices:
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
    config_entry: ConfigEntry,
    device: DeviceEntry,
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    nest_devices = _async_get_nest_devices(hass, config_entry)
    nest_device_id = next(iter(device.identifiers))[1]
    nest_device = nest_devices.get(nest_device_id)
    return nest_device.get_diagnostics() if nest_device else {}
