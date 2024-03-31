"""Diagnostics support for APCUPSD."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import APCUPSdCoordinator, APCUPSdData

TO_REDACT = {"SERIALNO", "HOSTNAME"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: APCUPSdCoordinator = hass.data[DOMAIN][entry.entry_id]
    data: APCUPSdData = coordinator.data
    return async_redact_data(data, TO_REDACT)
