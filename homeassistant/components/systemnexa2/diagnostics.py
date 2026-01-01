"""Diagnostics support for System Nexa 2."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import SystemNexa2ConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: SystemNexa2ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data.coordinator

    return {
        "config_entry": dict(entry.data),
        "device_info": asdict(coordinator.data.info_data),
        "available": coordinator.data.available,
        "state": getattr(coordinator.data, "state", None),
        "settings": {
            name: {
                "name": setting.name,
                "current": setting.is_enabled(),
            }
            for name, setting in coordinator.data.on_off_settings.items()
        },
    }
