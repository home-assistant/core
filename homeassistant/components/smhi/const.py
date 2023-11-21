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

# SOURCE: https://www.smhi.se/kunskapsbanken/meteorologi/vaderprognoser/vad-betyder-smhis-vadersymboler-1.12109
weather_icons = {
    "SUN": "https://www.smhi.se/polopoly_fs/1.27958.1518507527!/image/2.png_gen/derivatives/Original_259px/image/2.png",
    "CLOUD": "https://www.smhi.se/polopoly_fs/1.12114.1518507791!/image/6.png_gen/derivatives/Original_259px/image/6.png",
    "RAIN": "https://www.smhi.se/polopoly_fs/1.130680.1518509884!/image/20.png_gen/derivatives/Original_259px/image/20.png",
    "SNOWFLAKE": "https://www.smhi.se/polopoly_fs/1.130694.1518510246!/image/27.png_gen/derivatives/Original_259px/image/27.png",
}

# SOURCE: https://opendata.smhi.se/apidocs/metfcst/parameters.html#parameter-wsymb
weather_conditions = {
    "1": "Clear sky",
    "2": "Nearly clear sky",
    "3": "Variable cloudiness",
    "4": "Halfclear sky",
    "5": "Cloudy sky",
    "6": "Overcast",
    "7": "Fog",
    "8": "Light rain showers",
    "9": "Moderate rain showers",
    "10": "Heavy rain showers",
    "11": "Thunderstorm",
    "12": "Light sleet showers",
    "13": "Moderate sleet showers",
    "14": "Heavy sleet showers",
    "15": "Light snow showers",
    "16": "Moderate snow showers",
    "17": "Heavy snow showers",
    "18": "Light rain",
    "19": "Moderate rain",
    "20": "Heavy rain",
    "21": "Thunder",
    "22": "Light sleet",
    "23": "Moderate sleet",
    "24": "Heavy sleet",
    "25": "Light snowfall",
    "26": "Moderate snowfall",
    "27": "Heavy snowfall",
}
