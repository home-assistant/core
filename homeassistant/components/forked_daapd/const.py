"""Const for forked-daapd."""
from homeassistant.components.media_player.const import (
    SUPPORT_CLEAR_PLAYLIST,
    SUPPORT_NEXT_TRACK,
    SUPPORT_PAUSE,
    SUPPORT_PLAY,
    SUPPORT_PLAY_MEDIA,
    SUPPORT_PREVIOUS_TRACK,
    SUPPORT_SEEK,
    SUPPORT_SHUFFLE_SET,
    SUPPORT_STOP,
    SUPPORT_TURN_OFF,
    SUPPORT_TURN_ON,
    SUPPORT_VOLUME_MUTE,
    SUPPORT_VOLUME_SET,
)

DOMAIN = "forked_daapd"  # key for hass.data
DEFAULT_PORT = 3689
CONF_TTS_PAUSE_TIME = "tts_pause_time"
CONF_TTS_VOLUME = "tts_volume"
CONF_PIPE_CONTROL = "pipe_control"
CONF_PIPE_CONTROL_PORT = "pipe_control_port"
FD_NAME = "forked-daapd"
DEFAULT_PIPE_CONTROL_PORT = 24879
DEFAULT_SERVER_NAME = "My Server"
DEFAULT_TTS_PAUSE_TIME = 1.2
DEFAULT_TTS_VOLUME = 0.8
SERVER_UNIQUE_ID = "server"
DEFAULT_UNMUTE_VOLUME = 0.6
CONFIG_FLOW_UNIQUE_ID = "forked-daapd"
TTS_TIMEOUT = 20  # max time to wait between TTS getting sent and starting to play
CALLBACK_TIMEOUT = 8  # max time between command and callback from forked-daapd server
HASS_DATA_REMOVE_LISTENERS_KEY = "REMOVE_LISTENERS"
HASS_DATA_OUTPUTS_KEY = "OUTPUTS"
HASS_DATA_UPDATER_KEY = "UPDATER"
SIGNAL_ADD_ZONES = "forked-daapd_add_zones"
SIGNAL_UPDATE_MASTER = "forked-daapd_update_master"
SIGNAL_UPDATE_OUTPUTS = "forked-daapd_update_outputs"
SIGNAL_UPDATE_PLAYER = "forked-daapd_update_player"
SIGNAL_UPDATE_QUEUE = "forked-daapd_update_queue"
SIGNAL_CONFIG_OPTIONS_UPDATE = "forked-daapd_config_options_update"
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
    SUPPORT_PLAY
    | SUPPORT_PAUSE
    | SUPPORT_STOP
    | SUPPORT_SEEK
    | SUPPORT_VOLUME_SET
    | SUPPORT_VOLUME_MUTE
    | SUPPORT_PREVIOUS_TRACK
    | SUPPORT_NEXT_TRACK
    | SUPPORT_CLEAR_PLAYLIST
    | SUPPORT_SHUFFLE_SET
    | SUPPORT_TURN_ON
    | SUPPORT_TURN_OFF
    | SUPPORT_PLAY_MEDIA
)
SUPPORTED_FEATURES_ZONE = (
    SUPPORT_VOLUME_SET | SUPPORT_VOLUME_MUTE | SUPPORT_TURN_ON | SUPPORT_TURN_OFF
)
