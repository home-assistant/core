"""The Fluss+ integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant

from .api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,  # noqa: F401
    FlussApiClientCommunicationError,  # noqa: F401
    FlussApiClientError,  # noqa: F401
)

LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fluss+ from a config entry."""
    try:
        api = FlussApiClient(entry.data[CONF_API_KEY], hass)
    except FlussApiClientAuthenticationError as e:
        LOGGER.error("Authentication error initializing FlussApiClient: %s", e)
        return False
    except FlussApiClientCommunicationError as e:
        LOGGER.error("Communication error initializing FlussApiClient: %s", e)
        return False
    except FlussApiClientError as e:
        LOGGER.error("General error initializing FlussApiClient: %s", e)
        return False

    entry.runtime_data = {"api": api}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
