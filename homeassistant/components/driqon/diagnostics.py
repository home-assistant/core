"""Redacted Home Assistant diagnostics for DRIQON."""
from __future__ import annotations

from urllib.parse import urlsplit

from homeassistant.core import HomeAssistant

from . import DriqonConfigEntry, DriqonRuntimeData
from .const import DEFAULT_API_URL


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: DriqonConfigEntry,
) -> dict[str, object]:
    """Return account-independent status and device metadata only."""
    runtime: DriqonRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    api_host = urlsplit(DEFAULT_API_URL).hostname
    devices = coordinator.data or {}
    return {
        "api_host": api_host,
        "last_update_success": coordinator.last_update_success,
        "device_count": len(devices),
        "devices": [
            {
                "device_type": device.get("device_type"),
                "status": device.get("status"),
                "permission": device.get("permission"),
                "is_shared": device.get("is_shared"),
                "capabilities": device.get("capabilities", []),
            }
            for device in devices.values()
        ],
    }
