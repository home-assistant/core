"""Diagnostics support for IKEA Tradfri."""
from __future__ import annotations

from pytradfri import Gateway, PytradfriError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_GATEWAY_ID,
    COORDINATOR,
    COORDINATOR_LIST,
    DOMAIN,
    GROUPS_LIST,
    KEY_API,
    TIMEOUT_API,
)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics the Tradfri platform."""
    _entry_data = hass.data[DOMAIN][entry.entry_id]

    _coordinator_data = _entry_data[COORDINATOR]

    _api = _coordinator_data[KEY_API]
    _gateway: Gateway = _coordinator_data[CONF_GATEWAY_ID]

    try:
        _gateway_info = await _api(_gateway.get_gateway_info(), timeout=TIMEOUT_API)
        _fw_version = _gateway_info.firmware_version
    except PytradfriError:
        _fw_version = "Not available"

    _device_data: list = []
    for coordinator in _coordinator_data[COORDINATOR_LIST]:
        _device_data.append(coordinator.device.device_info.model_number)

    return {
        "gateway_version": _fw_version,
        "device_data": sorted(_device_data),
        "no_of_groups": len(_coordinator_data[GROUPS_LIST]),
    }
