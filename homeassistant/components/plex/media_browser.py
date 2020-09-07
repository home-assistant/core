"""Support to interface with the Plex API."""
import logging

from homeassistant.components.media_player import BrowseMedia
from homeassistant.components.media_player.errors import BrowseError

from .const import DOMAIN

EXPANDABLES = ["album", "artist", "playlist", "season", "show"]
PLAYLISTS_BROWSE_PAYLOAD = {
    "title": "Playlists",
    "media_content_id": "all",
    "media_content_type": "playlists",
    "can_play": False,
    "can_expand": True,
}
SPECIAL_METHODS = {
    "On Deck": "onDeck",
    "Recently Added": "recentlyAdded",
}

_LOGGER = logging.getLogger(__name__)


def browse_media(
    entity_id, plex_server, media_content_type=None, media_content_id=None
):
    """Implement the websocket media browsing helper."""

    def build_item_response(payload):
        """Create response payload for the provided media query."""
        media = plex_server.lookup_media(**payload)

        if media is None:
            return None

        media_info = item_payload(media)
        if media_info.can_expand:
            media_info.children = []
            for item in media:
                media_info.children.append(item_payload(item))
        return media_info

    if media_content_id and ":" in media_content_id:
        media_content_id, special_folder = media_content_id.split(":")
    else:
        special_folder = None

    if (
        media_content_type
        and media_content_type == "server"
        and media_content_id != plex_server.machine_identifier
    ):
        raise BrowseError(
            f"Plex server with ID '{media_content_id}' is not associated with {entity_id}"
        )

    if special_folder:
        if media_content_type == "server":
            library_or_section = plex_server.library
            title = plex_server.friendly_name
        elif media_content_type == "library":
            library_or_section = plex_server.library.sectionByID(media_content_id)
            title = library_or_section.title

        payload = {
            "title": title,
            "media_content_id": f"{media_content_id}:{special_folder}",
            "media_content_type": media_content_type,
            "can_play": False,
            "can_expand": True,
            "children": [],
        }

        method = SPECIAL_METHODS[special_folder]
        items = getattr(library_or_section, method)()
        for item in items:
            payload["children"].append(item_payload(item))
        return BrowseMedia(**payload)

    if media_content_type in ["server", None]:
        return server_payload(plex_server)

    if media_content_type == "library":
        return library_payload(plex_server, media_content_id)

    if media_content_type == "playlists":
        return playlists_payload(plex_server)

    payload = {
        "media_type": DOMAIN,
        "plex_key": int(media_content_id),
    }
    response = build_item_response(payload)
    if response is None:
        raise BrowseError(f"Media not found: {media_content_type} / {media_content_id}")
    return response


def item_payload(item):
    """Create response payload for a single media item."""
    payload = {
        "title": item.title,
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
        media_content_id=f"{parent_payload.media_content_id}:{special_type}",
        media_content_type=parent_payload.media_content_type,
        can_play=False,
        can_expand=True,
    )


def server_payload(plex_server):
    """Create response payload to describe libraries of the Plex server."""
    server_info = BrowseMedia(
        title=plex_server.friendly_name,
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
        library_info.children.append(item_payload(item))
    return library_info


def playlists_payload(plex_server):
    """Create response payload for all available playlists."""
    playlists_info = {**PLAYLISTS_BROWSE_PAYLOAD, "children": []}
    for playlist in plex_server.playlists():
        playlists_info["children"].append(item_payload(playlist))
    return BrowseMedia(**playlists_info)
