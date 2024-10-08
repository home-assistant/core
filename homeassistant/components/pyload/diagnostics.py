"""Diagnostics support for pyLoad."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import PyLoadConfigEntry
from .coordinator import PyLoadData

TO_REDACT = {CONF_USERNAME, CONF_PASSWORD, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: PyLoadConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    pyload_data: PyLoadData = config_entry.runtime_data.data

    return {
        "config_entry_data": async_redact_data(dict(config_entry.data), TO_REDACT),
        "pyload_data": asdict(pyload_data),
    }
