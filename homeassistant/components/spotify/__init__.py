"""The spotify integration."""

from dataclasses import dataclass
from typing import Any

import aiohttp
from spotipy import Spotify, SpotifyException
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_CREDENTIALS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from . import config_flow
from .browse_media import async_browse_media
from .const import DOMAIN, SPOTIFY_SCOPES
from .util import is_spotify_media_type, resolve_spotify_media_type

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Inclusive(CONF_CLIENT_ID, ATTR_CREDENTIALS): cv.string,
                vol.Inclusive(CONF_CLIENT_SECRET, ATTR_CREDENTIALS): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [Platform.MEDIA_PLAYER]


__all__ = [
    "async_browse_media",
    "DOMAIN",
    "is_spotify_media_type",
    "resolve_spotify_media_type",
]


@dataclass
class HomeAssistantSpotifyData:
    """Spotify data stored in the Home Assistant data object."""

    client: Spotify
    current_user: dict[str, Any]
    session: OAuth2Session


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Spotify integration."""
    if DOMAIN not in config:
        return True

    if CONF_CLIENT_ID in config[DOMAIN]:
        config_flow.SpotifyFlowHandler.async_register_implementation(
            hass,
            config_entry_oauth2_flow.LocalOAuth2Implementation(
                hass,
                DOMAIN,
                config[DOMAIN][CONF_CLIENT_ID],
                config[DOMAIN][CONF_CLIENT_SECRET],
                "https://accounts.spotify.com/authorize",
                "https://accounts.spotify.com/api/token",
            ),
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Spotify from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    spotify = Spotify(auth=session.token["access_token"])

    try:
        current_user = await hass.async_add_executor_job(spotify.me)
    except SpotifyException as err:
        raise ConfigEntryNotReady from err

    if not current_user:
        raise ConfigEntryNotReady

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = HomeAssistantSpotifyData(
        client=spotify,
        current_user=current_user,
        session=session,
    )

    if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
        raise ConfigEntryAuthFailed

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Spotify config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][entry.entry_id]
    return unload_ok
