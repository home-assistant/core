"""Diagnostics support for BSBLan."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from . import BSBLanConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BSBLanConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    # Build diagnostic data
    diagnostics = {
        "info": data.info.to_dict(),
        "device": data.device.to_dict(),
        "coordinator_data": {
            "state": data.coordinator.data.state.to_dict(),
            "sensor": data.coordinator.data.sensor.to_dict(),
            "dhw": data.coordinator.data.dhw.to_dict(),
        },
        "static": data.static.to_dict(),
    }

    # Add DHW config and schedule if available
    if data.coordinator.data.dhw_config:
        diagnostics["coordinator_data"]["dhw_config"] = (
            data.coordinator.data.dhw_config.to_dict()
        )
    if data.coordinator.data.dhw_schedule:
        diagnostics["coordinator_data"]["dhw_schedule"] = (
            data.coordinator.data.dhw_schedule.to_dict()
        )

    return diagnostics
