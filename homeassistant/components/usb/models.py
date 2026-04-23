"""Models helper class for the usb integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True, kw_only=True)
class SerialDevice:
    """A serial device."""

    device: str
    serial_number: str | None
    manufacturer: str | None
    description: str | None


@dataclass(slots=True, frozen=True, kw_only=True)
class USBDevice(SerialDevice):
    """A usb device."""

    vid: str
    pid: str
