"""Initialize the Redgtech integration for Home Assistant."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .const import DOMAIN
from .coordinator import RedgtechDataUpdateCoordinator, RedgtechConfigEntry

_LOGGER = logging.getLogger(__name__)


PLATFORMS: list[Platform] = [Platform.SWITCH]

async def async_setup_entry(hass: HomeAssistant, entry: RedgtechConfigEntry) -> bool:
    """Set up Redgtech from a config entry."""
    _LOGGER.debug("Setting up Redgtech entry: %s", entry.entry_id)
    coordinator = RedgtechDataUpdateCoordinator(hass, entry)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _LOGGER.debug("Successfully set up Redgtech entry: %s", entry.entry_id)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: RedgtechConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Redgtech entry: %s", entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
