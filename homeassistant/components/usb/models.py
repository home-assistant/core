"""Models helper class for the usb integration."""
from __future__ import annotations

from typing import TypedDict


class USBDevice(TypedDict):
    """A usb device."""

    device: str
    vid: int
    pid: int
    serial_number: str
