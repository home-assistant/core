"""Diagnostics support for ViCare."""
from __future__ import annotations

import json
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DOMAIN, VICARE_DEVICE_CONFIG
from .helpers import get_unique_device_id

TO_REDACT = {CONF_CLIENT_ID, CONF_PASSWORD, CONF_USERNAME}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    device_dumps = await hass.async_add_executor_job(dump_device_state, hass, entry)

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": device_dumps,
    }


def dump_device_state(hass: HomeAssistant, entry: ConfigEntry):
    """Dump devices state to dict."""
    devices = hass.data[DOMAIN][entry.entry_id][VICARE_DEVICE_CONFIG]
    device_dumps = dict[str, Any]()
    for device in devices:
        device_dumps[get_unique_device_id(device)] = json.loads(device.dump_secure())
    return device_dumps
