"""The USB Discovery integration."""

from collections.abc import Sequence
import fnmatch
import os
import string
from urllib.parse import parse_qs, urlsplit

from serialx import SerialPortInfo, list_serial_ports

from homeassistant.helpers.service_info.usb import UsbServiceInfo
from homeassistant.loader import USBMatcher

from .models import SerialDevice, USBDevice


def usb_device_from_port(port: SerialPortInfo) -> USBDevice:
    """Convert serialx SerialPortInfo to USBDevice."""
    assert port.vid is not None
    assert port.pid is not None

    return USBDevice(
        device=port.device,
        resolved_device=port.resolved_device,
        vid=f"{hex(port.vid)[2:]:0>4}".upper(),
        pid=f"{hex(port.pid)[2:]:0>4}".upper(),
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.description,
        bcd_device=port.bcd_device,
        interface_description=port.interface_description,
        interface_num=port.interface_num,
    )


def serial_device_from_port(port: SerialPortInfo) -> SerialDevice:
    """Convert serialx SerialPortInfo to SerialDevice."""
    return SerialDevice(
        device=port.device,
        resolved_device=port.resolved_device,
        serial_number=port.serial_number,
        manufacturer=port.manufacturer,
        description=port.description,
        interface_description=port.interface_description,
        interface_num=port.interface_num,
    )


def usb_serial_device_from_port(port: SerialPortInfo) -> USBDevice | SerialDevice:
    """Convert serialx SerialPortInfo to USBDevice or SerialDevice."""
    if port.vid is not None and port.pid is not None:
        return usb_device_from_port(port)
    return serial_device_from_port(port)


def scan_serial_ports() -> Sequence[USBDevice | SerialDevice]:
    """Scan serial ports and return USB and other serial devices."""
    return [usb_serial_device_from_port(port) for port in list_serial_ports()]


# udev builds /dev/serial/by-id links in 60-serial.rules from the USB string descriptors,
# after the usb_id builtin has sanitized them. Reproducing that naming lets a port reached
# through a scanner, an ESPHome device say, be recognized as the adapter a stored by-id
# path refers to, without config entries having to store anything beyond the path.
SERIAL_BY_ID_DIR = "/dev/serial/by-id"
_UDEV_SAFE_CHARS = frozenset(string.ascii_letters + string.digits + "#+-.:=@_")
# usb_id keeps the vendor and model in 64-byte buffers
_UDEV_MAX_STRING_LEN = 63


def _udev_sanitize(value: str) -> str:
    """Apply usb_id's whitespace and character replacement to a descriptor string."""
    # udev_replace_whitespace: trim, and collapse each run of whitespace to one underscore
    collapsed = "_".join(value.split())[:_UDEV_MAX_STRING_LEN]
    # udev_replace_chars: everything outside the safe set becomes an underscore, except
    # for valid UTF-8 beyond ASCII, which is kept as it is
    return "".join(
        char if char in _UDEV_SAFE_CHARS or ord(char) > 0x7F else "_"
        for char in collapsed
    )


def udev_serial_by_id_names(device: USBDevice) -> list[str]:
    """Return the /dev/serial/by-id links udev would give this device on a Linux host.

    Two candidates come back, because the driver cannot be told from the device alone: a
    CDC ACM port has no `-port0` suffix, a port from a `usb-serial` driver has one.
    """
    # A device without a manufacturer or product string is named by the hex ids, the way
    # sysfs spells them
    vendor = (
        _udev_sanitize(device.manufacturer)
        if device.manufacturer
        else device.vid.lower()
    )

    # The scan folds the interface string into the description; udev uses the product alone
    product = device.description
    if product is not None and device.interface_description is not None:
        product = product.removesuffix(f" - {device.interface_description}")
    model = _udev_sanitize(product) if product else device.pid.lower()

    id_serial = f"{vendor}_{model}"
    if device.serial_number:
        id_serial += f"_{_udev_sanitize(device.serial_number)}"

    interface_num = device.interface_num if device.interface_num is not None else 0
    base = f"{SERIAL_BY_ID_DIR}/usb-{id_serial}-if{interface_num:02x}"
    return [base, f"{base}-port0"]


def usb_device_matches_serial_path(device: USBDevice, path: str) -> bool:
    """Whether a stored serial port path refers to this device, wherever it is now.

    A stored path is either a Linux by-id link or a scanner URL that pins a device in its
    query. Both name the adapter rather than the socket it sits in, which is what allows an
    adapter to be recognized after moving between a USB port on the host and one behind a
    scanner. Plain device nodes and URLs that pin nothing name a socket, and never match.
    """
    if path == device.device:
        return True

    if path.startswith(f"{SERIAL_BY_ID_DIR}/"):
        return path in udev_serial_by_id_names(device)

    if "://" not in path:
        return False

    query = parse_qs(urlsplit(path).query)
    if "usb_serial" not in query or not device.serial_number:
        return False
    if query["usb_serial"][0] != device.serial_number:
        return False

    for key, value in (("vid", device.vid), ("pid", device.pid)):
        if key in query and query[key][0].upper() != value.upper():
            return False

    return True


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
