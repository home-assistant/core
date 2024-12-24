"""Support for the AEMET OpenData diagnostics."""

from __future__ import annotations

from typing import Any

from aemet_opendata.const import AOD_COORDS, AOD_IMG_BYTES

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
)
from homeassistant.core import HomeAssistant

from .coordinator import AemetConfigEntry

TO_REDACT_CONFIG = [
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UNIQUE_ID,
]

TO_REDACT_COORD = [
    AOD_COORDS,
    AOD_IMG_BYTES,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AemetConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data.coordinator

    return {
        "api_data": coordinator.aemet.raw_data(),
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT_CONFIG),
        "coord_data": async_redact_data(coordinator.data, TO_REDACT_COORD),
    }
