"""Integration for PAJ GPS trackers."""

import logging

from homeassistant import core
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .coordinator import PajGpsCoordinator

type PajGpsConfigEntry = ConfigEntry[PajGpsCoordinator]

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]
# Target platforms after complete implementation: [Platform.DEVICE_TRACKER, Platform.SENSOR, Platform.BINARY_SENSOR, Platform.SWITCH]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: PajGpsConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    pajgps_coordinator = PajGpsCoordinator(hass, entry, async_get_clientsession(hass))
    await pajgps_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = pajgps_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: core.HomeAssistant, entry: PajGpsConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
