"""Diagnostics support for BSBLan."""

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
        "info": data.info.model_dump(),
        "device": data.device.model_dump(),
        "fast_coordinator_data": {
            "states": {
                str(circuit): state.model_dump()
                for circuit, state in data.fast_coordinator.data.states.items()
            },
            "sensor": data.fast_coordinator.data.sensor.model_dump(),
            "dhw": data.fast_coordinator.data.dhw.model_dump()
            if data.fast_coordinator.data.dhw
            else None,
        },
        "static": {
            str(circuit): static.model_dump() if static is not None else None
            for circuit, static in data.static.items()
        },
        "available_circuits": data.available_circuits,
    }

    # Add DHW config and schedule from slow coordinator if available
    if slow_coordinator_data := data.slow_coordinator.data_or_none:
        slow_data = {}
        if slow_coordinator_data.dhw_config:
            slow_data["dhw_config"] = slow_coordinator_data.dhw_config.model_dump()
        if slow_coordinator_data.dhw_schedule:
            slow_data["dhw_schedule"] = slow_coordinator_data.dhw_schedule.model_dump()
        if slow_coordinator_data.heating_schedule:
            slow_data["heating_schedule"] = {
                str(circuit): schedule.model_dump()
                for circuit, schedule in slow_coordinator_data.heating_schedule.items()
            }
        if slow_data:
            diagnostics["slow_coordinator_data"] = slow_data

    return diagnostics
