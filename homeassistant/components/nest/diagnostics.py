"""Diagnostics support for Nest."""

from __future__ import annotations

from google_nest_sdm import diagnostics
from google_nest_sdm.device import Device
from google_nest_sdm.device_traits import InfoTrait
from google_nest_sdm.exceptions import ApiException

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DATA_SDM, DATA_SUBSCRIBER, DOMAIN

REDACT_DEVICE_TRAITS = {InfoTrait.NAME}


async def _get_nest_devices(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Device]:
    """Return dict of available devices."""
    if DATA_SDM not in config_entry.data:
        return {}

    if DATA_SUBSCRIBER not in hass.data[DOMAIN]:
        return {}

    subscriber = hass.data[DOMAIN][DATA_SUBSCRIBER]
    device_manager = await subscriber.async_get_device_manager()
    devices: dict[str, Device] = device_manager.devices
    return devices


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    try:
        nest_devices = await _get_nest_devices(hass, config_entry)
    except ApiException as err:
        return {"error": str(err)}
    if not nest_devices:
        return {}
    return {
        **diagnostics.get_diagnostics(),
        "devices": [
            nest_device.get_diagnostics() for nest_device in nest_devices.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device: DeviceEntry,
) -> dict:
    """Return diagnostics for a device."""
    try:
        nest_devices = await _get_nest_devices(hass, config_entry)
    except ApiException as err:
        return {"error": str(err)}
    nest_device_id = next(iter(device.identifiers))[1]
    nest_device = nest_devices.get(nest_device_id)
    return nest_device.get_diagnostics() if nest_device else {}
