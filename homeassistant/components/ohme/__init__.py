"""Set up ohme integration."""

import logging

from homeassistant import core

from .const import PLATFORMS
from .coordinator import OhmeConfigEntry, OhmeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: core.HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Set up Ohme from a config entry."""

    coordinator = OhmeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: core.HomeAssistant, entry: OhmeConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
