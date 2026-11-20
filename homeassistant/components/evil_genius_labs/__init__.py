"""The Evil Genius Labs integration."""

import pyevilgenius

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .coordinator import EvilGeniusConfigEntry, EvilGeniusUpdateCoordinator

PLATFORMS = [Platform.LIGHT]

UPDATE_INTERVAL = 10


async def async_setup_entry(hass: HomeAssistant, entry: EvilGeniusConfigEntry) -> None:
    """Set up Evil Genius Labs from a config entry."""
    coordinator = EvilGeniusUpdateCoordinator(
        hass,
        entry,
        pyevilgenius.EvilGeniusDevice(
            entry.data["host"], aiohttp_client.async_get_clientsession(hass)
        ),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: EvilGeniusConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
