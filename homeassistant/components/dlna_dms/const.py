"""Constants for the DLNA MediaServer integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from homeassistant.components.media_player import MediaClass

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "dlna_dms"
DEFAULT_NAME: Final = "DLNA Media Server"

CONF_SOURCE_ID: Final = "source_id"
CONFIG_VERSION: Final = 1

SOURCE_SEP: Final = "/"
ROOT_OBJECT_ID: Final = "0"
PATH_SEP: Final = "/"
PATH_SEARCH_FLAG: Final = "?"
PATH_OBJECT_ID_FLAG: Final = ":"
# Only request the metadata needed to build a browse response
DLNA_BROWSE_FILTER: Final = [
    "id",
    "upnp:class",
    "dc:title",
    "res",
    "@childCount",
    "upnp:albumArtURI",
]
# Get all metadata when resolving, for the use of media_players
DLNA_RESOLVE_FILTER: Final = "*"
# Metadata needed to resolve a path
DLNA_PATH_FILTER: Final = ["id", "upnp:class", "dc:title"]
DLNA_SORT_CRITERIA: Final = ["+upnp:class", "+upnp:originalTrackNumber", "+dc:title"]

PROTOCOL_HTTP: Final = "http-get"
PROTOCOL_RTSP: Final = "rtsp-rtp-udp"
PROTOCOL_ANY: Final = "*"
STREAMABLE_PROTOCOLS: Final = [PROTOCOL_HTTP, PROTOCOL_RTSP, PROTOCOL_ANY]

# Map UPnP object class to media_player media class
MEDIA_CLASS_MAP: Mapping[str, MediaClass] = {
    "object": MediaClass.URL,
    "object.item": MediaClass.URL,
    "object.item.imageItem": MediaClass.IMAGE,
    "object.item.imageItem.photo": MediaClass.IMAGE,
    "object.item.audioItem": MediaClass.MUSIC,
    "object.item.audioItem.musicTrack": MediaClass.MUSIC,
    "object.item.audioItem.audioBroadcast": MediaClass.MUSIC,
    "object.item.audioItem.audioBook": MediaClass.PODCAST,
    "object.item.videoItem": MediaClass.VIDEO,
    "object.item.videoItem.movie": MediaClass.MOVIE,
    "object.item.videoItem.videoBroadcast": MediaClass.TV_SHOW,
    "object.item.videoItem.musicVideoClip": MediaClass.VIDEO,
    "object.item.playlistItem": MediaClass.TRACK,
    "object.item.textItem": MediaClass.URL,
    "object.item.bookmarkItem": MediaClass.URL,
    "object.item.epgItem": MediaClass.EPISODE,
    "object.item.epgItem.audioProgram": MediaClass.MUSIC,
    "object.item.epgItem.videoProgram": MediaClass.VIDEO,
    "object.container": MediaClass.DIRECTORY,
    "object.container.person": MediaClass.ARTIST,
    "object.container.person.musicArtist": MediaClass.ARTIST,
    "object.container.playlistContainer": MediaClass.PLAYLIST,
    "object.container.album": MediaClass.ALBUM,
    "object.container.album.musicAlbum": MediaClass.ALBUM,
    "object.container.album.photoAlbum": MediaClass.ALBUM,
    "object.container.genre": MediaClass.GENRE,
    "object.container.genre.musicGenre": MediaClass.GENRE,
    "object.container.genre.movieGenre": MediaClass.GENRE,
    "object.container.channelGroup": MediaClass.CHANNEL,
    "object.container.channelGroup.audioChannelGroup": MediaClass.CHANNEL,
    "object.container.channelGroup.videoChannelGroup": MediaClass.CHANNEL,
    "object.container.epgContainer": MediaClass.DIRECTORY,
    "object.container.storageSystem": MediaClass.DIRECTORY,
    "object.container.storageVolume": MediaClass.DIRECTORY,
    "object.container.storageFolder": MediaClass.DIRECTORY,
    "object.container.bookmarkFolder": MediaClass.DIRECTORY,
}
