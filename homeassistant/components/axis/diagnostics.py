"""Diagnostics support for Axis."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.system_info import async_get_system_info

from .const import DOMAIN as AXIS_DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device = hass.data[AXIS_DOMAIN][config_entry.unique_id]
    diag: dict[str, Any] = {}

    diag["home_assistant"] = await async_get_system_info(hass)
    diag["config_entry"] = dict(config_entry.data)

    if device.api.vapix.api_discovery:
        diag["api_discovery"] = [
            {"id": api.id, "name": api.name, "version": api.version}
            for api in device.api.vapix.api_discovery.values()
        ]

    if device.api.vapix.basic_device_info:
        diag["basic_device_info"] = {
            attr.id: attr.raw for attr in device.api.vapix.basic_device_info.values()
        }

    if device.api.vapix.params:
        diag["params"] = {
            param.id: param.raw for param in device.api.vapix.params.values()
        }

    return diag
