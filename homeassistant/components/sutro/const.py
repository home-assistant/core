"""Constants for Sutro."""
# Base component constants
NAME = "Sutro"
DOMAIN = "sutro"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "0.0.1"

ATTRIBUTION = "Data provided by http://jsonplaceholder.typicode.com/"
ISSUE_URL = "https://github.com/ydogandjiev/hass-sutro/issues"

# Icons
ICON_ACIDITY = "mdi:ph"
ICON_ALKALINITY = "mdi:test-tube"
ICON_CHLORINE = "mdi:water-percent"
ICON_TEMPERATURE = "mdi:thermometer"
ICON_BATTERY = "mdi:battery"

# Platforms
SENSOR = "sensor"
PLATFORMS = [SENSOR]

# Configuration and options
CONF_TOKEN = "token"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
