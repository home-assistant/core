"""Constants for the DLNA DMR component."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from homeassistant.components.media_player import const as _mp_const

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "dlna_dmr"

CONF_LISTEN_PORT: Final = "listen_port"
CONF_CALLBACK_URL_OVERRIDE: Final = "callback_url_override"
CONF_POLL_AVAILABILITY: Final = "poll_availability"

DEFAULT_NAME: Final = "DLNA Digital Media Renderer"

CONNECT_TIMEOUT: Final = 10

# Map UPnP class to media_player media_content_type
MEDIA_TYPE_MAP: Mapping[str, str] = {
    "object": _mp_const.MEDIA_TYPE_URL,
    "object.item": _mp_const.MEDIA_TYPE_URL,
    "object.item.imageItem": _mp_const.MEDIA_TYPE_IMAGE,
    "object.item.imageItem.photo": _mp_const.MEDIA_TYPE_IMAGE,
    "object.item.audioItem": _mp_const.MEDIA_TYPE_MUSIC,
    "object.item.audioItem.musicTrack": _mp_const.MEDIA_TYPE_MUSIC,
    "object.item.audioItem.audioBroadcast": _mp_const.MEDIA_TYPE_MUSIC,
    "object.item.audioItem.audioBook": _mp_const.MEDIA_TYPE_PODCAST,
    "object.item.videoItem": _mp_const.MEDIA_TYPE_VIDEO,
    "object.item.videoItem.movie": _mp_const.MEDIA_TYPE_MOVIE,
    "object.item.videoItem.videoBroadcast": _mp_const.MEDIA_TYPE_TVSHOW,
    "object.item.videoItem.musicVideoClip": _mp_const.MEDIA_TYPE_VIDEO,
    "object.item.playlistItem": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.item.textItem": _mp_const.MEDIA_TYPE_URL,
    "object.item.bookmarkItem": _mp_const.MEDIA_TYPE_URL,
    "object.item.epgItem": _mp_const.MEDIA_TYPE_EPISODE,
    "object.item.epgItem.audioProgram": _mp_const.MEDIA_TYPE_EPISODE,
    "object.item.epgItem.videoProgram": _mp_const.MEDIA_TYPE_EPISODE,
    "object.container": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.container.person": _mp_const.MEDIA_TYPE_ARTIST,
    "object.container.person.musicArtist": _mp_const.MEDIA_TYPE_ARTIST,
    "object.container.playlistContainer": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.container.album": _mp_const.MEDIA_TYPE_ALBUM,
    "object.container.album.musicAlbum": _mp_const.MEDIA_TYPE_ALBUM,
    "object.container.album.photoAlbum": _mp_const.MEDIA_TYPE_ALBUM,
    "object.container.genre": _mp_const.MEDIA_TYPE_GENRE,
    "object.container.genre.musicGenre": _mp_const.MEDIA_TYPE_GENRE,
    "object.container.genre.movieGenre": _mp_const.MEDIA_TYPE_GENRE,
    "object.container.channelGroup": _mp_const.MEDIA_TYPE_CHANNELS,
    "object.container.channelGroup.audioChannelGroup": _mp_const.MEDIA_TYPE_CHANNELS,
    "object.container.channelGroup.videoChannelGroup": _mp_const.MEDIA_TYPE_CHANNELS,
    "object.container.epgContainer": _mp_const.MEDIA_TYPE_TVSHOW,
    "object.container.storageSystem": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.container.storageVolume": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.container.storageFolder": _mp_const.MEDIA_TYPE_PLAYLIST,
    "object.container.bookmarkFolder": _mp_const.MEDIA_TYPE_PLAYLIST,
}
