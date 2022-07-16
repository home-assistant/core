"""The generic component."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

DOMAIN = "generic"
PLATFORMS = [Platform.CAMERA]
_LOGGER = logging.getLogger(__name__)


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_migrate_unique_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate entities to the new unique id."""

    @callback
    def _async_migrator(entity_entry: er.RegistryEntry) -> dict[str, Any] | None:
        if entity_entry.unique_id == entry.entry_id:
            # Already correct, nothing to do
            return None
        # There is only one entity, and its unique id
        # should always be the same as the config entry entry_id
        return {"new_unique_id": entry.entry_id}

    await er.async_migrate_entries(hass, entry.entry_id, _async_migrator)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate an old config entry."""

    _LOGGER.debug("Migrating from version %s", entry.version)

    if entry.version == 1:  # 1 -> 2: Eliminate 'None' for unused fields #75265.
        entry.version = 2

        data = entry.options.copy()
        for key in list(data.keys()):
            if data[key] is None:
                del data[key]
        hass.config_entries.async_update_entry(entry, options=data)

    _LOGGER.info("Migration to version %s successful", entry.version)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up generic IP camera from a config entry."""

    await _async_migrate_unique_ids(hass, entry)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
