"""Diagnostics support for GDACS integration."""

from __future__ import annotations

from typing import Any

from aio_georss_client.status_update import StatusUpdate

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from . import GdacsFeedEntityManager
from .const import DOMAIN, FEED

TO_REDACT = {CONF_LATITUDE, CONF_LONGITUDE}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager: GdacsFeedEntityManager = hass.data[DOMAIN][FEED][config_entry.entry_id]
    status_info: StatusUpdate = manager.status_info()

    return {
        "info": async_redact_data(config_entry.data, TO_REDACT),
        "service": {
            "status": status_info.status if status_info else "",
            "total": status_info.total if status_info else "",
            "last_update": status_info.last_update if status_info else "",
            "last_update_successful": status_info.last_update_successful
            if status_info
            else "",
            "last_timestamp": status_info.last_timestamp if status_info else "",
        },
    }
