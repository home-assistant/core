"""The OneDrive integration."""

from collections.abc import Awaitable, Callable
from html import unescape
from json import dumps, loads
import logging
from typing import TYPE_CHECKING, cast

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)

from homeassistant.components.backup import async_get_manager
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.instance_id import async_get as async_get_instance_id
from homeassistant.helpers.typing import ConfigType

from .const import CONF_FOLDER_ID, CONF_FOLDER_NAME, DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .coordinator import (
    OneDriveConfigEntry,
    OneDriveRuntimeData,
    OneDriveUpdateCoordinator,
)
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OneDrive integration."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
    """Set up OneDrive from a config entry."""
    client, get_access_token = await _get_onedrive_client(hass, entry)

    # get approot, will be created automatically if it does not exist
    approot = await _handle_item_operation(client.get_approot, "approot")
    folder_name = entry.data[CONF_FOLDER_NAME]

    try:
        backup_folder = await _handle_item_operation(
            lambda: client.get_drive_item(path_or_id=entry.data[CONF_FOLDER_ID]),
            folder_name,
        )
    except NotFoundError:
        _LOGGER.debug("Creating backup folder %s", folder_name)
        backup_folder = await _handle_item_operation(
            lambda: client.create_folder(parent_id=approot.id, name=folder_name),
            folder_name,
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_FOLDER_ID: backup_folder.id}
        )

    # update in case folder was renamed manually inside OneDrive
    if backup_folder.name != entry.data[CONF_FOLDER_NAME]:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_FOLDER_NAME: backup_folder.name}
        )

    coordinator = OneDriveUpdateCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = OneDriveRuntimeData(
        client=client,
        token_function=get_access_token,
        backup_folder_id=backup_folder.id,
        coordinator=coordinator,
    )

    try:
        await _migrate_backup_files(client, backup_folder.id)
    except OneDriveException as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_migrate_files",
        ) from err

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
    """Unload a OneDrive config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)


async def _migrate_backup_files(client: OneDriveClient, backup_folder_id: str) -> None:
    """Migrate backup files from metadata version 1 to version 2.

    Version 1: Backup metadata was stored in the backup file's description field.
    Version 2: Backup metadata is stored in a separate .metadata.json file.
    """
    files = await client.list_drive_items(backup_folder_id)
    for file in files:
        if file.description and '"metadata_version": 1' in (
            metadata_json := unescape(file.description)
        ):
            metadata = loads(metadata_json)
            del metadata["metadata_version"]
            metadata_filename = file.name.rsplit(".", 1)[0] + ".metadata.json"
            await client.upload_file(
                backup_folder_id,
                metadata_filename,
                dumps(metadata),
            )
            _LOGGER.debug("Migrated backup file %s", file.name)


async def async_migrate_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> None:
    """Migrate old entry."""

    if (version := entry.version) == 1 and (minor_version := entry.minor_version) == 1:
        _LOGGER.debug(
            "Migrating OneDrive config entry from version %s.%s", version, minor_version
        )
        client, _ = await _get_onedrive_client(hass, entry)
        instance_id = await async_get_instance_id(hass)
        try:
            approot = await client.get_approot()
            folder = await client.get_drive_item(
                f"{approot.id}:/backups_{instance_id[:8]}:"
            )
        except AuthenticationError as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except OneDriveException as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="failed_to_get_folder",
                translation_placeholders={"folder": f"backups_{instance_id[:8]}"},
            ) from err

        hass.config_entries.async_update_entry(
            entry,
            data={
                **entry.data,
                CONF_FOLDER_ID: folder.id,
                CONF_FOLDER_NAME: f"backups_{instance_id[:8]}",
            },
            minor_version=2,
        )
        _LOGGER.debug("Migration to version 1.2 successful")

    if entry.version == 1 and entry.minor_version == 2:
        if TYPE_CHECKING:
            assert entry.unique_id
        # Microsoft returns drive IDs with inconsistent casing
        drive_id = entry.unique_id.upper()
        if (
            other_entry := hass.config_entries.async_entry_for_domain_unique_id(
                DOMAIN, drive_id
            )
        ) and other_entry.entry_id != entry.entry_id:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="duplicate_drive",
                translation_placeholders={"title": other_entry.title},
            )

        entity_registry = er.async_get(hass)

        @callback
        def _uppercase_drive_id(
            entity_entry: er.RegistryEntry,
        ) -> dict[str, str] | None:
            if entity_entry.unique_id.startswith(drive_id):
                return None
            new_unique_id = drive_id + entity_entry.unique_id[len(drive_id) :]
            # A casing flip may have created a duplicate, keep the older entity
            if (
                (
                    existing_entity_id := entity_registry.async_get_entity_id(
                        entity_entry.domain, DOMAIN, new_unique_id
                    )
                )
                and (existing_entity := entity_registry.async_get(existing_entity_id))
                and existing_entity.config_entry_id == entry.entry_id
            ):
                if existing_entity.created_at <= entity_entry.created_at:
                    entity_registry.async_remove(entity_entry.entity_id)
                    return None
                entity_registry.async_remove(existing_entity_id)
            return {"new_unique_id": new_unique_id}

        await er.async_migrate_entries(hass, entry.entry_id, _uppercase_drive_id)
        device_registry = dr.async_get(hass)
        # A casing flip may have created duplicate devices, keep the oldest
        if devices := sorted(
            dr.async_entries_for_config_entry(device_registry, entry.entry_id),
            key=lambda device: device.created_at,
        ):
            device, *duplicates = devices
            for duplicate in duplicates:
                for entity_entry in er.async_entries_for_device(
                    entity_registry, duplicate.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(
                        entity_entry.entity_id, device_id=device.id
                    )
                device_registry.async_remove_device(duplicate.id)
            device_registry.async_update_device(
                device.id, new_identifiers={(DOMAIN, drive_id)}
            )
        if entry.unique_id != drive_id:
            async_get_manager(hass).async_rename_agent(
                f"{DOMAIN}.{entry.unique_id}",
                f"{DOMAIN}.{drive_id}",
                # No other config entry has the drive ID, checked above
                overwrite_orphaned_settings=True,
            )
        hass.config_entries.async_update_entry(
            entry, unique_id=drive_id, minor_version=3
        )
        _LOGGER.debug("Migration to version 1.3 successful")


async def _get_onedrive_client(
    hass: HomeAssistant, entry: OneDriveConfigEntry
) -> tuple[OneDriveClient, Callable[[], Awaitable[str]]]:
    """Get OneDrive client."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    # Refresh up front, so a failure surfaces here instead of from inside the client
    await session.async_ensure_token_valid()

    async def get_access_token() -> str:
        await session.async_ensure_token_valid()
        return cast(str, session.token[CONF_ACCESS_TOKEN])

    return (
        OneDriveClient(get_access_token, async_get_clientsession(hass)),
        get_access_token,
    )


async def _handle_item_operation[T](func: Callable[[], Awaitable[T]], folder: str) -> T:
    try:
        return await func()
    except NotFoundError:
        raise
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except (OneDriveException, TimeoutError) as err:
        _LOGGER.debug("Failed to get approot", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": folder},
        ) from err
