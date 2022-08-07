"""Diagnostics support for RainMachine."""
from __future__ import annotations

import asyncio
from typing import Any

from regenmaschine.errors import RequestError

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_ELEVATION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant

from . import RainMachineData
from .const import DOMAIN

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
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

    controller_tasks = {
        "versions": data.controller.api.versions(),
        "current_diagnostics": data.controller.diagnostics.current(),
    }
    controller_results = await asyncio.gather(
        *controller_tasks.values(), return_exceptions=True
    )

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(entry.data, TO_REDACT),
            "options": dict(entry.options),
        },
        "data": {
            "coordinator": async_redact_data(
                {
                    api_category: controller.data
                    for api_category, controller in data.coordinators.items()
                },
                TO_REDACT,
            ),
            "controller": {
                category: result
                for category, result in zip(controller_tasks, controller_results)
                if not isinstance(result, RequestError)
            },
        },
    }
