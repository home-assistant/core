"""Models helper class for the usb integration."""

from dataclasses import dataclass
from typing import Literal


@dataclass(slots=True, frozen=True, kw_only=True)
class SerialDevice:
    """A serial device."""

    device: str
    resolved_device: str | None = None

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


@dataclass(slots=True, frozen=True, kw_only=True)
class SerialPortConsumer:
    """An integration or app configured to use a serial port."""

    kind: Literal["config_entry", "app"]
    title: str
    active: bool
    domain: str | None = None
    config_entry_id: str | None = None
    slug: str | None = None
