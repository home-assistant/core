"""Diagnostics support for PurpleAir."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PurpleAirDataUpdateCoordinator

CONF_TITLE = "title"

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    # Config entry title and unique ID contain the API key (whole or part):
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: PurpleAirDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    return async_redact_data(
        {
            "entry": entry.as_dict(),
            "data": coordinator.data.dict(),
        },
        TO_REDACT,
    )
