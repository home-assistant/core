"""Constants for the DLNA DMR component."""
from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from async_upnp_client.profiles.dlna import PlayMode as _PlayMode

from homeassistant.components.media_player import const as _mp_const

LOGGER = logging.getLogger(__package__)

DOMAIN: Final = "dlna_dmr"

CONF_LISTEN_PORT: Final = "listen_port"
CONF_CALLBACK_URL_OVERRIDE: Final = "callback_url_override"
CONF_POLL_AVAILABILITY: Final = "poll_availability"
CONF_BROWSE_UNFILTERED: Final = "browse_unfiltered"

DEFAULT_NAME: Final = "DLNA Digital Media Renderer"

CONNECT_TIMEOUT: Final = 10

PROTOCOL_HTTP: Final = "http-get"
PROTOCOL_RTSP: Final = "rtsp-rtp-udp"
PROTOCOL_ANY: Final = "*"
STREAMABLE_PROTOCOLS: Final = [PROTOCOL_HTTP, PROTOCOL_RTSP, PROTOCOL_ANY]

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

# Map media_player media_content_type to UPnP class. Not everything will map
# directly, in which case it's not specified and other defaults will be used.
MEDIA_UPNP_CLASS_MAP: Mapping[str, str] = {
    _mp_const.MEDIA_TYPE_ALBUM: "object.container.album.musicAlbum",
    _mp_const.MEDIA_TYPE_ARTIST: "object.container.person.musicArtist",
    _mp_const.MEDIA_TYPE_CHANNEL: "object.item.videoItem.videoBroadcast",
    _mp_const.MEDIA_TYPE_CHANNELS: "object.container.channelGroup",
    _mp_const.MEDIA_TYPE_COMPOSER: "object.container.person.musicArtist",
    _mp_const.MEDIA_TYPE_CONTRIBUTING_ARTIST: "object.container.person.musicArtist",
    _mp_const.MEDIA_TYPE_EPISODE: "object.item.epgItem.videoProgram",
    _mp_const.MEDIA_TYPE_GENRE: "object.container.genre",
    _mp_const.MEDIA_TYPE_IMAGE: "object.item.imageItem",
    _mp_const.MEDIA_TYPE_MOVIE: "object.item.videoItem.movie",
    _mp_const.MEDIA_TYPE_MUSIC: "object.item.audioItem.musicTrack",
    _mp_const.MEDIA_TYPE_PLAYLIST: "object.item.playlistItem",
    _mp_const.MEDIA_TYPE_PODCAST: "object.item.audioItem.audioBook",
    _mp_const.MEDIA_TYPE_SEASON: "object.item.epgItem.videoProgram",
    _mp_const.MEDIA_TYPE_TRACK: "object.item.audioItem.musicTrack",
    _mp_const.MEDIA_TYPE_TVSHOW: "object.item.videoItem.videoBroadcast",
    _mp_const.MEDIA_TYPE_URL: "object.item.bookmarkItem",
    _mp_const.MEDIA_TYPE_VIDEO: "object.item.videoItem",
}

# Translation of MediaMetadata keys to DIDL-Lite keys.
# See https://developers.google.com/cast/docs/reference/messages#MediaData via
# https://www.home-assistant.io/integrations/media_player/ for HA keys.
# See http://www.upnp.org/specs/av/UPnP-av-ContentDirectory-v4-Service.pdf for
# DIDL-Lite keys.
MEDIA_METADATA_DIDL: Mapping[str, str] = {
    "subtitle": "longDescription",
    "releaseDate": "date",
    "studio": "publisher",
    "season": "episodeSeason",
    "episode": "episodeNumber",
    "albumName": "album",
    "trackNumber": "originalTrackNumber",
}

# For (un)setting repeat mode, map a combination of shuffle & repeat to a list
# of play modes in order of suitability. Fall back to _PlayMode.NORMAL in any
# case. NOTE: This list is slightly different to that in SHUFFLE_PLAY_MODES,
# due to fallback behaviour when turning on repeat modes.
REPEAT_PLAY_MODES: Mapping[tuple[bool, str], list[_PlayMode]] = {
    (False, _mp_const.REPEAT_MODE_OFF): [
        _PlayMode.NORMAL,
    ],
    (False, _mp_const.REPEAT_MODE_ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
    (False, _mp_const.REPEAT_MODE_ALL): [
        _PlayMode.REPEAT_ALL,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_OFF): [
        _PlayMode.SHUFFLE,
        _PlayMode.RANDOM,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_ALL): [
        _PlayMode.RANDOM,
        _PlayMode.REPEAT_ALL,
        _PlayMode.SHUFFLE,
        _PlayMode.NORMAL,
    ],
}

# For (un)setting shuffle mode, map a combination of shuffle & repeat to a list
# of play modes in order of suitability. Fall back to _PlayMode.NORMAL in any
# case.
SHUFFLE_PLAY_MODES: Mapping[tuple[bool, str], list[_PlayMode]] = {
    (False, _mp_const.REPEAT_MODE_OFF): [
        _PlayMode.NORMAL,
    ],
    (False, _mp_const.REPEAT_MODE_ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
    (False, _mp_const.REPEAT_MODE_ALL): [
        _PlayMode.REPEAT_ALL,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_OFF): [
        _PlayMode.SHUFFLE,
        _PlayMode.RANDOM,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_ONE): [
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, _mp_const.REPEAT_MODE_ALL): [
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
}
