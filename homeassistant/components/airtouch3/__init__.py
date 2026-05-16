"""The AirTouch 3 Air Conditioner integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant

from .coordinator import Airtouch3DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.CLIMATE]
type AirTouch3ConfigEntry = ConfigEntry[Airtouch3DataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Set up AirTouch 3 Air Conditioner from a config entry."""
    host = entry.data[CONF_HOST]
    coordinator = Airtouch3DataUpdateCoordinator(hass, entry, host)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    _LOGGER.debug("Setting up AirTouch 3 at %s", host)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTouch3ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
