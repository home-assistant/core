"""Constants for the OpenRGB integration."""

from enum import StrEnum

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
