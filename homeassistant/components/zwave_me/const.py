"""Constants for ZWaveMe."""

from homeassistant.const import Platform

# Base component constants
DOMAIN = "zwave_me"

ZWAVE_PLATFORMS = [
    "switchMultilevel",
    "binarySwitch",
    "toggleButton",
    "doorlock",
    "sensorMultilevel",
    "sensorBinary",
    "switchRGBW",
    "switchRGB",
]

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
