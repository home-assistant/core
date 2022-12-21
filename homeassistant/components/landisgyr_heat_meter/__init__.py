"""The Landis+Gyr Heat Meter integration."""
from __future__ import annotations

from datetime import timedelta
import logging

import ultraheat_api

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import async_migrate_entries
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up heat meter from a config entry."""

    _LOGGER.debug("Initializing %s integration on %s", DOMAIN, entry.data[CONF_DEVICE])
    reader = ultraheat_api.UltraheatReader(entry.data[CONF_DEVICE])
    api = ultraheat_api.HeatMeterService(reader)

    async def async_update_data():
        """Fetch data from the API."""
        _LOGGER.debug("Polling on %s", entry.data[CONF_DEVICE])
        return await hass.async_add_executor_job(api.read)

    # Polling is only daily to prevent battery drain.
    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name="ultraheat_gateway",
        update_method=async_update_data,
        update_interval=timedelta(days=1),
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    # Removing domain name and config entry id from entity unique id's, replacing it with device number
    if config_entry.version == 1:

        config_entry.version = 2

        device_number = config_entry.data["device_number"]

        @callback
        def update_entity_unique_id(entity_entry):
            """Update unique ID of entity entry."""
            if entity_entry.platform in entity_entry.unique_id:
                return {
                    "new_unique_id": entity_entry.unique_id.replace(
                        f"{entity_entry.platform}_{entity_entry.config_entry_id}",
                        f"{device_number}",
                    )
                }

        await async_migrate_entries(
            hass, config_entry.entry_id, update_entity_unique_id
        )
        hass.config_entries.async_update_entry(config_entry)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True
