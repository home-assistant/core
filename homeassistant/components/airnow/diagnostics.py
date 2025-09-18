"""Diagnostics support for AirNow."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .coordinator import AirNowConfigEntry

ATTR_LATITUDE_CAP = "Latitude"
ATTR_LONGITUDE_CAP = "Longitude"
ATTR_REPORTING_AREA = "ReportingArea"
ATTR_STATE_CODE = "StateCode"

CONF_TITLE = "title"

TO_REDACT = {
    ATTR_LATITUDE_CAP,
    ATTR_LONGITUDE_CAP,
    ATTR_REPORTING_AREA,
    ATTR_STATE_CODE,
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    # The config entry title has latitude/longitude:
    CONF_TITLE,
    # The config entry unique ID has latitude/longitude:
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AirNowConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": coordinator.data,
        },
        TO_REDACT,
    )
