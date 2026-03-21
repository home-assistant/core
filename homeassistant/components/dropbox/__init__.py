"""The Dropbox integration."""

from __future__ import annotations

from python_dropbox_api import (
    DropboxAPIClient,
    DropboxAuthException,
    DropboxUnknownException,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
    OAuth2Session,
    async_get_config_entry_implementation,
)

from .auth import DropboxConfigEntryAuth
from .const import DATA_BACKUP_AGENT_LISTENERS, DOMAIN

type DropboxConfigEntry = ConfigEntry[DropboxAPIClient]


async def async_setup_entry(hass: HomeAssistant, entry: DropboxConfigEntry) -> bool:
    """Set up Dropbox from a config entry."""
    try:
        oauth2_implementation = await async_get_config_entry_implementation(hass, entry)
    except ImplementationUnavailableError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="oauth2_implementation_unavailable",
        ) from err
    oauth2_session = OAuth2Session(hass, entry, oauth2_implementation)

    auth = DropboxConfigEntryAuth(
        aiohttp_client.async_get_clientsession(hass), oauth2_session
    )

    client = DropboxAPIClient(auth)

    try:
        await client.get_account_info()
    except DropboxAuthException as err:
        raise ConfigEntryAuthFailed from err
    except (DropboxUnknownException, TimeoutError) as err:
        raise ConfigEntryNotReady from err

    entry.runtime_data = client

    def async_notify_backup_listeners() -> None:
        for listener in hass.data.get(DATA_BACKUP_AGENT_LISTENERS, []):
            listener()

    entry.async_on_unload(entry.async_on_state_change(async_notify_backup_listeners))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: DropboxConfigEntry) -> bool:
    """Unload a config entry."""
    return True
