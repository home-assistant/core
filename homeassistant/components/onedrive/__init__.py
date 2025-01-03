"""The OneDrive integration."""

from __future__ import annotations

from msgraph import GraphRequestAdapter, GraphServiceClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.httpx_client import get_async_client

from .api import (
    OneDriveBearerTokenAuthenticationProvider,
    OneDriveConfigEntryAccessTokenProvider,
)
from .const import DATA_BACKUP_AGENT_LISTENERS

type OneDriveConfigEntry = ConfigEntry[GraphServiceClient]


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    auth_provider = OneDriveBearerTokenAuthenticationProvider(
        access_token_provider=OneDriveConfigEntryAccessTokenProvider(session)
    )
    adapter = GraphRequestAdapter(
        auth_provider=auth_provider, client=get_async_client(hass)
    )

    graph_client = GraphServiceClient(request_adapter=adapter)

    # TODO: setup check

    entry.runtime_data = graph_client

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
