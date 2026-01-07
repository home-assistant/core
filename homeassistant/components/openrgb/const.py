"""Constants for the OpenRGB integration."""

from datetime import timedelta
from enum import StrEnum
import socket

from openrgb.utils import (
    ControllerParsingError,
    DeviceType,
    OpenRGBDisconnected,
    SDKVersionError,
)

DOMAIN = "openrgb"

UID_SEPARATOR = "||"

# Defaults
DEFAULT_PORT = 6742
DEFAULT_CLIENT_NAME = "Home Assistant"

# Update interval
SCAN_INTERVAL = timedelta(seconds=15)

DEFAULT_COLOR = (255, 255, 255)
DEFAULT_BRIGHTNESS = 255
OFF_COLOR = (0, 0, 0)


class OpenRGBMode(StrEnum):
    """OpenRGB modes."""

    OFF = "Off"
    STATIC = "Static"
    DIRECT = "Direct"
    CUSTOM = "Custom"


EFFECT_OFF_OPENRGB_MODES = {OpenRGBMode.STATIC, OpenRGBMode.DIRECT, OpenRGBMode.CUSTOM}

DEVICE_TYPE_ICONS: dict[DeviceType, str] = {
    DeviceType.MOTHERBOARD: "mdi:developer-board",
    DeviceType.DRAM: "mdi:memory",
    DeviceType.GPU: "mdi:expansion-card",
    DeviceType.COOLER: "mdi:fan",
    DeviceType.LEDSTRIP: "mdi:led-variant-on",
    DeviceType.KEYBOARD: "mdi:keyboard",
    DeviceType.MOUSE: "mdi:mouse",
    DeviceType.MOUSEMAT: "mdi:rug",
    DeviceType.HEADSET: "mdi:headset",
    DeviceType.HEADSET_STAND: "mdi:headset-dock",
    DeviceType.GAMEPAD: "mdi:gamepad-variant",
    DeviceType.SPEAKER: "mdi:speaker",
    DeviceType.STORAGE: "mdi:harddisk",
    DeviceType.CASE: "mdi:desktop-tower",
    DeviceType.MICROPHONE: "mdi:microphone",
    DeviceType.KEYPAD: "mdi:dialpad",
}

CONNECTION_ERRORS = (
    ConnectionRefusedError,
    OpenRGBDisconnected,
    ControllerParsingError,
    TimeoutError,
    socket.gaierror,  # DNS errors
    SDKVersionError,  # The OpenRGB SDK server version is incompatible with the client
)
