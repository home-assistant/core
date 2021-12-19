"""Support to interface with the Plex API."""
from itertools import islice
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

from .const import DOMAIN
from .helpers import pretty_title


class UnknownMediaType(BrowseError):
    """Unknown media type."""


EXPANDABLES = ["album", "artist", "playlist", "season", "show"]
PLAYLISTS_BROWSE_PAYLOAD = {
    "title": "Playlists",
    "media_class": MEDIA_CLASS_DIRECTORY,
    "media_content_id": "all",
    "media_content_type": "playlists",
    "can_play": False,
    "can_expand": True,
}

LIBRARY_PREFERRED_LIBTYPE = {
    "show": "episode",
    "artist": "album",
}

ITEM_TYPE_MEDIA_CLASS = {
    "album": MEDIA_CLASS_ALBUM,
    "artist": MEDIA_CLASS_ARTIST,
    "episode": MEDIA_CLASS_EPISODE,
    "movie": MEDIA_CLASS_MOVIE,
    "playlist": MEDIA_CLASS_PLAYLIST,
    "season": MEDIA_CLASS_SEASON,
    "show": MEDIA_CLASS_TV_SHOW,
    "track": MEDIA_CLASS_TRACK,
    "video": MEDIA_CLASS_VIDEO,
}

_LOGGER = logging.getLogger(__name__)


def browse_media(  # noqa: C901
    entity, is_internal, media_content_type=None, media_content_id=None
):
    """Implement the websocket media browsing helper."""

    def item_payload(item, short_name=False):
        """Create response payload for a single media item."""
        try:
            media_class = ITEM_TYPE_MEDIA_CLASS[item.type]
        except KeyError as err:
            _LOGGER.debug("Unknown type received: %s", item.type)
            raise UnknownMediaType from err
        payload = {
            "title": pretty_title(item, short_name),
            "media_class": media_class,
            "media_content_id": str(item.ratingKey),
            "media_content_type": item.type,
            "can_play": True,
            "can_expand": item.type in EXPANDABLES,
        }
        if hasattr(item, "thumbUrl"):
            entity.plex_server.thumbnail_cache.setdefault(
                str(item.ratingKey), item.thumbUrl
            )

            if is_internal:
                thumbnail = item.thumbUrl
            else:
                thumbnail = entity.get_browse_image_url(item.type, item.ratingKey)

            payload["thumbnail"] = thumbnail

        return BrowseMedia(**payload)

    def library_payload(library_id):
        """Create response payload to describe contents of a specific library."""
        library = entity.plex_server.library.sectionByID(library_id)
        library_info = library_section_payload(library)
        library_info.children = []
        library_info.children.append(special_library_payload(library_info, "On Deck"))
        library_info.children.append(
            special_library_payload(library_info, "Recently Added")
        )
        for item in library.all():
            try:
                library_info.children.append(item_payload(item))
            except UnknownMediaType:
                continue
        return library_info

    def playlists_payload():
        """Create response payload for all available playlists."""
        playlists_info = {**PLAYLISTS_BROWSE_PAYLOAD, "children": []}
        for playlist in entity.plex_server.playlists():
            try:
                playlists_info["children"].append(item_payload(playlist))
            except UnknownMediaType:
                continue
        response = BrowseMedia(**playlists_info)
        response.children_media_class = MEDIA_CLASS_PLAYLIST
        return response

    def build_item_response(payload):
        """Create response payload for the provided media query."""
        media = entity.plex_server.lookup_media(**payload)

        if media is None:
            return None

        try:
            media_info = item_payload(media)
        except UnknownMediaType:
            return None
        if media_info.can_expand:
            media_info.children = []
            for item in media:
                try:
                    media_info.children.append(item_payload(item, short_name=True))
                except UnknownMediaType:
                    continue
        return media_info

    if media_content_id and ":" in media_content_id:
        media_content_id, special_folder = media_content_id.split(":")
    else:
        special_folder = None

    if (
        media_content_type
        and media_content_type == "server"
        and media_content_id != entity.plex_server.machine_identifier
    ):
        raise BrowseError(
            f"Plex server with ID '{media_content_id}' is not associated with {entity.entity_id}"
        )

    if special_folder:
        if media_content_type == "server":
            library_or_section = entity.plex_server.library
            children_media_class = MEDIA_CLASS_DIRECTORY
            title = entity.plex_server.friendly_name
        elif media_content_type == "library":
            library_or_section = entity.plex_server.library.sectionByID(
                int(media_content_id)
            )
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
            "media_content_id": f"{media_content_id}:{special_folder}",
            "media_content_type": media_content_type,
            "can_play": False,
            "can_expand": True,
            "children": [],
            "children_media_class": children_media_class,
        }

        if special_folder == "On Deck":
            items = library_or_section.onDeck()
        elif special_folder == "Recently Added":
            if library_or_section.TYPE:
                libtype = LIBRARY_PREFERRED_LIBTYPE.get(
                    library_or_section.TYPE, library_or_section.TYPE
                )
                items = library_or_section.recentlyAdded(libtype=libtype)
            else:
                recent_iter = (
                    x
                    for x in library_or_section.search(sort="addedAt:desc", limit=100)
                    if x.type in ["album", "episode", "movie"]
                )
                items = list(islice(recent_iter, 30))

        for item in items:
            try:
                payload["children"].append(item_payload(item))
            except UnknownMediaType:
                continue

        return BrowseMedia(**payload)

    try:
        if media_content_type in ("server", None):
            return server_payload(entity.plex_server)

        if media_content_type == "library":
            return library_payload(int(media_content_id))

    except UnknownMediaType as err:
        raise BrowseError(
            f"Media not found: {media_content_type} / {media_content_id}"
        ) from err

    if media_content_type == "playlists":
        return playlists_payload()

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
        media_content_id=str(section.key),
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


def server_payload(plex_server):
    """Create response payload to describe libraries of the Plex server."""
    server_info = BrowseMedia(
        title=plex_server.friendly_name,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=plex_server.machine_identifier,
        media_content_type="server",
        can_play=False,
        can_expand=True,
        children_media_class=MEDIA_CLASS_DIRECTORY,
    )
    server_info.children = []
    server_info.children.append(special_library_payload(server_info, "On Deck"))
    server_info.children.append(special_library_payload(server_info, "Recently Added"))
    for library in plex_server.library.sections():
        if library.type == "photo":
            continue
        server_info.children.append(library_section_payload(library))
    server_info.children.append(BrowseMedia(**PLAYLISTS_BROWSE_PAYLOAD))
    return server_info
