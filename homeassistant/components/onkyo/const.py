"""Constants for the Onkyo integration."""

from enum import Enum
import typing
from typing import Literal, Self

import pyeiscp

DOMAIN = "onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

type VolumeResolution = Literal[50, 80, 100, 200]
OPTION_VOLUME_RESOLUTION = "volume_resolution"
OPTION_VOLUME_RESOLUTION_DEFAULT: VolumeResolution = 50
VOLUME_RESOLUTION_ALLOWED: tuple[VolumeResolution, ...] = typing.get_args(
    VolumeResolution.__value__
)

OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100.0


class EnumWithMeaning(Enum):
    """Enum with meaning."""

    value_meaning: str

    def __new__(cls, value: str) -> Self:
        """Create enum."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.value_meaning = cls._get_meanings()[value]

        return obj

    @staticmethod
    def _get_meanings() -> dict[str, str]:
        raise NotImplementedError


OPTION_INPUT_SOURCES = "input_sources"
OPTION_LISTENING_MODES = "listening_modes"

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


class InputSource(EnumWithMeaning):
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

    @staticmethod
    def _get_meanings() -> dict[str, str]:
        return _INPUT_SOURCE_MEANINGS


_LISTENING_MODE_MEANINGS = {
    "00": "STEREO",
    "01": "DIRECT",
    "02": "SURROUND",
    "03": "FILM ··· GAME RPG ··· ADVANCED GAME",
    "04": "THX",
    "05": "ACTION ··· GAME ACTION",
    "06": "MUSICAL ··· GAME ROCK ··· ROCK/POP",
    "07": "MONO MOVIE",
    "08": "ORCHESTRA ··· CLASSICAL",
    "09": "UNPLUGGED",
    "0A": "STUDIO MIX ··· ENTERTAINMENT SHOW",
    "0B": "TV LOGIC ··· DRAMA",
    "0C": "ALL CH STEREO ··· EXTENDED STEREO",
    "0D": "THEATER DIMENSIONAL ··· FRONT STAGE SURROUND",
    "0E": "ENHANCED 7/ENHANCE ··· GAME SPORTS ··· SPORTS",
    "0F": "MONO",
    "11": "PURE AUDIO ··· PURE DIRECT",
    "12": "MULTIPLEX",
    "13": "FULL MONO ··· MONO MUSIC",
    "14": "DOLBY VIRTUAL/SURROUND ENHANCER",
    "15": "DTS SURROUND SENSATION",
    "16": "AUDYSSEY DSX",
    "17": "DTS VIRTUAL:X",
    "1F": "WHOLE HOUSE MODE ··· MULTI ZONE MUSIC",
    "23": "STAGE (JAPAN GENRE CONTROL)",
    "25": "ACTION (JAPAN GENRE CONTROL)",
    "26": "MUSIC (JAPAN GENRE CONTROL)",
    "2E": "SPORTS (JAPAN GENRE CONTROL)",
    "40": "STRAIGHT DECODE ··· 5.1 CH SURROUND",
    "41": "DOLBY EX/DTS ES",
    "42": "THX CINEMA",
    "43": "THX SURROUND EX",
    "44": "THX MUSIC",
    "45": "THX GAMES",
    "50": "THX U(2)/S(2)/I/S CINEMA",
    "51": "THX U(2)/S(2)/I/S MUSIC",
    "52": "THX U(2)/S(2)/I/S GAMES",
    "80": "DOLBY ATMOS/DOLBY SURROUND ··· PLII/PLIIx MOVIE",
    "81": "PLII/PLIIx MUSIC",
    "82": "DTS:X/NEURAL:X ··· NEO:6/NEO:X CINEMA",
    "83": "NEO:6/NEO:X MUSIC",
    "84": "DOLBY SURROUND THX CINEMA ··· PLII/PLIIx THX CINEMA",
    "85": "DTS NEURAL:X THX CINEMA ··· NEO:6/NEO:X THX CINEMA",
    "86": "PLII/PLIIx GAME",
    "87": "NEURAL SURR",
    "88": "NEURAL THX/NEURAL SURROUND",
    "89": "DOLBY SURROUND THX GAMES ··· PLII/PLIIx THX GAMES",
    "8A": "DTS NEURAL:X THX GAMES ··· NEO:6/NEO:X THX GAMES",
    "8B": "DOLBY SURROUND THX MUSIC ··· PLII/PLIIx THX MUSIC",
    "8C": "DTS NEURAL:X THX MUSIC ··· NEO:6/NEO:X THX MUSIC",
    "8D": "NEURAL THX CINEMA",
    "8E": "NEURAL THX MUSIC",
    "8F": "NEURAL THX GAMES",
    "90": "PLIIz HEIGHT",
    "91": "NEO:6 CINEMA DTS SURROUND SENSATION",
    "92": "NEO:6 MUSIC DTS SURROUND SENSATION",
    "93": "NEURAL DIGITAL MUSIC",
    "94": "PLIIz HEIGHT + THX CINEMA",
    "95": "PLIIz HEIGHT + THX MUSIC",
    "96": "PLIIz HEIGHT + THX GAMES",
    "97": "PLIIz HEIGHT + THX U2/S2 CINEMA",
    "98": "PLIIz HEIGHT + THX U2/S2 MUSIC",
    "99": "PLIIz HEIGHT + THX U2/S2 GAMES",
    "9A": "NEO:X GAME",
    "A0": "PLIIx/PLII Movie + AUDYSSEY DSX",
    "A1": "PLIIx/PLII MUSIC + AUDYSSEY DSX",
    "A2": "PLIIx/PLII GAME + AUDYSSEY DSX",
    "A3": "NEO:6 CINEMA + AUDYSSEY DSX",
    "A4": "NEO:6 MUSIC + AUDYSSEY DSX",
    "A5": "NEURAL SURROUND + AUDYSSEY DSX",
    "A6": "NEURAL DIGITAL MUSIC + AUDYSSEY DSX",
    "A7": "DOLBY EX + AUDYSSEY DSX",
    "FF": "AUTO SURROUND",
}


class ListeningMode(EnumWithMeaning):
    """Receiver listening mode."""

    _ignore_ = "ListeningMode _k _v _meaning"

    ListeningMode = vars()
    for _k in _LISTENING_MODE_MEANINGS:
        ListeningMode["I" + _k] = _k

    @staticmethod
    def _get_meanings() -> dict[str, str]:
        return _LISTENING_MODE_MEANINGS


ZONES = {"main": "Main", "zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}

PYEISCP_COMMANDS = pyeiscp.commands.COMMANDS
