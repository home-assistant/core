"""Diagnostics support for AirVisual."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_STATE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import CONF_CITY, CONF_COUNTRY, DOMAIN

ATTR_DATA = "data"
ATTR_OPTIONS = "options"
ATTR_TITLE = "title"


@callback
def _async_get_redacted_entry_info(entry: ConfigEntry) -> dict[str, Any]:
    """Get redacted config entry data/options/etc."""
    info = {
        ATTR_TITLE: entry.title,
        ATTR_DATA: {**entry.data},
        ATTR_OPTIONS: {**entry.options},
    }

    for field in (
        CONF_API_KEY,
        CONF_CITY,
        CONF_COUNTRY,
        CONF_LATITUDE,
        CONF_LONGITUDE,
        CONF_STATE,
    ):
        if field not in info["data"]:
            info["data"][field] = "REDACTED"

    return info


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    print(coordinator)
    return {
        "entry": _async_get_redacted_entry_info(entry),
        "data": {**coordinator.data},
    }
