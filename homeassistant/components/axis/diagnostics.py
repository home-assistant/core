"""Diagnostics support for Axis."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN as AXIS_DOMAIN
from .device import AxisNetworkDevice

REDACT_CONFIG = {CONF_MAC, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME}
REDACT_BASIC_DEVICE_INFO = {"SerialNumber", "SocSerialNumber"}
REDACT_VAPIX_PARAMS = {"root.Network", "System.SerialNumber"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device: AxisNetworkDevice = hass.data[AXIS_DOMAIN][config_entry.unique_id]
    diag: dict[str, Any] = {}

    diag["config"] = async_redact_data(config_entry.as_dict(), REDACT_CONFIG)

    if device.api.vapix.api_discovery:
        diag["api_discovery"] = [
            {"id": api.id, "name": api.name, "version": api.version}
            for api in device.api.vapix.api_discovery.values()
        ]

    if device.api.vapix.basic_device_info:
        diag["basic_device_info"] = async_redact_data(
            {attr.id: attr.raw for attr in device.api.vapix.basic_device_info.values()},
            REDACT_BASIC_DEVICE_INFO,
        )

    if device.api.vapix.params:
        diag["params"] = async_redact_data(
            {param.id: param.raw for param in device.api.vapix.params.values()},
            REDACT_VAPIX_PARAMS,
        )

    return diag
