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

from .coordinator import FlussDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.BUTTON]


class FlussConfigEntryData(TypedDict):
    """Type definition for Fluss config entry data."""

    api_key: str


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry[FlussApiClient],
) -> bool:
    """Set up Fluss+ from a config entry."""
    try:
        api = FlussApiClient(entry.data[CONF_API_KEY])
    except FlussApiClientAuthenticationError as e:
        raise ConfigEntryAuthFailed from e
    except (FlussApiClientCommunicationError, FlussApiClientError) as e:
        raise ConfigEntryNotReady from e

    entry.runtime_data = api
    coordinator = FlussDataUpdateCoordinator(hass, api, entry.data[CONF_API_KEY])
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry[FlussDataUpdateCoordinator]
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    coordinator: FlussDataUpdateCoordinator = entry.runtime_data
    await coordinator.api.close()

    return True
