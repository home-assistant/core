"""Diagnostics support for Tomorrow.io."""

from typing import Any

from pytomorrowio.const import CURRENT, DAILY, FORECASTS, HOURLY, NOWCAST

from homeassistant.core import HomeAssistant

from .const import CONF_TIMESTEP, SUBENTRY_TYPE_LOCATION
from .coordinator import TomorrowioConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: TomorrowioConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    # The API key, the coordinates and the names of the locations are left
    # out. Locations are emitted as a list instead of a dict keyed by subentry
    # ID, and the forecasts are summarized instead of dumped, as they hold
    # hundreds of entries per location.
    locations: list[dict[str, Any]] = []
    for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_LOCATION):
        data: dict[str, Any] = coordinator.data.get(subentry.subentry_id) or {}
        current: dict[str, Any] = data.get(CURRENT) or {}
        forecasts: dict[str, Any] = data.get(FORECASTS) or {}
        locations.append(
            {
                "timestep": subentry.data[CONF_TIMESTEP],
                "current_fields": sorted(
                    key for key, value in current.items() if value is not None
                ),
                "forecasts": {
                    forecast_type: _summarize_forecast(forecasts.get(forecast_type))
                    for forecast_type in (NOWCAST, HOURLY, DAILY)
                },
            }
        )

    return {
        "last_update_success": coordinator.last_update_success,
        "update_interval": (
            coordinator.update_interval.total_seconds()
            if coordinator.update_interval is not None
            else None
        ),
        "locations": locations,
    }


def _summarize_forecast(forecast: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Summarize a forecast to its size and time range."""
    if not forecast:
        return {"count": 0}
    return {
        "count": len(forecast),
        "first_start_time": forecast[0].get("startTime"),
        "last_start_time": forecast[-1].get("startTime"),
    }
