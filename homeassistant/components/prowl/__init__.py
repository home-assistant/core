"""The prowl component."""

import logging

import prowlpy

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import DOMAIN, PLATFORMS
from .notify import PLATFORM_SCHEMA, ProwlNotificationEntity

_LOGGER = logging.getLogger(__name__)

__all__ = ["DOMAIN", "PLATFORM_SCHEMA"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Prowl service."""
    # This just checks if the API key is valid before initialising the entry
    prowl = ProwlNotificationEntity(
        hass, entry.data[CONF_NAME], entry.data[CONF_API_KEY]
    )
    try:
        if not await prowl.async_verify_key():
            raise ConfigEntryAuthFailed(
                "Unable to validate Prowl API key (Key invalid or expired)"
            )
    except TimeoutError as ex:
        raise ConfigEntryNotReady("API call to Prowl failed") from ex
    except prowlpy.APIError as ex:
        if str(ex).startswith("Not accepted: exceeded rate limit"):
            raise ConfigEntryNotReady(
                "Prowl API rate limit exceeded, try again later"
            ) from ex
        if str(ex).startswith(
            "Not approved: The user has yet to approve your retrieve request"
        ):
            raise ConfigEntryNotReady(
                "Prowl user has yet to approve your retrieve request"
            ) from ex
        raise ConfigEntryAuthFailed("Failed to validate Prowl API key ({ex})") from ex

    entry.runtime_data = prowl
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


type ProwlConfigEntry = ConfigEntry[ProwlNotificationEntity]


async def async_unload_entry(hass: HomeAssistant, entry: ProwlConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
