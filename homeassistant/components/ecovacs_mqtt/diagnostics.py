"""Diagnostics support for Ecovacs mqtt."""
from __future__ import annotations

import logging
from typing import Any

from deebot_client.device import Device

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import DOMAIN
from .controller import EcovacsController

REDACT_CONFIG = {CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, "title"}
REDACT_DEVICE = {"did", "name", "homeId"}

_LOGGER = logging.getLogger(__name__)


def _get_device_info(
    devices: list[Device], device_entry: DeviceEntry
) -> dict[str, str]:
    """Get the device info for the given entry."""
    identifiers = (identifier[1] for identifier in device_entry.identifiers)

    for device in devices:
        info = device.device_info
        if info.did in identifiers:
            return async_redact_data(info.api_device_info, REDACT_DEVICE)

    _LOGGER.error("Could not find the device with entry: %s", device_entry.json_repr)
    return {"error": "Could not find the device"}


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    controller: EcovacsController = hass.data[DOMAIN][config_entry.entry_id]
    diag: dict[str, Any] = {
        "config": async_redact_data(config_entry.as_dict(), REDACT_CONFIG),
        "devices": len(controller.devices),
        "device": _get_device_info(controller.devices, device),
    }
    return diag
