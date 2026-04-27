"""Diagnostics support for Whois."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import WhoisConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: WhoisConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    if (data := entry.runtime_data.data) is None:
        return {}
    return {
        "creation_date": data.creation_date,
        "expiration_date": data.expiration_date,
        "last_updated": data.last_updated,
        "status": data.status,
        "statuses": data.statuses,
        "dnssec": data.dnssec,
    }
