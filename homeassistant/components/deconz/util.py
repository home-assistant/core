"""Utilities for deCONZ integration."""
from __future__ import annotations


def serial_from_unique_id(unique_id: str | None) -> str | None:
    """Get a device serial number from a unique ID, if possible."""
    if not unique_id or unique_id.count(":") != 7:
        return None
    return unique_id.partition("-")[0]
