"""Meteo-France component constants."""

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
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
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)
from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    LENGTH_MILLIMETERS,
    PERCENTAGE,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)

DOMAIN = "meteo_france"
PLATFORMS = ["sensor", "weather"]
COORDINATOR_FORECAST = "coordinator_forecast"
COORDINATOR_RAIN = "coordinator_rain"
COORDINATOR_ALERT = "coordinator_alert"
UNDO_UPDATE_LISTENER = "undo_update_listener"
ATTRIBUTION = "Data provided by Météo-France"

CONF_CITY = "city"
FORECAST_MODE_HOURLY = "hourly"
FORECAST_MODE_DAILY = "daily"
FORECAST_MODE = [FORECAST_MODE_HOURLY, FORECAST_MODE_DAILY]

ATTR_NEXT_RAIN_1_HOUR_FORECAST = "1_hour_forecast"
ATTR_NEXT_RAIN_DT_REF = "forecast_time_ref"

ENTITY_NAME = "name"
ENTITY_UNIT = "unit"
ENTITY_ICON = "icon"
ENTITY_DEVICE_CLASS = "device_class"
ENTITY_ENABLE = "enable"
ENTITY_API_DATA_PATH = "data_path"

SENSOR_TYPES = {
    "pressure": {
        ENTITY_NAME: "Pressure",
        ENTITY_UNIT: PRESSURE_HPA,
        ENTITY_ICON: None,
        ENTITY_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
        ENTITY_ENABLE: False,
        ENTITY_API_DATA_PATH: "current_forecast:sea_level",
    },
    "rain_chance": {
        ENTITY_NAME: "Rain chance",
        ENTITY_UNIT: PERCENTAGE,
        ENTITY_ICON: "mdi:weather-rainy",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "probability_forecast:rain:3h",
    },
    "snow_chance": {
        ENTITY_NAME: "Snow chance",
        ENTITY_UNIT: PERCENTAGE,
        ENTITY_ICON: "mdi:weather-snowy",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "probability_forecast:snow:3h",
    },
    "freeze_chance": {
        ENTITY_NAME: "Freeze chance",
        ENTITY_UNIT: PERCENTAGE,
        ENTITY_ICON: "mdi:snowflake",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "probability_forecast:freezing",
    },
    "wind_speed": {
        ENTITY_NAME: "Wind speed",
        ENTITY_UNIT: SPEED_KILOMETERS_PER_HOUR,
        ENTITY_ICON: "mdi:weather-windy",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: False,
        ENTITY_API_DATA_PATH: "current_forecast:wind:speed",
    },
    "next_rain": {
        ENTITY_NAME: "Next rain",
        ENTITY_UNIT: None,
        ENTITY_ICON: None,
        ENTITY_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: None,
    },
    "temperature": {
        ENTITY_NAME: "Temperature",
        ENTITY_UNIT: TEMP_CELSIUS,
        ENTITY_ICON: None,
        ENTITY_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
        ENTITY_ENABLE: False,
        ENTITY_API_DATA_PATH: "current_forecast:T:value",
    },
    "uv": {
        ENTITY_NAME: "UV",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:sunglasses",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "today_forecast:uv",
    },
    "weather_alert": {
        ENTITY_NAME: "Weather alert",
        ENTITY_UNIT: None,
        ENTITY_ICON: "mdi:weather-cloudy-alert",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: None,
    },
    "precipitation": {
        ENTITY_NAME: "Daily precipitation",
        ENTITY_UNIT: LENGTH_MILLIMETERS,
        ENTITY_ICON: "mdi:cup-water",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "today_forecast:precipitation:24h",
    },
    "cloud": {
        ENTITY_NAME: "Cloud cover",
        ENTITY_UNIT: PERCENTAGE,
        ENTITY_ICON: "mdi:weather-partly-cloudy",
        ENTITY_DEVICE_CLASS: None,
        ENTITY_ENABLE: True,
        ENTITY_API_DATA_PATH: "current_forecast:clouds",
    },
}

CONDITION_CLASSES = {
    ATTR_CONDITION_CLEAR_NIGHT: ["Nuit Claire", "Nuit claire"],
    ATTR_CONDITION_CLOUDY: ["Très nuageux", "Couvert"],
    ATTR_CONDITION_FOG: [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
        "Bancs de Brouillard",
    ],
    ATTR_CONDITION_HAIL: ["Risque de grêle", "Risque de grèle"],
    ATTR_CONDITION_LIGHTNING: ["Risque d'orages", "Orages"],
    ATTR_CONDITION_LIGHTNING_RAINY: [
        "Pluie orageuses",
        "Pluies orageuses",
        "Averses orageuses",
    ],
    ATTR_CONDITION_PARTLYCLOUDY: [
        "Ciel voilé",
        "Ciel voilé nuit",
        "Éclaircies",
        "Eclaircies",
        "Peu nuageux",
    ],
    ATTR_CONDITION_POURING: ["Pluie forte"],
    ATTR_CONDITION_RAINY: [
        "Bruine / Pluie faible",
        "Bruine",
        "Pluie faible",
        "Pluies éparses / Rares averses",
        "Pluies éparses",
        "Rares averses",
        "Pluie modérée",
        "Pluie / Averses",
        "Averses",
        "Pluie",
    ],
    ATTR_CONDITION_SNOWY: [
        "Neige / Averses de neige",
        "Neige",
        "Averses de neige",
        "Neige forte",
        "Quelques flocons",
    ],
    ATTR_CONDITION_SNOWY_RAINY: ["Pluie et neige", "Pluie verglaçante"],
    ATTR_CONDITION_SUNNY: ["Ensoleillé"],
    ATTR_CONDITION_WINDY: [],
    ATTR_CONDITION_WINDY_VARIANT: [],
    ATTR_CONDITION_EXCEPTIONAL: [],
}
