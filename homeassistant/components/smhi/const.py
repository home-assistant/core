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

# SOURCES
# SUN: https://www.flaticon.com/free-icon/sun_6974833
# CLOUD: https://www.flaticon.com/free-icon/cloud-computing_3208676
# RAIN: https://uxwing.com/water-droplet-icon/
# SNOWFLAKE: https://uxwing.com/snowflake-color-icon/
weather_icons = {
    "SUN": "https://cdn-icons-png.flaticon.com/512/6974/6974833.png",
    "CLOUD": "https://cdn-icons-png.flaticon.com/512/3208/3208676.png",
    "RAIN": "https://uxwing.com/wp-content/themes/uxwing/download/weather/water-droplet-icon.png",
    "SNOWFLAKE": "https://uxwing.com/wp-content/themes/uxwing/download/weather/snowflake-color-icon.png",
}
