"""Provides diagnostics for Advantage Air."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN as ADVANTAGE_AIR_DOMAIN

SYSTEM_BLACKLIST = ["dealerPhoneNumber", "latitude", "logoPIN", "longitude", "postCode"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id]["coordinator"].data

    for item in SYSTEM_BLACKLIST:
        data["system"].pop(item, None)

    # Return only the relevant children
    return {
        "aircons": data["aircons"],
        "system": data["system"],
    }
