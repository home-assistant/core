"""The Logitech Squeezebox integration."""

import logging

from homeassistant.components.media_player import DOMAIN as MP_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DISCOVERY_TASK, DOMAIN, PLAYER_DISCOVERY_UNSUB

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Logitech Squeezebox component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Logitech Squeezebox from a config entry."""
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MP_DOMAIN)
    )
    return True


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    # Stop player discovery task for this config entry.
    hass.data[DOMAIN][entry.entry_id][PLAYER_DISCOVERY_UNSUB]()

    # Remove stored data for this config entry
    hass.data[DOMAIN].pop(entry.entry_id)

    # Stop server discovery task if this is the last config entry.
    current_entries = hass.config_entries.async_entries(DOMAIN)
    if len(current_entries) == 1 and current_entries[0] == entry:
        _LOGGER.debug("Stopping server discovery task")
        hass.data[DOMAIN][DISCOVERY_TASK].cancel()
        hass.data[DOMAIN].pop(DISCOVERY_TASK)

    return await hass.config_entries.async_forward_entry_unload(entry, MP_DOMAIN)
