"""Constants for the Onkyo integration."""

from enum import Enum
import typing
from typing import Any, ClassVar, Literal, Self, overload

import pyeiscp

DOMAIN = "onkyo"

DEVICE_INTERVIEW_TIMEOUT = 5
DEVICE_DISCOVERY_TIMEOUT = 5

CONF_RECEIVER_MAX_VOLUME = "receiver_max_volume"

type VolumeResolution = Literal[50, 80, 100, 200]
CONF_VOLUME_RESOLUTION = "volume_resolution"
CONF_VOLUME_RESOLUTION_DEFAULT: VolumeResolution = 50
VOLUME_RESOLUTION_ALLOWED: tuple[VolumeResolution, ...] = typing.get_args(
    VolumeResolution.__value__
)

OPTION_MAX_VOLUME = "max_volume"
OPTION_MAX_VOLUME_DEFAULT = 100.0

_cmds_base = pyeiscp.commands.COMMANDS
_cmds = dict(
    sorted(
        {
            **_cmds_base["main"]["SLI"]["values"],
            **_cmds_base["zone2"]["SLZ"]["values"],
        }.items()
    )
)


class InputSource(Enum):
    """Receiver input source."""

    __single_meaning_mapping: ClassVar[dict[str, Self]] = {}  # type: ignore[misc]

    value_hex: str
    value_meaning: str
    value_meaning_singles: tuple[str, ...]

    _ignore_ = "InputSource _k _v _value"

    InputSource = vars()
    for _k, _v in _cmds.items():
        try:
            _value = int(_k, 16)
            if _value == 0x7F:
                continue
            InputSource["I" + _k] = _value, _k.lower(), _v["name"]
        except ValueError:
            pass

    def __new__(
        cls, value: int, value_hex: str, meanings_raw: str | tuple[str, ...]
    ) -> Self:
        """Create InputSource enum."""
        obj = object.__new__(cls)
        obj._value_ = value
        obj.value_hex = value_hex

        meaning_singles: tuple[str, ...]
        if isinstance(meanings_raw, str):
            meaning = meanings_raw
            meaning_singles = (meanings_raw,)
        else:
            meaning_singles = meanings_raw
            meaning = ", ".join(meanings_raw)

        obj.value_meaning = meaning
        obj.value_meaning_singles = meaning_singles

        for meaning_single in meaning_singles:
            cls.__single_meaning_mapping[meaning_single] = obj

        return obj

    @overload  # type: ignore[misc]
    def __init__(self, value: int) -> None: ...

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Empty init to provide the proper signature to mypy.

        It is necessary, becauese mypy does not understand __new__ magic.
        """

    @classmethod
    def from_single_meaning(cls, meaning: str) -> Self:
        """Create InputSource enum from single meaning."""
        return cls.__single_meaning_mapping[meaning]

    @classmethod
    def all_single_meanings(cls) -> set[str]:
        """All InputSource single meanings."""
        return set(cls.__single_meaning_mapping)


OPTION_SOURCES = "sources"
# This should be kept in sync with strings.json for dynamic options generation
# to work correctly.
OPTION_SOURCE_PREFIX = "source_"
OPTION_SOURCES_ALLOWED = [
    f"{OPTION_SOURCE_PREFIX}{source.value_hex}" for source in InputSource
]

ZONES = {"main": "Main", "zone2": "Zone 2", "zone3": "Zone 3", "zone4": "Zone 4"}
