"""The Google Photos integration."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponseError
from google_photos_library_api.api import GooglePhotosLibraryApi

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import api
from .const import DOMAIN
from .coordinator import GooglePhotosConfigEntry, GooglePhotosUpdateCoordinator
from .services import async_register_services

__all__ = [
    "DOMAIN",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Set up Google Photos from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    web_session = async_get_clientsession(hass)
    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(web_session, oauth_session)
    try:
        await auth.async_get_access_token()
    except ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                "OAuth session is not valid, reauth required"
            ) from err
        raise ConfigEntryNotReady from err
    except ClientError as err:
        raise ConfigEntryNotReady from err
    coordinator = GooglePhotosUpdateCoordinator(
        hass, entry, GooglePhotosLibraryApi(auth)
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Unload a config entry."""
    return True
