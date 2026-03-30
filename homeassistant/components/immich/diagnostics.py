"""Diagnostics support for immich."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant

from .coordinator import ImmichConfigEntry

TO_REDACT = {CONF_API_KEY, CONF_HOST}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ImmichConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = entry.runtime_data
    data = coordinator.data

    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "data": {
            "server_about": data.server_about.model_dump()
            if data.server_about
            else None,
            "server_storage": data.server_storage.model_dump()
            if data.server_storage
            else None,
            "server_usage": data.server_usage.model_dump()
            if data.server_usage
            else None,
            "server_version_check": data.server_version_check.model_dump()
            if data.server_version_check
            else None,
        },
    }
