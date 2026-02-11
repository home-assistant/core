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

    # Build diagnostic data from both coordinators
    diagnostics = {
        "info": data.info.to_dict(),
        "device": data.device.to_dict(),
        "fast_coordinator_data": {
            "state": data.fast_coordinator.data.state.to_dict(),
            "sensor": data.fast_coordinator.data.sensor.to_dict(),
            "dhw": data.fast_coordinator.data.dhw.to_dict(),
        },
        "static": data.static.to_dict(),
    }

    # Add DHW config and schedule from slow coordinator if available
    if data.slow_coordinator.data:
        slow_data = {}
        if data.slow_coordinator.data.dhw_config:
            slow_data["dhw_config"] = data.slow_coordinator.data.dhw_config.to_dict()
        if data.slow_coordinator.data.dhw_schedule:
            slow_data["dhw_schedule"] = (
                data.slow_coordinator.data.dhw_schedule.to_dict()
            )
        if slow_data:
            diagnostics["slow_coordinator_data"] = slow_data

    return diagnostics
