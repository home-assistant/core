"""Constants for ZWaveMe."""
# Base component constants
NAME = "Z-Wave-Me"
DOMAIN = "zwave_me"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"
ATTRIBUTION = "Z-Wave-Me"
ISSUE_URL = "https://github.com/Z-Wave-Me/ha-core/pulls"

ZWAVEPLATFORMS = [
    "switchMultilevel",
]

PLATFORMS = [
    "number",
]
# Device classes
BINARY_SENSOR_DEVICE_CLASS = "connectivity"

# Platforms
BINARY_SENSOR = "binary_sensor"
SENSOR = "sensor"
SWITCH = "switch"

# Configuration and options
CONF_ENABLED = "enabled"
CONF_URL = "url"
CONF_TOKEN = "token"

# Defaults
DEFAULT_NAME = DOMAIN


STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a ZWave-Me Integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
