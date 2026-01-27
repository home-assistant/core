"""The rejseplanen component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import RejseplanenConfigEntry, RejseplanenDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Set py_rejseplan library to WARNING level by default to reduce log noise
# Users can override in configuration.yaml with: py_rejseplan: debug
logging.getLogger("py_rejseplan").setLevel(logging.WARNING)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Set up Rejseplanen from a config entry."""
    coordinator = RejseplanenDataUpdateCoordinator(hass, config_entry)

    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    # Register update listener for subentry changes - but use minimal reload
    config_entry.async_on_unload(
        config_entry.add_update_listener(_async_update_listener)
    )

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def _async_update_listener(
    hass: HomeAssistant,
    config_entry: RejseplanenConfigEntry,
) -> None:
    """Handle update when subentries are added/removed."""
    _LOGGER.debug("Update listener triggered for entry: %s", config_entry.entry_id)

    # Instead of setting up platforms again, reload the entire config entry
    # This is the standard approach for handling subentry changes
    await hass.config_entries.async_reload(config_entry.entry_id)
