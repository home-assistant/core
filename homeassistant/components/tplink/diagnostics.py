"""Diagnostics support for TPLink."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TPLinkDataUpdateCoordinator

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
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TPLinkDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(
        {"device_last_response": coordinator.device.internal_state}, TO_REDACT
    )
