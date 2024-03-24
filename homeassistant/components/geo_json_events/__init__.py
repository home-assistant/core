"""The GeoJSON events component."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)

from .const import DOMAIN, PLATFORMS
from .manager import GeoJsonFeedEntityManager

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the GeoJSON events component as config entry."""
    feeds = hass.data.setdefault(DOMAIN, {})
    # Create feed entity manager for all platforms.
    manager = GeoJsonFeedEntityManager(hass, config_entry)
    feeds[config_entry.entry_id] = manager
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    await remove_orphaned_entities(hass, config_entry.entry_id)
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
    entity_registry = async_get(hass)
    orphaned_entries = async_entries_for_config_entry(entity_registry, entry_id)
    if orphaned_entries is not None:
        for entry in orphaned_entries:
            if entry.domain == Platform.GEO_LOCATION:
                _LOGGER.debug("Removing orphaned entry %s", entry.entity_id)
                entity_registry.async_remove(entry.entity_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the GeoJSON events config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager: GeoJsonFeedEntityManager = hass.data[DOMAIN].pop(entry.entry_id)
        await manager.async_stop()
    return unload_ok
