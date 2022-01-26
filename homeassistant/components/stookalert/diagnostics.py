"""Diagnostics support for Stookalert."""
from __future__ import annotations

from typing import Any

import stookalert

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    client: stookalert.stookalert = hass.data[DOMAIN][entry.entry_id]
    return {"state": client.state}
