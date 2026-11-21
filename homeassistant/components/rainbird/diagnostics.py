"""Diagnostics support for Rain Bird."""

from typing import Any

from homeassistant.core import HomeAssistant

from .types import RainbirdConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RainbirdConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    model = data.model_info
    state = data.coordinator.data
    schedule = data.schedule_coordinator.data
    return {
        "options": dict(entry.options),
        "model": {
            "model": f"{model.model:04X}",
            "name": model.model_name,
            "firmware": f"{model.major}.{model.minor}",
            "max_programs": model.model_info.max_programs,
            "max_stations": model.model_info.max_stations,
        },
        "state": {
            "zones": sorted(state.zones),
            "active_zones": sorted(state.active_zones),
            "rain": state.rain,
            "rain_delay": state.rain_delay,
        },
        "schedule": schedule.to_dict() if schedule else None,
    }
