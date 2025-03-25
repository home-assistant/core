"""The GeoJSON events component."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import PLATFORMS
from .manager import GeoJsonConfigEntry, GeoJsonFeedEntityManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: GeoJsonConfigEntry
) -> bool:
    """Set up the GeoJSON events component as config entry."""
    # Create feed entity manager for all platforms.
    manager = GeoJsonFeedEntityManager(hass, config_entry)
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    await remove_orphaned_entities(hass, config_entry.entry_id)

    config_entry.runtime_data = manager
    config_entry.async_on_unload(manager.async_stop)
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    await manager.async_init()
    return True


async def remove_orphaned_entities(hass: HomeAssistant, entry_id: str) -> None:
    """Remove orphaned geo_location entities.

    This is needed because when fetching data from the external feed this integration is
    determining which entities need to be added, updated or removed by comparing the
    current with the previous data. After a restart of Home Assistant the integration
    has no previous data to compare against, and thus all entities managed by this
    integration are removed after startup.
    """
    entity_registry = er.async_get(hass)
    orphaned_entries = er.async_entries_for_config_entry(entity_registry, entry_id)
    if orphaned_entries is not None:
        for entry in orphaned_entries:
            if entry.domain == Platform.GEO_LOCATION:
                _LOGGER.debug("Removing orphaned entry %s", entry.entity_id)
                entity_registry.async_remove(entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: GeoJsonConfigEntry) -> bool:
    """Unload the GeoJSON events config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
