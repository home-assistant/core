"""The Google Drive integration."""

from __future__ import annotations

from collections.abc import Callable

from aiohttp.client_exceptions import ClientError, ClientResponseError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import instance_id
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.util.hass_dict import HassKey

from .api import AsyncConfigEntryAuth, DriveClient
from .const import DOMAIN

DATA_BACKUP_AGENT_LISTENERS: HassKey[list[Callable[[], None]]] = HassKey(
    f"{DOMAIN}.backup_agent_listeners"
)


type GoogleDriveConfigEntry = ConfigEntry[DriveClient]


async def async_setup_entry(hass: HomeAssistant, entry: GoogleDriveConfigEntry) -> bool:
    """Set up Google Drive from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    auth = AsyncConfigEntryAuth(hass, OAuth2Session(hass, entry, implementation))

    # Test we can refresh the token and raise ConfigEntryAuthFailed or ConfigEntryNotReady if not
    await auth.check_and_refresh_token()

    client = DriveClient(
        session=async_get_clientsession(hass),
        ha_instance_id=await instance_id.async_get(hass),
        access_token=None,
        auth=auth,
    )
    entry.runtime_data = client

    # Test we can access Google Drive and raise if not
    try:
        await client.async_create_ha_root_folder_if_not_exists()
    except ClientError as err:
        if isinstance(err, ClientResponseError) and 400 <= err.status < 500:
            raise ConfigEntryError(
                translation_key="config_entry_error_folder_4xx"
            ) from err
        raise ConfigEntryNotReady from err

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GoogleDriveConfigEntry
) -> bool:
    """Unload a config entry."""
    hass.async_create_task(_notify_backup_listeners(hass), eager_start=False)
    return True


async def _notify_backup_listeners(hass: HomeAssistant) -> None:
    for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
        listener()
