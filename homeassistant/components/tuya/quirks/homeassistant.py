"""Quirks registry."""

from __future__ import annotations

from enum import StrEnum


def parse_enum[T: StrEnum](enum_class: type[T], value: str | None) -> T | None:
    """Parse a string to an enum member, or return None if value is None."""
    if value is None:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None


class TuyaCoverDeviceClass(StrEnum):
    """Device class for cover."""

    # Keep synchronized with homeassistant
    AWNING = "awning"
    BLIND = "blind"
    CURTAIN = "curtain"
    DAMPER = "damper"
    DOOR = "door"
    GARAGE = "garage"
    GATE = "gate"
    SHADE = "shade"
    SHUTTER = "shutter"
    WINDOW = "window"
