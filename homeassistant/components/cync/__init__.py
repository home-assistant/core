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
_MESH_UNIQUE_IDS_DEVICE_FINALIZE_PENDING = "mesh_unique_ids_device_finalize_pending"
_MESH_UNIQUE_ID_MIGRATION_PREFIX = "__cync_mesh_id_migration__"


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
        if new_unique_id := temporary_id_map.get(entity_entry.unique_id):
            entity_registry.async_update_entity(
                entity_entry.entity_id,
                new_unique_id=new_unique_id,
            )

    light_entity_entries = get_light_entity_entries()
    final_ids_by_device: dict[str, set[str]] = {}
    source_ids_by_device: dict[str, set[str]] = {}
    for entity_entry in light_entity_entries:
        if (
            entity_entry.device_id is not None
            and entity_entry.unique_id in id_map.values()
        ):
            final_ids_by_device.setdefault(entity_entry.device_id, set()).add(
                entity_entry.unique_id
            )
            previous_unique_id = entity_entry.previous_unique_id
            if (
                previous_unique_id is not None
                and id_map.get(previous_unique_id) == entity_entry.unique_id
            ):
                source_ids_by_device.setdefault(entity_entry.device_id, set()).add(
                    previous_unique_id
                )
            elif (
                previous_unique_id is not None
                and temporary_id_map.get(previous_unique_id) == entity_entry.unique_id
            ):
                source_ids_by_device.setdefault(entity_entry.device_id, set()).add(
                    previous_unique_id.removeprefix(_MESH_UNIQUE_ID_MIGRATION_PREFIX)
                )
            else:
                source_ids_by_device.setdefault(entity_entry.device_id, set()).update(
                    old_unique_id
                    for old_unique_id, new_unique_id in id_map.items()
                    if new_unique_id == entity_entry.unique_id
                )

    entity_device_ids = {
        entity_entry.device_id
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        )
        if entity_entry.device_id is not None
    }
    device_registry = dr.async_get(hass)
    device_finalization_pending = bool(
        entry.data.get(_MESH_UNIQUE_IDS_DEVICE_FINALIZE_PENDING)
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
                source_ids_by_device.setdefault(config_entry_device.id, set()).add(
                    identifier.removeprefix(_MESH_UNIQUE_ID_MIGRATION_PREFIX)
                )
                final_ids_by_device.setdefault(config_entry_device.id, set()).add(
                    temporary_id_map[identifier]
                )
            elif not device_finalization_pending and identifier in id_map:
                source_ids_by_device.setdefault(config_entry_device.id, set()).add(
                    identifier
                )
                final_ids_by_device.setdefault(config_entry_device.id, set()).add(
                    id_map[identifier]
                )

    if not device_finalization_pending:
        for device_id in migrated_device_ids:
            device_entry = device_registry.async_get(device_id)
            if device_entry is None:
                continue
            source_ids = source_ids_by_device.get(device_id, set())
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
                _MESH_UNIQUE_IDS_DEVICE_FINALIZE_PENDING: True,
            },
        )

    for device_id in migrated_device_ids:
        device_entry = device_registry.async_get(device_id)
        if device_entry is None:
            continue
        final_ids = final_ids_by_device.get(device_id, set())
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

    data = dict(entry.data)
    data.pop(_MESH_UNIQUE_IDS_MIGRATION_PENDING)
    data.pop(_MESH_UNIQUE_IDS_DEVICE_FINALIZE_PENDING)
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
