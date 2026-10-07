"""Diagnostics support for Axle Energy."""

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AxleConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AxleConfigEntry
) -> dict[str, Any]:
    """Return cached event data without requesting an update."""
    coordinator = entry.runtime_data
    return {
        "last_update_success": coordinator.last_update_success,
        "data": asdict(coordinator.data) if coordinator.data is not None else None,
    }
