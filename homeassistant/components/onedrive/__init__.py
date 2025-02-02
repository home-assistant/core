"""The OneDrive integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.drives.item.items.items_request_builder import (
    ItemsRequestBuilder,
)
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.folder import Folder

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN, OAUTH_SCOPES


@dataclass
class OneDriveRuntimeData:
    """Runtime data for the OneDrive integration."""

    items: ItemsRequestBuilder
    backup_folder_id: str


type OneDriveConfigEntry = ConfigEntry[OneDriveRuntimeData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    auth_provider = BaseBearerTokenAuthenticationProvider(
        access_token_provider=OneDriveConfigEntryAccessTokenProvider(session)
    )
    adapter = GraphRequestAdapter(
        auth_provider=auth_provider,
        client=create_async_httpx_client(hass, follow_redirects=True),
    )

    graph_client = GraphServiceClient(
        request_adapter=adapter,
        scopes=OAUTH_SCOPES,
    )
    assert entry.unique_id
    drive_item = graph_client.drives.by_drive_id(entry.unique_id)

    # get approot, will be created automatically if it does not exist
    try:
        approot = await drive_item.special.by_drive_item_id("approot").get()
    except APIError as err:
        if err.response_status_code == 403:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        _LOGGER.debug("Failed to get approot", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": "approot"},
        ) from err

    if approot is None or not approot.id:
        _LOGGER.debug("Failed to get approot, was None")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": "approot"},
        )

    instance_id = await async_get_instance_id(hass)
    backup_folder_id = await _async_create_folder_if_not_exists(
        items=drive_item.items,
        base_folder_id=approot.id,
        folder=f"backups_{instance_id[:8]}",
    )

    entry.runtime_data = OneDriveRuntimeData(
        items=drive_item.items,
        backup_folder_id=backup_folder_id,
    )

    _async_notify_backup_listeners_soon(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    _async_notify_backup_listeners_soon(hass)
    return True


def _async_notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()


@callback
def _async_notify_backup_listeners_soon(hass: HomeAssistant) -> None:
    hass.loop.call_soon(_async_notify_backup_listeners, hass)


async def _async_create_folder_if_not_exists(
    items: ItemsRequestBuilder,
    base_folder_id: str,
    folder: str,
) -> str:
    """Check if a folder exists and create it if it does not exist."""
    folder_item: DriveItem | None = None

    try:
        folder_item = await items.by_drive_item_id(f"{base_folder_id}:/{folder}:").get()
    except APIError as err:
        if err.response_status_code != 404:
            _LOGGER.debug("Failed to get folder %s", folder, exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="failed_to_get_folder",
                translation_placeholders={"folder": folder},
            ) from err
        # is 404 not found, create folder
        _LOGGER.debug("Creating folder %s", folder)
        request_body = DriveItem(
            name=folder,
            folder=Folder(),
            additional_data={
                "@microsoft_graph_conflict_behavior": "fail",
            },
        )
        try:
            folder_item = await items.by_drive_item_id(base_folder_id).children.post(
                request_body
            )
        except APIError as create_err:
            _LOGGER.debug("Failed to create folder %s", folder, exc_info=True)
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN,
                translation_key="failed_to_create_folder",
                translation_placeholders={"folder": folder},
            ) from create_err
        _LOGGER.debug("Created folder %s", folder)
    else:
        _LOGGER.debug("Found folder %s", folder)
    if folder_item is None or not folder_item.id:
        _LOGGER.debug("Failed to get folder %s, was None", folder)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": folder},
        )
    return folder_item.id
