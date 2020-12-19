"""Define constants for the Pioneer component."""

DOMAIN = "pioneer"

CONF_SOURCES = "sources"

DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 23  # telnet 'default'. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT = 0
DEFAULT_SOURCES = {}
DEFAULT_MAX_VOLUME = 185

MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60

# Most common sources based on https://www.home-assistant.io/integrations/pioneer/
POSSIBLE_SOURCES = {
    "PHONO": {"code": "00", "common": False},
    "CD": {"code": "01", "common": True},
    "Tuner": {"code": "02", "common": True},
    "CD-R/TAPE": {"code": "03", "common": False},
    "DVD": {"code": "04", "common": True},
    "TV": {"code": "05", "common": True},
    "Sat/Cbl": {"code": "06", "common": True},
    "Video 1": {"code": "10", "common": False},
    "Video 2": {"code": "14", "common": False},
    "DVR/BDR": {"code": "15", "common": True},
    "iPod/USB": {"code": "17", "common": True},
    "HDMI1": {"code": "19", "common": True},
    "HDMI2": {"code": "20", "common": False},
    "HDMI3": {"code": "21", "common": False},
    "HDMI4": {"code": "22", "common": False},
    "HDMI5": {"code": "23", "common": False},
    "HDMI6": {"code": "24", "common": False},
    "BD": {"code": "25", "common": True},
    "HOME MEDIA GALLERY(Internet Radio)": {"code": "26", "common": False},
    "Adapter": {"code": "33", "common": True},
    "Netradio": {"code": "38", "common": True},
    "Pandora": {"code": "41", "common": False},
    "Media Server": {"code": "44", "common": True},
    "Favorites": {"code": "45", "common": True},
    "HDMI/MHL": {"code": "48", "common": False},
    "Game": {"code": "49", "common": True},
}
