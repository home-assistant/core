"""Constant values for the AEMET OpenData component."""

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
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
)
from homeassistant.const import (
    DEGREE,
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    PERCENTAGE,
    PRECIPITATION_MILLIMETERS_PER_HOUR,
    PRESSURE_HPA,
    SPEED_KILOMETERS_PER_HOUR,
    TEMP_CELSIUS,
)

ATTRIBUTION = "Powered by AEMET OpenData"
COMPONENTS = ["sensor", "weather"]
DEFAULT_NAME = "AEMET"
DOMAIN = "aemet"
ENTRY_NAME = "name"
ENTRY_WEATHER_COORDINATOR = "weather_coordinator"
UPDATE_LISTENER = "update_listener"
SENSOR_NAME = "sensor_name"
SENSOR_UNIT = "sensor_unit"
SENSOR_DEVICE_CLASS = "sensor_device_class"

ATTR_API_CONDITION = "condition"
ATTR_API_FORECAST_DAILY = "forecast-daily"
ATTR_API_FORECAST_HOURLY = "forecast-hourly"
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
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
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

FORECAST_SENSOR_TYPES = {
    ATTR_FORECAST_CONDITION: {
        SENSOR_NAME: "Condition",
    },
    ATTR_FORECAST_PRECIPITATION: {
        SENSOR_NAME: "Precipitation",
        SENSOR_UNIT: PRECIPITATION_MILLIMETERS_PER_HOUR,
    },
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: {
        SENSOR_NAME: "Precipitation probability",
        SENSOR_UNIT: PERCENTAGE,
    },
    ATTR_FORECAST_TEMP: {
        SENSOR_NAME: "Temperature",
        SENSOR_UNIT: TEMP_CELSIUS,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    ATTR_FORECAST_TEMP_LOW: {
        SENSOR_NAME: "Temperature Low",
        SENSOR_UNIT: TEMP_CELSIUS,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    ATTR_FORECAST_TIME: {
        SENSOR_NAME: "Time",
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
    ATTR_FORECAST_WIND_BEARING: {
        SENSOR_NAME: "Wind bearing",
        SENSOR_UNIT: DEGREE,
    },
    ATTR_FORECAST_WIND_SPEED: {
        SENSOR_NAME: "Wind speed",
        SENSOR_UNIT: SPEED_KILOMETERS_PER_HOUR,
    },
}
WEATHER_SENSOR_TYPES = {
    ATTR_API_CONDITION: {
        SENSOR_NAME: "Condition",
    },
    ATTR_API_HUMIDITY: {
        SENSOR_NAME: "Humidity",
        SENSOR_UNIT: PERCENTAGE,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_HUMIDITY,
    },
    ATTR_API_PRESSURE: {
        SENSOR_NAME: "Pressure",
        SENSOR_UNIT: PRESSURE_HPA,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_PRESSURE,
    },
    ATTR_API_RAIN: {
        SENSOR_NAME: "Rain",
        SENSOR_UNIT: PRECIPITATION_MILLIMETERS_PER_HOUR,
    },
    ATTR_API_RAIN_PROB: {
        SENSOR_NAME: "Rain probability",
        SENSOR_UNIT: PERCENTAGE,
    },
    ATTR_API_SNOW: {
        SENSOR_NAME: "Snow",
        SENSOR_UNIT: PRECIPITATION_MILLIMETERS_PER_HOUR,
    },
    ATTR_API_SNOW_PROB: {
        SENSOR_NAME: "Snow probability",
        SENSOR_UNIT: PERCENTAGE,
    },
    ATTR_API_STATION_ID: {
        SENSOR_NAME: "Station ID",
    },
    ATTR_API_STATION_NAME: {
        SENSOR_NAME: "Station name",
    },
    ATTR_API_STATION_TIMESTAMP: {
        SENSOR_NAME: "Station timestamp",
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
    ATTR_API_STORM_PROB: {
        SENSOR_NAME: "Storm probability",
        SENSOR_UNIT: PERCENTAGE,
    },
    ATTR_API_TEMPERATURE: {
        SENSOR_NAME: "Temperature",
        SENSOR_UNIT: TEMP_CELSIUS,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    ATTR_API_TEMPERATURE_FEELING: {
        SENSOR_NAME: "Temperature feeling",
        SENSOR_UNIT: TEMP_CELSIUS,
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TEMPERATURE,
    },
    ATTR_API_TOWN_ID: {
        SENSOR_NAME: "Town ID",
    },
    ATTR_API_TOWN_NAME: {
        SENSOR_NAME: "Town name",
    },
    ATTR_API_TOWN_TIMESTAMP: {
        SENSOR_NAME: "Town timestamp",
        SENSOR_DEVICE_CLASS: DEVICE_CLASS_TIMESTAMP,
    },
    ATTR_API_WIND_BEARING: {
        SENSOR_NAME: "Wind bearing",
        SENSOR_UNIT: DEGREE,
    },
    ATTR_API_WIND_MAX_SPEED: {
        SENSOR_NAME: "Wind max speed",
        SENSOR_UNIT: SPEED_KILOMETERS_PER_HOUR,
    },
    ATTR_API_WIND_SPEED: {
        SENSOR_NAME: "Wind speed",
        SENSOR_UNIT: SPEED_KILOMETERS_PER_HOUR,
    },
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
