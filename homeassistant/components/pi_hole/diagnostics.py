"""Diagnostics support for the Pi-hole integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant

from . import PiHoleConfigEntry

TO_REDACT = {CONF_API_KEY}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PiHoleConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    api = entry.runtime_data.api

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": api.data,
        "versions": api.versions,
    }
