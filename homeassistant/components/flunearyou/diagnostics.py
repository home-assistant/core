"""Diagnostics support for Flu Near You."""
from __future__ import annotations

from types import MappingProxyType
from typing import Any

from homeassistant.components.diagnostics import REDACTED
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

CONF_COORDINATES = "coordinates"


@callback
def _async_redact_data(data: MappingProxyType | dict) -> dict[str, Any]:
    """Redact sensitive data in a dict."""
    redacted = {**data}

    for key, value in redacted.items():
        if key in (CONF_LATITUDE, CONF_LONGITUDE):
            redacted[key] = REDACTED
        elif isinstance(value, dict):
            redacted[key] = _async_redact_data(value)

    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {}
    # return {
    #     "entry": {
    #         "title": entry.title,
    #         "data": _async_redact_data(entry.data),
    #     },
    #     "data": {
    #         api_category: _async_redact_data(coordinator.data)
    #         for api_category, coordinator in coordinators.items()
    #     },
    # }
