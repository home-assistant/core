"""Constants for the DLNA MediaServer integration."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from homeassistant.components.media_player import const as _mp_const

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
MEDIA_CLASS_MAP: Mapping[str, str] = {
    "object": _mp_const.MEDIA_CLASS_URL,
    "object.item": _mp_const.MEDIA_CLASS_URL,
    "object.item.imageItem": _mp_const.MEDIA_CLASS_IMAGE,
    "object.item.imageItem.photo": _mp_const.MEDIA_CLASS_IMAGE,
    "object.item.audioItem": _mp_const.MEDIA_CLASS_MUSIC,
    "object.item.audioItem.musicTrack": _mp_const.MEDIA_CLASS_MUSIC,
    "object.item.audioItem.audioBroadcast": _mp_const.MEDIA_CLASS_MUSIC,
    "object.item.audioItem.audioBook": _mp_const.MEDIA_CLASS_PODCAST,
    "object.item.videoItem": _mp_const.MEDIA_CLASS_VIDEO,
    "object.item.videoItem.movie": _mp_const.MEDIA_CLASS_MOVIE,
    "object.item.videoItem.videoBroadcast": _mp_const.MEDIA_CLASS_TV_SHOW,
    "object.item.videoItem.musicVideoClip": _mp_const.MEDIA_CLASS_VIDEO,
    "object.item.playlistItem": _mp_const.MEDIA_CLASS_TRACK,
    "object.item.textItem": _mp_const.MEDIA_CLASS_URL,
    "object.item.bookmarkItem": _mp_const.MEDIA_CLASS_URL,
    "object.item.epgItem": _mp_const.MEDIA_CLASS_EPISODE,
    "object.item.epgItem.audioProgram": _mp_const.MEDIA_CLASS_MUSIC,
    "object.item.epgItem.videoProgram": _mp_const.MEDIA_CLASS_VIDEO,
    "object.container": _mp_const.MEDIA_CLASS_DIRECTORY,
    "object.container.person": _mp_const.MEDIA_CLASS_ARTIST,
    "object.container.person.musicArtist": _mp_const.MEDIA_CLASS_ARTIST,
    "object.container.playlistContainer": _mp_const.MEDIA_CLASS_PLAYLIST,
    "object.container.album": _mp_const.MEDIA_CLASS_ALBUM,
    "object.container.album.musicAlbum": _mp_const.MEDIA_CLASS_ALBUM,
    "object.container.album.photoAlbum": _mp_const.MEDIA_CLASS_ALBUM,
    "object.container.genre": _mp_const.MEDIA_CLASS_GENRE,
    "object.container.genre.musicGenre": _mp_const.MEDIA_CLASS_GENRE,
    "object.container.genre.movieGenre": _mp_const.MEDIA_CLASS_GENRE,
    "object.container.channelGroup": _mp_const.MEDIA_CLASS_CHANNEL,
    "object.container.channelGroup.audioChannelGroup": _mp_const.MEDIA_TYPE_CHANNELS,
    "object.container.channelGroup.videoChannelGroup": _mp_const.MEDIA_TYPE_CHANNELS,
    "object.container.epgContainer": _mp_const.MEDIA_CLASS_DIRECTORY,
    "object.container.storageSystem": _mp_const.MEDIA_CLASS_DIRECTORY,
    "object.container.storageVolume": _mp_const.MEDIA_CLASS_DIRECTORY,
    "object.container.storageFolder": _mp_const.MEDIA_CLASS_DIRECTORY,
    "object.container.bookmarkFolder": _mp_const.MEDIA_CLASS_DIRECTORY,
}
