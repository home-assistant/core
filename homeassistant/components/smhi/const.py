"""Constants in smhi component."""

from datetime import timedelta
import logging
from typing import Final

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_THUNDER_PROBABILITY: Final = "thunder_probability"

DOMAIN = "smhi"

HOME_LOCATION_NAME = "Home"
DEFAULT_NAME = "Weather"

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".smhi_{}"

LOGGER = logging.getLogger(__package__)

DEFAULT_SCAN_INTERVAL = timedelta(minutes=31)
TIMEOUT = 10
