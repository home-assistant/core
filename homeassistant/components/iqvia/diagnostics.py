"""Diagnostics support for IQVIA."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_ZIP_CODE, DOMAIN

CONF_CITY = "City"
CONF_DISPLAY_LOCATION = "DisplayLocation"
CONF_MARKET = "Market"
CONF_TITLE = "title"
CONF_ZIP_CAP = "ZIP"
CONF_STATE_CAP = "State"

TO_REDACT = {
    CONF_CITY,
    CONF_DISPLAY_LOCATION,
    CONF_MARKET,
    CONF_STATE_CAP,
    # Config entry title and unique ID may contain sensitive data:
    CONF_TITLE,
    CONF_UNIQUE_ID,
    CONF_ZIP_CAP,
    CONF_ZIP_CODE,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinators: dict[str, DataUpdateCoordinator] = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": async_redact_data(
            {
                data_type: coordinator.data
                for data_type, coordinator in coordinators.items()
            },
            TO_REDACT,
        ),
    }
