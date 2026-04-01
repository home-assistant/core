"""Diagnostics support for the GridX integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .types import GridxConfigEntry

TO_REDACT: set[str] = {CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: GridxConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a GridX config entry."""
    return {
        "config_entry": async_redact_data(dict(entry.data), TO_REDACT),
        "live_data": entry.runtime_data.live_coordinator.data,
        "historical_data": entry.runtime_data.hist_coordinator.data,
    }
