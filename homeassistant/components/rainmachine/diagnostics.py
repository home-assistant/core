"""Diagnostics support for RainMachine."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import RainMachineData
from .const import DOMAIN

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_PASSWORD,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: RainMachineData = hass.data[DOMAIN][entry.entry_id]

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
                "api_version": data.controller.api_version,
                "hardware_version": data.controller.hardware_version,
                "name": data.controller.name,
                "software_version": data.controller.software_version,
            },
        },
    }
