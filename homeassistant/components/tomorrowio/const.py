"""Constants for the Tomorrow.io integration."""

from __future__ import annotations

from enum import StrEnum
import logging

from pytomorrowio.const import DAILY, HOURLY, NOWCAST, WeatherCode

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
)

LOGGER = logging.getLogger(__package__)

CONF_TIMESTEP = "timestep"
FORECAST_TYPES = [DAILY, HOURLY, NOWCAST]

DEFAULT_TIMESTEP = 60
DEFAULT_FORECAST_TYPE = DAILY
DOMAIN = "tomorrowio"
INTEGRATION_NAME = "Tomorrow.io"
DEFAULT_NAME = INTEGRATION_NAME
ATTRIBUTION = "Powered by Tomorrow.io"

MAX_REQUESTS_PER_DAY = 100

CLEAR_CONDITIONS = {"night": ATTR_CONDITION_CLEAR_NIGHT, "day": ATTR_CONDITION_SUNNY}

MAX_FORECASTS = {
    DAILY: 14,
    HOURLY: 24,
    NOWCAST: 30,
}

# Additional attributes
ATTR_WIND_GUST = "wind_gust"
ATTR_CLOUD_COVER = "cloud_cover"
ATTR_PRECIPITATION_TYPE = "precipitation_type"

# V4 constants
CONDITIONS = {
    WeatherCode.WIND: ATTR_CONDITION_WINDY,
    WeatherCode.LIGHT_WIND: ATTR_CONDITION_WINDY,
    WeatherCode.STRONG_WIND: ATTR_CONDITION_WINDY,
    WeatherCode.FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.HEAVY_FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.LIGHT_FREEZING_RAIN: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.FREEZING_DRIZZLE: ATTR_CONDITION_SNOWY_RAINY,
    WeatherCode.ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.HEAVY_ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.LIGHT_ICE_PELLETS: ATTR_CONDITION_HAIL,
    WeatherCode.SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.HEAVY_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.LIGHT_SNOW: ATTR_CONDITION_SNOWY,
    WeatherCode.FLURRIES: ATTR_CONDITION_SNOWY,
    WeatherCode.THUNDERSTORM: ATTR_CONDITION_LIGHTNING_RAINY,
    WeatherCode.HEAVY_RAIN: ATTR_CONDITION_POURING,
    WeatherCode.RAIN: ATTR_CONDITION_RAINY,
    WeatherCode.LIGHT_RAIN: ATTR_CONDITION_RAINY,
    WeatherCode.DRIZZLE: ATTR_CONDITION_RAINY,
    WeatherCode.FOG: ATTR_CONDITION_FOG,
    WeatherCode.LIGHT_FOG: ATTR_CONDITION_FOG,
    WeatherCode.CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCode.MOSTLY_CLOUDY: ATTR_CONDITION_CLOUDY,
    WeatherCode.PARTLY_CLOUDY: ATTR_CONDITION_PARTLYCLOUDY,
}


# This should be in pytomorrowio
class TomorrowioAttr(StrEnum):
    """Weather attributes."""

    # Weather constants
    TIMESTAMP = "startTime"
    TEMPERATURE = "temperature"
    TEMPERATURE_HIGH = "temperatureMax"
    TEMPERATURE_LOW = "temperatureMin"
    PRESSURE = "pressureSeaLevel"
    HUMIDITY = "humidity"
    WIND_SPEED = "windSpeed"
    WIND_DIRECTION = "windDirection"
    OZONE = "pollutantO3"
    CONDITION = "weatherCode"
    VISIBILITY = "visibility"
    PRECIPITATION = "precipitationIntensityAvg"
    PRECIPITATION_PROBABILITY = "precipitationProbability"
    WIND_GUST = "windGust"
    CLOUD_COVER = "cloudCover"
    PRECIPITATION_TYPE = "precipitationType"

    # Sensor attributes
    PARTICULATE_MATTER_25 = "particulateMatter25"
    PARTICULATE_MATTER_10 = "particulateMatter10"
    NITROGEN_DIOXIDE = "pollutantNO2"
    CARBON_MONOXIDE = "pollutantCO"
    SULPHUR_DIOXIDE = "pollutantSO2"
    EPA_AQI = "epaIndex"
    EPA_PRIMARY_POLLUTANT = "epaPrimaryPollutant"
    EPA_HEALTH_CONCERN = "epaHealthConcern"
    CHINA_AQI = "mepIndex"
    CHINA_PRIMARY_POLLUTANT = "mepPrimaryPollutant"
    CHINA_HEALTH_CONCERN = "mepHealthConcern"
    POLLEN_TREE = "treeIndex"
    POLLEN_WEED = "weedIndex"
    POLLEN_GRASS = "grassIndex"
    FIRE_INDEX = "fireIndex"
    FEELS_LIKE = "temperatureApparent"
    DEW_POINT = "dewPoint"
    PRESSURE_SURFACE_LEVEL = "pressureSurfaceLevel"
    SOLAR_GHI = "solarGHI"
    CLOUD_BASE = "cloudBase"
    CLOUD_CEILING = "cloudCeiling"
    UV_INDEX = "uvIndex"
    UV_HEALTH_CONCERN = "uvHealthConcern"
