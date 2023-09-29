"""OpenSky constants."""
from homeassistant.const import Platform

PLATFORMS = [Platform.SENSOR]
DEFAULT_NAME = "OpenSky"
DOMAIN = "opensky"
CLIENT = "client"

CONF_ALTITUDE = "altitude"
ATTR_ICAO24 = "icao24"
ATTR_CALLSIGN = "callsign"
ATTR_ALTITUDE = "altitude"
ATTR_ON_GROUND = "on_ground"
ATTR_SENSOR = "sensor"
ATTR_STATES = "states"
DEFAULT_ALTITUDE = 0

EVENT_OPENSKY_ENTRY = f"{DOMAIN}_entry"
EVENT_OPENSKY_EXIT = f"{DOMAIN}_exit"
