"""Support for the Swedish weather institute weather service."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_registry import RegistryEntry, async_migrate_entries

PLATFORMS = [Platform.WEATHER]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SMHI forecast as config entry."""

    @callback
    def async_migrate_callback(entity_entry: RegistryEntry) -> dict | None:
        """
        Define a callback to migrate appropriate to new unique IDs.

        Old: {latitude}, {longitude}
        New: {entry_id}, {latitude}, {longitude}
        """

        if entity_entry.unique_id.startswith(entry.entry_id):
            return None

        new_unique_id = f"{entry.entry_id}, {entry.data[CONF_LATITUDE]}, {entry.data[CONF_LONGITUDE]}"

        _LOGGER.debug(
            "Migrating entity %s from old unique ID '%s' to new unique ID '%s'",
            entity_entry.entity_id,
            entity_entry.unique_id,
            new_unique_id,
        )

        return {"new_unique_id": new_unique_id}

    await async_migrate_entries(hass, entry.entry_id, async_migrate_callback)

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
