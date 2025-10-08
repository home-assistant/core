"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Sequence
import os

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


def usb_device_from_path(device_path: str) -> USBDevice | None:
    """Get USB device info from a device path."""

    # Scan all symlinks first
    by_id = "/dev/serial/by-id"
    realpath_to_by_id: dict[str, str] = {}
    if os.path.isdir(by_id):
        for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink()):
            realpath_to_by_id[os.path.realpath(path)] = path

    # Then compare the actual path to each serial port's
    device_path_real = os.path.realpath(device_path)

    for device in scan_serial_ports():
        normalized_path = realpath_to_by_id.get(device.device, device.device)
        if (
            normalized_path == device_path
            or os.path.realpath(device.device) == device_path_real
        ):
            return USBDevice(
                device=normalized_path,
                vid=device.vid,
                pid=device.pid,
                serial_number=device.serial_number,
                manufacturer=device.manufacturer,
                description=device.description,
            )

    return None
