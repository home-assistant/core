"""Diagnostics support for RainMachine."""

from __future__ import annotations

from typing import Any

from regenmaschine.errors import RainMachineError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from . import RainMachineData
from .const import DOMAIN, LOGGER

CONF_STATION_ID = "stationID"
CONF_STATION_NAME = "stationName"
CONF_STATION_SOURCE = "stationSource"
CONF_TIMEZONE = "timezone"

TO_REDACT = {
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
    CONF_STATION_ID,
    CONF_STATION_NAME,
    CONF_STATION_SOURCE,
    CONF_TIMEZONE,
    # Config entry unique ID may contain sensitive data:
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

    try:
        controller_diagnostics = await data.controller.diagnostics.current()
    except RainMachineError:
        LOGGER.warning("Unable to download controller-specific diagnostics")
        controller_diagnostics = None

    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": {
                "coordinator": {
                    api_category: controller.data
                    for api_category, controller in data.coordinators.items()
                },
                "controller_diagnostics": controller_diagnostics,
            },
        },
        TO_REDACT,
    )
