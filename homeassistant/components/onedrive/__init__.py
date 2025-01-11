"""The OneDrive integration."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
import logging

from kiota_abstractions.api_error import APIError
from kiota_abstractions.authentication import BaseBearerTokenAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.models.drive_item import DriveItem

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryError,
    ConfigEntryNotReady,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.httpx_client import create_async_httpx_client
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN, OAUTH_SCOPES
from .util import get_backup_folder_name


@dataclass
class OneDriveRuntimeData:
    """Runtime data for the OneDrive integration."""

    client: GraphServiceClient
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
    approot_id = await _get_drive_item_id(
        hass, drive_item.special.by_drive_item_id("approot").get, "approot"
    )

    backup_folder_name = await get_backup_folder_name(hass)

    # get backup folder, raise issue if it does not exist
    backup_folder_id = await _get_drive_item_id(
        hass,
        drive_item.items.by_drive_item_id(f"{approot_id}/{backup_folder_name}:").get,
        backup_folder_name,
    )

    entry.runtime_data = OneDriveRuntimeData(
        client=graph_client,
        backup_folder_id=backup_folder_id,
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Unload a OneDrive config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()


async def _get_drive_item_id(
    hass: HomeAssistant,
    func: Callable[[], Awaitable[DriveItem | None]],
    folder: str,
) -> str:
    """Get drive item id."""
    try:
        drive_item = await func()
    except APIError as err:
        if err.response_status_code == 403:
            raise ConfigEntryAuthFailed(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        if err.response_status_code == 404:
            _LOGGER.debug("Backup folder did not exist")
            async_create_issue(
                hass,
                domain=DOMAIN,
                is_fixable=True,
                issue_id="backup_folder_did_not_exist",
                translation_key="backup_folder_did_not_exist",
                translation_placeholders={"folder": folder},
                severity=IssueSeverity.ERROR,
            )
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="failed_to_get_folder",
                translation_placeholders={"folder": folder},
            ) from err
        _LOGGER.debug("Failed to get backup folder", exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": folder},
        ) from err

    if drive_item is None or not drive_item.id:
        _LOGGER.debug("Failed to get backup folder, was None")
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="failed_to_get_folder",
            translation_placeholders={"folder": folder},
        )
    return drive_item.id
