"""Diagnostics support for Hisense AC Plugin."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Redact sensitive data
TO_REDACT = {
    "access_token",
    "refresh_token",
    "token",
    "client_secret",
    "puid",
    "deviceId",
    "sourceId",
    "appId",
    "timeStamp",
    "randStr",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    _LOGGER.debug("Getting diagnostics for config entry: %s", config_entry.entry_id)

    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    if not coordinator:
        return {"error": "Coordinator not found"}

    # Get basic config entry data
    config_data = {
        "entry_id": config_entry.entry_id,
        "version": config_entry.version,
        "domain": config_entry.domain,
        "title": config_entry.title,
        "source": config_entry.source,
        "state": config_entry.state.value,
        "options": config_entry.options,
        "pref_disable_new_entities": config_entry.pref_disable_new_entities,
        "pref_disable_polling": config_entry.pref_disable_polling,
    }

    # Get coordinator data
    coordinator_data = {
        "last_update_success": coordinator.last_update_success,
        "last_update_time": coordinator.last_update_time.isoformat() if coordinator.last_update_time else None,
        "update_interval": coordinator.update_interval.total_seconds() if coordinator.update_interval else None,
        "device_count": len(coordinator._devices) if hasattr(coordinator, "_devices") else 0,
    }

    # Get device information
    devices_data = {}
    if hasattr(coordinator, "_devices") and coordinator._devices:
        for device_id, device in coordinator._devices.items():
            devices_data[device_id] = {
                "name": device.name,
                "type_code": device.type_code,
                "feature_code": device.feature_code,
                "feature_name": device.feature_name,
                "online": not getattr(device, "offlineState", False),
                "status_keys": list(device.status.keys()) if hasattr(device, "status") else [],
                "failed_data": device.failed_data if hasattr(device, "failed_data") else [],
            }

    # Get API client information
    api_data = {}
    if hasattr(coordinator, "api_client"):
        api_client = coordinator.api_client
        api_data = {
            "has_auth_provider": api_client.auth_provider is not None,
            "has_oauth_session": api_client.oauth_session is not None,
            "has_config_entry": api_client.config_entry is not None,
            "websocket_connected": getattr(api_client, "_websocket", None) is not None,
            "parsers_count": len(api_client.parsers) if hasattr(api_client, "parsers") else 0,
            "static_data_count": len(api_client.static_data) if hasattr(api_client, "static_data") else 0,
        }

    # Get WebSocket information
    websocket_data = {}
    if hasattr(coordinator, "_websocket") and coordinator._websocket:
        websocket_data = {
            "connected": getattr(coordinator._websocket, "connected", False),
            "reconnect_interval": getattr(coordinator._websocket, "reconnect_interval", None),
        }

    # Combine all data
    diagnostics_data = {
        "config_entry": config_data,
        "coordinator": coordinator_data,
        "devices": devices_data,
        "api_client": api_data,
        "websocket": websocket_data,
    }

    # Redact sensitive data
    return async_redact_data(diagnostics_data, TO_REDACT)


async def async_get_device_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry, device_id: str
) -> dict[str, Any]:
    """Return diagnostics for a specific device."""
    _LOGGER.debug("Getting diagnostics for device: %s", device_id)

    coordinator = hass.data[DOMAIN].get(config_entry.entry_id)
    if not coordinator:
        return {"error": "Coordinator not found"}

    device = coordinator.get_device(device_id)
    if not device:
        return {"error": f"Device {device_id} not found"}

    # Get device information
    device_data = {
        "device_id": device.device_id,
        "puid": device.puid,
        "name": device.name,
        "type_code": device.type_code,
        "feature_code": device.feature_code,
        "feature_name": device.feature_name,
        "online": not getattr(device, "offlineState", False),
        "status": device.status if hasattr(device, "status") else {},
        "failed_data": device.failed_data if hasattr(device, "failed_data") else [],
        "static_data": device.static_data if hasattr(device, "static_data") else {},
    }

    # Get parser information
    parser_data = {}
    if hasattr(coordinator.api_client, "parsers") and device_id in coordinator.api_client.parsers:
        parser = coordinator.api_client.parsers[device_id]
        parser_data = {
            "type": type(parser).__name__,
            "attributes": list(parser.attributes.keys()) if hasattr(parser, "attributes") else [],
        }

    # Combine device data
    diagnostics_data = {
        "device": device_data,
        "parser": parser_data,
    }

    # Redact sensitive data
    return async_redact_data(diagnostics_data, TO_REDACT)
