"""Support for Roku."""
from __future__ import annotations

import logging

from rokuecp import RokuConnectionError, RokuError

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import RokuDataUpdateCoordinator

CONFIG_SCHEMA = cv.deprecated(DOMAIN)

PLATFORMS = [MEDIA_PLAYER_DOMAIN, REMOTE_DOMAIN]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Roku from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = hass.data[DOMAIN].get(entry.entry_id)
    if not coordinator:
        coordinator = RokuDataUpdateCoordinator(hass, host=entry.data[CONF_HOST])
        hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


def roku_exception_handler(func):
    """Decorate Roku calls to handle Roku exceptions."""

    async def handler(self, *args, **kwargs):
        try:
            await func(self, *args, **kwargs)
        except RokuConnectionError as error:
            if self.available:
                _LOGGER.error("Error communicating with API: %s", error)
        except RokuError as error:
            if self.available:
                _LOGGER.error("Invalid response from API: %s", error)

    return handler
