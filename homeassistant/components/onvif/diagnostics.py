"""Diagnostics support for ONVIF."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .device import ONVIFDevice

REDACT_CONFIG = {CONF_HOST, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device: ONVIFDevice = hass.data[DOMAIN][entry.unique_id]
    data: dict[str, Any] = {}

    data["config"] = async_redact_data(entry.as_dict(), REDACT_CONFIG)
    data["device"] = {
        "info": asdict(device.info),
        "capabilities": asdict(device.capabilities),
        "profiles": [asdict(profile) for profile in device.profiles],
        "services": {
            str(key): service.url for key, service in device.device.services.items()
        },
        "xaddrs": device.device.xaddrs,
    }
    data["events"] = {
        "webhook_manager_state": device.events.webhook_manager.state,
        "pullpoint_manager_state": device.events.pullpoint_manager.state,
    }

    return data
