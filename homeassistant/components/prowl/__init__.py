"""The prowl component."""

import logging

import prowlpy

from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .helpers import async_verify_key
from .notify import PLATFORM_SCHEMA, ProwlConfigEntry

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "PLATFORM_SCHEMA"]


# This is just to suppress https://github.com/home-assistant/core/blob/dev/homeassistant/setup.py#L365-L378
async def async_setup(hass: HomeAssistant, entry: ProwlConfigEntry) -> bool:
    """Set up the Prowl component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ProwlConfigEntry) -> bool:
    """Set up a Prowl service."""
    try:
        if not await async_verify_key(hass, entry.data[CONF_API_KEY]):
            raise ConfigEntryError(
                "Unable to validate Prowl API key (Key invalid or expired)"
            )
    except TimeoutError as ex:
        raise ConfigEntryNotReady("API call to Prowl failed") from ex
    except prowlpy.APIError as ex:
        if str(ex).startswith("Not accepted: exceeded rate limit"):
            raise ConfigEntryNotReady("Prowl API rate limit exceeded") from ex
        raise ConfigEntryError("Failed to validate Prowl API key ({ex})") from ex

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ProwlConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
