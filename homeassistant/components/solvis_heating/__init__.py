"""The Solvis Heating integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SolvisRemoteCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solvis Heating from a config entry."""

    _LOGGER.debug("Setting up Solvis Remote Reader")
    coordinator = SolvisRemoteCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Solvis Heating config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
