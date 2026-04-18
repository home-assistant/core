"""The Fing integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError

from .coordinator import FingConfigEntry, FingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]


async def async_setup_entry(hass: HomeAssistant, config_entry: FingConfigEntry) -> bool:
    """Set up the Fing component."""

    coordinator = FingDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    if coordinator.data.network_id is None:
        _LOGGER.warning(
            "Skip setting up Fing integration; Received an empty NetworkId from the request - Check if the API version is the latest"
        )
        raise ConfigEntryError(
            "The Agent's API version is outdated. Please update the agent to the latest version."
        )

    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FingConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
