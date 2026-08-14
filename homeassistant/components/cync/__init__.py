"""The Cync integration."""

from pycync import Auth, Cync, CyncLight, User
from pycync.exceptions import AuthFailedError, CyncError

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util.ssl import get_default_context

from .const import (
    CONF_AUTHORIZE_STRING,
    CONF_EXPIRES_AT,
    CONF_REFRESH_TOKEN,
    CONF_USER_ID,
    DOMAIN,
)
from .coordinator import CyncConfigEntry, CyncCoordinator

_PLATFORMS: list[Platform] = [Platform.LIGHT, Platform.SWITCH]

_MESH_UNIQUE_IDS_MIGRATION_PENDING = "mesh_unique_ids_migration_pending"
_MESH_UNIQUE_ID_MIGRATION_PREFIX = "__cync_mesh_id_migration__"
_MIGRATE_ENTITIES_TO_TEMPORARY = "entities_to_temporary"
_MIGRATE_ENTITIES_TO_FINAL = "entities_to_final"
_MIGRATE_DEVICES_TO_TEMPORARY = "devices_to_temporary"
_MIGRATE_DEVICES_TO_FINAL = "devices_to_final"


def _migrate_unique_ids(
    hass: HomeAssistant, entry: CyncConfigEntry, cync: Cync
) -> None:
    """Migrate entity unique IDs from {home_id}-{device_id} to {home_id}-{mesh_device_id}.

    pycync 0.6.0 changed the unique ID format; migrate existing registry entries
    so automations and history are preserved after upgrading.
    """
    id_map = {
        f"{device.parent_home_id}-{device.device_id}": device.unique_id
        for home in cync.get_homes()
        for device in home.get_flattened_device_list()
        if isinstance(device, CyncLight)
        and f"{device.parent_home_id}-{device.device_id}" != device.unique_id
    }
    temporary_id_map = {
        f"{_MESH_UNIQUE_ID_MIGRATION_PREFIX}{old_unique_id}": new_unique_id
        for old_unique_id, new_unique_id in id_map.items()
    }

    def set_stage(stage: str) -> None:
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, _MESH_UNIQUE_IDS_MIGRATION_PENDING: stage},
        )

    stage = entry.data[_MESH_UNIQUE_IDS_MIGRATION_PENDING]
    if stage is True:
        stage = _MIGRATE_ENTITIES_TO_TEMPORARY
        set_stage(stage)

    if not id_map:
        return

    entity_registry = er.async_get(hass)

    def get_entity_entries() -> list[er.RegistryEntry]:
        return [
            entity_entry
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if entity_entry.platform == DOMAIN and entity_entry.domain == Platform.LIGHT
        ]

    entity_entries = get_entity_entries()

    if stage == _MIGRATE_ENTITIES_TO_TEMPORARY:
        for entity_entry in entity_entries:
            if entity_entry.unique_id in id_map:
                entity_registry.async_update_entity(
                    entity_entry.entity_id,
                    new_unique_id=(
                        f"{_MESH_UNIQUE_ID_MIGRATION_PREFIX}{entity_entry.unique_id}"
                    ),
                )
        stage = _MIGRATE_ENTITIES_TO_FINAL
        set_stage(stage)

    if stage == _MIGRATE_ENTITIES_TO_FINAL:
        entity_entries = get_entity_entries()
        for entity_entry in entity_entries:
            if new_unique_id := temporary_id_map.get(entity_entry.unique_id):
                entity_registry.async_update_entity(
                    entity_entry.entity_id,
                    new_unique_id=new_unique_id,
                )
        stage = _MIGRATE_DEVICES_TO_TEMPORARY
        set_stage(stage)

    entity_entries = get_entity_entries()
    migrated_unique_ids = id_map.keys() | id_map.values() | temporary_id_map.keys()
    migrated_device_ids = {
        entity_entry.device_id
        for entity_entry in entity_entries
        if entity_entry.unique_id in migrated_unique_ids
        and entity_entry.device_id is not None
    }
    device_registry = dr.async_get(hass)

    if stage == _MIGRATE_DEVICES_TO_TEMPORARY:
        for device_id in migrated_device_ids:
            device_entry = device_registry.async_get(device_id)
            if device_entry is None:
                continue
            temporary_identifiers = {
                (
                    domain,
                    f"{_MESH_UNIQUE_ID_MIGRATION_PREFIX}{identifier}"
                    if domain == DOMAIN and identifier in id_map
                    else identifier,
                )
                for domain, identifier in device_entry.identifiers
            }
            if temporary_identifiers != device_entry.identifiers:
                device_registry.async_update_device(
                    device_entry.id,
                    new_identifiers=temporary_identifiers,
                )
        stage = _MIGRATE_DEVICES_TO_FINAL
        set_stage(stage)

    if stage == _MIGRATE_DEVICES_TO_FINAL:
        for device_id in migrated_device_ids:
            device_entry = device_registry.async_get(device_id)
            if device_entry is None:
                continue
            final_identifiers = {
                (
                    domain,
                    temporary_id_map.get(identifier, identifier)
                    if domain == DOMAIN
                    else identifier,
                )
                for domain, identifier in device_entry.identifiers
            }
            if final_identifiers != device_entry.identifiers:
                device_registry.async_update_device(
                    device_entry.id,
                    new_identifiers=final_identifiers,
                )

        data = dict(entry.data)
        data.pop(_MESH_UNIQUE_IDS_MIGRATION_PENDING)
        hass.config_entries.async_update_entry(entry, data=data)


async def _async_create_cync(hass: HomeAssistant, entry: CyncConfigEntry) -> Cync:
    """Create an authenticated Cync client."""
    user_info = User(
        entry.data[CONF_ACCESS_TOKEN],
        entry.data[CONF_REFRESH_TOKEN],
        entry.data[CONF_AUTHORIZE_STRING],
        entry.data[CONF_USER_ID],
        expires_at=entry.data[CONF_EXPIRES_AT],
    )
    cync_auth = Auth(async_get_clientsession(hass), user=user_info)
    ssl_context = get_default_context()

    try:
        return await Cync.create(
            auth=cync_auth,
            ssl_context=ssl_context,
        )
    except AuthFailedError as ex:
        raise ConfigEntryAuthFailed("User token invalid") from ex
    except CyncError as ex:
        raise ConfigEntryNotReady("Unable to connect to Cync") from ex


async def async_migrate_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Migrate an existing Cync config entry."""
    if entry.version == 1:
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                _MESH_UNIQUE_IDS_MIGRATION_PENDING: (_MIGRATE_ENTITIES_TO_TEMPORARY),
            },
            version=2,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Set up Cync from a config entry."""
    cync = await _async_create_cync(hass, entry)

    devices_coordinator = CyncCoordinator(hass, entry, cync)

    cync.set_update_callback(devices_coordinator.on_data_update)

    await devices_coordinator.async_config_entry_first_refresh()
    entry.runtime_data = devices_coordinator

    if entry.data.get(_MESH_UNIQUE_IDS_MIGRATION_PENDING):
        _migrate_unique_ids(hass, entry, cync)

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Unload a config entry."""
    cync = entry.runtime_data.cync
    await cync.shut_down()
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
