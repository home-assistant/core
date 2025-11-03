"""Common utility functions for Tuya quirks."""

from __future__ import annotations

from enum import StrEnum


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
