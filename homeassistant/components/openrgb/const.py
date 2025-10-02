"""Constants for the OpenRGB integration."""

from enum import StrEnum

from openrgb.utils import DeviceType

DOMAIN = "openrgb"

# Defaults
DEFAULT_PORT = 6742
DEFAULT_CLIENT_NAME = "Home Assistant"

DEFAULT_COLOR = (255, 255, 255)
DEFAULT_BRIGHTNESS = 255
OFF_COLOR = (0, 0, 0)


class OpenRGBMode(StrEnum):
    """OpenRGB modes."""

    OFF = "Off"
    STATIC = "Static"
    DIRECT = "Direct"


EFFECT_OFF_OPENRGB_MODES = {OpenRGBMode.STATIC, OpenRGBMode.DIRECT}

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
