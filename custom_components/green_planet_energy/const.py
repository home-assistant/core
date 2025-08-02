"""Constants for the Green Planet Energy integration."""

DOMAIN = "green_planet_energy"

# Config flow keys
CONF_API_URL = "api_url"

# Default values
DEFAULT_API_URL = "https://mein.green-planet-energy.de/p2"
DEFAULT_SCAN_INTERVAL = 60  # minutes

# API constants
API_METHOD = "getVerbrauchspreisUndWindsignal"
AGGREGATS_ZEITRAUM = ""
AGGREGATS_TYP = ""
SOURCE = "Portal"

# Sensor keys for each hour (9-18)
SENSOR_HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17, 18]
