"""Provides diagnostics for Advantage Air."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN

TO_REDACT = ["dealerPhoneNumber", "latitude", "logoPIN", "longitude", "postCode"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id].coordinator.data

    # Return only the relevant children
    return {
        "aircon": data.get("aircon"),
        "lights": data.get("lights"),
        "things": data.get("things"),
        "system": async_redact_data(data["system"], TO_REDACT),
    }
