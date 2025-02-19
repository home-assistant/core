"""The OneDrive integration."""

from __future__ import annotations

from html import unescape
from json import dumps, loads
import logging
from typing import cast

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    HttpRequestException,
    OneDriveException,
)
from onedrive_personal_sdk.models.items import ItemUpdate

from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from homeassistant.components.backup import async_setup_config_entry_backup_listeners

from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN
from .coordinator import (
    OneDriveConfigEntry,
    OneDriveRuntimeData,
    OneDriveUpdateCoordinator,
)

PLATFORMS = [Platform.SENSOR]


_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    async def get_access_token() -> str:
        await session.async_ensure_token_valid()
        return cast(str, session.token[CONF_ACCESS_TOKEN])

    client = OneDriveClient(get_access_token, async_get_clientsession(hass))

    # get approot, will be created automatically if it does not exist
    try:
        approot = await client.get_approot()
    except AuthenticationError as err:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN, translation_key="authentication_failed"
        ) from err
    except (HttpRequestException, OneDriveException, TimeoutError) as err:
        _LOGGER.debug("Failed to get approot", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": "approot"},
        ) from err

    instance_id = await async_get_instance_id(hass)
    backup_folder_name = f"backups_{instance_id[:8]}"
    try:
        backup_folder = await client.create_folder(
            parent_id=approot.id, name=backup_folder_name
        )
    except (HttpRequestException, OneDriveException, TimeoutError) as err:
        _LOGGER.debug("Failed to create backup folder", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": backup_folder_name},
        ) from err

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
    async_setup_config_entry_backup_listeners(hass, DOMAIN, DATA_BACKUP_AGENT_LISTENERS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _migrate_backup_files(client: OneDriveClient, backup_folder_id: str) -> None:
    """Migrate backup files to metadata version 2."""
    files = await client.list_drive_items(backup_folder_id)