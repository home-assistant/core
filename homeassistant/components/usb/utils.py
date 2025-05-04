"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Sequence

from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo

from .models import USBDevice


def usb_device_from_port(port: ListPortInfo) -> USBDevice:
    """Convert serial ListPortInfo to USBDevice."""
    return USBDevice(
        device=port.device,
        vid=f"{hex(port.vid)[2:]:0>4}".upper(),
        pid=f"{hex(port.pid)[2:]:0>4}".upper(),
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.description,
    )


def scan_serial_ports() -> Sequence[USBDevice]:
    """Scan serial ports for USB devices."""
    return [
        usb_device_from_port(port)
        for port in comports()
        if port.vid is not None or port.pid is not None
    ]
