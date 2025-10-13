"""The Nederlandse Spoorwegen integration."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import SUBENTRY_TYPE_ROUTE
from .coordinator import NSConfigEntry, NSDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Set up Nederlandse Spoorwegen from a config entry."""
    coordinators: dict[str, NSDataUpdateCoordinator] = {}

    # Set up coordinators for all existing routes
    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type == SUBENTRY_TYPE_ROUTE:
            coordinator = NSDataUpdateCoordinator(
                hass,
                entry,
                subentry_id,
                subentry,
            )

            coordinators[subentry_id] = coordinator

    entry.runtime_data = coordinators

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()
    return True


async def async_reload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> None:
    """Reload NS integration when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: NSConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
