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

