"""Diagnostics support for Flu Near You."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CATEGORY_CDC_REPORT, CATEGORY_USER_REPORT, DOMAIN

TO_REDACT = {
    CONF_LATITUDE,
    CONF_LONGITUDE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id]

    return async_redact_data(
        {
            CATEGORY_CDC_REPORT: coordinators[CATEGORY_CDC_REPORT].data,
            CATEGORY_USER_REPORT: coordinators[CATEGORY_USER_REPORT].data,
        },
        TO_REDACT,
    )
