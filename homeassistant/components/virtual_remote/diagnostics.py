"""Diagnostics support for Virtual Remote."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

TO_REDACT = {"device_id", "unique_id", "uuid"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "entry": async_redact_data(
            {
                "title": entry.title,
                "domain": entry.domain,
                "data": dict(entry.data),
                "options": dict(entry.options),
                "unique_id": entry.unique_id,
            },
            TO_REDACT,
        ),
    }
