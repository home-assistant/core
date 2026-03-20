"""Diagnostics support for RDW."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import RDWDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: RDWDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    data: dict[str, Any] = coordinator.data.to_dict()
    return data
