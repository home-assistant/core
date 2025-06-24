"""Diagnostics support for fibaro integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import CONF_IMPORT_PLUGINS, FibaroConfigEntry

TO_REDACT = {"password"}


def _create_diagnostics_data(
    config_entry: FibaroConfigEntry, devices: list[DeviceModel]
) -> dict[str, Any]:
    """Combine diagnostics information and redact sensitive information."""
    return {
        "config": {CONF_IMPORT_PLUGINS: config_entry.data.get(CONF_IMPORT_PLUGINS)},
        "fibaro_devices": async_redact_data([d.raw_data for d in devices], TO_REDACT),
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: FibaroConfigEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a config entry."""
    controller = config_entry.runtime_data
    devices = controller.get_all_devices()
    return _create_diagnostics_data(config_entry, devices)


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: FibaroConfigEntry, device: DeviceEntry
) -> Mapping[str, Any]:
    """Return diagnostics for a device."""
    controller = config_entry.runtime_data
    devices = controller.get_all_devices()

    ha_device_id = next(iter(device.identifiers))[1]
    if ha_device_id == controller.hub_serial:
        # special case where the device is representing the fibaro hub
        return _create_diagnostics_data(config_entry, devices)

    # normal devices are represented by a parent / child structure
    filtered_devices = [
        device
        for device in devices
        if ha_device_id in (device.fibaro_id, device.parent_fibaro_id)
    ]
    return _create_diagnostics_data(config_entry, filtered_devices)
