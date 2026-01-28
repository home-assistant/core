"""The Hidromotic integration."""

from __future__ import annotations

import logging

from pyhidromotic import HidromoticClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .coordinator import HidromoticCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]

type HidromoticConfigEntry = ConfigEntry[HidromoticCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: HidromoticConfigEntry) -> bool:
    """Set up Hidromotic from a config entry."""
    host = entry.data[CONF_HOST]

    # Create client
    client = HidromoticClient(host)

    # Create coordinator
    coordinator = HidromoticCoordinator(hass, client, entry)

    # Set up the connection
    if not await coordinator.async_setup():
        raise ConfigEntryNotReady(f"Failed to connect to Hidromotic device at {host}")

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: HidromoticConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload platforms
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Shutdown coordinator
        await entry.runtime_data.async_shutdown()

    return unload_ok
