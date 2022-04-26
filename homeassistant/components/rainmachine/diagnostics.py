"""Diagnostics support for RainMachine."""
from __future__ import annotations

from typing import Any

from regenmaschine.controller import Controller

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DATA_CONTROLLER, DATA_COORDINATOR, DOMAIN

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinators: dict[str, DataUpdateCoordinator] = data[DATA_COORDINATOR]
    controller: Controller = data[DATA_CONTROLLER]

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
                    for api_category, controller in coordinators.items()
                },
                TO_REDACT,
            ),
            "controller": {
                "api_version": controller.api_version,
                "hardware_version": controller.hardware_version,
                "name": controller.name,
                "software_version": controller.software_version,
            },
        },
    }
