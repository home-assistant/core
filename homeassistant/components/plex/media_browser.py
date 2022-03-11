"""Support to interface with the Plex API."""
from __future__ import annotations

import json
import logging

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_SEASON,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_CLASS_VIDEO,
)
from homeassistant.components.media_player.errors import BrowseError

from .const import DOMAIN, PLEX_URI_SCHEME
from .helpers import pretty_title


class UnknownMediaType(BrowseError):
    """Unknown media type."""


HUB_PREFIX = "hub:"
EXPANDABLES = ["album", "artist", "playlist", "season", "show"]
PLAYLISTS_BROWSE_PAYLOAD = {
    "title": "Playlists",
    "media_class": MEDIA_CLASS_DIRECTORY,
    "media_content_id": PLEX_URI_SCHEME + "all",
    "media_content_type": "playlists",
    "can_play": False,
    "can_expand": True,
}
ITEM_TYPE_MEDIA_CLASS = {
    "album": MEDIA_CLASS_ALBUM,
    "artist": MEDIA_CLASS_ARTIST,
    "clip": MEDIA_CLASS_VIDEO,
    "episode": MEDIA_CLASS_EPISODE,
    "mixed": MEDIA_CLASS_DIRECTORY,
    "movie": MEDIA_CLASS_MOVIE,
    "playlist": MEDIA_CLASS_PLAYLIST,
    "season": MEDIA_CLASS_SEASON,
    "show": MEDIA_CLASS_TV_SHOW,
    "station": MEDIA_CLASS_ARTIST,
    "track": MEDIA_CLASS_TRACK,
    "video": MEDIA_CLASS_VIDEO,
}

_LOGGER = logging.getLogger(__name__)


def browse_media(  # noqa: C901
    plex_server, is_internal, media_content_type, media_content_id, *, platform=None
):
    """Implement the websocket media browsing helper."""

    def item_payload(item, short_name=False, extra_content_id_params=None):
        """Create response payload for a single media item."""
        try:
            media_class = ITEM_TYPE_MEDIA_CLASS[item.type]
        except KeyError as err:
            _LOGGER.debug("Unknown type received: %s", item.type)
            raise UnknownMediaType from err
        content_id = {"plex_key": item.ratingKey}
        if extra_content_id_params:
            content_id |= extra_content_id_params
        payload = {
            "title": pretty_title(item, short_name),
            "media_class": media_class,
            "media_content_id": PLEX_URI_SCHEME + json.dumps(content_id),
            "media_content_type": item.type,
            "can_play": True,
            "can_expand": item.type in EXPANDABLES,
        }
        if hasattr(item, "thumbUrl"):
            plex_server.thumbnail_cache.setdefault(str(item.ratingKey), item.thumbUrl)
            if is_internal:
                thumbnail = item.thumbUrl
            else:
                thumbnail = get_proxy_image_url(
                    plex_server.machine_identifier,
                    item.ratingKey,
                )
            payload["thumbnail"] = thumbnail

        return BrowseMedia(**payload)

    def library_payload(library_id):
        """Create response payload to describe contents of a specific library."""
        library = plex_server.library.sectionByID(library_id)
        library_info = library_section_payload(library)
        library_info.children = [special_library_payload(library_info, "Recommended")]
        for item in library.all():
            try:
                library_info.children.append(item_payload(item))
            except UnknownMediaType:
                continue
        return library_info

    def playlists_payload(platform):
        """Create response payload for all available playlists."""
        playlists_info = {**PLAYLISTS_BROWSE_PAYLOAD, "children": []}
        for playlist in plex_server.playlists():
            if playlist.playlistType != "audio" and platform == "sonos":
                continue
            try:
                playlists_info["children"].append(item_payload(playlist))
            except UnknownMediaType:
                continue
        response = BrowseMedia(**playlists_info)
        response.children_media_class = MEDIA_CLASS_PLAYLIST
        return response

    def build_item_response(payload):
        """Create response payload for the provided media query."""
        media = plex_server.lookup_media(**payload)

        if media is None:
            return None

        try:
            media_info = item_payload(media)
        except UnknownMediaType:
            return None
        if media_info.can_expand:
            media_info.children = []
            if media.TYPE == "artist" and platform != "sonos":
                if (station := media.station()) is not None:
                    media_info.children.append(station_payload(station))
            for item in media:
                try:
                    media_info.children.append(item_payload(item, short_name=True))
                except UnknownMediaType:
                    continue
        return media_info

    if media_content_id:
        assert media_content_id.startswith(PLEX_URI_SCHEME)
        media_content_id = media_content_id[len(PLEX_URI_SCHEME) :]

    if media_content_id and media_content_id.startswith(HUB_PREFIX):
        media_content_id = media_content_id[len(HUB_PREFIX) :]
        location, hub_identifier = media_content_id.split(":")
        if location == "server":
            hub = next(
                x
                for x in plex_server.library.hubs()
                if x.hubIdentifier == hub_identifier
            )
            media_content_id = f"{HUB_PREFIX}server:{hub.hubIdentifier}"
        else:
            library_section = plex_server.library.sectionByID(int(location))
            hub = next(
                x for x in library_section.hubs() if x.hubIdentifier == hub_identifier
            )
            media_content_id = f"{HUB_PREFIX}{hub.librarySectionID}:{hub.hubIdentifier}"
        try:
            children_media_class = ITEM_TYPE_MEDIA_CLASS[hub.type]
        except KeyError as err:
            raise BrowseError(f"Unknown type received: {hub.type}") from err
        payload = {
            "title": hub.title,
            "media_class": MEDIA_CLASS_DIRECTORY,
            "media_content_id": PLEX_URI_SCHEME + media_content_id,
            "media_content_type": hub.type,
            "can_play": False,
            "can_expand": True,
            "children": [],
            "children_media_class": children_media_class,
        }
        for item in hub.items:
            if hub.type == "station":
                if platform == "sonos":
                    continue
                payload["children"].append(station_payload(item))
            else:
                extra_params = None
                hub_context = hub.context.split(".")[-1]
                if hub_context in ("continue", "inprogress", "ondeck"):
                    extra_params = {"resume": True}
                payload["children"].append(
                    item_payload(item, extra_content_id_params=extra_params)
                )
        return BrowseMedia(**payload)

    special_folder = None
    if media_content_id and "plex_key" in media_content_id:
        media_content_id = json.loads(media_content_id)["plex_key"]
    elif media_content_id and ":" in media_content_id:
        media_content_id, special_folder = media_content_id.split(":")

    if special_folder:
        if media_content_type == "server":
            library_or_section = plex_server.library
            children_media_class = MEDIA_CLASS_DIRECTORY
            title = plex_server.friendly_name
        elif media_content_type == "library":
            library_or_section = plex_server.library.sectionByID(int(media_content_id))
            title = library_or_section.title
            try:
                children_media_class = ITEM_TYPE_MEDIA_CLASS[library_or_section.TYPE]
            except KeyError as err:
                raise BrowseError(
                    f"Unknown type received: {library_or_section.TYPE}"
                ) from err
        else:
            raise BrowseError(
                f"Media not found: {media_content_type} / {media_content_id}"
            )

        payload = {
            "title": title,
            "media_class": MEDIA_CLASS_DIRECTORY,
            "media_content_id": PLEX_URI_SCHEME
            + f"{media_content_id}:{special_folder}",
            "media_content_type": media_content_type,
            "can_play": False,
            "can_expand": True,
            "children": [],
            "children_media_class": children_media_class,
        }

        if special_folder == "Recommended":
            for item in library_or_section.hubs():
                if item.type == "photo":
                    continue
                payload["children"].append(hub_payload(item))

        return BrowseMedia(**payload)

    try:
        if media_content_type in ("server", None):
            return server_payload(plex_server, platform)

        if media_content_type == "library":
            return library_payload(int(media_content_id))

    except UnknownMediaType as err:
        raise BrowseError(
            f"Media not found: {media_content_type} / {media_content_id}"
        ) from err

    if media_content_type == "playlists":
        return playlists_payload(platform)

    payload = {
        "media_type": DOMAIN,
        "plex_key": int(media_content_id),
    }
    response = build_item_response(payload)
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def library_section_payload(section):
    """Create response payload for a single library section."""
    try:
        children_media_class = ITEM_TYPE_MEDIA_CLASS[section.TYPE]
    except KeyError as err:
        _LOGGER.debug("Unknown type received: %s", section.TYPE)
        raise UnknownMediaType from err
    return BrowseMedia(
        title=section.title,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=PLEX_URI_SCHEME + str(section.key),
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children_media_class=children_media_class,
    )


def special_library_payload(parent_payload, special_type):
    """Create response payload for special library folders."""
    title = f"{special_type} ({parent_payload.title})"
    return BrowseMedia(
        title=title,
        media_class=parent_payload.media_class,
        media_content_id=f"{parent_payload.media_content_id}:{special_type}",
        media_content_type=parent_payload.media_content_type,
        can_play=False,
        can_expand=True,
        children_media_class=parent_payload.children_media_class,
    )


def server_payload(plex_server, platform):
    """Create response payload to describe libraries of the Plex server."""
    server_info = BrowseMedia(
        title=plex_server.friendly_name,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=PLEX_URI_SCHEME + plex_server.machine_identifier,
        media_content_type="server",
        can_play=False,
        can_expand=True,
        children=[],
        children_media_class=MEDIA_CLASS_DIRECTORY,
    )
    if platform != "sonos":
        server_info.children.append(special_library_payload(server_info, "Recommended"))
    for library in plex_server.library.sections():
        if library.type == "photo":
            continue
        if library.type != "artist" and platform == "sonos":
            continue
        server_info.children.append(library_section_payload(library))
    server_info.children.append(BrowseMedia(**PLAYLISTS_BROWSE_PAYLOAD))
    return server_info


def hub_payload(hub):
    """Create response payload for a hub."""
    if hasattr(hub, "librarySectionID"):
        media_content_id = f"{HUB_PREFIX}{hub.librarySectionID}:{hub.hubIdentifier}"
    else:
        media_content_id = f"{HUB_PREFIX}server:{hub.hubIdentifier}"
    payload = {
        "title": hub.title,
        "media_class": MEDIA_CLASS_DIRECTORY,
        "media_content_id": PLEX_URI_SCHEME + media_content_id,
        "media_content_type": hub.type,
        "can_play": False,
        "can_expand": True,
    }
    return BrowseMedia(**payload)


def station_payload(station):
    """Create response payload for a music station."""
    return BrowseMedia(
        title=station.title,
        media_class=ITEM_TYPE_MEDIA_CLASS[station.type],
        media_content_id=PLEX_URI_SCHEME + station.key,
        media_content_type="station",
        can_play=True,
        can_expand=False,
    )


def get_proxy_image_url(
    server_id: str,
    media_content_id: str,
) -> str:
    """Generate an url for a Plex media browser image."""
    return f"/api/plex_image_proxy/{server_id}/{media_content_id}"
