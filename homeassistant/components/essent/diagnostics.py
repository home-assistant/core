"""Diagnostics support for Essent integration."""

from __future__ import annotations

from typing import Any
from homeassistant.core import HomeAssistant

from .coordinator import EssentConfigEntry, EssentDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: EssentConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: EssentDataUpdateCoordinator = entry.runtime_data

    return {
        "coordinator_data": coordinator.data if coordinator.data else None,
        "last_update_success": coordinator.last_update_success,
        "api_fetch_minute_offset": coordinator.api_fetch_minute_offset,
        "api_refresh_scheduled": coordinator.api_refresh_scheduled,
        "listener_tick_scheduled": coordinator.listener_tick_scheduled,
    }
