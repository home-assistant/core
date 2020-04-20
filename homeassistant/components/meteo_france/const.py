"""Meteo-France component constants."""

from homeassistant.const import (
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
    TIME_MINUTES,
    UNIT_PERCENTAGE,
)

DOMAIN = "meteo_france"
PLATFORMS = ["sensor", "weather"]
ATTRIBUTION = "Data provided by Météo-France"

CONF_CITY = "city"

DEFAULT_WEATHER_CARD = True

SENSOR_TYPE_NAME = "name"
SENSOR_TYPE_UNIT = "unit"
SENSOR_TYPE_ICON = "icon"
SENSOR_TYPE_CLASS = "device_class"
SENSOR_TYPES = {
    "rain_chance": {
        SENSOR_TYPE_NAME: "Rain chance",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:weather-rainy",
        SENSOR_TYPE_CLASS: None,
    },
    "freeze_chance": {
        SENSOR_TYPE_NAME: "Freeze chance",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:snowflake",
        SENSOR_TYPE_CLASS: None,
    },
    "thunder_chance": {
        SENSOR_TYPE_NAME: "Thunder chance",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:weather-lightning",
        SENSOR_TYPE_CLASS: None,
    },
    "snow_chance": {
        SENSOR_TYPE_NAME: "Snow chance",
        SENSOR_TYPE_UNIT: UNIT_PERCENTAGE,
        SENSOR_TYPE_ICON: "mdi:weather-snowy",
        SENSOR_TYPE_CLASS: None,
    },
    "weather": {
        SENSOR_TYPE_NAME: "Weather",
        SENSOR_TYPE_UNIT: None,
        SENSOR_TYPE_ICON: "mdi:weather-partly-cloudy",
        SENSOR_TYPE_CLASS: None,
    },
    "wind_speed": {
        SENSOR_TYPE_NAME: "Wind Speed",
        SENSOR_TYPE_UNIT: SPEED_KILOMETERS_PER_HOUR,
        SENSOR_TYPE_ICON: "mdi:weather-windy",
        SENSOR_TYPE_CLASS: None,
    },
    "next_rain": {
        SENSOR_TYPE_NAME: "Next rain",
        SENSOR_TYPE_UNIT: TIME_MINUTES,
        SENSOR_TYPE_ICON: "mdi:weather-rainy",
        SENSOR_TYPE_CLASS: None,
    },
    "temperature": {
        SENSOR_TYPE_NAME: "Temperature",
        SENSOR_TYPE_UNIT: TEMP_CELSIUS,
        SENSOR_TYPE_ICON: "mdi:thermometer",
        SENSOR_TYPE_CLASS: "temperature",
    },
    "uv": {
        SENSOR_TYPE_NAME: "UV",
        SENSOR_TYPE_UNIT: None,
        SENSOR_TYPE_ICON: "mdi:sunglasses",
        SENSOR_TYPE_CLASS: None,
    },
    "weather_alert": {
        SENSOR_TYPE_NAME: "Weather Alert",
        SENSOR_TYPE_UNIT: None,
        SENSOR_TYPE_ICON: "mdi:weather-cloudy-alert",
        SENSOR_TYPE_CLASS: None,
    },
}

CONDITION_CLASSES = {
    "clear-night": ["Nuit Claire", "Nuit claire"],
    "cloudy": ["Très nuageux"],
    "fog": [
        "Brume ou bancs de brouillard",
        "Brume",
        "Brouillard",
        "Brouillard givrant",
    ],
    "hail": ["Risque de grêle"],
    "lightning": ["Risque d'orages", "Orages"],
    "lightning-rainy": ["Pluie orageuses", "Pluies orageuses", "Averses orageuses"],
    "partlycloudy": ["Ciel voilé", "Ciel voilé nuit", "Éclaircies"],
    "pouring": ["Pluie forte"],
    "rainy": [
        "Bruine / Pluie faible",
        "Bruine",
        "Pluie faible",
        "Pluies éparses / Rares averses",
        "Pluies éparses",
        "Rares averses",
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
