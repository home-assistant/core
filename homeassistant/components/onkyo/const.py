"""Constants for the Onkyo integration."""

from enum import Enum
import typing
from typing import ClassVar, Literal, Self

import pyeiscp

DOMAIN = "onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

CONF_SOURCES = "sources"
CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"

type VolumeResolution = Literal[50, 80, 100, 200]
OPTION_VOLUME_RESOLUTION = "volume_resolution"
OPTION_VOLUME_RESOLUTION_DEFAULT: VolumeResolution = 50
VOLUME_RESOLUTION_ALLOWED: tuple[VolumeResolution, ...] = typing.get_args(
    VolumeResolution.__value__
)

OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100.0

OPTION_INPUT_SOURCES = "input_sources"

_INPUT_SOURCE_MEANINGS = {
    "00": "VIDEO1 ··· VCR/DVR ··· STB/DVR",
    "01": "VIDEO2 ··· CBL/SAT",
    "02": "VIDEO3 ··· GAME/TV ··· GAME",
    "03": "VIDEO4 ··· AUX",
    "04": "VIDEO5 ··· AUX2 ··· GAME2",
    "05": "VIDEO6 ··· PC",
    "06": "VIDEO7",
    "07": "HIDDEN1 ··· EXTRA1",
    "08": "HIDDEN2 ··· EXTRA2",
    "09": "HIDDEN3 ··· EXTRA3",
    "10": "DVD ··· BD/DVD",
    "11": "STRM BOX",
    "12": "TV",
    "20": "TAPE ··· TV/TAPE",
    "21": "TAPE2",
    "22": "PHONO",
    "23": "CD ··· TV/CD",
    "24": "FM",
    "25": "AM",
    "26": "TUNER",
    "27": "MUSIC SERVER ··· P4S ··· DLNA",
    "28": "INTERNET RADIO ··· IRADIO FAVORITE",
    "29": "USB ··· USB(FRONT)",
    "2A": "USB(REAR)",
    "2B": "NETWORK ··· NET",
    "2D": "AIRPLAY",
    "2E": "BLUETOOTH",
    "2F": "USB DAC IN",
    "30": "MULTI CH",
    "31": "XM",
    "32": "SIRIUS",
    "33": "DAB",
    "40": "UNIVERSAL PORT",
    "41": "LINE",
    "42": "LINE2",
    "44": "OPTICAL",
    "45": "COAXIAL",
    "55": "HDMI 5",
    "56": "HDMI 6",
    "57": "HDMI 7",
    "80": "MAIN SOURCE",
}


class InputSource(Enum):
    """Receiver input source."""

    DVR = "00"
    CBL = "01"
    GAME = "02"
    AUX = "03"
    GAME2 = "04"
    PC = "05"
    VIDEO7 = "06"
    EXTRA1 = "07"
    EXTRA2 = "08"
    EXTRA3 = "09"
    DVD = "10"
    STRM_BOX = "11"
    TV = "12"
    TAPE = "20"
    TAPE2 = "21"
    PHONO = "22"
    CD = "23"
    FM = "24"
    AM = "25"
    TUNER = "26"
    MUSIC_SERVER = "27"
    INTERNET_RADIO = "28"
    USB = "29"
    USB_REAR = "2A"
    NETWORK = "2B"
    AIRPLAY = "2D"
    BLUETOOTH = "2E"
    USB_DAC_IN = "2F"
    MULTI_CH = "30"
    XM = "31"
    SIRIUS = "32"
    DAB = "33"
    UNIVERSAL_PORT = "40"
    LINE = "41"
    LINE2 = "42"
    OPTICAL = "44"
    COAXIAL = "45"
    HDMI_5 = "55"
    HDMI_6 = "56"
    HDMI_7 = "57"
    MAIN_SOURCE = "80"

    __meaning_mapping: ClassVar[dict[str, Self]] = {}  # type: ignore[misc]

    value_meaning: str

    def __new__(cls, value: str) -> Self:
        """Create InputSource enum."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.value_meaning = _INPUT_SOURCE_MEANINGS[value]

        cls.__meaning_mapping[obj.value_meaning] = obj

        return obj

    @classmethod
    def from_meaning(cls, meaning: str) -> Self:
        """Get InputSource enum from its meaning."""
        return cls.__meaning_mapping[meaning]


ZONES = {"main": "Main", "zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}

PYEISCP_COMMANDS = pyeiscp.commands.COMMANDS
