"""Constants for ZWaveMe."""

from homeassistant.const import Platform

# Base component constants
DOMAIN = "zwave_me"

ZWAVE_PLATFORMS = [
    "switchMultilevel",
    "binarySwitch"
]

PLATFORMS = [
    Platform.NUMBER,
    Platform.SWITCH
]
