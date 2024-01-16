"""Diagnostics support for Ring."""
from __future__ import annotations

from typing import Any

import ring_doorbell

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

TO_REDACT = {
    "id",
    "device_id",
    "description",
    "first_name",
    "last_name",
    "email",
    "location_id",
    "ring_net_id",
    "wifi_name",
    "latitude",
    "longitude",
    "address",
    "ring_id",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    ring: ring_doorbell.Ring = hass.data[DOMAIN][entry.entry_id]["api"]
    devices_raw = []
    for device_type in ring.devices_data:
        for device_id in ring.devices_data[device_type]:
            devices_raw.append(ring.devices_data[device_type][device_id])
    return async_redact_data(
        {"device_data": devices_raw},
        TO_REDACT,
    )
