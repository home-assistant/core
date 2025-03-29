"""Diagnostics support for Roomba."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from . import roomba_reported_state
from .const import DOMAIN
from .models import RoombaData


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, config_entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    domain_data: RoombaData = hass.data[DOMAIN][config_entry.entry_id]
    return {
        "lastCommand": roomba_reported_state(domain_data.roomba).get("lastCommand", {}),
    }
