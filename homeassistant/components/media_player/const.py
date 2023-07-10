"""Provides the constants needed for component."""
from enum import IntFlag

from homeassistant.backports.enum import StrEnum

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
MEDIA_CLASS_ALBUM = "album"
MEDIA_CLASS_APP = "app"
MEDIA_CLASS_ARTIST = "artist"
MEDIA_CLASS_CHANNEL = "channel"
MEDIA_CLASS_COMPOSER = "composer"
MEDIA_CLASS_CONTRIBUTING_ARTIST = "contributing_artist"
MEDIA_CLASS_DIRECTORY = "directory"
MEDIA_CLASS_EPISODE = "episode"
MEDIA_CLASS_GAME = "game"
MEDIA_CLASS_GENRE = "genre"
MEDIA_CLASS_IMAGE = "image"
MEDIA_CLASS_MOVIE = "movie"
MEDIA_CLASS_MUSIC = "music"
MEDIA_CLASS_PLAYLIST = "playlist"
MEDIA_CLASS_PODCAST = "podcast"
MEDIA_CLASS_SEASON = "season"
MEDIA_CLASS_TRACK = "track"
MEDIA_CLASS_TV_SHOW = "tv_show"
MEDIA_CLASS_URL = "url"
MEDIA_CLASS_VIDEO = "video"


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
MEDIA_TYPE_ALBUM = "album"
MEDIA_TYPE_APP = "app"
MEDIA_TYPE_APPS = "apps"
MEDIA_TYPE_ARTIST = "artist"
MEDIA_TYPE_CHANNEL = "channel"
MEDIA_TYPE_CHANNELS = "channels"
MEDIA_TYPE_COMPOSER = "composer"
MEDIA_TYPE_CONTRIBUTING_ARTIST = "contributing_artist"
MEDIA_TYPE_EPISODE = "episode"
MEDIA_TYPE_GAME = "game"
MEDIA_TYPE_GENRE = "genre"
MEDIA_TYPE_IMAGE = "image"
MEDIA_TYPE_MOVIE = "movie"
MEDIA_TYPE_MUSIC = "music"
MEDIA_TYPE_PLAYLIST = "playlist"
MEDIA_TYPE_PODCAST = "podcast"
MEDIA_TYPE_SEASON = "season"
MEDIA_TYPE_TRACK = "track"
MEDIA_TYPE_TVSHOW = "tvshow"
MEDIA_TYPE_URL = "url"
MEDIA_TYPE_VIDEO = "video"

SERVICE_CLEAR_PLAYLIST = "clear_playlist"
SERVICE_JOIN = "join"
SERVICE_PLAY_MEDIA = "play_media"
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
REPEAT_MODE_ALL = "all"
REPEAT_MODE_OFF = "off"
REPEAT_MODE_ONE = "one"
REPEAT_MODES = [REPEAT_MODE_OFF, REPEAT_MODE_ALL, REPEAT_MODE_ONE]


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


# These SUPPORT_* constants are deprecated as of Home Assistant 2022.5.
# Please use the MediaPlayerEntityFeature enum instead.
SUPPORT_PAUSE = 1
SUPPORT_SEEK = 2
SUPPORT_VOLUME_SET = 4
SUPPORT_VOLUME_MUTE = 8
SUPPORT_PREVIOUS_TRACK = 16
SUPPORT_NEXT_TRACK = 32

SUPPORT_TURN_ON = 128
SUPPORT_TURN_OFF = 256
SUPPORT_PLAY_MEDIA = 512
SUPPORT_VOLUME_STEP = 1024
SUPPORT_SELECT_SOURCE = 2048
SUPPORT_STOP = 4096
SUPPORT_CLEAR_PLAYLIST = 8192
SUPPORT_PLAY = 16384
SUPPORT_SHUFFLE_SET = 32768
SUPPORT_SELECT_SOUND_MODE = 65536
SUPPORT_BROWSE_MEDIA = 131072
SUPPORT_REPEAT_SET = 262144
SUPPORT_GROUPING = 524288
