"""The USB Discovery integration."""

from __future__ import annotations

from collections.abc import Sequence
import fnmatch
import os

from serialx import SerialPortInfo, list_serial_ports

from homeassistant.core import HomeAssistant
from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.loader import USBMatcher

from .models import SerialDevice, USBDevice


def usb_device_from_port(port: SerialPortInfo) -> USBDevice:
    """Convert serialx SerialPortInfo to USBDevice."""
    assert port.vid is not None
    assert port.pid is not None

    return USBDevice(
        device=port.device,
        vid=f"{hex(port.vid)[2:]:0>4}".upper(),
        pid=f"{hex(port.pid)[2:]:0>4}".upper(),
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.product,
    )


def serial_device_from_port(port: SerialPortInfo) -> SerialDevice:
    """Convert serialx SerialPortInfo to SerialDevice."""
    return SerialDevice(
        device=port.device,
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.product,
    )


def usb_serial_device_from_port(port: SerialPortInfo) -> USBDevice | SerialDevice:
    """Convert serialx SerialPortInfo to USBDevice or SerialDevice."""
    if port.vid is not None and port.pid is not None:
        return usb_device_from_port(port)
    return serial_device_from_port(port)


def scan_serial_ports() -> Sequence[USBDevice | SerialDevice]:
    """Scan serial ports and return USB and other serial devices."""
    return [usb_serial_device_from_port(port) for port in list_serial_ports()]


async def async_scan_serial_ports(
    hass: HomeAssistant,
) -> Sequence[USBDevice | SerialDevice]:
    """Scan serial ports and return USB and other serial devices, async."""
    return await hass.async_add_executor_job(scan_serial_ports)


def usb_device_from_path(device_path: str) -> USBDevice | None:
    """Get USB device info from a device path."""

    device_path_real = os.path.realpath(device_path)

    for device in scan_serial_ports():
        # Skip non-USB serial devices
        if not isinstance(device, USBDevice):
            continue

        if os.path.realpath(device.device) == device_path_real:
            return device

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
