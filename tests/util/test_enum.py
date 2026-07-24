"""Test enum helpers."""

from enum import Enum, IntEnum, IntFlag, StrEnum
from typing import Any

import pytest

from homeassistant.util.enum import try_parse_enum


class _AStrEnum(StrEnum):
    VALUE = "value"


class _AnIntEnum(IntEnum):
    VALUE = 1


class _AnIntFlag(IntFlag):
    VALUE = 1
    SECOND = 2


@pytest.mark.parametrize(
    ("enum_type", "value", "expected"),
    [
        # StrEnum valid checks
        (_AStrEnum, _AStrEnum.VALUE, _AStrEnum.VALUE),
        (_AStrEnum, "value", _AStrEnum.VALUE),
        # StrEnum invalid checks
        (_AStrEnum, "invalid", None),
        (_AStrEnum, 1, None),
        (_AStrEnum, None, None),
        # IntEnum valid checks
        (_AnIntEnum, _AnIntEnum.VALUE, _AnIntEnum.VALUE),
        (_AnIntEnum, 1, _AnIntEnum.VALUE),
        # IntEnum invalid checks
        (_AnIntEnum, "value", None),
        (_AnIntEnum, 2, None),
        (_AnIntEnum, None, None),
        # IntFlag valid checks
        (_AnIntFlag, _AnIntFlag.VALUE, _AnIntFlag.VALUE),
        (_AnIntFlag, 1, _AnIntFlag.VALUE),
        (_AnIntFlag, 2, _AnIntFlag(2)),
        # IntFlag invalid checks
        (_AnIntFlag, "value", None),
        (_AnIntFlag, None, None),
    ],
)
def test_try_parse(enum_type: type[Enum], value: Any, expected: Enum | None) -> None:
    """Test parsing of values into an Enum."""
    assert try_parse_enum(enum_type, value) is expected
