"""Helpers for interacting with pynws."""
from homeassistant.components.nws.const import CONF_STATION
from homeassistant.components.weather import (
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_VISIBILITY,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    SPEED_KILOMETERS_PER_HOUR,
    SPEED_MILES_PER_HOUR,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.speed import convert as convert_speed
from homeassistant.util.temperature import convert as convert_temperature

NWS_CONFIG = {
    CONF_API_KEY: "test",
    CONF_LATITUDE: 35,
    CONF_LONGITUDE: -75,
    CONF_STATION: "ABC",
}

DEFAULT_STATIONS = ["ABC", "XYZ"]

DEFAULT_OBSERVATION = {
    "temperature": 10,
    "seaLevelPressure": 100000,
    "barometricPressure": 100000,
    "relativeHumidity": 10,
    "windSpeed": 10,
    "windDirection": 180,
    "visibility": 10000,
    "textDescription": "A long description",
    "station": "ABC",
    "timestamp": "2019-08-12T23:53:00+00:00",
    "iconTime": "day",
    "iconWeather": (("Fair/clear", None),),
    "dewpoint": 5,
    "windChill": 5,
    "heatIndex": 15,
    "windGust": 20,
}

SENSOR_EXPECTED_OBSERVATION_METRIC = {
    "dewpoint": "5",
    "temperature": "10",
    "windChill": "5",
    "heatIndex": "15",
    "relativeHumidity": "10",
    "windSpeed": "10",
    "windGust": "20",
    "windDirection": "180",
    "barometricPressure": "100000",
    "seaLevelPressure": "100000",
    "visibility": "10000",
}

SENSOR_EXPECTED_OBSERVATION_IMPERIAL = {
    "dewpoint": str(round(convert_temperature(5, TEMP_CELSIUS, TEMP_FAHRENHEIT))),
    "temperature": str(round(convert_temperature(10, TEMP_CELSIUS, TEMP_FAHRENHEIT))),
    "windChill": str(round(convert_temperature(5, TEMP_CELSIUS, TEMP_FAHRENHEIT))),
    "heatIndex": str(round(convert_temperature(15, TEMP_CELSIUS, TEMP_FAHRENHEIT))),
    "relativeHumidity": "10",
    "windSpeed": str(
        round(convert_speed(10, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR))
    ),
    "windGust": str(
        round(convert_speed(20, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR))
    ),
    "windDirection": "180",
    "barometricPressure": str(
        round(convert_pressure(100000, PRESSURE_PA, PRESSURE_INHG), 2)
    ),
    "seaLevelPressure": str(
        round(convert_pressure(100000, PRESSURE_PA, PRESSURE_INHG), 2)
    ),
    "visibility": str(round(convert_distance(10000, LENGTH_METERS, LENGTH_MILES))),
}

WEATHER_EXPECTED_OBSERVATION_IMPERIAL = {
    ATTR_WEATHER_TEMPERATURE: round(
        convert_temperature(10, TEMP_CELSIUS, TEMP_FAHRENHEIT)
    ),
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: round(
        convert_speed(10, SPEED_KILOMETERS_PER_HOUR, SPEED_MILES_PER_HOUR), 2
    ),
    ATTR_WEATHER_PRESSURE: round(
        convert_pressure(100000, PRESSURE_PA, PRESSURE_INHG), 2
    ),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(10000, LENGTH_METERS, LENGTH_MILES), 2
    ),
    ATTR_WEATHER_HUMIDITY: 10,
}

WEATHER_EXPECTED_OBSERVATION_METRIC = {
    ATTR_WEATHER_TEMPERATURE: 10,
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: 10,
    ATTR_WEATHER_PRESSURE: round(convert_pressure(100000, PRESSURE_PA, PRESSURE_HPA)),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(10000, LENGTH_METERS, LENGTH_KILOMETERS)
    ),
    ATTR_WEATHER_HUMIDITY: 10,
}

NONE_OBSERVATION = {key: None for key in DEFAULT_OBSERVATION}

DEFAULT_FORECAST = [
    {
        "number": 1,
        "name": "Tonight",
        "startTime": "2019-08-12T20:00:00-04:00",
        "isDaytime": False,
        "temperature": 10,
        "windSpeedAvg": 10,
        "windBearing": 180,
        "detailedForecast": "A detailed forecast.",
        "timestamp": "2019-08-12T23:53:00+00:00",
        "iconTime": "night",
        "iconWeather": (("lightning-rainy", 40), ("lightning-rainy", 90)),
    },
]

EXPECTED_FORECAST_IMPERIAL = {
    ATTR_FORECAST_CONDITION: ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: 10,
    ATTR_FORECAST_WIND_SPEED: 10,
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: 90,
}

EXPECTED_FORECAST_METRIC = {
    ATTR_FORECAST_CONDITION: ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: round(
        convert_temperature(10, TEMP_FAHRENHEIT, TEMP_CELSIUS), 1
    ),
    ATTR_FORECAST_WIND_SPEED: round(
        convert_speed(10, SPEED_MILES_PER_HOUR, SPEED_KILOMETERS_PER_HOUR), 2
    ),
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: 90,
}

NONE_FORECAST = [{key: None for key in DEFAULT_FORECAST[0]}]
