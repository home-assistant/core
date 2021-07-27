"""The Aussie Broadband integration."""
from __future__ import annotations

from aussiebb import AussieBB

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import ATTR_PASSWORD, ATTR_USERNAME, DOMAIN

PLATFORMS = ["sensor", "camera"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Neato component."""
    hass.data[DOMAIN] = {}
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Aussie Broadband from a config entry."""
    hass.data[DOMAIN][entry.entry_id] = await hass.async_add_executor_job(
        AussieBB, entry.data[ATTR_USERNAME], entry.data[ATTR_PASSWORD]
    )
    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
