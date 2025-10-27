"""Diagnostics support for Bbox."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import BboxConfigEntry

TO_REDACT = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BboxConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    router_info = coordinator.data.router_info if coordinator.data else None
    return {
        "entry": {
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
            "title": entry.title,
            "unique_id": entry.unique_id,
        },
        "data": {
            "router_info": {
                "model": router_info.modelname if router_info else None,
                "serial": router_info.serialnumber if router_info else None,
                "version": router_info.main.version if router_info else None,
            },
            "connected_devices_count": len(coordinator.data.connected_devices)
            if coordinator.data
            else 0,
            "last_update_success": coordinator.last_update_success,
        },
    }
