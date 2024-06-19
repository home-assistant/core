"""Diagnostics support for TPLink."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

from . import TPLinkConfigEntry

TO_REDACT = {
    # Entry fields
    "unique_id",  # based on mac address
    # Device identifiers
    "alias",
    "mac",
    "mic_mac",
    "host",
    "hwId",
    "oemId",
    "deviceId",
    # Device location
    "latitude",
    "latitude_i",
    "longitude",
    "longitude_i",
    # Cloud connectivity info
    "username",
    # SMART devices
    "device_id",
    "hw_id",
    "fw_id",
    "oem_id",
    "ssid",
    "nickname",
    "ip",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TPLinkConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    coordinator = data.parent_coordinator
    oui = format_mac(coordinator.device.mac)[:8].upper()
    return async_redact_data(
        {"device_last_response": coordinator.device.internal_state, "oui": oui},
        TO_REDACT,
    )
