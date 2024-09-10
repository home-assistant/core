"""Diagnostics support for GeoNet NZ Quakes Feeds integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import GeonetnzQuakesFeedEntityManager
from .const import DOMAIN, FEED

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: dict[str, Any] = {
        "info": async_redact_data(config_entry.data, TO_REDACT),
    }

    manager: GeonetnzQuakesFeedEntityManager = hass.data[DOMAIN][FEED][
        config_entry.entry_id
    ]
    status_info = manager.status_info()
    if status_info:
        data["service"] = {
            "status": status_info.status,
            "total": status_info.total,
            "last_update": status_info.last_update,
            "last_update_successful": status_info.last_update_successful,
            "last_timestamp": status_info.last_timestamp,
        }

    return data
