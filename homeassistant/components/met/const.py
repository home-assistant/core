"""Constants for Met component."""
import logging

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

DOMAIN = "met"

HOME_LOCATION_NAME = "Home"

CONF_TRACK_HOME = "track_home"

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".met_{}"
ENTITY_ID_SENSOR_FORMAT_HOME = ENTITY_ID_SENSOR_FORMAT.format(HOME_LOCATION_NAME)

_LOGGER = logging.getLogger(".")
