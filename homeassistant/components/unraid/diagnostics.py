"""Diagnostics support for Unraid integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from . import UnraidConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Use runtime_data (HA 2024.4+ pattern)
    runtime_data = entry.runtime_data
    server_info = runtime_data.server_info
    system_coordinator = runtime_data.system_coordinator
    storage_coordinator = runtime_data.storage_coordinator

    return {
        "entry_id": entry.entry_id,
        "title": entry.title,
        "version": entry.version,
        "server_info": {
            "uuid": server_info.get("uuid"),
            "hostname": server_info.get("name"),
            "manufacturer": server_info.get("manufacturer"),
            "model": server_info.get("model"),
            "sw_version": server_info.get("sw_version"),
            "api_version": server_info.get("api_version"),
            "license_type": server_info.get("license_type"),
        },
        "system_coordinator": {
            "last_update_success": system_coordinator.last_update_success,
            "last_update_time": str(system_coordinator.last_update_success_time)
            if hasattr(system_coordinator, "last_update_success_time")
            else None,
        },
        "storage_coordinator": {
            "last_update_success": storage_coordinator.last_update_success,
            "last_update_time": str(storage_coordinator.last_update_success_time)
            if hasattr(storage_coordinator, "last_update_success_time")
            else None,
        },
    }
