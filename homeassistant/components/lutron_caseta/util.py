"""Support for Lutron Caseta."""

from __future__ import annotations


def serial_to_unique_id(serial: int) -> str:
    """Convert a lutron serial number to a unique id."""
    return hex(serial)[2:].zfill(8)
