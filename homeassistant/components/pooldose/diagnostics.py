"""Diagnostics support for Pooldose."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import PooldoseConfigEntry

TO_REDACT = {"IP", "MAC", "SERIAL_NUMBER", "DEVICE_ID", "OWNERID", "NAME", "GROUPNAME"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PooldoseConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return {
        "entry": {
            "title": entry.title,
            "unique_id": entry.unique_id,
            "version": entry.version,
        },
        "device_info": async_redact_data(coordinator.device_info, TO_REDACT),
        "coordinator": {
            "update_interval": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval
                else None
            ),
            "last_update_success": coordinator.last_update_success,
            "last_exception": str(coordinator.last_exception)
            if coordinator.last_exception
            else None,
        },
        "data": coordinator.data,
    }
