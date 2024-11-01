"""Support for the Airzone diagnostics."""

from __future__ import annotations

from typing import Any

from aioairzone.const import API_MAC, AZD_MAC

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.const import CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant

from . import AirzoneConfigEntry

TO_REDACT_API = [
    API_MAC,
]

TO_REDACT_CONFIG = [
    CONF_UNIQUE_ID,
]

TO_REDACT_COORD = [
    AZD_MAC,
]


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: AirzoneConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = config_entry.runtime_data

    return {
        "api_data": async_redact_data(coordinator.airzone.raw_data(), TO_REDACT_API),
        "config_entry": async_redact_data(config_entry.as_dict(), TO_REDACT_CONFIG),
        "coord_data": async_redact_data(coordinator.data, TO_REDACT_COORD),
    }
