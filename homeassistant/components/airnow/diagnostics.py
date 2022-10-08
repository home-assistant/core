"""Diagnostics support for AirNow."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import AirNowDataUpdateCoordinator
from .const import DOMAIN

ATTR_LATITUDE_CAP = "Latitude"
ATTR_LONGITUDE_CAP = "Longitude"
ATTR_REPORTING_AREA = "ReportingArea"
ATTR_STATE_CODE = "StateCode"

TO_REDACT = {
    ATTR_LATITUDE_CAP,
    ATTR_LONGITUDE_CAP,
    ATTR_REPORTING_AREA,
    ATTR_STATE_CODE,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: AirNowDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
        },
        "data": async_redact_data(coordinator.data, TO_REDACT),
    }
