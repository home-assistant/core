"""Constants for the Jellyfin integration."""

from typing import Final

from homeassistant.components.media_player.const import (
    MEDIA_CLASS_DIRECTORY,
    MEDIA_CLASS_EPISODE,
    MEDIA_CLASS_MOVIE,
    MEDIA_CLASS_SEASON,
    MEDIA_TYPE_MOVIE,
    MEDIA_TYPE_TVSHOW,
)
from homeassistant.const import Platform

DOMAIN: Final = "jellyfin"

CLIENT_VERSION: Final = "1.0"

COLLECTION_TYPE_MOVIES: Final = "movies"
COLLECTION_TYPE_MUSIC: Final = "music"

DATA_CLIENT: Final = "client"

ITEM_KEY_COLLECTION_TYPE: Final = "CollectionType"
ITEM_KEY_ID: Final = "Id"
ITEM_KEY_IMAGE_TAGS: Final = "ImageTags"
ITEM_KEY_INDEX_NUMBER: Final = "IndexNumber"
ITEM_KEY_MEDIA_SOURCES: Final = "MediaSources"
ITEM_KEY_MEDIA_TYPE: Final = "MediaType"
ITEM_KEY_NAME: Final = "Name"

ITEM_TYPE_ALBUM: Final = "MusicAlbum"
ITEM_TYPE_ARTIST: Final = "MusicArtist"
ITEM_TYPE_AUDIO: Final = "Audio"
ITEM_TYPE_LIBRARY: Final = "CollectionFolder"
ITEM_TYPE_MOVIE: Final = "Movie"

MAX_IMAGE_WIDTH: Final = 500
MAX_STREAMING_BITRATE: Final = "140000000"


MEDIA_SOURCE_KEY_PATH: Final = "Path"

MEDIA_TYPE_AUDIO: Final = "Audio"
MEDIA_TYPE_NONE: Final = ""
MEDIA_TYPE_VIDEO: Final = "Video"

SUPPORTED_COLLECTION_TYPES: Final = [COLLECTION_TYPE_MUSIC, COLLECTION_TYPE_MOVIES]

USER_APP_NAME: Final = "Home Assistant"
USER_AGENT: Final = f"Home-Assistant/{CLIENT_VERSION}"

PLATFORMS = frozenset([Platform.MEDIA_PLAYER])

CONTENT_TYPE_MAP = {
    "Series": MEDIA_TYPE_TVSHOW,
    "Movie": MEDIA_TYPE_MOVIE,
    "CollectionFolder": "collection",
    "Folder": "library",
    "BoxSet": "boxset",
}
MEDIA_CLASS_MAP = {
    "Series": MEDIA_CLASS_DIRECTORY,
    "Movie": MEDIA_CLASS_MOVIE,
    "CollectionFolder": MEDIA_CLASS_DIRECTORY,
    "Folder": MEDIA_CLASS_DIRECTORY,
    "BoxSet": MEDIA_CLASS_DIRECTORY,
    "Episode": MEDIA_CLASS_EPISODE,
    "Season": MEDIA_CLASS_SEASON,
}
EXPANDABLE_TYPES = ["Movie", "Episode"]
SUPPORTED_LIBRARY_TYPES = ["movies", "tvshows"]
