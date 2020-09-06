"""Meteo-France component constants."""

from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
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
        ENTITY_UNIT: "mm",
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
    "clear-night": ["Nuit Claire", "Nuit claire"],
    "cloudy": ["Très nuageux", "Couvert"],
    "fog": [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
    ],
    "hail": ["Risque de grêle", "Risque de grèle"],
    "lightning": ["Risque d'orages", "Orages"],
    "lightning-rainy": ["Pluie orageuses", "Pluies orageuses", "Averses orageuses"],
    "partlycloudy": [
        "Ciel voilé",
        "Ciel voilé nuit",
        "Éclaircies",
        "Eclaircies",
        "Peu nuageux",
    ],
    "pouring": ["Pluie forte"],
    "rainy": [
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
    "snowy": [
        "Neige / Averses de neige",
        "Neige",
        "Averses de neige",
        "Neige forte",
        "Quelques flocons",
    ],
    "snowy-rainy": ["Pluie et neige", "Pluie verglaçante"],
    "sunny": ["Ensoleillé"],
    "windy": [],
    "windy-variant": [],
    "exceptional": [],
}
