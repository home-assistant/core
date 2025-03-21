"""The OneDrive integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from html import unescape
from json import dumps, loads
import logging
from typing import cast

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    NotFoundError,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import Item, ItemUpdate

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
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
from .services import async_register_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the OneDrive integration."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
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

    # write instance id to description
    if backup_folder.description != (instance_id := await async_get_instance_id(hass)):
        await _handle_item_operation(
            lambda: client.update_drive_item(
                backup_folder.id, ItemUpdate(description=instance_id)
            ),
            folder_name,
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

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _migrate_backup_files(client: OneDriveClient, backup_folder_id: str) -> None:
    """Migrate backup files to metadata version 2."""
    files = await client.list_drive_items(backup_folder_id)
    for file in files:
        if file.description and '"metadata_version": 1' in (
            metadata_json := unescape(file.description)
        ):
            metadata = loads(metadata_json)
            del metadata["metadata_version"]
            metadata_filename = file.name.rsplit(".", 1)[0] + ".metadata.json"
            metadata_file = await client.upload_file(
                backup_folder_id,
                metadata_filename,
                dumps(metadata),
            )
            metadata_description = {
                "metadata_version": 2,
                "backup_id": metadata["backup_id"],
                "backup_file_id": file.id,
            }
            await client.update_drive_item(
                path_or_id=metadata_file.id,
                data=ItemUpdate(description=dumps(metadata_description)),
            )
            await client.update_drive_item(
                path_or_id=file.id,
                data=ItemUpdate(description=""),
            )
            _LOGGER.debug("Migrated backup file %s", file.name)


async def async_migrate_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Migrate old entry."""
    if entry.version > 1:
        # This means the user has downgraded from a future version
        return False

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
        except OneDriveException:
            _LOGGER.exception("Migration to version 1.2 failed")
            return False

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
    return True


async def _get_onedrive_client(
    hass: HomeAssistant, entry: OneDriveConfigEntry
) -> tuple[OneDriveClient, Callable[[], Awaitable[str]]]:
    """Get OneDrive client."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    async def get_access_token() -> str:
        await session.async_ensure_token_valid()
        return cast(str, session.token[CONF_ACCESS_TOKEN])

    return (
        OneDriveClient(get_access_token, async_get_clientsession(hass)),
        get_access_token,
    )


async def _handle_item_operation(
    func: Callable[[], Awaitable[Item]], folder: str
) -> Item:
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
