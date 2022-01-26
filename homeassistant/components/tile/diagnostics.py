"""Diagnostics support for Tile."""
from __future__ import annotations

from typing import Any

from pytile.tile import Tile

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import DATA_TILE, DOMAIN

CONF_ALTITUDE = "altitude"
CONF_UUID = "uuid"

TO_REDACT = {
    CONF_ALTITUDE,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_UUID,
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    tiles: dict[str, Tile] = hass.data[DOMAIN][entry.entry_id][DATA_TILE]

    return async_redact_data(
        {"tiles": [tile.as_dict() for tile in tiles.values()]}, TO_REDACT
    )
