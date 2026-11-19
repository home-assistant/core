"""Diagnostics support for Met Office."""

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import MetOfficeConfigEntry, MetOfficeUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MetOfficeConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data

    # The API key, the configured coordinates and name, and the name,
    # coordinates and elevation of the forecast site are left out, as they
    # reveal the location. The forecasts are summarized instead of dumped.
    return {
        "hourly": _coordinator_diagnostics(data.hourly_coordinator),
        "daily": _coordinator_diagnostics(data.daily_coordinator),
        "twice_daily": _coordinator_diagnostics(data.twice_daily_coordinator),
    }


def _coordinator_diagnostics(
    coordinator: MetOfficeUpdateCoordinator,
) -> dict[str, Any]:
    """Return a summary of the forecast of a coordinator."""
    diagnostics: dict[str, Any] = {
        "last_update_success": coordinator.last_update_success,
        "last_update_success_time": (
            coordinator.last_update_success_time.isoformat()
            if coordinator.last_update_success_time is not None
            else None
        ),
    }
    # The twice daily coordinator is only refreshed when its forecast is used
    if (forecast := coordinator.data_or_none) is None:
        diagnostics["forecast"] = None
        return diagnostics
    timesteps = forecast.timesteps
    diagnostics["forecast"] = {
        "frequency": forecast.frequency,
        "model_run_date": forecast.data_date.isoformat(),
        "distance_from_requested_location": forecast.distance_from_requested_location,
        "timesteps": len(timesteps),
        "first_timestep": timesteps[0]["time"].isoformat() if timesteps else None,
        "last_timestep": timesteps[-1]["time"].isoformat() if timesteps else None,
    }
    return diagnostics
