"""Constants for the Onkyo integration."""

from enum import Enum
import typing
from typing import Any, ClassVar, Literal, Self, overload

import pyeiscp

DOMAIN = "onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

CONF_SOURCES = "sources"
CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"

type VolumeResolution = Literal[50, 80, 100, 200]
CONF_VOLUME_RESOLUTION = "volume_resolution"
CONF_VOLUME_RESOLUTION_DEFAULT: VolumeResolution = 50
VOLUME_RESOLUTION_ALLOWED: tuple[VolumeResolution, ...] = typing.get_args(
    VolumeResolution.__value__
)

OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100.0

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
    "11": "STRM-BOX",
    "12": "TV",
    "20": "TAPE ··· TV/TAPE",
    "21": "TAPE2",
    "22": "PHONO",
    "23": "CD ··· TV/CD",
    "24": "FM",
    "25": "AM",
    "26": "TUNER",
    "27": "MUSIC-SERVER ··· P4S ··· DLNA",
    "28": "INTERNET-RADIO ··· IRADIO-FAVORITE",
    "29": "USB ··· USB(FRONT)",
    "2a": "USB(REAR)",
    "2b": "NETWORK ··· NET",
    "2d": "AIRPLAY",
    "2e": "BLUETOOTH",
    "2f": "USB-DAC-IN",
    "30": "MULTI-CH",
    "31": "XM",
    "32": "SIRIUS",
    "33": "DAB",
    "40": "UNIVERSAL-PORT",
    "41": "LINE",
    "42": "LINE2",
    "44": "OPTICAL",
    "45": "COAXIAL",
    "55": "HDMI-5",
    "56": "HDMI-6",
    "57": "HDMI-7",
    "80": "MAIN-SOURCE",
}

_cmds_base = pyeiscp.commands.COMMANDS
_cmds = dict(
    sorted(
        {
            **_cmds_base["main"]["SLI"]["values"],
            **_cmds_base["zone2"]["SLZ"]["values"],
        }.items()
    )
)
del _cmds["2C"]  # USB(TOGGLE)
del _cmds["7F"]  # OFF

type InputLibValue = str | tuple[str, ...]


class InputSource(Enum):
    """Receiver input source."""

    __meaning_mapping: ClassVar[dict[str, Self]] = {}  # type: ignore[misc]
    __lib_mapping: ClassVar[dict[InputLibValue, Self]] = {}  # type: ignore[misc]

    value_hex: str
    value_meaning: str
    value_lib: InputLibValue

    _ignore_ = "InputSource _k _v _value _meaning"

    InputSource = vars()
    for _k, _v in _cmds.items():
        try:
            _value = int(_k, 16)
            InputSource["I" + _k] = _value, _k.lower(), _v["name"]
        except ValueError:
            pass

    def __new__(cls, value: int, value_hex: str, value_lib: InputLibValue) -> Self:
        """Create InputSource enum."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.value_hex = value_hex
        obj.value_meaning = _INPUT_SOURCE_MEANINGS[value_hex]
        obj.value_lib = value_lib

        cls.__meaning_mapping[obj.value_meaning] = obj
        cls.__lib_mapping[value_lib] = obj

        return obj

    @overload  # type: ignore[misc]
    def __init__(self, value: int) -> None: ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Empty init to provide the proper signature to mypy.

        It is necessary, becauese mypy does not understand __new__ magic.
        """

    @classmethod
    def from_meaning(cls, meaning: str) -> Self:
        """Get InputSource enum from its meaning."""
        return cls.__meaning_mapping[meaning]

    @classmethod
    def from_lib(cls, value_lib: InputLibValue) -> Self:
        """Get InputSource enum from lib value."""
        return cls.__lib_mapping[value_lib]


OPTION_INPUT_SOURCES = "input_sources"

ZONES = {"main": "Main", "zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}
