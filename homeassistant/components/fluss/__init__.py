"""The Fluss+ integration."""

from __future__ import annotations

import logging

from fluss_api import (
    FlussApiClient,
    FlussApiClientAuthenticationError,
    FlussApiClientCommunicationError,
    FlussApiClientError,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [Platform.BUTTON]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Fluss+ from a config entry."""

    try:
        api = FlussApiClient(entry.data[CONF_API_KEY])
    except FlussApiClientAuthenticationError as e:
        LOGGER.error("Authentication error initializing FlussApiClient: %s", e)
        raise ConfigEntryAuthFailed from e
    except FlussApiClientCommunicationError as e:
        LOGGER.error("Communication error initializing FlussApiClient: %s", e)
        raise ConfigEntryNotReady from e
    except FlussApiClientError as e:
        LOGGER.error("General error initializing FlussApiClient: %s", e)
        raise ConfigEntryNotReady from e

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
