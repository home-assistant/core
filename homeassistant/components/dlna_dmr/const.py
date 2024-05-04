"""Constants for the DLNA DMR component."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Final

from async_upnp_client.profiles.dlna import PlayMode as _PlayMode

from homeassistant.components.media_player import MediaType, RepeatMode

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
MEDIA_TYPE_MAP: Mapping[str, MediaType] = {
    "object": MediaType.URL,
    "object.item": MediaType.URL,
    "object.item.imageItem": MediaType.IMAGE,
    "object.item.imageItem.photo": MediaType.IMAGE,
    "object.item.audioItem": MediaType.MUSIC,
    "object.item.audioItem.musicTrack": MediaType.MUSIC,
    "object.item.audioItem.audioBroadcast": MediaType.MUSIC,
    "object.item.audioItem.audioBook": MediaType.PODCAST,
    "object.item.videoItem": MediaType.VIDEO,
    "object.item.videoItem.movie": MediaType.MOVIE,
    "object.item.videoItem.videoBroadcast": MediaType.TVSHOW,
    "object.item.videoItem.musicVideoClip": MediaType.VIDEO,
    "object.item.playlistItem": MediaType.PLAYLIST,
    "object.item.textItem": MediaType.URL,
    "object.item.bookmarkItem": MediaType.URL,
    "object.item.epgItem": MediaType.EPISODE,
    "object.item.epgItem.audioProgram": MediaType.EPISODE,
    "object.item.epgItem.videoProgram": MediaType.EPISODE,
    "object.container": MediaType.PLAYLIST,
    "object.container.person": MediaType.ARTIST,
    "object.container.person.musicArtist": MediaType.ARTIST,
    "object.container.playlistContainer": MediaType.PLAYLIST,
    "object.container.album": MediaType.ALBUM,
    "object.container.album.musicAlbum": MediaType.ALBUM,
    "object.container.album.photoAlbum": MediaType.ALBUM,
    "object.container.genre": MediaType.GENRE,
    "object.container.genre.musicGenre": MediaType.GENRE,
    "object.container.genre.movieGenre": MediaType.GENRE,
    "object.container.channelGroup": MediaType.CHANNELS,
    "object.container.channelGroup.audioChannelGroup": MediaType.CHANNELS,
    "object.container.channelGroup.videoChannelGroup": MediaType.CHANNELS,
    "object.container.epgContainer": MediaType.TVSHOW,
    "object.container.storageSystem": MediaType.PLAYLIST,
    "object.container.storageVolume": MediaType.PLAYLIST,
    "object.container.storageFolder": MediaType.PLAYLIST,
    "object.container.bookmarkFolder": MediaType.PLAYLIST,
}

# Map media_player media_content_type to UPnP class. Not everything will map
# directly, in which case it's not specified and other defaults will be used.
MEDIA_UPNP_CLASS_MAP: Mapping[MediaType | str, str] = {
    MediaType.ALBUM: "object.container.album.musicAlbum",
    MediaType.ARTIST: "object.container.person.musicArtist",
    MediaType.CHANNEL: "object.item.videoItem.videoBroadcast",
    MediaType.CHANNELS: "object.container.channelGroup",
    MediaType.COMPOSER: "object.container.person.musicArtist",
    MediaType.CONTRIBUTING_ARTIST: "object.container.person.musicArtist",
    MediaType.EPISODE: "object.item.epgItem.videoProgram",
    MediaType.GENRE: "object.container.genre",
    MediaType.IMAGE: "object.item.imageItem",
    MediaType.MOVIE: "object.item.videoItem.movie",
    MediaType.MUSIC: "object.item.audioItem.musicTrack",
    MediaType.PLAYLIST: "object.item.playlistItem",
    MediaType.PODCAST: "object.item.audioItem.audioBook",
    MediaType.SEASON: "object.item.epgItem.videoProgram",
    MediaType.TRACK: "object.item.audioItem.musicTrack",
    MediaType.TVSHOW: "object.item.videoItem.videoBroadcast",
    MediaType.URL: "object.item.bookmarkItem",
    MediaType.VIDEO: "object.item.videoItem",
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
REPEAT_PLAY_MODES: Mapping[tuple[bool, RepeatMode], list[_PlayMode]] = {
    (False, RepeatMode.OFF): [
        _PlayMode.NORMAL,
    ],
    (False, RepeatMode.ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
    (False, RepeatMode.ALL): [
        _PlayMode.REPEAT_ALL,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.OFF): [
        _PlayMode.SHUFFLE,
        _PlayMode.RANDOM,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.ALL): [
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
    (False, RepeatMode.OFF): [
        _PlayMode.NORMAL,
    ],
    (False, RepeatMode.ONE): [
        _PlayMode.REPEAT_ONE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
    (False, RepeatMode.ALL): [
        _PlayMode.REPEAT_ALL,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.OFF): [
        _PlayMode.SHUFFLE,
        _PlayMode.RANDOM,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.ONE): [
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.REPEAT_ONE,
        _PlayMode.NORMAL,
    ],
    (True, RepeatMode.ALL): [
        _PlayMode.RANDOM,
        _PlayMode.SHUFFLE,
        _PlayMode.REPEAT_ALL,
        _PlayMode.NORMAL,
    ],
}
