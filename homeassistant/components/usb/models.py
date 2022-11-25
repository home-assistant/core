"""Models helper class for the usb integration."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class USBDevice:
    """A usb device."""

    device: str
    vid: str | None
    pid: str | None
    serial_number: str | None
    manufacturer: str | None
    description: str | None
