"""Constants in smhi component."""
from typing import Final

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_CLOUDINESS: Final = "cloudiness"
ATTR_SMHI_WIND_GUST_SPEED: Final = "wind_gust_speed"
ATTR_SMHI_THUNDER_PROBABILITY: Final = "thunder_probability"

DOMAIN = "smhi"

HOME_LOCATION_NAME = "Home"

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".smhi_{}"
