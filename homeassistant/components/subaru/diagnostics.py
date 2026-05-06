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

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_DEVICE_ID, CONF_PASSWORD, CONF_PIN, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntry

from .const import VEHICLE_VIN
from .coordinator import SubaruConfigEntry

CONFIG_FIELDS_TO_REDACT = [CONF_USERNAME, CONF_PASSWORD, CONF_PIN, CONF_DEVICE_ID]
DATA_FIELDS_TO_REDACT = [VEHICLE_VIN, VEHICLE_NAME, LATITUDE, LONGITUDE, ODOMETER]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: SubaruConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data.coordinator

    return {
        "config_entry": async_redact_data(config_entry.data, CONFIG_FIELDS_TO_REDACT),
        "options": async_redact_data(config_entry.options, []),
        "data": [
            async_redact_data(info, DATA_FIELDS_TO_REDACT)
            for info in coordinator.data.values()
        ],
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: SubaruConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    coordinator = config_entry.runtime_data.coordinator
    controller = config_entry.runtime_data.controller

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
