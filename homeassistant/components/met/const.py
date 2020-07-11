"""Constants for Met component."""
import logging

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

DOMAIN = "met"

HOME_LOCATION_NAME = "Home"

CONF_TRACK_HOME = "track_home"

ENTITY_ID_SENSOR_FORMAT_HOME = f"{WEATHER_DOMAIN}.met_{HOME_LOCATION_NAME}"

_LOGGER = logging.getLogger(".")
