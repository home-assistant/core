"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Sequence
import fnmatch
import os

from serial.tools.list_ports import comports
from serial.tools.list_ports_common import ListPortInfo

from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.loader import USBMatcher

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


def _fnmatch_lower(name: str | None, pattern: str) -> bool:
    """Match a lowercase version of the name."""
    if name is None:
        return False
    return fnmatch.fnmatch(name.lower(), pattern)


def usb_device_matches_matcher(device: USBDevice, matcher: USBMatcher) -> bool:
    """Check if a USB device matches a USB matcher."""
    if "vid" in matcher and device.vid != matcher["vid"]:
        return False

    if "pid" in matcher and device.pid != matcher["pid"]:
        return False

    if "serial_number" in matcher and not _fnmatch_lower(
        device.serial_number, matcher["serial_number"]
    ):
        return False

    if "manufacturer" in matcher and not _fnmatch_lower(
        device.manufacturer, matcher["manufacturer"]
    ):
        return False

    if "description" in matcher and not _fnmatch_lower(
        device.description, matcher["description"]
    ):
        return False

    return True


def usb_unique_id_from_service_info(usb_info: UsbServiceInfo) -> str:
    """Generate a unique ID from USB service info."""
    return (
        f"{usb_info.vid}:{usb_info.pid}_"
        f"{usb_info.serial_number}_"
        f"{usb_info.manufacturer}_"
        f"{usb_info.description}"
    )


def usb_service_info_from_device(usb_device: USBDevice) -> UsbServiceInfo:
    """Convert a USBDevice to UsbServiceInfo."""
    return UsbServiceInfo(
        device=usb_device.device,
        vid=usb_device.vid,
        pid=usb_device.pid,
        serial_number=usb_device.serial_number,
        manufacturer=usb_device.manufacturer,
        description=usb_device.description,
    )
