"""Provides diagnostics for Fyta."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import FytaConfigEntry

TO_REDACT = [
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_ACCESS_TOKEN,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: FytaConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = config_entry.runtime_data.data

    return {
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT),
        "plant_data": data,
    }
