"""The USB Discovery integration."""
from __future__ import annotations

import os.path

from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo

from .models import USBDevice


def usb_device_from_port(port: ListPortInfo) -> USBDevice:
    """Convert serial ListPortInfo to USBDevice."""
    return USBDevice(
        device=port.device,
        vid=f"{port.vid:04X}" if port.vid is not None else None,
        pid=f"{port.pid:04X}" if port.pid is not None else None,
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.description,
    )


def get_by_id_symlinks() -> dict[str, str]:
    """Map all `by-id` symlinks to their resolved location."""
    by_id = "/dev/serial/by-id"

    if not os.path.isdir(by_id):
        return {}

    return {
        os.path.realpath(path): path
        for path in (entry.path for entry in os.scandir(by_id) if entry.is_symlink())
    }


def list_serial_ports() -> list[USBDevice]:
    """List all available serial ports."""
    ports = []
    by_id_symlinks = get_by_id_symlinks()

    for port in comports():
        if port.device in by_id_symlinks:
            port.device = by_id_symlinks[port.device]

        ports.append(usb_device_from_port(port))

    return ports
