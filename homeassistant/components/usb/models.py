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
    interface_description: str | None = None
    interface_num: int | None = None


@dataclass(slots=True, frozen=True, kw_only=True)
class USBDevice(SerialDevice):
    """A usb device."""

    vid: str
    pid: str

    # bcdDevice descriptor, often the firmware revision
    bcd_device: int | None = None
