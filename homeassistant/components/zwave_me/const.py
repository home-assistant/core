"""Constants for ZWaveMe."""
# Base component constants
NAME = "Z-Wave-Me"
DOMAIN = "zwave_me"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ATTRIBUTION = "Z-Wave-Me"

ZWAVE_PLATFORMS = [
    "switchMultilevel",
]

PLATFORMS = [
    "number",
]

# Configuration and options
CONF_URL = "url"
CONF_TOKEN = "token"
