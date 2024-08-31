"""Constants for the Jellyfin integration."""

import logging
from typing import Final

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.const import Platform, __version__ as hass_version

DOMAIN: Final = "jellyfin"

CLIENT_VERSION: Final = hass_version

COLLECTION_TYPE_MOVIES: Final = "movies"
COLLECTION_TYPE_MUSIC: Final = "music"
COLLECTION_TYPE_TVSHOWS: Final = "tvshows"

CONF_AUDIO_CODEC: Final = "audio_codec"
CONF_CLIENT_DEVICE_ID: Final = "client_device_id"

DEFAULT_NAME: Final = "Jellyfin"

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
ITEM_TYPE_EPISODE: Final = "Episode"
ITEM_TYPE_LIBRARY: Final = "CollectionFolder"
ITEM_TYPE_MOVIE: Final = "Movie"
ITEM_TYPE_SERIES: Final = "Series"
ITEM_TYPE_SEASON: Final = "Season"

MAX_IMAGE_WIDTH: Final = 500
MAX_STREAMING_BITRATE: Final = "140000000"

MEDIA_SOURCE_KEY_PATH: Final = "Path"

MEDIA_TYPE_AUDIO: Final = "Audio"
MEDIA_TYPE_NONE: Final = ""
MEDIA_TYPE_VIDEO: Final = "Video"

SUPPORTED_COLLECTION_TYPES: Final = [
    COLLECTION_TYPE_MUSIC,
    COLLECTION_TYPE_MOVIES,
    COLLECTION_TYPE_TVSHOWS,
]

SUPPORTED_AUDIO_CODECS: Final = ["aac", "mp3", "vorbis", "wma"]

PLAYABLE_ITEM_TYPES: Final = [ITEM_TYPE_AUDIO, ITEM_TYPE_EPISODE, ITEM_TYPE_MOVIE]


USER_APP_NAME: Final = "Home Assistant"
USER_AGENT: Final = f"Home-Assistant/{CLIENT_VERSION}"

CONTENT_TYPE_MAP = {
    "Audio": MediaType.MUSIC,
    "Episode": MediaType.EPISODE,
    "Season": MediaType.SEASON,
    "Series": MediaType.TVSHOW,
    "Movie": MediaType.MOVIE,
    "CollectionFolder": "collection",
    "AggregateFolder": "library",
    "Folder": "library",
    "BoxSet": "boxset",
}
MEDIA_CLASS_MAP = {
    "MusicAlbum": MediaClass.ALBUM,
    "MusicArtist": MediaClass.ARTIST,
    "Audio": MediaClass.MUSIC,
    "Series": MediaClass.DIRECTORY,
    "Movie": MediaClass.MOVIE,
    "CollectionFolder": MediaClass.DIRECTORY,
    "Folder": MediaClass.DIRECTORY,
    "BoxSet": MediaClass.DIRECTORY,
    "Episode": MediaClass.EPISODE,
    "Season": MediaClass.SEASON,
}

PLATFORMS = [Platform.MEDIA_PLAYER, Platform.SENSOR]
LOGGER = logging.getLogger(__package__)
