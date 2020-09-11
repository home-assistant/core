"""Support to interface with the Plex API."""
import logging

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.const import (
    MEDIA_CLASS_ALBUM,
    MEDIA_CLASS_APP,
    MEDIA_CLASS_ARTIST,
    MEDIA_CLASS_CHANNEL,
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_PLAYLIST,
    MEDIA_CLASS_SEASON,
    MEDIA_CLASS_TRACK,
    MEDIA_CLASS_TV_SHOW,
    MEDIA_CLASS_VIDEO,
    MEDIA_TYPE_APPS,
    MEDIA_TYPE_CHANNELS,
)
from homeassistant.components.media_player.errors import BrowseError

from .const import DOMAIN


class UnknownMediaType(BrowseError):
    """Unknown media type."""


EXPANDABLES = ["album", "artist", "playlist", "season", "show"]
PLAYLISTS_BROWSE_PAYLOAD = {
    "title": "Playlists",
    "media_class": MEDIA_CLASS_PLAYLIST,
    "media_content_id": "all",
    "media_content_type": "playlists",
    "can_play": False,
    "can_expand": True,
}
SPECIAL_METHODS = {
    "On Deck": "onDeck",
    "Recently Added": "recentlyAdded",
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


def browse_media_library(channels: bool = False) -> BrowseMedia:
    """Create response payload to describe contents of a specific library."""
    ais_library_info = BrowseMedia(
        title="AIS Audio",
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id="library",
        media_content_type="library",
        can_play=False,
        can_expand=True,
        children=[],
    )

    ais_library_info.children.append(
        BrowseMedia(
            title="Apps",
            media_class=MEDIA_CLASS_APP,
            media_content_id="apps",
            media_content_type=MEDIA_TYPE_APPS,
            can_expand=True,
            can_play=False,
        )
    )

    return ais_library_info


def browse_media(media_content_type=None, media_content_id=None):
    """Implement the websocket media browsing helper."""

    if media_content_type in [None, "library"]:
        return browse_media_library(channels=False)

    response = None

    # if media_content_type == MEDIA_TYPE_APPS:
    #     response = BrowseMedia(
    #         title="Apps",
    #         media_class=MEDIA_CLASS_APP,
    #         media_content_id="apps",
    #         media_content_type=MEDIA_TYPE_APPS,
    #         can_expand=True,
    #         can_play=False,
    #         children=[
    #             BrowseMedia(
    #                 title=app.name,
    #                 thumbnail=self.coordinator.roku.app_icon_url(app.app_id),
    #                 media_class=MEDIA_CLASS_APP,
    #                 media_content_id=app.app_id,
    #                 media_content_type=MEDIA_TYPE_APP,
    #                 can_play=True,
    #                 can_expand=False,
    #             )
    #             for app in self.coordinator.data.apps
    #         ],
    #     )
    #
    # if media_content_type == MEDIA_TYPE_CHANNELS:
    #     response = BrowseMedia(
    #         title="Channels",
    #         media_class=MEDIA_CLASS_CHANNEL,
    #         media_content_id="channels",
    #         media_content_type=MEDIA_TYPE_CHANNELS,
    #         can_expand=True,
    #         can_play=False,
    #         children=[
    #             BrowseMedia(
    #                 title=channel.name,
    #                 media_class=MEDIA_CLASS_CHANNEL,
    #                 media_content_id=channel.number,
    #                 media_content_type=MEDIA_TYPE_CHANNEL,
    #                 can_play=True,
    #                 can_expand=False,
    #             )
    #             for channel in self.coordinator.data.channels
    #         ],
    #     )

    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def item_payload(item):
    """Create response payload for a single media item."""
    try:
        media_class = ITEM_TYPE_MEDIA_CLASS[item.type]
    except KeyError as err:
        _LOGGER.debug("Unknown type received: %s", item.type)
        raise UnknownMediaType from err
    payload = {
        "title": item.title,
        "media_class": media_class,
        "media_content_id": str(item.ratingKey),
        "media_content_type": item.type,
        "can_play": True,
        "can_expand": item.type in EXPANDABLES,
    }
    if hasattr(item, "thumbUrl"):
        payload["thumbnail"] = item.thumbUrl

    return BrowseMedia(**payload)


def library_section_payload(section):
    """Create response payload for a single library section."""
    return BrowseMedia(
        title=section.title,
        media_class=MEDIA_CLASS_DIRECTORY,
        media_content_id=section.key,
        media_content_type="library",
        can_play=False,
        can_expand=True,
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


def library_payload(plex_server, library_id):
    """Create response payload to describe contents of a specific library."""
    library = plex_server.library.sectionByID(library_id)
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


def playlists_payload(plex_server):
    """Create response payload for all available playlists."""
    playlists_info = {**PLAYLISTS_BROWSE_PAYLOAD, "children": []}
    for playlist in plex_server.playlists():
        try:
            playlists_info["children"].append(item_payload(playlist))
        except UnknownMediaType:
            continue
    return BrowseMedia(**playlists_info)
