"""Provides diagnostics for Advantage Air."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    ADVANTAGE_AIR_AIRCONS,
    ADVANTAGE_AIR_COORDINATOR,
    ADVANTAGE_AIR_LIGHTS,
    DOMAIN as ADVANTAGE_AIR_DOMAIN,
)

TO_REDACT = ["dealerPhoneNumber", "latitude", "logoPIN", "longitude", "postCode"]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = hass.data[ADVANTAGE_AIR_DOMAIN][config_entry.entry_id][
        ADVANTAGE_AIR_COORDINATOR
    ].data

    # Return only the relevant children
    return {
        "aircons": data.get(ADVANTAGE_AIR_AIRCONS),
        "lights": data.get(ADVANTAGE_AIR_LIGHTS),
        "system": async_redact_data(data["system"], TO_REDACT),
    }
