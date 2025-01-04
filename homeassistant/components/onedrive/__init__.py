"""The OneDrive integration."""

from __future__ import annotations

import logging

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.models.drive_item import DriveItem
from msgraph.generated.models.folder import Folder

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import CONF_BACKUP_FOLDER, DATA_BACKUP_AGENT_LISTENERS, OAUTH_SCOPES

type OneDriveConfigEntry = ConfigEntry[GraphServiceClient]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_provider = BaseBearerTokenAuthenticationProvider(
        access_token_provider=OneDriveConfigEntryAccessTokenProvider(session)
    )
    adapter = GraphRequestAdapter(
        auth_provider=auth_provider, client=get_async_client(hass)
    )

    graph_client = GraphServiceClient(
        request_adapter=adapter,
        scopes=OAUTH_SCOPES,
    )

    # check the backup folder exists, if it does not exist, create it
    backup_folder = str(entry.data[CONF_BACKUP_FOLDER]).strip("/")
    try:
        await (
            graph_client.drives.by_drive_id(entry.unique_id)
            .items.by_drive_item_id(f"root:/{backup_folder}:")
            .get()
        )
    except APIError as err:
        if err.response_status_code != 404:
            raise ConfigEntryNotReady from err
        # did not exist, create it
        _LOGGER.debug("Creating backup folder %s", backup_folder)
        folders = backup_folder.split("/")
        for i, folder in enumerate(folders):
            try:
                await (
                    graph_client.drives.by_drive_id(entry.unique_id)
                    .items.by_drive_item_id(f"root:/{"/".join(folders[: i + 1])}:")
                    .get()
                )
            except APIError as get_folder_err:
                if err.response_status_code != 404:
                    raise ConfigEntryNotReady from get_folder_err
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
                    await (
                        graph_client.drives.by_drive_id(entry.unique_id)
                        .items.by_drive_item_id(f"root:/{"/".join(folders[:i])}:")
                        .children.post(request_body)
                    )
                except APIError as create_err:
                    raise ConfigEntryError(
                        f"Failed to create folder {folder}"
                    ) from create_err
                _LOGGER.debug("Created folder %s", folder)
            else:
                _LOGGER.debug("Found folder %s", folder)

    entry.runtime_data = graph_client

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
