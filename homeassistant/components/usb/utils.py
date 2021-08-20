"""The USB Discovery integration."""
from __future__ import annotations

from typing import Optional, Tuple

from serial.tools.list_ports_common import ListPortInfo

from .models import USBDevice

USBDeviceTupleType = Tuple[str, str, str, Optional[str], Optional[str], Optional[str]]


def usb_device_from_port(port: ListPortInfo) -> USBDevice:
    """Convert serial ListPortInfo to USBDevice."""
    return {
        "device": port.device,
        "vid": f"{hex(port.vid)[2:]:0>4}".upper(),
        "pid": f"{hex(port.pid)[2:]:0>4}".upper(),
        "serial_number": port.serial_number,
        "manufacturer": port.manufacturer,
        "description": port.description,
    }


def usb_device_tuple(usb_device: USBDevice) -> USBDeviceTupleType:
    """Generate a unique tuple for a usb device."""
    return (
        usb_device["device"],
        usb_device["vid"],
        usb_device["pid"],
        usb_device["serial_number"],
        usb_device["manufacturer"],
        usb_device["description"],
    )
