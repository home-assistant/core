"""LG IR Remote integration for Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import CONF_INFRARED_RECEIVER_ENTITY_ID

PLATFORMS = [Platform.BUTTON, Platform.MEDIA_PLAYER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up LG IR from a config entry."""
    platforms = list(PLATFORMS)
    if entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        platforms.append(Platform.EVENT)

    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a LG IR config entry."""
    platforms = list(PLATFORMS)
    if entry.data.get(CONF_INFRARED_RECEIVER_ENTITY_ID):
        platforms.append(Platform.EVENT)

    return await hass.config_entries.async_unload_platforms(entry, platforms)
