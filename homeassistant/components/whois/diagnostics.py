"""Diagnostics support for Whois."""
from __future__ import annotations

from typing import Any

from whois import Domain

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[Domain] = hass.data[DOMAIN][entry.entry_id]
    return {
        "creation_date": coordinator.data.creation_date,
        "expiration_date": coordinator.data.expiration_date,
        "last_updated": coordinator.data.last_updated,
        "status": coordinator.data.status,
        "statuses": coordinator.data.statuses,
        "dnssec": coordinator.data.dnssec,
    }
