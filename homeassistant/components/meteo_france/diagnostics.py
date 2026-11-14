"""Diagnostics support for Meteo-France."""

from typing import Any

from meteofrance_api.model import Forecast, Rain

from homeassistant.core import HomeAssistant

from .coordinator import MeteoFranceConfigEntry

# Position keys that help debugging without revealing the configured location
POSITION_KEYS = {"country", "dept", "rain_product_available", "timezone"}


def _without_location(data: Forecast | Rain) -> dict[str, Any]:
    """Return raw data with only non-identifying position fields."""
    return {
        **data.raw_data,
        "position": {
            key: value for key, value in data.position.items() if key in POSITION_KEYS
        },
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MeteoFranceConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = entry.runtime_data
    return {
        "options": dict(entry.options),
        "forecast": _without_location(data.forecast_coordinator.data),
        "rain": (
            _without_location(data.rain_coordinator.data)
            if data.rain_coordinator
            else None
        ),
        "alert": (
            data.alert_coordinator.data.raw_data if data.alert_coordinator else None
        ),
    }
