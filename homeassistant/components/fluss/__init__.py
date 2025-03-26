"""The Fluss+ integration."""

from __future__ import annotations

from typing import TypedDict

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

PLATFORMS: list[Platform] = [Platform.BUTTON]


class FlussConfigEntryData(TypedDict):
    """Type definition for Fluss+ config entry data."""

    api_key: str


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry[FlussConfigEntryData]
) -> bool:
    """Set up Fluss+ from a config entry."""
    try:
        api = FlussApiClient(entry.data[CONF_API_KEY])
    except FlussApiClientAuthenticationError as e:
        raise ConfigEntryAuthFailed from e
    except (FlussApiClientCommunicationError, FlussApiClientError) as e:
        raise ConfigEntryNotReady from e

    entry.runtime_data = api

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
