"""Diagnostics support for pyLoad."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import PyLoadConfigEntry
from .coordinator import pyLoadData

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PyLoadConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    pyload_data: pyLoadData = config_entry.runtime_data.data

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "pyload_data": pyload_data,
    }
