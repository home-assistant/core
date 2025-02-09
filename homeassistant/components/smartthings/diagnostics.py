"""Diagnostics support for SmartThings."""

from __future__ import annotations

from typing import Any

import orjson

from homeassistant.core import HomeAssistant

from . import CONF_LOCATION_ID
from .coordinator import SmartThingsConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SmartThingsConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client = entry.runtime_data.client
    location_id = entry.data[CONF_LOCATION_ID]

    raw_device_list = await client._get("devices", params={"locationId": location_id})  # noqa: SLF001
    resp = orjson.loads(raw_device_list)

    raw_devices = {}

    for device in resp["items"]:
        device_id = device["deviceId"]
        raw_device = await client._get(f"devices/{device_id}/status")  # noqa: SLF001
        raw_devices[device_id] = orjson.loads(raw_device)

    return {
        "device_list": resp,
        "devices": raw_devices,
    }
