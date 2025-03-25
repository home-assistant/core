"""The prowl component."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.typing import ConfigType

from .notify import PLATFORM_SCHEMA, ProwlNotificationService

_LOGGER = logging.getLogger(__name__)

__all__ = ["PLATFORM_SCHEMA"]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Prowl integration."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Prowl entry."""

    # This just checks if the API key is valid before initialising the entry
    prowl = ProwlNotificationService(hass, entry.data[CONF_API_KEY])
    try:
        if not await prowl.async_verify_key():
            raise ConfigEntryAuthFailed(
                "Unable to validate Prowl API key (Key invalid or expired)"
            )
    except TimeoutError as ex:
        raise ConfigEntryNotReady("API call to Prowl failed") from ex

    await hass.config_entries.async_forward_entry_setups(entry, [Platform.NOTIFY])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, [Platform.NOTIFY])
