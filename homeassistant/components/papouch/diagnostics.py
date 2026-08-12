"""Diagnostics file for Papouch integration."""

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .coordinator import PapouchDataUpdateCoordinator

type PapouchConfigEntry = ConfigEntry[PapouchDataUpdateCoordinator]

TO_REDACT = {"password"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: PapouchConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""

    return {
        "entry_data": async_redact_data(entry.data, TO_REDACT),
        "data": entry.runtime_data.data,
    }
