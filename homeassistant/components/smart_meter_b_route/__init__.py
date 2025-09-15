"""The Smart Meter B Route integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BRouteConfigEntry, BRouteUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Set up Smart Meter B Route from a config entry."""

    coordinator = BRouteUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> bool:
    """Unload a config entry."""
    entry.runtime_data.api.close()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
