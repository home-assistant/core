"""Support for the AEMET OpenData diagnostics."""

from __future__ import annotations

from typing import Any

from aemet_opendata.const import AOD_COORDS

from homeassistant.components.diagnostics.util import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN, ENTRY_WEATHER_COORDINATOR
from .coordinator import WeatherUpdateCoordinator

TO_REDACT_CONFIG = [
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
]

TO_REDACT_COORD = [
    AOD_COORDS,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    aemet_entry = hass.data[DOMAIN][config_entry.entry_id]
    coordinator: WeatherUpdateCoordinator = aemet_entry[ENTRY_WEATHER_COORDINATOR]

    return {
        "api_data": coordinator.aemet.raw_data(),
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT_CONFIG),
        "coord_data": async_redact_data(coordinator.data, TO_REDACT_COORD),
    }
