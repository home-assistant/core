"""The OneDrive integration."""

from __future__ import annotations

import logging

from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import CONF_BACKUP_FOLDER, DATA_BACKUP_AGENT_LISTENERS, OAUTH_SCOPES
from .util import async_create_folder_if_not_exists

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
    await async_create_folder_if_not_exists(
        items=graph_client.drives.by_drive_id(entry.unique_id).items,
        folder_path=entry.data[CONF_BACKUP_FOLDER],
    )

    entry.runtime_data = graph_client

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
