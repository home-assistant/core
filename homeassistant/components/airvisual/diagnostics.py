"""Diagnostics support for AirVisual."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_STATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CITY, CONF_COUNTRY, DOMAIN

CONF_COORDINATES = "coordinates"


@callback
def _async_redact_data(data: MappingProxyType | dict) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}

    for key, value in redacted.items():
        if key in (
            CONF_API_KEY,
            CONF_CITY,
            CONF_COORDINATES,
            CONF_COUNTRY,
            CONF_LATITUDE,
            CONF_LONGITUDE,
            CONF_STATE,
        ):
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = _async_redact_data(value)

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": _async_redact_data(entry.data),
            "options": _async_redact_data(entry.options),
        },
        "data": _async_redact_data(coordinator.data["data"]),
    }
