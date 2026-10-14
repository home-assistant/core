"""The Smart Meter B Route integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import BRouteConfigEntry, BRouteUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> None:
    """Set up Smart Meter B Route from a config entry."""

    coordinator = BRouteUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: BRouteConfigEntry) -> None:
    """Unload a config entry."""
    await hass.async_add_executor_job(entry.runtime_data.api.close)
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
