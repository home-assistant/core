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

_PLATFORMS: list[Platform] = [Platform.LIGHT]

_MESH_UNIQUE_IDS_MIGRATION_PENDING = "mesh_unique_ids_migration_pending"
_MESH_UNIQUE_IDS_DEVICE_IDENTIFIER_PARKING_COMPLETE = (
    "mesh_unique_ids_device_identifier_parking_complete"
)
_MESH_UNIQUE_ID_MIGRATION_PREFIX = "__cync_mesh_id_migration__"

type _DeviceIdentifierMigrations = dict[str, tuple[set[str], set[str]]]


def _record_device_identifier_migration(
    migrations: _DeviceIdentifierMigrations,
    device_id: str,
    source_id: str,
    final_id: str,
) -> None:
    """Record a device identifier migration."""
    source_ids, final_ids = migrations.setdefault(device_id, (set(), set()))
    source_ids.add(source_id)
    final_ids.add(final_id)


def _migrate_light_entity_unique_ids(
    hass: HomeAssistant,
    entry: CyncConfigEntry,
    id_map: dict[str, str],
    temporary_id_map: dict[str, str],
) -> tuple[_DeviceIdentifierMigrations, set[str]]:
    """Migrate light entity unique IDs and return their device migrations."""

    entity_registry = er.async_get(hass)

    def get_light_entity_entries() -> list[er.RegistryEntry]:
        return [
            entity_entry
            for entity_entry in er.async_entries_for_config_entry(
                entity_registry, entry.entry_id
            )
            if entity_entry.platform == DOMAIN and entity_entry.domain == Platform.LIGHT
        ]

    pending_entity_migrations = {
        entity_entry.entity_id: (
            entity_entry.unique_id,
            id_map[entity_entry.unique_id],
        )
        for entity_entry in get_light_entity_entries()
        if entity_entry.unique_id in id_map
        and not (
            entity_entry.previous_unique_id is not None
            and (
                id_map.get(entity_entry.previous_unique_id) == entity_entry.unique_id
                or temporary_id_map.get(entity_entry.previous_unique_id)
                == entity_entry.unique_id
            )
        )
    }
    while pending_entity_migrations:
        for entity_id, (_, new_unique_id) in list(pending_entity_migrations.items()):
            if entity_registry.async_get_entity_id(
                Platform.LIGHT, DOMAIN, new_unique_id
            ):
                continue
            entity_registry.async_update_entity(
                entity_id,
                new_unique_id=new_unique_id,
            )
            pending_entity_migrations.pop(entity_id)
            break
        else:
            break

    for entity_id, (old_unique_id, _) in pending_entity_migrations.items():
        entity_registry.async_update_entity(
            entity_id,
            new_unique_id=f"{_MESH_UNIQUE_ID_MIGRATION_PREFIX}{old_unique_id}",
        )
    for entity_entry in get_light_entity_entries():
        if temporary_new_unique_id := temporary_id_map.get(entity_entry.unique_id):
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=temporary_new_unique_id,
            )

    device_identifier_migrations: _DeviceIdentifierMigrations = {}
    for entity_entry in get_light_entity_entries():
        if (
            entity_entry.device_id is None
            or entity_entry.unique_id not in id_map.values()
        ):
            continue
        previous_unique_id = entity_entry.previous_unique_id
        source_ids: tuple[str, ...]
        if (
            previous_unique_id is not None
            and id_map.get(previous_unique_id) == entity_entry.unique_id
        ):
            source_ids = (previous_unique_id,)
        elif (
            previous_unique_id is not None
            and temporary_id_map.get(previous_unique_id) == entity_entry.unique_id
        ):
            source_ids = (
                previous_unique_id.removeprefix(_MESH_UNIQUE_ID_MIGRATION_PREFIX),
            )
        else:
            source_ids = tuple(
                old_unique_id
                for old_unique_id, new_unique_id in id_map.items()
                if new_unique_id == entity_entry.unique_id
            )
        for source_id in source_ids:
            _record_device_identifier_migration(
                device_identifier_migrations,
                entity_entry.device_id,
                source_id,
                entity_entry.unique_id,
            )

    entity_device_ids = {
        entity_entry.device_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entity_entry.device_id is not None
    }
    return device_identifier_migrations, entity_device_ids


def _migrate_device_identifiers(
    hass: HomeAssistant,
    entry: CyncConfigEntry,
    id_map: dict[str, str],
    temporary_id_map: dict[str, str],
    device_identifier_migrations: _DeviceIdentifierMigrations,
    entity_device_ids: set[str],
) -> None:
    """Migrate device identifiers to mesh-based IDs."""
    device_registry = dr.async_get(hass)
    device_identifier_parking_complete = bool(
        entry.data.get(_MESH_UNIQUE_IDS_DEVICE_IDENTIFIER_PARKING_COMPLETE)
    )
    migrated_device_ids: set[str] = set()
    for config_entry_device in dr.async_entries_for_config_entry(
        device_registry, entry.entry_id
    ):
        cync_identifiers = {
            identifier
            for domain, identifier in config_entry_device.identifiers
            if domain == DOMAIN
        }
        if not cync_identifiers.intersection(
            id_map.keys() | id_map.values() | temporary_id_map.keys()
        ):
            continue
        migrated_device_ids.add(config_entry_device.id)
        if config_entry_device.id in entity_device_ids:
            continue
        for identifier in cync_identifiers:
            if identifier in temporary_id_map:
                _record_device_identifier_migration(
                    device_identifier_migrations,
                    config_entry_device.id,
                    identifier.removeprefix(_MESH_UNIQUE_ID_MIGRATION_PREFIX),
                    temporary_id_map[identifier],
                )
            elif not device_identifier_parking_complete and identifier in id_map:
                _record_device_identifier_migration(
                    device_identifier_migrations,
                    config_entry_device.id,
                    identifier,
                    id_map[identifier],
                )

    if not device_identifier_parking_complete:
        for device_id in migrated_device_ids:
            device_entry = device_registry.async_get(device_id)
            if device_entry is None:
                continue
            source_ids, _ = device_identifier_migrations.get(device_id, (set(), set()))
            temporary_identifiers = {
                (
                    domain,
                    f"{_MESH_UNIQUE_ID_MIGRATION_PREFIX}{identifier}"
                    if domain == DOMAIN and identifier in source_ids
                    else identifier,
                )
                for domain, identifier in device_entry.identifiers
            }
            if temporary_identifiers != device_entry.identifiers:
                device_registry.async_update_device(
                    device_id,
                    new_identifiers=temporary_identifiers,
                )
        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                _MESH_UNIQUE_IDS_DEVICE_IDENTIFIER_PARKING_COMPLETE: True,
            },
        )

    for device_id in migrated_device_ids:
        device_entry = device_registry.async_get(device_id)
        if device_entry is None:
            continue
        _, final_ids = device_identifier_migrations.get(device_id, (set(), set()))
        final_identifiers = {
            (
                domain,
                temporary_id_map.get(identifier, identifier)
                if domain == DOMAIN
                else identifier,
            )
            for domain, identifier in device_entry.identifiers
        } | {(DOMAIN, identifier) for identifier in final_ids}
        if final_identifiers != device_entry.identifiers:
            device_registry.async_update_device(
                device_id,
                new_identifiers=final_identifiers,
            )


# Legacy and mesh ID namespaces can overlap. Entity-less devices have no
# previous_unique_id history to disambiguate a partially completed migration.
# Persist that all device source identifiers are parked before finalizing them,
# so setup retries cannot remap an already-final identifier.
def _migrate_unique_ids(
    hass: HomeAssistant, entry: CyncConfigEntry, cync: Cync
) -> None:
    """Migrate legacy light registry IDs to pycync's mesh-based unique IDs."""
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
    device_identifier_migrations, entity_device_ids = _migrate_light_entity_unique_ids(
        hass, entry, id_map, temporary_id_map
    )
    _migrate_device_identifiers(
        hass,
        entry,
        id_map,
        temporary_id_map,
        device_identifier_migrations,
        entity_device_ids,
    )

    data = dict(entry.data)
    data.pop(_MESH_UNIQUE_IDS_MIGRATION_PENDING)
    data.pop(_MESH_UNIQUE_IDS_DEVICE_IDENTIFIER_PARKING_COMPLETE)
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
                _MESH_UNIQUE_IDS_MIGRATION_PENDING: True,
            },
            version=2,
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: CyncConfigEntry) -> bool:
    """Set up Cync from a config entry."""
    cync = await _async_create_cync(hass, entry)
    entry.async_on_unload(cync.shut_down)

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
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
