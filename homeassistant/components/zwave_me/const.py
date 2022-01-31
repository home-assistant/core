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
]

PLATFORMS = [
    Platform.BUTTON,
    Platform.LOCK,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]
