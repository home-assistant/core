"""Diagnostics support for IPMA."""

from __future__ import annotations

from typing import Any

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import IpmaConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: IpmaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    location = entry.runtime_data.location
    api = entry.runtime_data.api

    return {
        "location_information": {
            "latitude": round(float(entry.data[CONF_LATITUDE]), 3),
            "longitude": round(float(entry.data[CONF_LONGITUDE]), 3),
            "global_id_local": location.global_id_local,
            "id_station": location.id_station,
            "name": location.name,
            "station": location.station,
        },
        "current_weather": await location.observation(api),
        "weather_forecast": await location.forecast(api, 1),
    }
