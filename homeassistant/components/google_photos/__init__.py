"""The Google Photos integration."""

from __future__ import annotations

from aiohttp import ClientError, ClientResponseError
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_FILENAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv

from . import api
from .const import DOMAIN, UPLOAD_SCOPE
from .services import async_register_services

type GooglePhotosConfigEntry = ConfigEntry[api.AsyncConfigEntryAuth]

__all__ = [
    "DOMAIN",
]

CONF_CONFIG_ENTRY_ID = "config_entry_id"

UPLOAD_SERVICE = "upload"
UPLOAD_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONFIG_ENTRY_ID): cv.string,
        vol.Required(CONF_FILENAME): vol.All(cv.ensure_list, [cv.string]),
    }
)


async def async_setup_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Set up Google Photos from a config entry."""
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )
    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    auth = api.AsyncConfigEntryAuth(hass, session)
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
    entry.runtime_data = auth

    scopes = entry.data["token"]["scope"].split(" ")
    if any(scope == UPLOAD_SCOPE for scope in scopes):
        async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GooglePhotosConfigEntry
) -> bool:
    """Unload a config entry."""
    return True
