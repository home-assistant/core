"""Diagnostics support for august."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import AugustData
from .const import DOMAIN

TO_REDACT = {"password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data: AugustData = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": dict(entry.data),
        },
        "locks": {
            async_redact_data(data.get_device_detail(device_id), TO_REDACT)
            for device_id in data.locks
        },
        "dorbells": {
            async_redact_data(data.get_device_detail(device_id), TO_REDACT)
            for device_id in data.doorbells
        },
    }
