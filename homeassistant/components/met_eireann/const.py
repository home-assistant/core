"""Constants for Met component."""
import logging

from homeassistant.components.weather import DOMAIN as WEATHER_DOMAIN

ATTRIBUTION = "Data provided by Met Éireann"

DEFAULT_NAME = "Met Éireann"

DOMAIN = "met_eireann"

HOME_LOCATION_NAME = "Home"

CONF_TRACK_HOME = "track_home"

ENTITY_ID_SENSOR_FORMAT_HOME = f"{WEATHER_DOMAIN}.met_eireann_{HOME_LOCATION_NAME}"

_LOGGER = logging.getLogger(".")

CONDITION_MAP = {
    "clear-night": ["Dark_Sun"],
    "cloudy": ["Cloud"],
    "fog": ["Fog"],
    "lightning-rainy": [
        "LightRainThunderSun",
        "LightRainThunderSun",
        "RainThunder",
        "SnowThunder",
        "SleetSunThunder",
        "Dark_SleetSunThunder",
        "SnowSunThunder",
        "Dark_SnowSunThunder",
        "LightRainThunder",
        "SleetThunder",
        "DrizzleThunderSun",
        "Dark_DrizzleThunderSun",
        "RainThunderSun",
        "Dark_RainThunderSun",
        "LightSleetThunderSun",
        "Dark_LightSleetThunderSun",
        "HeavySleetThunderSun",
        "Dark_HeavySleetThunderSun",
        "LightSnowThunderSun",
        "Dark_LightSnowThunderSun",
        "HeavySnowThunderSun",
        "Dark_HeavySnowThunderSun",
        "DrizzleThunder",
        "LightSleetThunder",
        "HeavySleetThunder",
        "LightSnowThunder",
        "HeavySnowThunder",
    ],
    "partlycloudy": [
        "LightCloud",
        "Dark_LightCloud",
        "PartlyCloud",
        "Dark_PartlyCloud",
    ],
    "rainy": [
        "LightRainSun",
        "Dark_LightRainSun",
        "LightRain",
        "Rain",
        "DrizzleSun",
        "Dark_DrizzleSun",
        "RainSun",
        "Dark_RainSun",
        "Drizzle",
    ],
    "snowy": [
        "SnowSun",
        "Dark_SnowSun",
        "Snow",
        "LightSnowSun",
        "Dark_LightSnowSun",
        "HeavySnowSun",
        "Dark_HeavySnowSun",
        "LightSnow",
        "HeavySnow",
    ],
    "snowy-rainy": [
        "SleetSun",
        "Dark_SleetSun",
        "Sleet",
        "LightSleetSun",
        "Dark_LightSleetSun",
        "HeavySleetSun",
        "Dark_HeavySleetSun",
        "LightSleet",
        "HeavySleet",
    ],
    "sunny": "Sun",
}
