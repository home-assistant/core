"""The touchline component."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import TouchlineConfigEntry, TouchlineCoordinator

PLATFORMS = [Platform.CLIMATE]
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
    """Set up touchline from a config entry."""
    _LOGGER.debug(
        "Touchline entry id: %s Unique id: %s", entry.entry_id, entry.unique_id
    )
    coordinator = TouchlineCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def async_unload_entry(hass: HomeAssistant, entry: TouchlineConfigEntry) -> None:
    """Unload a touchline config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
