"""Diagnostics for the Subaru integration."""

from __future__ import annotations

from typing import Any

from subarulink.const import (
    LATITUDE,
    LONGITUDE,
    ODOMETER,
    RAW_API_FIELDS_TO_REDACT,
    VEHICLE_NAME,
)

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, ENTRY_CONTROLLER, ENTRY_COORDINATOR, VEHICLE_VIN

CONFIG_FIELDS_TO_REDACT = [CONF_USERNAME, CONF_PASSWORD, CONF_PIN, CONF_DEVICE_ID]
DATA_FIELDS_TO_REDACT = [VEHICLE_VIN, VEHICLE_NAME, LATITUDE, LONGITUDE, ODOMETER]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id][ENTRY_COORDINATOR]

    return {
        "config_entry": async_redact_data(config_entry.data, CONFIG_FIELDS_TO_REDACT),
        "options": async_redact_data(config_entry.options, []),
        "data": [
            async_redact_data(info, DATA_FIELDS_TO_REDACT)
            for info in coordinator.data.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = entry[ENTRY_COORDINATOR]
    controller = entry[ENTRY_CONTROLLER]

    vin = next(iter(device.identifiers))[1]

    if info := coordinator.data.get(vin):
        return {
            "config_entry": async_redact_data(
                config_entry.data, CONFIG_FIELDS_TO_REDACT
            ),
            "options": async_redact_data(config_entry.options, []),
            "data": async_redact_data(info, DATA_FIELDS_TO_REDACT),
            "raw_data": async_redact_data(
                controller.get_raw_data(vin), RAW_API_FIELDS_TO_REDACT
            ),
        }

    raise HomeAssistantError("Device not found")
