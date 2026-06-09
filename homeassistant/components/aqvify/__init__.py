"""The Aqvify integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import AqvifyConfigEntry, AqvifyCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Set up Aqvify from a config entry."""

    coordinator = AqvifyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AqvifyConfigEntry) -> bool:
    """Unload Aqvify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
