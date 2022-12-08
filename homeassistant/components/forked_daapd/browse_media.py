"""Browse media for forked-daapd."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Union, cast
from urllib.parse import quote, unquote

from homeassistant.components.media_player import BrowseMedia, MediaClass, MediaType
from homeassistant.components.media_player.errors import BrowseError
from homeassistant.helpers.network import is_internal_request

from .const import CAN_PLAY_TYPE, URI_SCHEMA

if TYPE_CHECKING:
    from . import media_player

MEDIA_TYPE_DIRECTORY = "directory"

TOP_LEVEL_LIBRARY = {
    "Albums": (MediaClass.ALBUM, MediaType.ALBUM, ""),
    "Artists": (MediaClass.ARTIST, MediaType.ARTIST, ""),
    "Playlists": (MediaClass.PLAYLIST, MediaType.PLAYLIST, ""),
    "Albums by Genre": (MediaClass.GENRE, MediaType.GENRE, MediaType.ALBUM),
    "Tracks by Genre": (MediaClass.GENRE, MediaType.GENRE, MediaType.TRACK),
    "Artists by Genre": (MediaClass.GENRE, MediaType.GENRE, MediaType.ARTIST),
    "Directories": (MediaClass.DIRECTORY, MEDIA_TYPE_DIRECTORY, ""),
}
MEDIA_TYPE_TO_MEDIA_CLASS = {
    MediaType.ALBUM: MediaClass.ALBUM,
    MediaType.APP: MediaClass.APP,
    MediaType.ARTIST: MediaClass.ARTIST,
    MediaType.TRACK: MediaClass.TRACK,
    MediaType.PLAYLIST: MediaClass.PLAYLIST,
    MediaType.GENRE: MediaClass.GENRE,
    MEDIA_TYPE_DIRECTORY: MediaClass.DIRECTORY,
}
CAN_EXPAND_TYPE = {
    MediaType.ALBUM,
    MediaType.ARTIST,
    MediaType.PLAYLIST,
    MediaType.GENRE,
    MEDIA_TYPE_DIRECTORY,
}
# The keys and values in the below dict are identical only because the
# HA constants happen to align with the Owntone constants.
OWNTONE_TYPE_TO_MEDIA_TYPE = {
    "track": MediaType.TRACK,
    "playlist": MediaType.PLAYLIST,
    "artist": MediaType.ARTIST,
    "album": MediaType.ALBUM,
    "genre": MediaType.GENRE,
    MediaType.APP: MediaType.APP,  # This is just for passthrough
    MEDIA_TYPE_DIRECTORY: MEDIA_TYPE_DIRECTORY,  # This is just for passthrough
}
MEDIA_TYPE_TO_OWNTONE_TYPE = {v: k for k, v in OWNTONE_TYPE_TO_MEDIA_TYPE.items()}

# media_content_id is a uri in the form of SCHEMA:Title:OwnToneURI:Subtype (Subtype only used for Genre)
# OwnToneURI is in format library:type:id (for directories, id is path)
# media_content_type - type of item (mostly used to check if playable or can expand)
# Owntone type may differ from media_content_type when media_content_type is a directory
# Owntone type is used in our own branching, but media_content_type is used for determining playability


@dataclass
class MediaContent:
    """Class for representing Owntone media content."""

    title: str
    type: str
    id_or_path: str
    subtype: str

    def __init__(self, media_content_id: str) -> None:
        """Create MediaContent from media_content_id."""
        (
            _schema,
            self.title,
            _library,
            self.type,
            self.id_or_path,
            self.subtype,
        ) = media_content_id.split(":")
        self.title = unquote(self.title)  # Title may have special characters
        self.id_or_path = unquote(self.id_or_path)  # May have special characters
        self.type = OWNTONE_TYPE_TO_MEDIA_TYPE[self.type]


def create_owntone_uri(media_type: str, id_or_path: str) -> str:
    """Create an Owntone uri."""
    return f"library:{MEDIA_TYPE_TO_OWNTONE_TYPE[media_type]}:{quote(id_or_path)}"


def create_media_content_id(
    title: str,
    owntone_uri: str = "",
    media_type: str = "",
    id_or_path: str = "",
    subtype: str = "",
) -> str:
    """Create a media_content_id.

    Either owntone_uri or both type and id_or_path must be specified.
    """
    if not owntone_uri:
        owntone_uri = create_owntone_uri(media_type, id_or_path)
    return f"{URI_SCHEMA}:{quote(title)}:{owntone_uri}:{subtype}"


def is_owntone_media_content_id(media_content_id: str) -> bool:
    """Return whether this media_content_id is from our integration."""
    return media_content_id[: len(URI_SCHEMA)] == URI_SCHEMA


def convert_to_owntone_uri(media_content_id: str) -> str:
    """Convert media_content_id to Owntone URI."""
    return ":".join(media_content_id.split(":")[2:-1])


async def get_owntone_content(
    master: media_player.ForkedDaapdMaster,
    media_content_id: str,
) -> BrowseMedia:
    """Create response for the given media_content_id."""

    media_content = MediaContent(media_content_id)
    result: list[dict[str, int | str]] | dict[str, Any] | None = None
    if media_content.type == MediaType.APP:
        return base_owntone_library()
    # Query API for next level
    if media_content.type == MEDIA_TYPE_DIRECTORY:
        # returns tracks, directories, and playlists
        directory_path = media_content.id_or_path
        if directory_path:
            result = await master.api.get_directory(directory=directory_path)
        else:
            result = await master.api.get_directory()
        if result is None:
            raise BrowseError(
                f"Media not found for {media_content.type} / {media_content_id}"
            )
        # Fill in children with subdirectories
        children = []
        assert isinstance(result, dict)
        for directory in result["directories"]:
            path = directory["path"]
            children.append(
                BrowseMedia(
                    title=path,
                    media_class=MediaClass.DIRECTORY,
                    media_content_id=create_media_content_id(
                        title=path, media_type=MEDIA_TYPE_DIRECTORY, id_or_path=path
                    ),
                    media_content_type=MEDIA_TYPE_DIRECTORY,
                    can_play=False,
                    can_expand=True,
                )
            )
        result = result["tracks"]["items"] + result["playlists"]["items"]
        return create_browse_media_response(
            master,
            media_content,
            cast(list[dict[str, Union[int, str]]], result),
            children,
        )
    if media_content.id_or_path == "":  # top level search
        if media_content.type == MediaType.ALBUM:
            result = (
                await master.api.get_albums()
            )  # list of albums with name, artist, uri
        elif media_content.type == MediaType.ARTIST:
            result = await master.api.get_artists()  # list of artists with name, uri
        elif media_content.type == MediaType.GENRE:
            if result := await master.api.get_genres():  # returns list of genre names
                for item in result:
                    # add generated genre uris to list of genre names
                    item["uri"] = create_owntone_uri(
                        MediaType.GENRE, cast(str, item["name"])
                    )
        elif media_content.type == MediaType.PLAYLIST:
            result = (
                await master.api.get_playlists()
            )  # list of playlists with name, uri
        if result is None:
            raise BrowseError(
                f"Media not found for {media_content.type} / {media_content_id}"
            )
        return create_browse_media_response(
            master,
            media_content,
            cast(list[dict[str, Union[int, str]]], result),
        )
    # Not a directory or top level of library
    # We should have content type and id
    if media_content.type == MediaType.ALBUM:
        result = await master.api.get_tracks(album_id=media_content.id_or_path)
    elif media_content.type == MediaType.ARTIST:
        result = await master.api.get_albums(artist_id=media_content.id_or_path)
    elif media_content.type == MediaType.GENRE:
        if media_content.subtype in {
            MediaType.ALBUM,
            MediaType.ARTIST,
            MediaType.TRACK,
        }:
            result = await master.api.get_genre(
                media_content.id_or_path, media_type=media_content.subtype
            )
    elif media_content.type == MediaType.PLAYLIST:
        result = await master.api.get_tracks(playlist_id=media_content.id_or_path)

    if result is None:
        raise BrowseError(
            f"Media not found for {media_content.type} / {media_content_id}"
        )

    return create_browse_media_response(
        master, media_content, cast(list[dict[str, Union[int, str]]], result)
    )


def create_browse_media_response(
    master: media_player.ForkedDaapdMaster,
    media_content: MediaContent,
    result: list[dict[str, int | str]],
    children: list[BrowseMedia] | None = None,
) -> BrowseMedia:
    """Convert the results into a browse media response."""
    internal_request = is_internal_request(master.hass)
    if not children:  # Directory searches will pass in subdirectories as children
        children = []
    for item in result:
        if item.get("data_kind") == "spotify" or (
            "path" in item and cast(str, item["path"]).startswith("spotify")
        ):  # Exclude spotify data from Owntone library
            continue
        assert isinstance(item["uri"], str)
        media_type = OWNTONE_TYPE_TO_MEDIA_TYPE[item["uri"].split(":")[1]]
        title = item.get("name") or item.get("title")  # only tracks use title
        assert isinstance(title, str)
        media_content_id = create_media_content_id(
            title=f"{media_content.title} / {title}",
            owntone_uri=item["uri"],
            subtype=media_content.subtype,
        )
        if artwork := item.get("artwork_url"):
            thumbnail = (
                master.api.full_url(cast(str, artwork))
                if internal_request
                else master.get_browse_image_url(media_type, media_content_id)
            )
        else:
            thumbnail = None
        children.append(
            BrowseMedia(
                title=title,
                media_class=MEDIA_TYPE_TO_MEDIA_CLASS[media_type],
                media_content_id=media_content_id,
                media_content_type=media_type,
                can_play=media_type in CAN_PLAY_TYPE,
                can_expand=media_type in CAN_EXPAND_TYPE,
                thumbnail=thumbnail,
            )
        )
    return BrowseMedia(
        title=media_content.id_or_path
        if media_content.type == MEDIA_TYPE_DIRECTORY
        else media_content.title,
        media_class=MEDIA_TYPE_TO_MEDIA_CLASS[media_content.type],
        media_content_id="",
        media_content_type=media_content.type,
        can_play=media_content.type in CAN_PLAY_TYPE,
        can_expand=media_content.type in CAN_EXPAND_TYPE,
        children=children,
    )


def base_owntone_library() -> BrowseMedia:
    """Return the base of our Owntone library."""
    children = [
        BrowseMedia(
            title=name,
            media_class=media_class,
            media_content_id=create_media_content_id(
                title=name, media_type=media_type, subtype=media_subtype
            ),
            media_content_type=MEDIA_TYPE_DIRECTORY,
            can_play=False,
            can_expand=True,
        )
        for name, (media_class, media_type, media_subtype) in TOP_LEVEL_LIBRARY.items()
    ]
    return BrowseMedia(
        title="Owntone Library",
        media_class=MediaClass.APP,
        media_content_id=create_media_content_id(
            title="Owntone Library", media_type=MediaType.APP
        ),
        media_content_type=MediaType.APP,
        can_play=False,
        can_expand=True,
        children=children,
        thumbnail="https://brands.home-assistant.io/_/forked_daapd/logo.png",
    )


def library(other: Sequence[BrowseMedia] | None) -> BrowseMedia:
    """Create response to describe contents of library."""

    top_level_items = [
        BrowseMedia(
            title="Owntone Library",
            media_class=MediaClass.APP,
            media_content_id=create_media_content_id(
                title="Owntone Library", media_type=MediaType.APP
            ),
            media_content_type=MediaType.APP,
            can_play=False,
            can_expand=True,
            thumbnail="https://brands.home-assistant.io/_/forked_daapd/logo.png",
        )
    ]
    if other:
        top_level_items.extend(other)

    return BrowseMedia(
        title="Owntone",
        media_class=MediaClass.DIRECTORY,
        media_content_id="",
        media_content_type=MEDIA_TYPE_DIRECTORY,
        can_play=False,
        can_expand=True,
        children=top_level_items,
    )
