"""Provides diagnostics for Ohme."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import OhmeConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: OhmeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for Ohme."""
    coordinators = config_entry.runtime_data
    client = coordinators.charge_session_coordinator.client

    return {
        "device_info": client.device_info,
        "vehicles": client.vehicles,
        "ct_connected": client.ct_connected,
        "cap_available": client.cap_available,
    }
