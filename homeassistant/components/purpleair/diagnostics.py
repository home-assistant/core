"""Diagnostics support for PurpleAir."""

from __future__ import annotations

from typing import Any, Final

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .coordinator import PurpleAirConfigEntry

CONF_DATA: Final[str] = "data"
CONF_ENTRY: Final[str] = "entry"
CONF_TITLE: Final[str] = "title"

TO_REDACT = {
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    # Config entry title and unique ID contain the API key (whole or part):
    CONF_TITLE,
    CONF_UNIQUE_ID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PurpleAirConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    return async_redact_data(
        {
            CONF_ENTRY: entry.as_dict(),
            CONF_DATA: entry.runtime_data.data.model_dump(),
        },
        TO_REDACT,
    )
