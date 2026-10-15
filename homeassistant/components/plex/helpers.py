"""Helper methods for common Plex integration operations."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypedDict

from plexapi.gdm import GDM
from plexwebsocket import PlexWebsocket

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN

if TYPE_CHECKING:
    from . import PlexServer


@dataclass
class PlexRuntimeData:
    """Runtime data for a Plex config entry."""

    server: PlexServer
    websocket: PlexWebsocket
    dispatchers: list[CALLBACK_TYPE]


type PlexConfigEntry = ConfigEntry[PlexRuntimeData]


class PlexData(TypedDict):
    """Typed description of plex data stored in `hass.data`."""

    gdm_scanner: GDM
    gdm_debouncer: Callable[[], Coroutine[Any, Any, None]]


DATA_PLEX: HassKey[PlexData] = HassKey(DOMAIN)


def get_plex_data(hass: HomeAssistant) -> PlexData:
    """Get typed data from hass.data."""
    return hass.data[DATA_PLEX]


def get_plex_servers(hass: HomeAssistant) -> dict[str, PlexServer]:
    """Get the Plex servers of all loaded config entries."""
    entries: list[PlexConfigEntry] = hass.config_entries.async_loaded_entries(DOMAIN)
    return {
        entry.runtime_data.server.machine_identifier: entry.runtime_data.server
        for entry in entries
    }


def get_plex_server(hass: HomeAssistant, server_id: str) -> PlexServer:
    """Get a loaded Plex server by its identifier."""
    return get_plex_servers(hass)[server_id]


def pretty_title(media, short_name=False):
    """Return a formatted title for the given media item."""
    year = None
    if media.type == "album":
        if short_name:
            title = media.title
        else:
            title = f"{media.parentTitle} - {media.title}"
    elif media.type == "episode":
        title = f"{media.seasonEpisode.upper()} - {media.title}"
        if not short_name:
            title = f"{media.grandparentTitle} - {title}"
    elif media.type == "season":
        title = media.title
        if not short_name:
            title = f"{media.parentTitle} - {title}"
    elif media.type == "track":
        title = f"{media.index}. {media.title}"
    else:
        title = media.title

    if media.type in ["album", "movie", "season"]:
        year = media.year

    if year:
        title += f" ({year!s})"

    return title
