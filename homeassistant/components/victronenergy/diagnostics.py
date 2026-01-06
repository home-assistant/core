"""Diagnostics support for Victron Energy."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.redact import async_redact_data

from .const import CONF_TOKEN, DOMAIN

TO_REDACT = {CONF_TOKEN, "token", "ha_device_id", "password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    
    data = {}
    if manager:
        data = {
            "device_registry_count": len(manager._device_registry),
            "entity_registry_count": len(manager._entity_registry), 
            "topic_device_map_count": len(manager._topic_device_map),
            "topic_payload_cache_count": len(manager._topic_payload_cache),
            "connection_state": "connected" if manager.client else "disconnected",
        }

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": data,
    }


async def async_get_device_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry, device: dr.DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device entry."""
    manager = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    
    device_data = {}
    if manager:
        # Find device data in manager registries
        for identifier in device.identifiers:
            if identifier[0] == DOMAIN:
                device_id = identifier[1]
                device_data = {
                    "device_id": device_id,
                    "has_device_data": device_id in manager._device_registry,
                    "entity_count": len([
                        entity_id for entity_id, dev_id in manager._entity_registry.items()
                        if dev_id == device_id
                    ]),
                }
                break

    return {
        "device_info": {
            "identifiers": list(device.identifiers),
            "name": device.name,
            "manufacturer": device.manufacturer,
            "model": device.model,
            "sw_version": device.sw_version,
        },
        "device_data": device_data,
    }