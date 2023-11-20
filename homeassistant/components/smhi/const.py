"""Constants in smhi component."""
from typing import Final

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTR_SMHI_THUNDER_PROBABILITY: Final = "thunder_probability"

DOMAIN = "smhi"

HOME_LOCATION_NAME = "Home"
DEFAULT_NAME = "Weather"

ENTITY_ID_SENSOR_FORMAT = WEATHER_DOMAIN + ".smhi_{}"


smhi_warning_icons = {
    "YELLOW": "https://opendata.smhi.se/apidocs/IBWwarnings/res/yellow-weather-warning-56x56.png",
    "ORANGE": "https://opendata.smhi.se/apidocs/IBWwarnings/res/orange-weather-warning-56x56.png",
    "RED": "https://opendata.smhi.se/apidocs/IBWwarnings/res/red-weather-warning-56x56.png",
}
