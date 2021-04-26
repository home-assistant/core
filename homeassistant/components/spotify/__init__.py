"""The spotify integration."""

import aiohttp
from spotipy import Spotify, SpotifyException
import voluptuous as vol

from homeassistant.components.media_player import DOMAIN as MEDIA_PLAYER_DOMAIN
from homeassistant.components.spotify import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_CREDENTIALS, CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    DATA_SPOTIFY_CLIENT,
    DATA_SPOTIFY_ME,
    DATA_SPOTIFY_SESSION,
    DOMAIN,
    SPOTIFY_SCOPES,
)

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

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_SPOTIFY_CLIENT: spotify,
        DATA_SPOTIFY_ME: current_user,
        DATA_SPOTIFY_SESSION: session,
    }

    if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
        raise ConfigEntryAuthFailed

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, MEDIA_PLAYER_DOMAIN)
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Spotify config entry."""
    # Unload entities for this entry/device.
    await hass.config_entries.async_forward_entry_unload(entry, MEDIA_PLAYER_DOMAIN)

    # Cleanup
    del hass.data[DOMAIN][entry.entry_id]
    if not hass.data[DOMAIN]:
        del hass.data[DOMAIN]

    return True
