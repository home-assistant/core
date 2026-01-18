"""The liebherr integration."""

from __future__ import annotations

from pyliebherrhomeapi import LiebherrClient
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import LiebherrCoordinator
from .models import LiebherrConfigEntry, LiebherrData

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Set up Liebherr from a config entry."""
    client = LiebherrClient(
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    # Validate the API connection and get devices
    try:
        devices = await client.get_devices()
    except LiebherrAuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid API key") from err
    except LiebherrConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to Liebherr API: {err}") from err

    if not devices:
        raise ConfigEntryNotReady("No devices found for this API key")

    # Create a single coordinator for all devices to avoid rate limits
    coordinator = LiebherrCoordinator(
        hass=hass,
        client=client,
        config_entry=entry,
    )
    coordinator.device_ids = [device.device_id for device in devices]

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = LiebherrData(coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
