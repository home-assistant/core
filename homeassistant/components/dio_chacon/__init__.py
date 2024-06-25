"""The dio_chacon integration."""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import DioChaconDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.COVER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up dio_chacon from a config entry."""

    _LOGGER.debug("Start of async_setup_entry for dio_chacon integration")

    hass.data.setdefault(DOMAIN, {})

    coordinator = DioChaconDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    # Store an API object for the platforms to access
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    _LOGGER.debug("Start of async_unload_entry for dio_chacon integration")

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: DioChaconDataUpdateCoordinator = entry.runtime_data
        await coordinator.async_shutdown()

    return unload_ok
