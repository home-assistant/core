"""Diagnostics support for Axis."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_MAC, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import AxisConfigEntry

REDACT_CONFIG = {CONF_MAC, CONF_PASSWORD, CONF_UNIQUE_ID, CONF_USERNAME}
REDACT_BASIC_DEVICE_INFO = {"SerialNumber", "SocSerialNumber"}
REDACT_VAPIX_PARAMS = {"root.Network", "System.SerialNumber"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AxisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    hub = config_entry.runtime_data
    diag: dict[str, Any] = hub.additional_diagnostics.copy()

    diag["config"] = async_redact_data(config_entry.as_dict(), REDACT_CONFIG)

    if hub.api.vapix.api_discovery:
        diag["api_discovery"] = [
            {"id": api.id, "name": api.name, "version": api.version}
            for api in hub.api.vapix.api_discovery.values()
        ]

    if hub.api.vapix.basic_device_info:
        diag["basic_device_info"] = async_redact_data(
            hub.api.vapix.basic_device_info["0"],
            REDACT_BASIC_DEVICE_INFO,
        )

    if hub.api.vapix.params:
        diag["params"] = async_redact_data(
            hub.api.vapix.params.items(),
            REDACT_VAPIX_PARAMS,
        )

    return diag
