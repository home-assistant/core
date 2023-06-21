"""Const for forked-daapd."""
from homeassistant.components.media_player import MediaPlayerEntityFeature, MediaType

CALLBACK_TIMEOUT = 8  # max time between command and callback from forked-daapd server
CAN_PLAY_TYPE = {
    "audio/mp4",
    "audio/aac",
    "audio/mpeg",
    "audio/flac",
    "audio/ogg",
    "audio/x-ms-wma",
    "audio/aiff",
    "audio/wav",
    MediaType.TRACK,
    MediaType.PLAYLIST,
    MediaType.ARTIST,
    MediaType.ALBUM,
    MediaType.GENRE,
    MediaType.MUSIC,
    MediaType.EPISODE,
    "show",  # this is a spotify constant
}
CONF_LIBRESPOT_JAVA_PORT = "librespot_java_port"
CONF_MAX_PLAYLISTS = "max_playlists"
CONF_TTS_PAUSE_TIME = "tts_pause_time"
CONF_TTS_VOLUME = "tts_volume"
DEFAULT_PORT = 3689
DEFAULT_SERVER_NAME = "My Server"
DEFAULT_TTS_PAUSE_TIME = 1.2
DEFAULT_TTS_VOLUME = 0.8
DEFAULT_UNMUTE_VOLUME = 0.6
DOMAIN = "forked_daapd"  # key for hass.data
FD_NAME = "OwnTone"
HASS_DATA_REMOVE_LISTENERS_KEY = "REMOVE_LISTENERS"
HASS_DATA_UPDATER_KEY = "UPDATER"
KNOWN_PIPES = {"librespot-java"}
PIPE_FUNCTION_MAP = {
    "librespot-java": {
        "async_media_play": "player_resume",
        "async_media_pause": "player_pause",
        "async_media_stop": "player_pause",
        "async_media_previous_track": "player_prev",
        "async_media_next_track": "player_next",
    }
}
SIGNAL_ADD_ZONES = "forked-daapd_add_zones {}"
SIGNAL_CONFIG_OPTIONS_UPDATE = "forked-daapd_config_options_update {}"
SIGNAL_UPDATE_DATABASE = "forked-daapd_update_database {}"
SIGNAL_UPDATE_MASTER = "forked-daapd_update_master {}"
SIGNAL_UPDATE_OUTPUTS = "forked-daapd_update_outputs {}"
SIGNAL_UPDATE_PLAYER = "forked-daapd_update_player {}"
SIGNAL_UPDATE_QUEUE = "forked-daapd_update_queue {}"
SOURCE_NAME_CLEAR = "Clear queue"
SOURCE_NAME_DEFAULT = "Default (no pipe)"
STARTUP_DATA = {
    "player": {
        "state": "stop",
        "repeat": "off",
        "consume": False,
        "shuffle": False,
        "volume": 0,
        "item_id": 0,
        "item_length_ms": 0,
        "item_progress_ms": 0,
    },
    "queue": {"version": 0, "count": 0, "items": []},
    "outputs": [],
}
SUPPORTED_FEATURES = (
    MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PAUSE
    | MediaPlayerEntityFeature.STOP
    | MediaPlayerEntityFeature.SEEK
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.PREVIOUS_TRACK
    | MediaPlayerEntityFeature.NEXT_TRACK
    | MediaPlayerEntityFeature.CLEAR_PLAYLIST
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.SHUFFLE_SET
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.BROWSE_MEDIA
)
SUPPORTED_FEATURES_ZONE = (
    MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_MUTE
    | MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
)
TTS_TIMEOUT = 20  # max time to wait between TTS getting sent and starting to play
URI_SCHEMA = "owntone"
