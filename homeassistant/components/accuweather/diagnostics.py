"""Diagnostics support for AccuWeather."""
from __future__ import annotations

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import AccuWeatherDataUpdateCoordinator
from .const import DOMAIN

TO_REDACT = {CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict:
    """Return diagnostics for a config entry."""
    coordinator: AccuWeatherDataUpdateCoordinator = hass.data[DOMAIN][
        config_entry.entry_id
    ]

    diagnostics_data = {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "coordinator_data": coordinator.data,
    }

    return diagnostics_data
