"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum
from functools import partial

from homeassistant.helpers.deprecation import (
    DeprecatedConstantEnum,
    all_with_deprecated_constants,
    check_if_deprecated_constant,
    dir_with_deprecated_constants,
)

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

DOMAIN = "media_player"


class MediaPlayerState(StrEnum):
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


# These MEDIA_CLASS_* constants are deprecated as of Home Assistant 2022.10.
# Please use the MediaClass enum instead.
_DEPRECATED_MEDIA_CLASS_ALBUM = DeprecatedConstantEnum(MediaClass.ALBUM, "2025.10")
_DEPRECATED_MEDIA_CLASS_APP = DeprecatedConstantEnum(MediaClass.APP, "2025.10")
_DEPRECATED_MEDIA_CLASS_ARTIST = DeprecatedConstantEnum(MediaClass.ARTIST, "2025.10")
_DEPRECATED_MEDIA_CLASS_CHANNEL = DeprecatedConstantEnum(MediaClass.CHANNEL, "2025.10")
_DEPRECATED_MEDIA_CLASS_COMPOSER = DeprecatedConstantEnum(
    MediaClass.COMPOSER, "2025.10"
)
_DEPRECATED_MEDIA_CLASS_CONTRIBUTING_ARTIST = DeprecatedConstantEnum(
    MediaClass.CONTRIBUTING_ARTIST, "2025.10"
)
_DEPRECATED_MEDIA_CLASS_DIRECTORY = DeprecatedConstantEnum(
    MediaClass.DIRECTORY, "2025.10"
)
_DEPRECATED_MEDIA_CLASS_EPISODE = DeprecatedConstantEnum(MediaClass.EPISODE, "2025.10")
_DEPRECATED_MEDIA_CLASS_GAME = DeprecatedConstantEnum(MediaClass.GAME, "2025.10")
_DEPRECATED_MEDIA_CLASS_GENRE = DeprecatedConstantEnum(MediaClass.GENRE, "2025.10")
_DEPRECATED_MEDIA_CLASS_IMAGE = DeprecatedConstantEnum(MediaClass.IMAGE, "2025.10")
_DEPRECATED_MEDIA_CLASS_MOVIE = DeprecatedConstantEnum(MediaClass.MOVIE, "2025.10")
_DEPRECATED_MEDIA_CLASS_MUSIC = DeprecatedConstantEnum(MediaClass.MUSIC, "2025.10")
_DEPRECATED_MEDIA_CLASS_PLAYLIST = DeprecatedConstantEnum(
    MediaClass.PLAYLIST, "2025.10"
)
_DEPRECATED_MEDIA_CLASS_PODCAST = DeprecatedConstantEnum(MediaClass.PODCAST, "2025.10")
_DEPRECATED_MEDIA_CLASS_SEASON = DeprecatedConstantEnum(MediaClass.SEASON, "2025.10")
_DEPRECATED_MEDIA_CLASS_TRACK = DeprecatedConstantEnum(MediaClass.TRACK, "2025.10")
_DEPRECATED_MEDIA_CLASS_TV_SHOW = DeprecatedConstantEnum(MediaClass.TV_SHOW, "2025.10")
_DEPRECATED_MEDIA_CLASS_URL = DeprecatedConstantEnum(MediaClass.URL, "2025.10")
_DEPRECATED_MEDIA_CLASS_VIDEO = DeprecatedConstantEnum(MediaClass.VIDEO, "2025.10")


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


# These MEDIA_TYPE_* constants are deprecated as of Home Assistant 2022.10.
# Please use the MediaType enum instead.
_DEPRECATED_MEDIA_TYPE_ALBUM = DeprecatedConstantEnum(MediaType.ALBUM, "2025.10")
_DEPRECATED_MEDIA_TYPE_APP = DeprecatedConstantEnum(MediaType.APP, "2025.10")
_DEPRECATED_MEDIA_TYPE_APPS = DeprecatedConstantEnum(MediaType.APPS, "2025.10")
_DEPRECATED_MEDIA_TYPE_ARTIST = DeprecatedConstantEnum(MediaType.ARTIST, "2025.10")
_DEPRECATED_MEDIA_TYPE_CHANNEL = DeprecatedConstantEnum(MediaType.CHANNEL, "2025.10")
_DEPRECATED_MEDIA_TYPE_CHANNELS = DeprecatedConstantEnum(MediaType.CHANNELS, "2025.10")
_DEPRECATED_MEDIA_TYPE_COMPOSER = DeprecatedConstantEnum(MediaType.COMPOSER, "2025.10")
_DEPRECATED_MEDIA_TYPE_CONTRIBUTING_ARTIST = DeprecatedConstantEnum(
    MediaType.CONTRIBUTING_ARTIST, "2025.10"
)
_DEPRECATED_MEDIA_TYPE_EPISODE = DeprecatedConstantEnum(MediaType.EPISODE, "2025.10")
_DEPRECATED_MEDIA_TYPE_GAME = DeprecatedConstantEnum(MediaType.GAME, "2025.10")
_DEPRECATED_MEDIA_TYPE_GENRE = DeprecatedConstantEnum(MediaType.GENRE, "2025.10")
_DEPRECATED_MEDIA_TYPE_IMAGE = DeprecatedConstantEnum(MediaType.IMAGE, "2025.10")
_DEPRECATED_MEDIA_TYPE_MOVIE = DeprecatedConstantEnum(MediaType.MOVIE, "2025.10")
_DEPRECATED_MEDIA_TYPE_MUSIC = DeprecatedConstantEnum(MediaType.MUSIC, "2025.10")
_DEPRECATED_MEDIA_TYPE_PLAYLIST = DeprecatedConstantEnum(MediaType.PLAYLIST, "2025.10")
_DEPRECATED_MEDIA_TYPE_PODCAST = DeprecatedConstantEnum(MediaType.PODCAST, "2025.10")
_DEPRECATED_MEDIA_TYPE_SEASON = DeprecatedConstantEnum(MediaType.SEASON, "2025.10")
_DEPRECATED_MEDIA_TYPE_TRACK = DeprecatedConstantEnum(MediaType.TRACK, "2025.10")
_DEPRECATED_MEDIA_TYPE_TVSHOW = DeprecatedConstantEnum(MediaType.TVSHOW, "2025.10")
_DEPRECATED_MEDIA_TYPE_URL = DeprecatedConstantEnum(MediaType.URL, "2025.10")
_DEPRECATED_MEDIA_TYPE_VIDEO = DeprecatedConstantEnum(MediaType.VIDEO, "2025.10")


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


# These REPEAT_MODE_* constants are deprecated as of Home Assistant 2022.10.
# Please use the RepeatMode enum instead.
_DEPRECATED_REPEAT_MODE_ALL = DeprecatedConstantEnum(RepeatMode.ALL, "2025.10")
_DEPRECATED_REPEAT_MODE_OFF = DeprecatedConstantEnum(RepeatMode.OFF, "2025.10")
_DEPRECATED_REPEAT_MODE_ONE = DeprecatedConstantEnum(RepeatMode.ONE, "2025.10")
REPEAT_MODES = [cls.value for cls in RepeatMode]


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


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the MediaPlayerEntityFeature enum instead.
_DEPRECATED_SUPPORT_PAUSE = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.PAUSE, "2025.10"
)
_DEPRECATED_SUPPORT_SEEK = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.SEEK, "2025.10"
)
_DEPRECATED_SUPPORT_VOLUME_SET = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.VOLUME_SET, "2025.10"
)
_DEPRECATED_SUPPORT_VOLUME_MUTE = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.VOLUME_MUTE, "2025.10"
)
_DEPRECATED_SUPPORT_PREVIOUS_TRACK = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.PREVIOUS_TRACK, "2025.10"
)
_DEPRECATED_SUPPORT_NEXT_TRACK = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.NEXT_TRACK, "2025.10"
)
_DEPRECATED_SUPPORT_TURN_ON = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.TURN_ON, "2025.10"
)
_DEPRECATED_SUPPORT_TURN_OFF = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.TURN_OFF, "2025.10"
)
_DEPRECATED_SUPPORT_PLAY_MEDIA = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.PLAY_MEDIA, "2025.10"
)
_DEPRECATED_SUPPORT_VOLUME_STEP = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.VOLUME_STEP, "2025.10"
)
_DEPRECATED_SUPPORT_SELECT_SOURCE = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.SELECT_SOURCE, "2025.10"
)
_DEPRECATED_SUPPORT_STOP = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.STOP, "2025.10"
)
_DEPRECATED_SUPPORT_CLEAR_PLAYLIST = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.CLEAR_PLAYLIST, "2025.10"
)
_DEPRECATED_SUPPORT_PLAY = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.PLAY, "2025.10"
)
_DEPRECATED_SUPPORT_SHUFFLE_SET = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.SHUFFLE_SET, "2025.10"
)
_DEPRECATED_SUPPORT_SELECT_SOUND_MODE = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.SELECT_SOUND_MODE, "2025.10"
)
_DEPRECATED_SUPPORT_BROWSE_MEDIA = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.BROWSE_MEDIA, "2025.10"
)
_DEPRECATED_SUPPORT_REPEAT_SET = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.REPEAT_SET, "2025.10"
)
_DEPRECATED_SUPPORT_GROUPING = DeprecatedConstantEnum(
    MediaPlayerEntityFeature.GROUPING, "2025.10"
)

# These can be removed if no deprecated constant are in this module anymore
__getattr__ = partial(check_if_deprecated_constant, module_globals=globals())
__dir__ = partial(
    dir_with_deprecated_constants, module_globals_keys=[*globals().keys()]
)
__all__ = all_with_deprecated_constants(globals())
