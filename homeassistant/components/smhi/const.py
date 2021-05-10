"""Constants in smhi component."""
from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_CLOUDINESS = "cloudiness"
ATTR_SMHI_WIND_GUST_SPEED = "wind_gust_speed"
ATTR_SMHI_THUNDER_PROBABILITY = "thunder_probability"

DOMAIN = "smhi"

HOME_LOCATION_NAME = "Home"

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".smhi_{}"
ENTITY_ID_SENSOR_FORMAT_HOME = ENTITY_ID_SENSOR_FORMAT.format(HOME_LOCATION_NAME)
