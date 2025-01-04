"""The OneDrive integration."""

from __future__ import annotations

from dataclasses import dataclass

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import DATA_BACKUP_AGENT_LISTENERS, OAUTH_SCOPES


@dataclass
class OneDriveConfigEntryData:
    """Data for OneDrive config entry."""

    graph_client: GraphServiceClient
    drive_id: str


type OneDriveConfigEntry = ConfigEntry[OneDriveConfigEntryData]


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

    try:
        drives = await graph_client.drives.get()
    except APIError as err:
        raise ConfigEntryNotReady from err

    if not drives or not drives.value or not drives.value[0].id:
        raise ConfigEntryError("No drives found")

    entry.runtime_data = OneDriveConfigEntryData(
        graph_client=graph_client,
        drive_id=drives.value[0].id,  # TODO: Select drive
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
