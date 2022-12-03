"""Constants used by the Onkyo component."""
from pyeiscp.commands import COMMANDS

from homeassistant.components.media_player import MediaPlayerEntityFeature

DOMAIN = "onkyo"

CONNECT_TIMEOUT = 5
DISCOVER_TIMEOUT = 2
DISCOVER_ZONES_TIMEOUT = 1
AUDIO_VIDEO_INFORMATION_UPDATE_INTERVAL = 10

ZONES = {"zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}

CONF_IDENTIFIER = "identifier"
CONF_SOURCES = "sources"
CONF_ENABLED_SOURCES = "enabled_sources"
CONF_MAX_VOLUME = "max_volume"
CONF_RECEIVER = "receiver"

SERVICE_SELECT_HDMI_OUTPUT = "select_hdmi_output"

ATTR_HDMI_OUTPUT = "hdmi_output"
ATTR_PRESET = "preset"
ATTR_AUDIO_INFORMATION = "audio_information"
ATTR_VIDEO_INFORMATION = "video_information"
ATTR_VIDEO_OUT = "video_out"

MAX_VOLUME_MIN_VALUE = 1.0
MAX_VOLUME_MAX_VALUE = 200.0

DEFAULT_MAX_VOLUME = 80
DEFAULT_SOURCES = {
    "tv": "TV",
    "dvd": "BluRay",
    "video3": "Game",
    "strm-box": "Stream Box",
    "video4": "Aux1",
    "fm": "Radio",
    "cd": "CD",
}

DEFAULT_SOURCE_NAMES = {
    value["name"][0]
    if isinstance(value["name"], tuple)
    else value["name"]: value["description"].replace("sets ", "")
    for value in COMMANDS["main"]["SLI"]["values"].values()
    if value["name"] not in ["07", "08", "09", "up", "down", "query"]
}

SOUND_MODE_MAPPING = {
    "Auto": ["auto"],
    "Direct": ["direct"],
    "Pure Direct": ["pure-audio"],
    "Stereo": ["stereo"],
    "Extended Stereo": ["all-ch-stereo"],
    "Surround": ["surr", "surround"],
    "Auto Surround": ["auto-surround"],
    "Multichannel PCM": ["straight-decode"],
    "Dolby Digital": [
        "dolby-atmos",
        "dolby-surround",
        "dolby-virtual",
        "dolby-ex",
        "dolby-ex-audyssey-dsx",
        "dolby-surround-thx-cinema",
        "pliix-thx-cinema",
        "pliix-movie",
        "dolby-surround-thx-music",
        "pliix-thx-music",
        "pliix-music",
        "dolby-surround-thx-games",
        "pliix-thx-games",
        "pliix-game",
        "pliiz-height-thx-cinema",
        "pliiz-height-thx-games",
        "plii",
        "pliix",
        "pliiz-height-thx-music",
        "pliiz-height-thx-u2",
        "pliiz-height",
        "plii-game-audyssey-dsx",
        "plii-movie-audyssey-dsx",
        "plii-music-audyssey-dsx",
    ],
    "DTS Surround": [
        "dts-x",
        "neural-x",
        "dts-surround-sensation",
        "dts-neural-x-thx-cinema",
        "dts-neural-x-thx-music",
        "dts-neural-x-thx-games",
        "neural-surr",
        "neural-surround-audyssey-dsx",
        "neural-digital-music",
        "neural-digital-music-audyssey-dsx",
        "neo-6",
        "neo-6-music",
        "neo-6-cinema",
        "neo-6-cinema-dts-surround-sensation",
        "neo-6-music-dts-surround-sensation",
        "neo-6-cinema-audyssey-dsx",
        "neo-6-music-audyssey-dsx",
        "neo-x-music",
        "neo-x-cinema",
        "neo-x-game",
        "neo-x-thx-cinema",
        "neo-x-thx-music",
        "neo-x-thx-games",
    ],
    "THX": [
        "thx",
        "thx-surround-ex",
        "thx-cinema",
        "thx-music",
        "thx-musicmode",
        "thx-games",
        "thx-u2",
        "neural-thx",
        "neural-thx-cinema",
        "neural-thx-music",
        "neural-thx-games",
    ],
    "Mono": ["mono", "mono-movie"],
    "Extended Mono": ["full-mono"],
    "Action": ["action", "game-action"],
    "Drama": ["tv-logic"],
    "Entertainment Show": ["studio-mix"],
    "Advanced Game": ["film", "game-rpg"],
    "Sports": ["enhanced-7", "enhance", "game-sports"],
    "Classical": ["orchestra"],
    "Rock/Pop": ["musical", "game-rock"],
    "Unplugged": ["unplugged"],
    "Front Stage Surround": ["theater-dimensional"],
    "Whole House": ["whole-house"],
}

SOUND_MODE_REVERSE_MAPPING = {
    subval: key for key, values in SOUND_MODE_MAPPING.items() for subval in values
}

DEFAULT_PLAYABLE_SOURCES = ("fm", "am", "tuner")

SELECT_HDMI_OUTPUT_ACCEPTED_VALUES = [
    "no",
    "analog",
    "yes",
    "out",
    "out-sub",
    "sub",
    "hdbaset",
    "both",
    "up",
]

AUDIO_INFORMATION_MAPPING = [
    "audio_input_port",
    "input_signal_format",
    "input_frequency",
    "input_channels",
    "listening_mode",
    "output_channels",
    "output_frequency",
    "precision_quartz_lock_system",
    "auto_phase_control_delay",
    "auto_phase_control_phase",
]

VIDEO_INFORMATION_MAPPING = [
    "video_input_port",
    "input_resolution",
    "input_color_schema",
    "input_color_depth",
    "video_output_port",
    "output_resolution",
    "output_color_schema",
    "output_color_depth",
    "picture_mode",
]

SUPPORT_ONKYO_WO_VOLUME = (
    MediaPlayerEntityFeature.TURN_ON
    | MediaPlayerEntityFeature.TURN_OFF
    | MediaPlayerEntityFeature.SELECT_SOURCE
    | MediaPlayerEntityFeature.PLAY
    | MediaPlayerEntityFeature.PLAY_MEDIA
    | MediaPlayerEntityFeature.VOLUME_MUTE
)

SUPPORT_ONKYO_WO_SOUND_MODE = (
    SUPPORT_ONKYO_WO_VOLUME
    | MediaPlayerEntityFeature.VOLUME_SET
    | MediaPlayerEntityFeature.VOLUME_STEP
)

SUPPORT_ONKYO = SUPPORT_ONKYO_WO_SOUND_MODE | MediaPlayerEntityFeature.SELECT_SOUND_MODE
