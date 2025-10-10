"""The Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinators import NSCoordinatorsManager

_LOGGER = logging.getLogger(__name__)


type NSConfigEntry = ConfigEntry[NSCoordinatorsManager]

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""

    # Create the coordinators manager
    coordinators_manager = NSCoordinatorsManager(hass, entry)

    # Set up all coordinators for existing routes
    await coordinators_manager.async_setup()

    entry.runtime_data = coordinators_manager

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_reload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    # Unload all coordinators
    await entry.runtime_data.async_unload_all()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
