"""Provides diagnostics for Overkiz."""

from __future__ import annotations

from typing import Any

from pyoverkiz.enums import APIType
from pyoverkiz.obfuscate import obfuscate_id

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from . import HomeAssistantOverkizData
from .const import CONF_API_TYPE, CONF_HUB, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    client = entry_data.coordinator.client

    data = {
        "setup": await client.get_diagnostic_data(),
        "server": entry.data[CONF_HUB],
        "api_type": entry.data.get(CONF_API_TYPE, APIType.CLOUD),
    }

    # Only Overkiz cloud servers expose an endpoint with execution history
    if client.api_type == APIType.CLOUD:
        execution_history = [
            repr(execution) for execution in await client.get_execution_history()
        ]
        data["execution_history"] = execution_history

    return data


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    entry_data: HomeAssistantOverkizData = hass.data[DOMAIN][entry.entry_id]
    client = entry_data.coordinator.client

    device_url = min(device.identifiers)[1]

    data = {
        "device": {
            "controllable_name": device.hw_version,
            "firmware": device.sw_version,
            "device_url": obfuscate_id(device_url),
            "model": device.model,
        },
        "setup": await client.get_diagnostic_data(),
        "server": entry.data[CONF_HUB],
        "api_type": entry.data.get(CONF_API_TYPE, APIType.CLOUD),
    }

    # Only Overkiz cloud servers expose an endpoint with execution history
    if client.api_type == APIType.CLOUD:
        data["execution_history"] = [
            repr(execution)
            for execution in await client.get_execution_history()
            if any(command.device_url == device_url for command in execution.commands)
        ]

    return data
