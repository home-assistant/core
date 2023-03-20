"""The GeoJSON events component."""
from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import (
    async_entries_for_config_entry,
    async_get,
)
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, FEED, PLATFORMS
from .manager import GeoJsonFeedEntityManager

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the GeoJSON events component."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    latitude = conf.get(CONF_LATITUDE, hass.config.latitude)
    longitude = conf.get(CONF_LONGITUDE, hass.config.longitude)
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data={
                CONF_LATITUDE: latitude,
                CONF_LONGITUDE: longitude,
                CONF_RADIUS: conf[CONF_RADIUS],
                CONF_URL: conf[CONF_URL],
                CONF_SCAN_INTERVAL: scan_interval,
            },
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up the GeoJSON events component as config entry."""
    hass.data.setdefault(DOMAIN, {})
    feeds = hass.data[DOMAIN].setdefault(FEED, {})

    # Create feed entity manager for all platforms.
    manager = GeoJsonFeedEntityManager(hass, config_entry)
    feeds[config_entry.entry_id] = manager
    _LOGGER.debug("Feed entity manager added for %s", config_entry.entry_id)
    # Remove orphaned geo_location entities.
    entity_registry = async_get(hass)
    orphaned_entries = async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    if orphaned_entries is not None:
        for entry in orphaned_entries:
            if entry.domain == Platform.GEO_LOCATION:
                _LOGGER.debug("Removing orphaned entry %s", entry.entity_id)
                entity_registry.async_remove(entry.entity_id)
    await manager.async_init()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload the GeoJSON events config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager = hass.data[DOMAIN][FEED].pop(entry.entry_id)
        await manager.async_stop()
    return unload_ok
