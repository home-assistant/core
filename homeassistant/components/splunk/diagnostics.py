"""Diagnostics support for Splunk."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant

from . import DATA_FILTER

TO_REDACT = {CONF_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry_data": async_redact_data(dict(entry.data), TO_REDACT),
        "entity_filter": hass.data[DATA_FILTER].config,
    }
