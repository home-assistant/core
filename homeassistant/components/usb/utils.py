"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Sequence
import dataclasses
import os.path
import sys

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


def get_serial_by_id_mapping() -> dict[str, str]:
    """Return a mapping of /dev/serial/by-id to /dev/tty."""
    by_id = "/dev/serial/by-id"
    if not os.path.isdir(by_id):
        return {}

    mapping = {}
    for entry in os.scandir(by_id):
        if not entry.is_symlink():
            continue
        mapping[entry.path] = os.path.realpath(entry.path)
    return mapping


def scan_serial_ports() -> Sequence[USBDevice]:
    """Scan for serial ports."""
    ports = comports()
    serial_by_id_mapping = get_serial_by_id_mapping()

    usb_devices = [
        usb_device_from_port(port)
        for port in ports
        if port.vid is not None or port.pid is not None
    ]

    # Update the USB device path to point to the unique serial port, if one exists
    for index, device in enumerate(usb_devices):
        if device.device in serial_by_id_mapping:
            usb_devices[index] = dataclasses.replace(
                device, device=serial_by_id_mapping[device.device]
            )

    # CP2102N chips create *two* serial ports on macOS: `/dev/cu.usbserial-` and
    # `/dev/cu.SLAB_USBtoUART*`. The former does not work and we should ignore them.
    if sys.platform == "darwin":
        silabs_serials = {
            dev.serial_number
            for dev in usb_devices
            if dev.device.startswith("/dev/cu.SLAB_USBtoUART")
        }

        usb_devices = [
            dev
            for dev in usb_devices
            if dev.serial_number not in silabs_serials
            or (
                dev.serial_number in silabs_serials
                and dev.device.startswith("/dev/cu.SLAB_USBtoUART")
            )
        ]

    return usb_devices
