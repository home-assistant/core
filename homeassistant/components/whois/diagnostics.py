"""Diagnostics support for Whois."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import WhoisCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: WhoisCoordinator = hass.data[DOMAIN][entry.entry_id]
    if (data := coordinator.data) is None:
        return {}
    return {
        "creation_date": data.creation_date,
        "expiration_date": data.expiration_date,
        "last_updated": data.last_updated,
        "status": data.status,
        "statuses": data.statuses,
        "dnssec": data.dnssec,
    }
