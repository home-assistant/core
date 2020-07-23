"""The Haiku integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from itertools import chain
from homeassistant.const import MATCH_ALL

PLATFORMS = ["fan"]
_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Haiku component."""
    hass.helpers.discovery.load_platform("fan", DOMAIN, {}, config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Haiku from a config entry."""
    # Not supported
    return False


def show_setup_message(hass, entry_id):
    """Display persistent notification with setup information."""
    message = f"To remove your Haiku devices, please go to your entity config and click remove on all the devices."
    hass.components.persistent_notification.create(message, "Haiku", entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        show_setup_message(hass, entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Remove a config entry."""
    show_setup_message(hass, entry.entry_id)
    return True
