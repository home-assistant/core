"""Diagnostics support for Whois."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: DataUpdateCoordinator[dict[str, Any]] = hass.data[DOMAIN][
        entry.entry_id
    ]

    return {
        "creation_date": coordinator.data.get("creation_date"),
        "expiration_date": coordinator.data.get("expiration_date"),
        "last_updated": coordinator.data.get("last_updated"),
        "status": coordinator.data.get("status"),
        "statuses": coordinator.data.get("statuses"),
        "dnssec": coordinator.data.get("dnssec"),
        "name_servers": coordinator.data.get("name_servers"),
        "registrar": coordinator.data.get("registrar"),
    }
