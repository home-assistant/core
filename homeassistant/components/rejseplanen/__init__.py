"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    coordinator = RejseplanenDataUpdateCoordinator(
        hass,
        config_entry,
    )
    config_entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    _LOGGER.debug(
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
