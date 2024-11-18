"""The spotify integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import aiohttp
from spotifyaio import Device, SpotifyClient, SpotifyConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .browse_media import async_browse_media
from .const import DOMAIN, LOGGER, SPOTIFY_SCOPES
from .coordinator import SpotifyConfigEntry, SpotifyCoordinator
from .models import SpotifyData
from .util import (
    is_spotify_media_type,
    resolve_spotify_media_type,
    spotify_uri_from_media_browser_url,
)

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR]

__all__ = [
    "async_browse_media",
    "DOMAIN",
    "spotify_uri_from_media_browser_url",
    "is_spotify_media_type",
    "resolve_spotify_media_type",
]


async def async_setup_entry(hass: HomeAssistant, entry: SpotifyConfigEntry) -> bool:
    """Set up Spotify from a config entry."""
    implementation = await async_get_config_entry_implementation(hass, entry)
    session = OAuth2Session(hass, entry, implementation)

    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady from err

    spotify = SpotifyClient(async_get_clientsession(hass))

    spotify.authenticate(session.token[CONF_ACCESS_TOKEN])

    async def _refresh_token() -> str:
        await session.async_ensure_token_valid()
        token = session.token[CONF_ACCESS_TOKEN]
        if TYPE_CHECKING:
            assert isinstance(token, str)
        return token

    spotify.refresh_token_function = _refresh_token

    coordinator = SpotifyCoordinator(hass, spotify)

    await coordinator.async_config_entry_first_refresh()

    async def _update_devices() -> list[Device]:
        try:
            return await spotify.get_devices()
        except SpotifyConnectionError as err:
            raise UpdateFailed from err

    device_coordinator: DataUpdateCoordinator[list[Device]] = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{entry.title} Devices",
        config_entry=entry,
        update_interval=timedelta(minutes=5),
        update_method=_update_devices,
    )
    await device_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = SpotifyData(coordinator, session, device_coordinator)

    if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
        raise ConfigEntryAuthFailed

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Spotify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
