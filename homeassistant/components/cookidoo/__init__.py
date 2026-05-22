"""The Cookidoo integration."""

import logging

from cookidoo_api import CookidooAuthException, CookidooRequestException

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import DOMAIN
from .coordinator import CookidooConfigEntry, CookidooDataUpdateCoordinator
from .helpers import cookidoo_from_config_entry

PLATFORMS: list[Platform] = [
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.SENSOR,
    Platform.TODO,
]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Set up Cookidoo from a config entry."""

    coordinator = CookidooDataUpdateCoordinator(
        hass, await cookidoo_from_config_entry(hass, entry), entry
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CookidooConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: CookidooConfigEntry
) -> bool:
    """Migrate config entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1 and config_entry.minor_version == 1:
        # Add the unique uuid
        cookidoo = await cookidoo_from_config_entry(hass, config_entry)

        try:
            await cookidoo.login()
            user_info = await cookidoo.get_user_info()
        except (CookidooRequestException, CookidooAuthException) as e:
            _LOGGER.error(
                "Could not migrate config config_entry: %s",
                str(e),
            )
            return False

        new_unique_id = user_info.id
        old_prefix = config_entry.entry_id

        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=config_entry.entry_id
        )
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry_id=config_entry.entry_id
        )
        for dev in device_entries:
            new_identifiers = {
                (DOMAIN, new_unique_id) if domain == DOMAIN else (domain, identifier)
                for domain, identifier in dev.identifiers
            }
            device_registry.async_update_device(dev.id, new_identifiers=new_identifiers)
        for ent in entity_entries:
            if ent.unique_id and ent.unique_id.startswith(f"{old_prefix}_"):
                entity_registry.async_update_entity(
                    ent.entity_id,
                    new_unique_id=f"{new_unique_id}{ent.unique_id[len(old_prefix) :]}",
                )

        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, minor_version=3
        )

    if config_entry.version == 1 and config_entry.minor_version == 2:
        # Migrate unique_id from old CIAM sub to community profile id
        cookidoo = await cookidoo_from_config_entry(hass, config_entry)

        try:
            await cookidoo.login()
            user_info = await cookidoo.get_user_info()
        except (CookidooRequestException, CookidooAuthException) as e:
            _LOGGER.error(
                "Could not migrate config config_entry: %s",
                str(e),
            )
            return False

        old_unique_id = config_entry.unique_id
        new_unique_id = user_info.id

        device_registry = dr.async_get(hass)
        entity_registry = er.async_get(hass)
        device_entries = dr.async_entries_for_config_entry(
            device_registry, config_entry_id=config_entry.entry_id
        )
        entity_entries = er.async_entries_for_config_entry(
            entity_registry, config_entry_id=config_entry.entry_id
        )
        for dev in device_entries:
            new_identifiers = {
                (DOMAIN, new_unique_id) if domain == DOMAIN else (domain, identifier)
                for domain, identifier in dev.identifiers
            }
            device_registry.async_update_device(dev.id, new_identifiers=new_identifiers)
        for ent in entity_entries:
            if (
                ent.unique_id
                and old_unique_id
                and ent.unique_id.startswith(f"{old_unique_id}_")
            ):
                entity_registry.async_update_entity(
                    ent.entity_id,
                    new_unique_id=f"{new_unique_id}{ent.unique_id[len(old_unique_id) :]}",
                )

        hass.config_entries.async_update_entry(
            config_entry, unique_id=new_unique_id, minor_version=3
        )

    _LOGGER.debug(
        "Migration to version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
