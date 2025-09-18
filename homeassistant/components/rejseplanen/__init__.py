"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]

type RejseplanenConfigEntry = ConfigEntry[RejseplanenDataUpdateCoordinator]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    _LOGGER.info(
        "Setting up Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    await hass.config_entries.async_forward_entry_setups(
        config_entry, [Platform.SENSOR]
    )
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    _LOGGER.info(
        "Unloading Rejseplanen integration for entry: %s", config_entry.entry_id
    )
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> None:
    """Handle update."""
    _LOGGER.debug("Update listener triggered for entry: %s", config_entry.entry_id)
    await hass.config_entries.async_reload(config_entry.entry_id)
