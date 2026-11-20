"""The Droplet integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import DropletConfigEntry, DropletDataCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
]

logger = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> None:
    """Set up Droplet from a config entry."""

    droplet_coordinator = DropletDataCoordinator(hass, config_entry)
    await droplet_coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = droplet_coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, config_entry: DropletConfigEntry
) -> None:
    """Unload a config entry."""

    await hass.config_entries.async_unload_platforms_or_raise(config_entry, PLATFORMS)
