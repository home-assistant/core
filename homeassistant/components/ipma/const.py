"""Constants in ipma component."""
import logging

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_CLOUDINESS = 'cloudiness'

DOMAIN = 'ipma'

HOME_LOCATION_NAME = 'Home'

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".ipma_{}"
ENTITY_ID_SENSOR_FORMAT_HOME = ENTITY_ID_SENSOR_FORMAT.format(
    HOME_LOCATION_NAME)

LOGGER = logging.getLogger('homeassistant.components.ipma')
