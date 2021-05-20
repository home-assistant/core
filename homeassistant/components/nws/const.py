"""Constants for National Weather Service Integration."""
from datetime import timedelta

from homeassistant.components.weather import (
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    LENGTH_METERS,
    LENGTH_MILES,
    PERCENTAGE,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
)

DOMAIN = "nws"

CONF_STATION = "station"

ATTRIBUTION = "Data from National Weather Service/NOAA"

ATTR_FORECAST_DETAILED_DESCRIPTION = "detailed_description"
ATTR_FORECAST_DAYTIME = "daytime"
ATTR_ICON = "icon"
ATTR_LABEL = "label"
ATTR_UNIT = "unit"
ATTR_UNIT_CONVERT = "unit_convert"
ATTR_UNIT_CONVERT_METHOD = "unit_convert_method"

CONDITION_CLASSES = {
    ATTR_CONDITION_EXCEPTIONAL: [
        "Tornado",
        "Hurricane conditions",
        "Tropical storm conditions",
        "Dust",
        "Smoke",
        "Haze",
        "Hot",
        "Cold",
    ],
    ATTR_CONDITION_SNOWY: ["Snow", "Sleet", "Snow/sleet", "Blizzard"],
    ATTR_CONDITION_SNOWY_RAINY: [
        "Rain/snow",
        "Rain/sleet",
        "Freezing rain/snow",
        "Freezing rain",
        "Rain/freezing rain",
    ],
    ATTR_CONDITION_HAIL: [],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Thunderstorm (high cloud cover)",
        "Thunderstorm (medium cloud cover)",
        "Thunderstorm (low cloud cover)",
    ],
    ATTR_CONDITION_LIGHTNING: [],
    ATTR_CONDITION_POURING: [],
    ATTR_CONDITION_RAINY: [
        "Rain",
        "Rain showers (high cloud cover)",
        "Rain showers (low cloud cover)",
    ],
    ATTR_CONDITION_WINDY_VARIANT: ["Mostly cloudy and windy", "Overcast and windy"],
    ATTR_CONDITION_WINDY: [
        "Fair/clear and windy",
        "A few clouds and windy",
        "Partly cloudy and windy",
    ],
    ATTR_CONDITION_FOG: ["Fog/mist"],
    "clear": ["Fair/clear"],  # sunny and clear-night
    ATTR_CONDITION_CLOUDY: ["Mostly cloudy", "Overcast"],
    ATTR_CONDITION_PARTLYCLOUDY: ["A few clouds", "Partly cloudy"],
}

DAYNIGHT = "daynight"
HOURLY = "hourly"

NWS_DATA = "nws data"
COORDINATOR_OBSERVATION = "coordinator_observation"
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_FORECAST_HOURLY = "coordinator_forecast_hourly"

OBSERVATION_VALID_TIME = timedelta(minutes=20)
FORECAST_VALID_TIME = timedelta(minutes=45)

SENSOR_TYPES = {
    "dewpoint": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Dew Point",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_UNIT_CONVERT: TEMP_CELSIUS,
    },
    "temperature": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Temperature",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_UNIT_CONVERT: TEMP_CELSIUS,
    },
    "windChill": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Wind Chill",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_UNIT_CONVERT: TEMP_CELSIUS,
    },
    "heatIndex": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Heat Index",
        ATTR_UNIT: TEMP_CELSIUS,
        ATTR_UNIT_CONVERT: TEMP_CELSIUS,
    },
    "relativeHumidity": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
        ATTR_ICON: None,
        ATTR_LABEL: "Relative Humidity",
        ATTR_UNIT: PERCENTAGE,
        ATTR_UNIT_CONVERT: PERCENTAGE,
    },
    "windSpeed": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Speed",
        ATTR_UNIT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_CONVERT: SPEED_MILES_PER_HOUR,
    },
    "windGust": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:weather-windy",
        ATTR_LABEL: "Wind Gust",
        ATTR_UNIT: SPEED_KILOMETERS_PER_HOUR,
        ATTR_UNIT_CONVERT: SPEED_MILES_PER_HOUR,
    },
    "windDirection": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:compass-rose",
        ATTR_LABEL: "Wind Direction",
        ATTR_UNIT: DEGREE,
        ATTR_UNIT_CONVERT: DEGREE,
    },
    "barometricPressure": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Barometric Pressure",
        ATTR_UNIT: PRESSURE_PA,
        ATTR_UNIT_CONVERT: PRESSURE_INHG,
    },
    "seaLevelPressure": {
        ATTR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ATTR_ICON: None,
        ATTR_LABEL: "Sea Level Pressure",
        ATTR_UNIT: PRESSURE_PA,
        ATTR_UNIT_CONVERT: PRESSURE_INHG,
    },
    "visibility": {
        ATTR_DEVICE_CLASS: None,
        ATTR_ICON: "mdi:eye",
        ATTR_LABEL: "Visibility",
        ATTR_UNIT: LENGTH_METERS,
        ATTR_UNIT_CONVERT: LENGTH_MILES,
    },
}
