"""Diagnostics support for the IRM KMI integration."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_LOCATION, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from .coordinator import IrmKmiConfigEntry

# The unique ID and the title hold the resolved city name.
TO_REDACT = {CONF_LOCATION, CONF_UNIQUE_ID, "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IrmKmiConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    weather = entry.runtime_data.weather
    pollen = entry.runtime_data.pollen
    data = weather.data

    # Fields are listed one by one so new ones are not exposed by accident.
    return {
        "config_entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "weather": {
            "last_update_success": weather.last_update_success,
            "current_weather": data.current_weather,
            "country": data.country,
            "warnings": data.warnings,
            "radar_forecast": data.radar_forecast,
            "hourly_forecast": data.hourly_forecast,
            "daily_forecast": data.daily_forecast,
        },
        "pollen": {
            "last_update_success": pollen.last_update_success,
            "levels": pollen.data,
        },
    }
