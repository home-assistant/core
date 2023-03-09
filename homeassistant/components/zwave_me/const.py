"""Constants for ZWaveMe."""
from homeassistant.backports.enum import StrEnum
from homeassistant.const import Platform

# Base component constants
DOMAIN = "zwave_me"


class ZWaveMePlatform(StrEnum):
    """Included ZWaveMe platforms."""

    BINARY_SENSOR = "sensorBinary"
    BRIGHTNESS_LIGHT = "lightMultilevel"
    BUTTON = "toggleButton"
    CLIMATE = "thermostat"
    COVER = "motor"
    FAN = "fan"
    LOCK = "doorlock"
    NUMBER = "switchMultilevel"
    SWITCH = "switchBinary"
    SENSOR = "sensorMultilevel"
    SIREN = "siren"
    RGBW_LIGHT = "switchRGBW"
    RGB_LIGHT = "switchRGB"


PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CLIMATE,
    Platform.COVER,
    Platform.FAN,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SIREN,
    Platform.SWITCH,
]
