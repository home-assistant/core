"""Diagnostics support for ViCare."""

from __future__ import annotations

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DEVICE_LIST, DOMAIN

TO_REDACT = {CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    def dump_devices() -> list[dict[str, Any]]:
        """Dump devices."""
        return [
            json.loads(device.config.dump_secure())
            for device in hass.data[DOMAIN][entry.entry_id][DEVICE_LIST]
        ]

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": await hass.async_add_executor_job(dump_devices),
    }
