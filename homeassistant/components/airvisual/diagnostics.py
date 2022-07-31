"""Diagnostics support for AirVisual."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_STATE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CITY, CONF_COUNTRY, DOMAIN

CONF_COORDINATES = "coordinates"

TO_REDACT = {
    CONF_API_KEY,
    CONF_CITY,
    CONF_COORDINATES,
    CONF_COUNTRY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_STATE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": async_redact_data(entry.options, TO_REDACT),
        },
        "data": async_redact_data(coordinator.data["data"], TO_REDACT),
    }
