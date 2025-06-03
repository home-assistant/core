"""OpenSky constants."""

import logging

from homeassistant.const import Platform

LOGGER = logging.getLogger(__package__)

PLATFORMS = [Platform.SENSOR]
DEFAULT_NAME = "OpenSky"
DOMAIN = "opensky"
MANUFACTURER = "OpenSky Network"
CONF_ALTITUDE = "altitude"
CONF_CONTRIBUTING_USER = "contributing_user"
ATTR_ICAO24 = "icao24"
ATTR_CALLSIGN = "callsign"
ATTR_ALTITUDE = "altitude"
ATTR_ON_GROUND = "on_ground"
ATTR_SENSOR = "sensor"
ATTR_STATES = "states"
DEFAULT_ALTITUDE = 0

EVENT_OPENSKY_ENTRY = f"{DOMAIN}_entry"
EVENT_OPENSKY_EXIT = f"{DOMAIN}_exit"
