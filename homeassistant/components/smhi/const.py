"""Constants in smhi component."""
import logging

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_CLOUDINESS = 'cloudiness'

DOMAIN = 'smhi'

HOME_LOCATION_NAME = 'Home'

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".smhi_{}"
ENTITY_ID_SENSOR_FORMAT_HOME = ENTITY_ID_SENSOR_FORMAT.format(
    HOME_LOCATION_NAME)

LOGGER = logging.getLogger(__package__)
