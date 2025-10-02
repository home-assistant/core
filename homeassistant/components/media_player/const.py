"""Provides the constants needed for component."""

from enum import IntFlag, StrEnum

from homeassistant.helpers.deprecation import EnumWithDeprecatedMembers

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
