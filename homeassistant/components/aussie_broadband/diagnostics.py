"""Provides diagnostics for Aussie Broadband."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import DOMAIN

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

TO_REDACT = ["address", "ipAddresses", "description", "discounts", "coordinator"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return {
        "services": [
            {
                "service": async_redact_data(service, TO_REDACT),
                "usage": async_redact_data(service["coordinator"].data, ["historical"]),
            }
            for service in hass.data[DOMAIN][config_entry.entry_id]["services"]
        ]
    }
