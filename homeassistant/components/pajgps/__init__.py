"""Integration for PAJ GPS trackers."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import PajGpsConfigEntry, PajGpsCoordinator

PLATFORMS: list[Platform] = [Platform.DEVICE_TRACKER]
_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup_entry(hass: HomeAssistant, entry: PajGpsConfigEntry) -> bool:
    """Set up platform from a ConfigEntry."""
    pajgps_coordinator = PajGpsCoordinator(hass, entry)
    await pajgps_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = pajgps_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PajGpsConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
