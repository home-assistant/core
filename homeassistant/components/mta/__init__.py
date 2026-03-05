"""The MTA New York City Transit integration."""

from __future__ import annotations

import asyncio

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN as DOMAIN, SUBENTRY_TYPE_BUS, SUBENTRY_TYPE_SUBWAY
from .coordinator import MTAConfigEntry, MTADataUpdateCoordinator

PLATFORMS = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: MTAConfigEntry) -> bool:
    """Set up MTA from a config entry."""
    coordinators: dict[str, MTADataUpdateCoordinator] = {}

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type not in (SUBENTRY_TYPE_SUBWAY, SUBENTRY_TYPE_BUS):
            continue

        coordinators[subentry_id] = MTADataUpdateCoordinator(hass, entry, subentry)

    # Refresh all coordinators in parallel
    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in coordinators.values()
        )
    )

    entry.runtime_data = coordinators

    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_update_entry(hass: HomeAssistant, entry: MTAConfigEntry) -> None:
    """Handle config entry update (e.g., subentry changes)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MTAConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
