"""The Fing integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import FingDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.DEVICE_TRACKER]

type FingConfigEntry = ConfigEntry[FingDataUpdateCoordinator]


async def async_setup_entry(hass: HomeAssistant, config_entry: FingConfigEntry) -> bool:
    """Set up a skeleton component."""
    _LOGGER.info(config_entry.entry_id)
    config_entry.async_on_unload(
        config_entry.add_update_listener(async_update_listener)
    )

    await _setup_coordinator(hass, config_entry)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Return boolean to indicate that initialization was successfully.
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: FingConfigEntry
) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )
    if not unload_ok:
        return False

    return True


async def async_update_listener(hass: HomeAssistant, config_entry: FingConfigEntry):
    """Update component when options changed."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def _setup_coordinator(hass: HomeAssistant, config_entry: FingConfigEntry):
    """Initialize the coordinator."""

    coordinator = FingDataUpdateCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()
    config_entry.runtime_data = coordinator
