"""Diagnostics support for TechnoVE."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import TechnoVEDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: TechnoVEDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    data: dict[str, Any] = {"info": coordinator.data.info.__dict__}
    return data
