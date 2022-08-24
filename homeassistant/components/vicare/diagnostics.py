"""Diagnostics support for ViCare."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VICARE_DEVICE_CONFIG

TO_REDACT = {CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    # Currently we only support a single device
    device = hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG]
    data: dict[str, Any] = json.loads(
        await hass.async_add_executor_job(device.dump_secure)
    )
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": data,
    }
