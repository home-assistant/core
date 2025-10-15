"""The Silent Wave integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from pysilentwave.exceptions import SilentWaveError

from .coordinator import (
    TheSilentWaveCoordinator,
    TheSilentWaveConfigEntry,
)
from .const import DOMAIN


_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR]


async def async_setup_entry(
    hass: HomeAssistant, entry: TheSilentWaveConfigEntry
) -> bool:
    """Set up TheSilentWave from a config entry."""
    entry.runtime_data = coordinator = TheSilentWaveCoordinator(hass, entry)
    
    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: TheSilentWaveConfigEntry
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
