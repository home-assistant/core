"""Constant values for the AEMET OpenData component."""
from __future__ import annotations

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SUNNY,
)
from homeassistant.const import Platform

ATTRIBUTION = "Powered by AEMET OpenData"
CONF_STATION_UPDATES = "station_updates"
PLATFORMS = [Platform.SENSOR, Platform.WEATHER]
DEFAULT_NAME = "AEMET"
DOMAIN = "aemet"
ENTRY_NAME = "name"
ENTRY_WEATHER_COORDINATOR = "weather_coordinator"

ATTR_API_CONDITION = "condition"
ATTR_API_FORECAST_CONDITION = "condition"
ATTR_API_FORECAST_DAILY = "forecast-daily"
ATTR_API_FORECAST_HOURLY = "forecast-hourly"
ATTR_API_FORECAST_PRECIPITATION = "precipitation"
ATTR_API_FORECAST_PRECIPITATION_PROBABILITY = "precipitation_probability"
ATTR_API_FORECAST_TEMP = "temperature"
ATTR_API_FORECAST_TEMP_LOW = "templow"
ATTR_API_FORECAST_TIME = "datetime"
ATTR_API_FORECAST_WIND_BEARING = "wind_bearing"
ATTR_API_FORECAST_WIND_SPEED = "wind_speed"
ATTR_API_HUMIDITY = "humidity"
ATTR_API_PRESSURE = "pressure"
ATTR_API_RAIN = "rain"
ATTR_API_RAIN_PROB = "rain-probability"
ATTR_API_SNOW = "snow"
ATTR_API_SNOW_PROB = "snow-probability"
ATTR_API_STATION_ID = "station-id"
ATTR_API_STATION_NAME = "station-name"
ATTR_API_STATION_TIMESTAMP = "station-timestamp"
ATTR_API_STORM_PROB = "storm-probability"
ATTR_API_TEMPERATURE = "temperature"
ATTR_API_TEMPERATURE_FEELING = "temperature-feeling"
ATTR_API_TOWN_ID = "town-id"
ATTR_API_TOWN_NAME = "town-name"
ATTR_API_TOWN_TIMESTAMP = "town-timestamp"
ATTR_API_WIND_BEARING = "wind-bearing"
ATTR_API_WIND_MAX_SPEED = "wind-max-speed"
ATTR_API_WIND_SPEED = "wind-speed"

CONDITIONS_MAP = {
    ATTR_CONDITION_CLEAR_NIGHT: {
        "11n",  # Despejado (de noche)
    },
    ATTR_CONDITION_CLOUDY: {
        "14",  # Nuboso
        "14n",  # Nuboso (de noche)
        "15",  # Muy nuboso
        "15n",  # Muy nuboso (de noche)
        "16",  # Cubierto
        "16n",  # Cubierto (de noche)
        "17",  # Nubes altas
        "17n",  # Nubes altas (de noche)
    },
    ATTR_CONDITION_FOG: {
        "81",  # Niebla
        "81n",  # Niebla (de noche)
        "82",  # Bruma - Neblina
        "82n",  # Bruma - Neblina (de noche)
    },
    ATTR_CONDITION_LIGHTNING: {
        "51",  # Intervalos nubosos con tormenta
        "51n",  # Intervalos nubosos con tormenta (de noche)
        "52",  # Nuboso con tormenta
        "52n",  # Nuboso con tormenta (de noche)
        "53",  # Muy nuboso con tormenta
        "53n",  # Muy nuboso con tormenta (de noche)
        "54",  # Cubierto con tormenta
        "54n",  # Cubierto con tormenta (de noche)
    },
    ATTR_CONDITION_LIGHTNING_RAINY: {
        "61",  # Intervalos nubosos con tormenta y lluvia escasa
        "61n",  # Intervalos nubosos con tormenta y lluvia escasa (de noche)
        "62",  # Nuboso con tormenta y lluvia escasa
        "62n",  # Nuboso con tormenta y lluvia escasa (de noche)
        "63",  # Muy nuboso con tormenta y lluvia escasa
        "63n",  # Muy nuboso con tormenta y lluvia escasa (de noche)
        "64",  # Cubierto con tormenta y lluvia escasa
        "64n",  # Cubierto con tormenta y lluvia escasa (de noche)
    },
    ATTR_CONDITION_PARTLYCLOUDY: {
        "12",  # Poco nuboso
        "12n",  # Poco nuboso (de noche)
        "13",  # Intervalos nubosos
        "13n",  # Intervalos nubosos (de noche)
    },
    ATTR_CONDITION_POURING: {
        "27",  # Chubascos
        "27n",  # Chubascos (de noche)
    },
    ATTR_CONDITION_RAINY: {
        "23",  # Intervalos nubosos con lluvia
        "23n",  # Intervalos nubosos con lluvia (de noche)
        "24",  # Nuboso con lluvia
        "24n",  # Nuboso con lluvia (de noche)
        "25",  # Muy nuboso con lluvia
        "25n",  # Muy nuboso con lluvia (de noche)
        "26",  # Cubierto con lluvia
        "26n",  # Cubierto con lluvia (de noche)
        "43",  # Intervalos nubosos con lluvia escasa
        "43n",  # Intervalos nubosos con lluvia escasa (de noche)
        "44",  # Nuboso con lluvia escasa
        "44n",  # Nuboso con lluvia escasa (de noche)
        "45",  # Muy nuboso con lluvia escasa
        "45n",  # Muy nuboso con lluvia escasa (de noche)
        "46",  # Cubierto con lluvia escasa
        "46n",  # Cubierto con lluvia escasa (de noche)
    },
    ATTR_CONDITION_SNOWY: {
        "33",  # Intervalos nubosos con nieve
        "33n",  # Intervalos nubosos con nieve (de noche)
        "34",  # Nuboso con nieve
        "34n",  # Nuboso con nieve (de noche)
        "35",  # Muy nuboso con nieve
        "35n",  # Muy nuboso con nieve (de noche)
        "36",  # Cubierto con nieve
        "36n",  # Cubierto con nieve (de noche)
        "71",  # Intervalos nubosos con nieve escasa
        "71n",  # Intervalos nubosos con nieve escasa (de noche)
        "72",  # Nuboso con nieve escasa
        "72n",  # Nuboso con nieve escasa (de noche)
        "73",  # Muy nuboso con nieve escasa
        "73n",  # Muy nuboso con nieve escasa (de noche)
        "74",  # Cubierto con nieve escasa
        "74n",  # Cubierto con nieve escasa (de noche)
    },
    ATTR_CONDITION_SUNNY: {
        "11",  # Despejado
    },
}

FORECAST_MONITORED_CONDITIONS = [
    ATTR_API_FORECAST_CONDITION,
    ATTR_API_FORECAST_PRECIPITATION,
    ATTR_API_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_API_FORECAST_TEMP,
    ATTR_API_FORECAST_TEMP_LOW,
    ATTR_API_FORECAST_TIME,
    ATTR_API_FORECAST_WIND_BEARING,
    ATTR_API_FORECAST_WIND_SPEED,
]
MONITORED_CONDITIONS = [
    ATTR_API_CONDITION,
    ATTR_API_HUMIDITY,
    ATTR_API_PRESSURE,
    ATTR_API_RAIN,
    ATTR_API_RAIN_PROB,
    ATTR_API_SNOW,
    ATTR_API_SNOW_PROB,
    ATTR_API_STATION_ID,
    ATTR_API_STATION_NAME,
    ATTR_API_STATION_TIMESTAMP,
    ATTR_API_STORM_PROB,
    ATTR_API_TEMPERATURE,
    ATTR_API_TEMPERATURE_FEELING,
    ATTR_API_TOWN_ID,
    ATTR_API_TOWN_NAME,
    ATTR_API_TOWN_TIMESTAMP,
    ATTR_API_WIND_BEARING,
    ATTR_API_WIND_MAX_SPEED,
    ATTR_API_WIND_SPEED,
]

FORECAST_MODE_DAILY = "daily"
FORECAST_MODE_HOURLY = "hourly"
FORECAST_MODES = [
    FORECAST_MODE_DAILY,
    FORECAST_MODE_HOURLY,
]
FORECAST_MODE_ATTR_API = {
    FORECAST_MODE_DAILY: ATTR_API_FORECAST_DAILY,
    FORECAST_MODE_HOURLY: ATTR_API_FORECAST_HOURLY,
}


WIND_BEARING_MAP = {
    "C": None,
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SO": 225.0,
    "O": 270.0,
    "NO": 315.0,
}
