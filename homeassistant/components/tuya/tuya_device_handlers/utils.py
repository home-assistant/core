"""Common utility functions for Tuya quirks."""

from __future__ import annotations

from enum import StrEnum


def scale_value(value: int, step: float, scale: float) -> float:
    """Official scaling function from Tuya.

    See https://support.tuya.com/en/help/_detail/Kadi66s463e2q
    """
    return step * value / (10**scale)


def scale_value_back(value: float, step: float, scale: float) -> int:
    """Official scaling function from Tuya.

    See https://support.tuya.com/en/help/_detail/Kadi66s463e2q
    """

    return int(value * (10**scale) / step)


def parse_enum[T: StrEnum](enum_class: type[T], value: str | None) -> T | None:
    """Parse a string to an enum member.

    Return None if value is None or if the value does not correspond to any
    enum member.
    """
    if value is None:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None
