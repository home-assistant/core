"""Diagnostics support for Elgato."""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HassType

from .const import DOMAIN
from .coordinator import ElgatoDataUpdateCoordinator


async def async_get_config_entry_diagnostics(
    hass: HassType[ElgatoDataUpdateCoordinator], entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "info": coordinator.data.info.dict(),
        "state": coordinator.data.state.dict(),
    }
