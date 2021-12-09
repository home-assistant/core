"""Constants for ZWaveMe."""

from homeassistant.const import Platform
# Base component constants
DOMAIN = "zwave_me"

ZWAVE_PLATFORMS = [
    "switchMultilevel",
]

PLATFORMS = [
    Platform.NUMBER,
]

# Configuration and options
CONF_URL = "url"
CONF_TOKEN = "token"
