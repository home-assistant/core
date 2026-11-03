"""Diagnostics support for DSMR."""

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util.json import json_loads

from . import DsmrConfigEntry
from .const import CONF_ENCRYPTION_KEY

TO_REDACT = {CONF_ENCRYPTION_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: DsmrConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry": {
            "data": async_redact_data(config_entry.data, TO_REDACT),
            "unique_id": config_entry.unique_id,
        },
        "data": json_loads(config_entry.runtime_data.telegram.to_json())
        if config_entry.runtime_data.telegram
        else None,
    }
