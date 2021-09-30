"""Plugwise platform for Home Assistant Core."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .gateway import async_setup_entry_gw, async_unload_entry_gw


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Plugwise components from a config entry."""
    if entry.data.get(CONF_HOST):
        return await async_setup_entry_gw(hass, entry)
    # PLACEHOLDER USB entry setup
    return False


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the Plugwise components."""
    if entry.data.get(CONF_HOST):
        return await async_unload_entry_gw(hass, entry)
    # PLACEHOLDER USB entry setup
    return False
