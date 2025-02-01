"""The OneDrive integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from onedrive_personal_sdk import OneDriveClient
from onedrive_personal_sdk.exceptions import (
    AuthenticationError,
    HttpRequestException,
    OneDriveException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.instance_id import async_get as async_get_instance_id

from .api import OneDriveConfigEntryAccessTokenProvider
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN


@dataclass
class OneDriveRuntimeData:
    """Runtime data for the OneDrive integration."""

    client: OneDriveClient
    token_provider: OneDriveConfigEntryAccessTokenProvider
    backup_folder_id: str


type OneDriveConfigEntry = ConfigEntry[OneDriveRuntimeData]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: OneDriveConfigEntry) -> bool:
    """Set up OneDrive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)

    session = OAuth2Session(hass, entry, implementation)

    token_provider = OneDriveConfigEntryAccessTokenProvider(session)

    client = OneDriveClient(token_provider, async_get_clientsession(hass))

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

    entry.runtime_data = OneDriveRuntimeData(
        client=client,
        token_provider=token_provider,
        backup_folder_id=backup_folder.id,
    )

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
