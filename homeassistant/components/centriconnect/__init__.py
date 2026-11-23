"""The CentriConnect/MyPropane API integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import CentriConnectConfigEntry, CentriConnectCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: CentriConnectConfigEntry
) -> None:
    """Set up CentriConnect/MyPropane API from a config entry."""
    coordinator = CentriConnectCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(
    hass: HomeAssistant, entry: CentriConnectConfigEntry
) -> None:
    """Unload CentriConnect/MyPropane API integration platforms and coordinator."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
