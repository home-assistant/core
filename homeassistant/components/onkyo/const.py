"""Constants for the Onkyo integration."""

DOMAIN = "onkyo"
BRAND_NAME = "Onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

OPTION_SOURCE_PREFIX = "source."
OPTION_SOURCES = "sources"
OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100

CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"
CONF_RECEIVER_MAX_VOLUME_DEFAULT = 80
CONF_DEVICE = "device"
CONF_VOLUME_RESOLUTION = "volume_resolution"
CONF_VOLUME_RESOLUTION_DEFAULT = 80
CONF_SOURCES_DEFAULT = {
    "tv": "TV",
    "bd": "Bluray",
    "game": "Game",
    "aux1": "Aux1",
    "video1": "Video 1",
    "video2": "Video 2",
    "video3": "Video 3",
    "video4": "Video 4",
    "video5": "Video 5",
    "video6": "Video 6",
    "video7": "Video 7",
    "fm": "Radio",
}
# this should be kept in sync with strings.json for dynamic options generation
# to work correctly.
CONF_SOURCES_ALLOWED = [
    "aiplay",
    "am",
    "aux1",
    "aux2",
    "bd",
    "bluetooth",
    "cbl",
    "cd",
    "coaxial",
    "dab",
    "dlna",
    "dvd",
    "dvr",
    "fm",
    "game",
    "game/tv",
    "game1",
    "game2",
    "hdmi-5",
    "hdmi-6",
    "hdmi-7",
    "internet-radio",
    "iradio-favorite",
    "line",
    "line2",
    "multi-ch",
    "music-server",
    "net",
    "network",
    "optical",
    "p4s",
    "pc",
    "phono",
    "sat",
    "sirius",
    "stb",
    "strm-box",
    "tape-1",
    "tape2",
    "tuner",
    "tv",
    "tv/cd",
    "tv/tape",
    "universal-port",
    "usb",
    "usb-dac-in",
    "vcr",
    "video1",
    "video2",
    "video3",
    "video4",
    "video5",
    "video6",
    "video7",
    "xm",
]

ZONES = {"main": "Main", "zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}
