"""The GeoSphere Austria Warnings integration."""

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .coordinator import GeoSphereConfigEntry, GeoSphereUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: GeoSphereConfigEntry) -> bool:
    """Set up GeoSphere Austria Warnings from a config entry."""
    coordinator = GeoSphereUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: GeoSphereConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: GeoSphereConfigEntry) -> bool:
    """Migrate old entry."""
    _LOGGER.debug("Checking entry %s with version %s", entry.unique_id, entry.version)

    if entry.version < 2:
        _LOGGER.debug("Migrating configuration from version %s", entry.version)

        old_unique_id = f"{entry.unique_id}-warning_level"
        _LOGGER.debug("Old unique ID: %s", old_unique_id)
        new_unique_id = f"{entry.unique_id}-active_warning_level"
        _LOGGER.debug("New unique ID: %s", new_unique_id)
        entity_registry = er.async_get(hass)

        # Search within this config entry: do not migrate another entry's sensor.
        old_entity = next(
            (
                entity
                for entity in er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                )
                if entity.domain == "sensor"
                and entity.platform == DOMAIN
                and entity.unique_id == old_unique_id
            ),
            None,
        )
        if old_entity is not None:
            _LOGGER.debug(
                "Existing entity found for migration, entity ID: %s",
                old_entity.entity_id,
            )
        else:
            _LOGGER.debug("No existing entity found for migration")

        conflicting_entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, new_unique_id
        )

        if conflicting_entity_id is not None and old_entity is not None:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="entity_migration_conflict",
                translation_placeholders={
                    "new_unique_id": new_unique_id,
                    "conflicting_entity_id": conflicting_entity_id,
                },
            )

        if old_entity is not None:
            _LOGGER.debug(
                "Update unique ID of entity %s to %s",
                old_entity.entity_id,
                new_unique_id,
            )
            entity_registry.async_update_entity(
                entity_id=old_entity.entity_id,
                new_unique_id=new_unique_id,
            )

        # No old entry means either the new ID is already in place or the sensor
        # has never been registered. Normal setup handles the latter.
        hass.config_entries.async_update_entry(entry, version=2)

        _LOGGER.debug("Migration to configuration version %s successful", entry.version)

    return True
