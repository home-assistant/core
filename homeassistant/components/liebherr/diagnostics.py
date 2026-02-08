"""Diagnostics support for Liebherr."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from .coordinator import LiebherrConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: LiebherrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "devices": {
            device_id: {
                "coordinator": {
                    "last_update_success": coordinator.last_update_success,
                    "update_interval": str(coordinator.update_interval),
                    "last_exception": str(coordinator.last_exception)
                    if coordinator.last_exception
                    else None,
                },
                "data": asdict(coordinator.data),
            }
            for device_id, coordinator in entry.runtime_data.items()
        },
    }
