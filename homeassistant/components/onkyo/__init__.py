"""The onkyo component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

# PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SELECT]
PLATFORMS = [Platform.MEDIA_PLAYER]

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up the Onkyo platform from config_flow."""
    hass.data.setdefault(DOMAIN, {})

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Onkyo config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
