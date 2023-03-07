"""Consts used by pioneer."""
from typing import Final

DEFAULT_ZONE = 1

CONF_SOURCES = "sources"
CONF_ZONES = "zones"
DOMAIN = "pioneer"
DEFAULT_NAME = "Pioneer AVR"
DEFAULT_PORT = 23  # telnet default. Some Pioneer AVRs use 8102
DEFAULT_TIMEOUT: Final = 500
DEFAULT_SOURCES: dict[str, str] = {
    "Phono": "00",
    "CD": "01",
    "Tuner": "02",
    "CD-R/Tape": "03",
    "DVD": "04",
    "TV/Sat": "05",
    "Sat/Cbl": "06",
    "Video 1": "10",
    "Multi Channel In": "12",
    "Video 2": "14",
    "DVR/BDR": "15",
    "iPod/USB": "17",
    "XM Radio": "18",
    "HDMI 1": "19",
    "HDMI 2": "20",
    "HDMI 3": "21",
    "HDMI 4": "22",
    "HDMI 5": "23",
    "HDMI 6": "24",
    "Blu-Ray": "25",
    "Home Media Gallery (Internet Radio)": "26",
    "Sirius": "27",
    "Adapter Port": "33",
    "Netradio": "38",
    "Media Server": "44",
    "Favorites": "45",
    "Game": "49",
}

MAX_VOLUME = 185
MAX_SOURCE_NUMBERS = 60


ZONE_COMMANDS: dict[int, dict[str, dict[str, str]]] = {
    1: {
        "POWER": {"COMMAND": "?P", "PREFIX": "PWR"},
        "VOL": {"COMMAND": "?V", "PREFIX": "VOL"},
        "MUTE": {"COMMAND": "?M", "PREFIX": "MUT"},
        "SOURCE_NUM": {"COMMAND": "?F", "PREFIX": "FN"},
        "TURN_OFF": {"COMMAND": "PF", "PREFIX": ""},
        "VOL_UP": {"COMMAND": "VU", "PREFIX": ""},
        "VOL_DOWN": {"COMMAND": "VD", "PREFIX": ""},
        "VOL_LEVEL": {"COMMAND": "VL", "PREFIX": ""},
        "MUTE_VOL": {"COMMAND": "MF", "PREFIX": ""},
        "UNMUTE_VOL": {"COMMAND": "MO", "PREFIX": ""},
        "TURN_ON": {"COMMAND": "PO", "PREFIX": ""},
        "SELECT_SOURCE": {"COMMAND": "FN", "PREFIX": ""},
        "MUTED_VALUE": {"COMMAND": "MUT0", "PREFIX": ""},
    },
    2: {
        "POWER": {"COMMAND": "?AP", "PREFIX": "APR"},
        "VOL": {"COMMAND": "?ZV", "PREFIX": "ZV"},
        "MUTE": {"COMMAND": "?Z2M", "PREFIX": "Z2MUT"},
        "SOURCE_NUM": {"COMMAND": "?ZS", "PREFIX": "Z2F"},
        "TURN_OFF": {"COMMAND": "APF", "PREFIX": ""},
        "VOL_UP": {"COMMAND": "ZU", "PREFIX": ""},
        "VOL_DOWN": {"COMMAND": "ZD", "PREFIX": ""},
        "VOL_LEVEL": {"COMMAND": "ZV", "PREFIX": ""},
        "MUTE_VOL": {"COMMAND": "Z2MF", "PREFIX": ""},
        "UNMUTE_VOL": {"COMMAND": "Z2MO", "PREFIX": ""},
        "TURN_ON": {"COMMAND": "APO", "PREFIX": ""},
        "SELECT_SOURCE": {"COMMAND": "ZS", "PREFIX": ""},
        "MUTED_VALUE": {"COMMAND": "Z2MUT0", "PREFIX": ""},
    },
}
