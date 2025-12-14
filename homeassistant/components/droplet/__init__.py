"""The Droplet integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DropletConfigEntry, DropletDataCoordinator

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Set up Droplet from a config entry."""

    droplet_coordinator = DropletDataCoordinator(hass, config_entry)
    await droplet_coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = droplet_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
