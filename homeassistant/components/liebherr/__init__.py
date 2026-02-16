"""The liebherr integration."""

from __future__ import annotations

import asyncio

from pyliebherrhomeapi import LiebherrClient
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import LiebherrConfigEntry, LiebherrCoordinator

PLATFORMS: list[Platform] = [Platform.NUMBER, Platform.SENSOR, Platform.SWITCH]


async def async_setup_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Set up Liebherr from a config entry."""
    # Create shared API client
    client = LiebherrClient(
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    # Fetch device list to create coordinators
    try:
        devices = await client.get_devices()
    except LiebherrAuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid API key") from err
    except LiebherrConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to Liebherr API: {err}") from err

    # Create a coordinator for each device (may be empty if no devices)
    coordinators: dict[str, LiebherrCoordinator] = {}
    for device in devices:
        coordinator = LiebherrCoordinator(
            hass=hass,
            config_entry=entry,
            client=client,
            device_id=device.device_id,
        )
        coordinators[device.device_id] = coordinator

    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )

    # Store coordinators in runtime data
    entry.runtime_data = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
