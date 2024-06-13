"""The spotify integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import aiohttp
import requests
from spotipy import Spotify, SpotifyException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.config_entry_oauth2_flow import (
    OAuth2Session,
    async_get_config_entry_implementation,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .browse_media import async_browse_media
from .const import DOMAIN, LOGGER, SPOTIFY_SCOPES
from .util import (
    is_spotify_media_type,
    resolve_spotify_media_type,
    spotify_uri_from_media_browser_url,
)

PLATFORMS = [Platform.MEDIA_PLAYER]

__all__ = [
    "async_browse_media",
    "DOMAIN",
    "spotify_uri_from_media_browser_url",
    "is_spotify_media_type",
    "resolve_spotify_media_type",
]


@dataclass
class HomeAssistantSpotifyData:
    """Spotify data stored in the Home Assistant data object."""

    client: Spotify
    current_user: dict[str, Any]
    devices: DataUpdateCoordinator[list[dict[str, Any]]]
    session: OAuth2Session


type SpotifyConfigEntry = ConfigEntry[HomeAssistantSpotifyData]


async def async_setup_entry(hass: HomeAssistant, entry: SpotifyConfigEntry) -> bool:
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

    async def _update_devices() -> list[dict[str, Any]]:
        if not session.valid_token:
            await session.async_ensure_token_valid()
            await hass.async_add_executor_job(
                spotify.set_auth, session.token["access_token"]
            )

        try:
            devices: dict[str, Any] | None = await hass.async_add_executor_job(
                spotify.devices
            )
        except (requests.RequestException, SpotifyException) as err:
            raise UpdateFailed from err

        if devices is None:
            return []

        return devices.get("devices", [])

    device_coordinator: DataUpdateCoordinator[list[dict[str, Any]]] = (
        DataUpdateCoordinator(
            hass,
            LOGGER,
            name=f"{entry.title} Devices",
            update_interval=timedelta(minutes=5),
            update_method=_update_devices,
        )
    )
    await device_coordinator.async_config_entry_first_refresh()

    entry.runtime_data = HomeAssistantSpotifyData(
        client=spotify,
        current_user=current_user,
        devices=device_coordinator,
        session=session,
    )

    if not set(session.token["scope"].split(" ")).issuperset(SPOTIFY_SCOPES):
        raise ConfigEntryAuthFailed

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Spotify config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
