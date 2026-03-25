"""Helper methods for common Plex integration operations."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any, TypedDict

from plexapi.gdm import GDM
from plexwebsocket import PlexWebsocket

from homeassistant.core import CALLBACK_TYPE, HomeAssistant

from .const import DOMAIN, SERVERS

if TYPE_CHECKING:
    from . import PlexServer


class PlexData(TypedDict):
    """Typed description of plex data stored in `hass.data`."""

    servers: dict[str, PlexServer]
    dispatchers: dict[str, list[CALLBACK_TYPE]]
    websockets: dict[str, PlexWebsocket]
    gdm_scanner: GDM
    gdm_debouncer: Callable[[], Coroutine[Any, Any, None]]


def get_plex_data(hass: HomeAssistant) -> PlexData:
    """Get typed data from hass.data."""
    return hass.data[DOMAIN]


def get_plex_server(hass: HomeAssistant, server_id: str) -> PlexServer:
    """Get Plex server from hass.data."""
    return get_plex_data(hass)[SERVERS][server_id]


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
