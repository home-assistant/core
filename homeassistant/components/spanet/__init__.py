"""The SpaNET integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# async def async_setup(hass: HomeAssistant, config: dict) -> bool:
#     return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SpaNET from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    access_token = entry.data.get("access_token")
    refresh_token = entry.data.get("refresh_token")
    spa_name = entry.data.get("spa_name")

    hass.data[DOMAIN]["user"] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "spa_name": spa_name,
    }

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.WATER_HEATER])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, [Platform.WATER_HEATER]
    ):
        hass.data.pop(DOMAIN)
    return unload_ok
