"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum
from typing import TYPE_CHECKING, Final

import probatio

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.deprecation import EnumWithDeprecatedMembers
from homeassistant.helpers.entity_component import EntityComponent
from homeassistant.util.hass_dict import HassKey

if TYPE_CHECKING:
    from .entity import MediaPlayerEntity

DOMAIN: Final = "media_player"

DATA_COMPONENT: HassKey[EntityComponent[MediaPlayerEntity]] = HassKey(DOMAIN)

CACHE_IMAGES: Final = "images"
CACHE_MAXSIZE: Final = "maxsize"
CACHE_LOCK: Final = "lock"
CACHE_URL: Final = "url"
CACHE_CONTENT: Final = "content"

# How long our auth signature on the content should be valid for
CONTENT_AUTH_EXPIRY_TIME = 3600 * 24

ATTR_APP_ID = "app_id"
ATTR_APP_NAME = "app_name"
ATTR_ENTITY_PICTURE_LOCAL = "entity_picture_local"
ATTR_GROUP_MEMBERS = "group_members"
ATTR_INPUT_SOURCE = "source"
ATTR_INPUT_SOURCE_LIST = "source_list"
ATTR_MEDIA_ANNOUNCE = "announce"
ATTR_MEDIA_ALBUM_ARTIST = "media_album_artist"
ATTR_MEDIA_ALBUM_NAME = "media_album_name"
ATTR_MEDIA_ARTIST = "media_artist"
ATTR_MEDIA_CHANNEL = "media_channel"
ATTR_MEDIA_CONTENT_ID = "media_content_id"
ATTR_MEDIA_CONTENT_TYPE = "media_content_type"
ATTR_MEDIA_SEARCH_QUERY = "search_query"
ATTR_MEDIA_FILTER_CLASSES = "media_filter_classes"
ATTR_MEDIA_DURATION = "media_duration"
ATTR_MEDIA_ENQUEUE = "enqueue"
ATTR_MEDIA_EXTRA = "extra"
ATTR_MEDIA_EPISODE = "media_episode"
ATTR_MEDIA_PLAYLIST = "media_playlist"
ATTR_MEDIA_POSITION = "media_position"
ATTR_MEDIA_POSITION_UPDATED_AT = "media_position_updated_at"
ATTR_MEDIA_REPEAT = "repeat"
ATTR_MEDIA_SEASON = "media_season"
ATTR_MEDIA_SEEK_POSITION = "seek_position"
ATTR_MEDIA_SERIES_TITLE = "media_series_title"
ATTR_MEDIA_SHUFFLE = "shuffle"
ATTR_MEDIA_TITLE = "media_title"
ATTR_MEDIA_TRACK = "media_track"
ATTR_MEDIA_VOLUME_LEVEL = "volume_level"
ATTR_MEDIA_VOLUME_MUTED = "is_volume_muted"
ATTR_SOUND_MODE = "sound_mode"
ATTR_SOUND_MODE_LIST = "sound_mode_list"


INTENT_MEDIA_PAUSE = "HassMediaPause"
INTENT_MEDIA_UNPAUSE = "HassMediaUnpause"
INTENT_MEDIA_NEXT = "HassMediaNext"
INTENT_MEDIA_PREVIOUS = "HassMediaPrevious"
INTENT_PLAYER_MUTE = "HassMediaPlayerMute"
INTENT_PLAYER_UNMUTE = "HassMediaPlayerUnmute"
INTENT_SET_VOLUME = "HassSetVolume"
INTENT_SET_VOLUME_RELATIVE = "HassSetVolumeRelative"
INTENT_MEDIA_SEARCH_AND_PLAY = "HassMediaSearchAndPlay"


class MediaPlayerState(
    StrEnum,
    metaclass=EnumWithDeprecatedMembers,
    deprecated={
        "STANDBY": ("MediaPlayerState.OFF or MediaPlayerState.IDLE", "2026.8.0"),
    },
):
    """State of media player entities."""

    OFF = "off"
    ON = "on"
    IDLE = "idle"
    PLAYING = "playing"
    PAUSED = "paused"
    STANDBY = "standby"
    BUFFERING = "buffering"


class MediaClass(StrEnum):
    """Media class for media player entities."""

    ALBUM = "album"
    APP = "app"
    ARTIST = "artist"
    CHANNEL = "channel"
    COMPOSER = "composer"
    CONTRIBUTING_ARTIST = "contributing_artist"
    DIRECTORY = "directory"
    EPISODE = "episode"
    GAME = "game"
    GENRE = "genre"
    IMAGE = "image"
    MOVIE = "movie"
    MUSIC = "music"
    PLAYLIST = "playlist"
    PODCAST = "podcast"
    SEASON = "season"
    TRACK = "track"
    TV_SHOW = "tv_show"
    URL = "url"
    VIDEO = "video"


class MediaType(StrEnum):
    """Media type for media player entities."""

    ALBUM = "album"
    APP = "app"
    APPS = "apps"
    ARTIST = "artist"
    CHANNEL = "channel"
    CHANNELS = "channels"
    COMPOSER = "composer"
    CONTRIBUTING_ARTIST = "contributing_artist"
    EPISODE = "episode"
    GAME = "game"
    GENRE = "genre"
    IMAGE = "image"
    MOVIE = "movie"
    MUSIC = "music"
    PLAYLIST = "playlist"
    PODCAST = "podcast"
    SEASON = "season"
    TRACK = "track"
    TVSHOW = "tvshow"
    URL = "url"
    VIDEO = "video"


SERVICE_CLEAR_PLAYLIST = "clear_playlist"
SERVICE_JOIN = "join"
SERVICE_PLAY_MEDIA = "play_media"
SERVICE_BROWSE_MEDIA = "browse_media"
SERVICE_SEARCH_MEDIA = "search_media"
SERVICE_SELECT_SOUND_MODE = "select_sound_mode"
SERVICE_SELECT_SOURCE = "select_source"
SERVICE_UNJOIN = "unjoin"


class RepeatMode(StrEnum):
    """Repeat mode for media player entities."""

    ALL = "all"
    OFF = "off"
    ONE = "one"


REPEAT_MODES = [cls.value for cls in RepeatMode]


class MediaPlayerEntityCapabilityAttribute(StrEnum):
    """Capability attributes for media player entities."""

    INPUT_SOURCE_LIST = "source_list"
    SOUND_MODE_LIST = "sound_mode_list"


class MediaPlayerEntityStateAttribute(StrEnum):
    """State attributes for media player entities."""

    MEDIA_VOLUME_LEVEL = "volume_level"
    MEDIA_VOLUME_MUTED = "is_volume_muted"
    MEDIA_CONTENT_ID = "media_content_id"
    MEDIA_CONTENT_TYPE = "media_content_type"
    MEDIA_DURATION = "media_duration"
    MEDIA_POSITION = "media_position"
    MEDIA_POSITION_UPDATED_AT = "media_position_updated_at"
    MEDIA_TITLE = "media_title"
    MEDIA_ARTIST = "media_artist"
    MEDIA_ALBUM_NAME = "media_album_name"
    MEDIA_ALBUM_ARTIST = "media_album_artist"
    MEDIA_TRACK = "media_track"
    MEDIA_SERIES_TITLE = "media_series_title"
    MEDIA_SEASON = "media_season"
    MEDIA_EPISODE = "media_episode"
    MEDIA_CHANNEL = "media_channel"
    MEDIA_PLAYLIST = "media_playlist"
    APP_ID = "app_id"
    APP_NAME = "app_name"
    INPUT_SOURCE = "source"
    SOUND_MODE = "sound_mode"
    MEDIA_SHUFFLE = "shuffle"
    MEDIA_REPEAT = "repeat"
    GROUP_MEMBERS = "group_members"
    ENTITY_PICTURE_LOCAL = "entity_picture_local"


class MediaPlayerEntityFeature(IntFlag):
    """Supported features of the media player entity."""

    PAUSE = 1
    SEEK = 2
    VOLUME_SET = 4
    VOLUME_MUTE = 8
    PREVIOUS_TRACK = 16
    NEXT_TRACK = 32

    TURN_ON = 128
    TURN_OFF = 256
    PLAY_MEDIA = 512
    VOLUME_STEP = 1024
    SELECT_SOURCE = 2048
    STOP = 4096
    CLEAR_PLAYLIST = 8192
    PLAY = 16384
    SHUFFLE_SET = 32768
    SELECT_SOUND_MODE = 65536
    BROWSE_MEDIA = 131072
    REPEAT_SET = 262144
    GROUPING = 524288
    MEDIA_ANNOUNCE = 1048576
    MEDIA_ENQUEUE = 2097152
    SEARCH_MEDIA = 4194304


class MediaPlayerDeviceClass(StrEnum):
    """Device class for media players."""

    TV = "tv"
    SPEAKER = "speaker"
    RECEIVER = "receiver"
    PROJECTOR = "projector"


DEVICE_CLASSES_SCHEMA = probatio.All(
    probatio.Lower, probatio.Coerce(MediaPlayerDeviceClass)
)


ATTR_MEDIA = "media"


class MediaPlayerEnqueue(StrEnum):
    """Enqueue types for playing media."""

    # add given media item to end of the queue
    ADD = "add"
    # play the given media item next, keep queue
    NEXT = "next"
    # play the given media item now, keep queue
    PLAY = "play"
    # play the given media item now, clear queue
    REPLACE = "replace"


class MediaPlayerService(StrEnum):
    """Store keys for media player services."""

    BROWSE_MEDIA = "browse_media"
    CLEAR_PLAYLIST = "clear_playlist"
    JOIN = "join"
    MEDIA_NEXT_TRACK = "media_next_track"
    MEDIA_PAUSE = "media_pause"
    MEDIA_PLAY = "media_play"
    MEDIA_PLAY_PAUSE = "media_play_pause"
    MEDIA_PREVIOUS_TRACK = "media_previous_track"
    MEDIA_SEEK = "media_seek"
    MEDIA_STOP = "media_stop"
    PLAY_MEDIA = "play_media"
    REPEAT_SET = "repeat_set"
    SEARCH_MEDIA = "search_media"
    SELECT_SOUND_MODE = "select_sound_mode"
    SELECT_SOURCE = "select_source"
    SHUFFLE_SET = "shuffle_set"
    TOGGLE = "toggle"
    TURN_OFF = "turn_off"
    TURN_ON = "turn_on"
    UNJOIN = "unjoin"
    VOLUME_DOWN = "volume_down"
    VOLUME_MUTE = "volume_mute"
    VOLUME_SET = "volume_set"
    VOLUME_UP = "volume_up"


class MediaPlayerServiceArgument(StrEnum):
    """Store keys for media player service arguments."""

    ANNOUNCE = "announce"
    ENQUEUE = "enqueue"
    EXTRA = "extra"
    GROUP_MEMBERS = "group_members"
    IS_VOLUME_MUTED = "is_volume_muted"
    MEDIA = "media"
    MEDIA_CONTENT_ID = "media_content_id"
    MEDIA_CONTENT_TYPE = "media_content_type"
    MEDIA_FILTER_CLASSES = "media_filter_classes"
    REPEAT = "repeat"
    SEARCH_QUERY = "search_query"
    SEEK_POSITION = "seek_position"
    SHUFFLE = "shuffle"
    SOUND_MODE = "sound_mode"
    SOURCE = "source"
    VOLUME_LEVEL = "volume_level"


MEDIA_PLAYER_PLAY_MEDIA_SCHEMA = {
    probatio.Required(MediaPlayerServiceArgument.MEDIA_CONTENT_TYPE): cv.string,
    probatio.Required(MediaPlayerServiceArgument.MEDIA_CONTENT_ID): cv.string,
    probatio.Exclusive(
        MediaPlayerServiceArgument.ENQUEUE, "enqueue_announce"
    ): probatio.Any(cv.boolean, probatio.Coerce(MediaPlayerEnqueue)),
    probatio.Exclusive(
        MediaPlayerServiceArgument.ANNOUNCE, "enqueue_announce"
    ): cv.boolean,
    probatio.Optional(MediaPlayerServiceArgument.EXTRA, default={}): dict,
}
