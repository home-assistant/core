"""Helpers for interacting with pynws."""
from homeassistant.components.nws.const import CONF_STATION
from homeassistant.components.weather import (
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_DEW_POINT,
    ATTR_FORECAST_HUMIDITY,
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
    UnitOfLength,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.util.unit_conversion import (
    DistanceConverter,
    PressureConverter,
    SpeedConverter,
    TemperatureConverter,
)

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

CLEAR_NIGHT_OBSERVATION = DEFAULT_OBSERVATION.copy()
CLEAR_NIGHT_OBSERVATION["iconTime"] = "night"

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
    "dewpoint": str(
        round(
            TemperatureConverter.convert(
                5, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
            )
        )
    ),
    "temperature": str(
        round(
            TemperatureConverter.convert(
                10, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
            )
        )
    ),
    "windChill": str(
        round(
            TemperatureConverter.convert(
                5, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
            )
        )
    ),
    "heatIndex": str(
        round(
            TemperatureConverter.convert(
                15, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
            )
        )
    ),
    "relativeHumidity": "10",
    "windSpeed": str(
        round(
            SpeedConverter.convert(
                10, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
            )
        )
    ),
    "windGust": str(
        round(
            SpeedConverter.convert(
                20, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
            )
        )
    ),
    "windDirection": "180",
    "barometricPressure": str(
        round(
            PressureConverter.convert(100000, UnitOfPressure.PA, UnitOfPressure.INHG), 2
        )
    ),
    "seaLevelPressure": str(
        round(
            PressureConverter.convert(100000, UnitOfPressure.PA, UnitOfPressure.INHG), 2
        )
    ),
    "visibility": str(
        round(DistanceConverter.convert(10000, UnitOfLength.METERS, UnitOfLength.MILES))
    ),
}

WEATHER_EXPECTED_OBSERVATION_IMPERIAL = {
    ATTR_WEATHER_TEMPERATURE: round(
        TemperatureConverter.convert(
            10, UnitOfTemperature.CELSIUS, UnitOfTemperature.FAHRENHEIT
        )
    ),
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: round(
        SpeedConverter.convert(
            10, UnitOfSpeed.KILOMETERS_PER_HOUR, UnitOfSpeed.MILES_PER_HOUR
        ),
        2,
    ),
    ATTR_WEATHER_PRESSURE: round(
        PressureConverter.convert(100000, UnitOfPressure.PA, UnitOfPressure.INHG), 2
    ),
    ATTR_WEATHER_VISIBILITY: round(
        DistanceConverter.convert(10000, UnitOfLength.METERS, UnitOfLength.MILES), 2
    ),
    ATTR_WEATHER_HUMIDITY: 10,
}

WEATHER_EXPECTED_OBSERVATION_METRIC = {
    ATTR_WEATHER_TEMPERATURE: 10,
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: 10,
    ATTR_WEATHER_PRESSURE: round(
        PressureConverter.convert(100000, UnitOfPressure.PA, UnitOfPressure.HPA)
    ),
    ATTR_WEATHER_VISIBILITY: round(
        DistanceConverter.convert(10000, UnitOfLength.METERS, UnitOfLength.KILOMETERS)
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
        "probabilityOfPrecipitation": 89,
        "dewpoint": 4,
        "relativeHumidity": 75,
    },
]

EXPECTED_FORECAST_IMPERIAL = {
    ATTR_FORECAST_CONDITION: ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: 10,
    ATTR_FORECAST_WIND_SPEED: 10,
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: 89,
    ATTR_FORECAST_DEW_POINT: 4,
    ATTR_FORECAST_HUMIDITY: 75,
}

EXPECTED_FORECAST_METRIC = {
    ATTR_FORECAST_CONDITION: ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: round(
        TemperatureConverter.convert(
            10, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
        ),
        1,
    ),
    ATTR_FORECAST_WIND_SPEED: round(
        SpeedConverter.convert(
            10, UnitOfSpeed.MILES_PER_HOUR, UnitOfSpeed.KILOMETERS_PER_HOUR
        ),
        2,
    ),
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY: 89,
    ATTR_FORECAST_DEW_POINT: round(
        TemperatureConverter.convert(
            4, UnitOfTemperature.FAHRENHEIT, UnitOfTemperature.CELSIUS
        ),
        1,
    ),
    ATTR_FORECAST_HUMIDITY: 75,
}

NONE_FORECAST = [{key: None for key in DEFAULT_FORECAST[0]}]
