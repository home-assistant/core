"""Diagnostics support for DayBetter Services."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    DeviceEntry,
    async_get as async_get_device_registry,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Getting config entry diagnostics for %s", config_entry.entry_id)

    if DOMAIN not in hass.data:
        return {"error": "Integration not loaded"}

    entry_data = hass.data[DOMAIN].get(config_entry.entry_id)
    if not entry_data:
        return {"error": "No entry data found"}

    diagnostics_data = {
        "config_entry": {
            "entry_id": config_entry.entry_id,
            "version": config_entry.version,
            "domain": config_entry.domain,
            "title": config_entry.title,
            "data": {
                "user_code": config_entry.data.get("user_code", "***"),
                "token": config_entry.data.get("token", "***")[:10] + "..."
                if config_entry.data.get("token")
                else None,
            },
            "options": config_entry.options,
            "pref_disable_new_entities": config_entry.pref_disable_new_entities,
            "pref_disable_polling": config_entry.pref_disable_polling,
            "source": config_entry.source,
            "state": config_entry.state.value if config_entry.state else None,
        },
        "integration_data": {
            "api_available": "api" in entry_data,
            "mqtt_manager_available": "mqtt_manager" in entry_data,
            "devices_count": len(entry_data.get("devices", [])),
            "services_registered": hass.data[DOMAIN].get("services_registered", False),
        },
    }

    # Add API diagnostics if available
    if "api" in entry_data:
        api = entry_data["api"]
        diagnostics_data["api"] = {
            "authenticated": api.is_authenticated
            if hasattr(api, "is_authenticated")
            else "unknown",
            "token_length": len(api.token) if hasattr(api, "token") else 0,
        }

    # Add MQTT manager diagnostics if available
    if "mqtt_manager" in entry_data:
        mqtt_manager = entry_data["mqtt_manager"]
        diagnostics_data["mqtt"] = {
            "connected": getattr(mqtt_manager, "_connected", False),
            "connection_attempts": getattr(mqtt_manager, "_connection_attempts", 0),
            "last_connection_attempt": getattr(
                mqtt_manager, "_last_connection_attempt", None
            ),
        }

    # Add devices diagnostics
    devices = entry_data.get("devices", [])
    if devices:
        diagnostics_data["devices"] = []
        for device in devices:
            device_diagnostics = {
                "device_id": device.get("deviceId"),
                "device_name": device.get("deviceName"),
                "device_type": device.get("deviceType"),
                "online": device.get("online"),
                "mac": device.get("mac"),
                "device_group_id": device.get("deviceGroupId"),
                "device_mold_pid": device.get("deviceMoldPid"),
            }
            diagnostics_data["devices"].append(device_diagnostics)

    return diagnostics_data


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device: DeviceEntry
) -> dict[str, Any]:
    """Return diagnostics for a device."""
    _LOGGER.debug("Getting device diagnostics for %s", device.id)

    if DOMAIN not in hass.data:
        return {"error": "Integration not loaded"}

    entry_data = hass.data[DOMAIN].get(config_entry.entry_id)
    if not entry_data:
        return {"error": "No entry data found"}

    # Find the device data
    devices = entry_data.get("devices", [])
    device_data = None
    for dev in devices:
        if dev.get("deviceId") in device.identifiers:
            device_data = dev
            break

    if not device_data:
        return {"error": "Device data not found"}

    diagnostics_data = {
        "device_info": {
            "id": device.id,
            "name": device.name,
            "model": device.model,
            "manufacturer": device.manufacturer,
            "sw_version": device.sw_version,
            "hw_version": device.hw_version,
            "identifiers": list(device.identifiers),
            "connections": list(device.connections),
        },
        "device_data": device_data,
        "entities": [],
    }

    # Add entity information
    device_registry = async_get_device_registry(hass)
    for entity_id in device.identifiers:
        # Find entities for this device
        for entity in hass.states.async_all():
            if (
                hasattr(entity, "attributes")
                and entity.attributes.get("device_id") == device.id
            ):
                entity_info = {
                    "entity_id": entity.entity_id,
                    "state": entity.state,
                    "attributes": dict(entity.attributes),
                }
                diagnostics_data["entities"].append(entity_info)

    return diagnostics_data
