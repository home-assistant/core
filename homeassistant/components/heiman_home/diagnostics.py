"""Diagnostics utilities for Heiman Home integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_EMAIL, CONF_PASSWORD, DOMAIN

_LOGGER = logging.getLogger(__name__)

# Redact sensitive data
TO_REDACT = {
    CONF_EMAIL,
    CONF_PASSWORD,
    "accessToken",
    "access_token",
    "token",
    "password",
    "userName",
    "userId",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_id = config_entry.entry_id

    # Get integration data
    data = hass.data.get(DOMAIN, {})
    client = data.get("clients", {}).get(entry_id)
    devices = data.get("devices", {}).get(entry_id, {})

    diagnostics_data = {
        "entry_id": entry_id,
        "config": dict(config_entry.data),
    }

    # Add client info if available
    if client:
        diagnostics_data["client"] = {
            "user_id": client.user_id,
            "home_id": client.home_id,
            "api_url": client.api_url,
            "authenticated": client.access_token is not None,
            "device_count": len(client.devices),
        }

        # Add MQTT info if available
        if client.mqtt_client:
            diagnostics_data["mqtt"] = {
                "connected": client.mqtt_client.connected,
                "broker": client.mqtt_client.broker,
                "port": client.mqtt_client.port,
            }

    # Add device summary
    diagnostics_data["devices_summary"] = {
        "total_devices": len(devices),
        "device_ids": list(devices.keys()),
    }

    # Add first few devices with details
    device_samples = {}
    for idx, (did, device) in enumerate(devices.items()):
        if idx >= 3:  # Limit to 3 sample devices
            break

        # Try to get firmware version from runtime device object if available
        firmware_version = None
        heiman_devices = hass.data.get(DOMAIN, {}).get("heiman_devices", {})
        if entry_id in heiman_devices and did in heiman_devices[entry_id]:
            heiman_device = heiman_devices[entry_id][did]
            if hasattr(heiman_device, "firmware_version"):
                firmware_version = heiman_device.firmware_version

        device_samples[did] = {
            "device_id": did,
            "product_id": device.get("productId"),
            "device_name": device.get("deviceName"),
            "device_type": device.get("deviceType"),
            "online": device.get("online"),
            "firmware_version": firmware_version or device.get("sw_version", "N/A"),
        }

    if device_samples:
        diagnostics_data["device_samples"] = device_samples

    # Redact sensitive information
    return async_redact_data(diagnostics_data, TO_REDACT)
