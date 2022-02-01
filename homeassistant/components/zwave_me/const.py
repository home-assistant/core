"""Constants for ZWaveMe."""
from homeassistant.backports.enum import StrEnum
from homeassistant.const import Platform

# Base component constants
DOMAIN = "zwave_me"


class ZWaveMePlatform(StrEnum):
    """Included ZWaveMe platforms."""

    NUMBER = "switchMultilevel"
    SWITCH = "binarySwitch"
    BUTTON = "toggleButton"
    LOCK = "doorlock"
    SENSOR = "sensorMultilevel"
    BINARY_SENSOR = "sensorBinary"
    RGBW_LIGHT = "switchRGBW"
    RGB_LIGHT = "switchRGB"


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
