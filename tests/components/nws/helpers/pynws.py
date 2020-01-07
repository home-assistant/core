"""Helpers for interacting with pynws."""
from homeassistant.components.nws.weather import ATTR_FORECAST_PRECIP_PROB
from homeassistant.components.weather import (
    ATTR_FORECAST_CONDITION,
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
    LENGTH_KILOMETERS,
    LENGTH_METERS,
    LENGTH_MILES,
    PRESSURE_HPA,
    PRESSURE_INHG,
    PRESSURE_PA,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.util.distance import convert as convert_distance
from homeassistant.util.pressure import convert as convert_pressure
from homeassistant.util.temperature import convert as convert_temperature

TEST_STATION_LIST = ["ABC", "XYZ"]

DEFAULT_OBSERVATION = {
    "temperature": 10,
    "seaLevelPressure": 100000,
    "relativeHumidity": 10,
    "windSpeed": 10,
    "windDirection": 180,
    "visibility": 10000,
    "textDescription": "A long description",
    "station": TEST_STATION_LIST[0],
    "timestamp": "2019-08-12T23:53:00+00:00",
    "iconTime": "day",
    "iconWeather": (("Fair/clear", None),),
}

EXPECTED_OBSERVATION_IMPERIAL = {
    ATTR_WEATHER_TEMPERATURE: round(
        convert_temperature(10, TEMP_CELSIUS, TEMP_FAHRENHEIT)
    ),
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: round(
        convert_distance(10, LENGTH_METERS, LENGTH_MILES) * 3600
    ),
    ATTR_WEATHER_PRESSURE: round(
        convert_pressure(100000, PRESSURE_PA, PRESSURE_INHG), 2
    ),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(10000, LENGTH_METERS, LENGTH_MILES)
    ),
    ATTR_WEATHER_HUMIDITY: 10,
}

EXPECTED_OBSERVATION_METRIC = {
    ATTR_WEATHER_TEMPERATURE: 10,
    ATTR_WEATHER_WIND_BEARING: 180,
    ATTR_WEATHER_WIND_SPEED: round(
        convert_distance(10, LENGTH_METERS, LENGTH_KILOMETERS) * 3600
    ),
    ATTR_WEATHER_PRESSURE: round(convert_pressure(100000, PRESSURE_PA, PRESSURE_HPA)),
    ATTR_WEATHER_VISIBILITY: round(
        convert_distance(10000, LENGTH_METERS, LENGTH_KILOMETERS)
    ),
    ATTR_WEATHER_HUMIDITY: 10,
}

NONE_OBSERVATION = {key: None for key in DEFAULT_OBSERVATION.keys()}

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
    ATTR_FORECAST_CONDITION: "lightning-rainy",
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: 10,
    ATTR_FORECAST_WIND_SPEED: 10,
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIP_PROB: 90,
}

EXPECTED_FORECAST_METRIC = {
    ATTR_FORECAST_CONDITION: "lightning-rainy",
    ATTR_FORECAST_TIME: "2019-08-12T20:00:00-04:00",
    ATTR_FORECAST_TEMP: round(convert_temperature(10, TEMP_FAHRENHEIT, TEMP_CELSIUS)),
    ATTR_FORECAST_WIND_SPEED: round(
        convert_distance(10, LENGTH_MILES, LENGTH_KILOMETERS)
    ),
    ATTR_FORECAST_WIND_BEARING: 180,
    ATTR_FORECAST_PRECIP_PROB: 90,
}

NONE_FORECAST = [{key: None for key in DEFAULT_FORECAST[0].keys()}]


def mock_nws(
    STATIONS=TEST_STATION_LIST,
    OBSERVATION=DEFAULT_OBSERVATION,
    FORECAST=DEFAULT_FORECAST,
):
    """Return a mock SimpleNWS object."""

    class MockSimpleNWS:
        """Mock NWS simplified data."""

        def __init__(self):
            """Initiliaze Mock object."""
            self.station = None
            self.stations = None
            pass

        async def set_station(self, station=None):
            """Set station or retrieve station list."""
            if station:
                self.station = station
                self.stations = [station]
            else:
                self.station = STATIONS[0]
                self.stations = STATIONS

        async def update_observation(self):
            """Update observation."""
            pass

        async def update_forecast(self):
            """Update forecast."""
            pass

        async def update_forecast_hourly(self):
            """Update forecast."""
            pass

        @property
        def observation(self):
            """Observation dict."""
            return OBSERVATION

        @property
        def forecast(self):
            """Return forecast."""
            return FORECAST

        @property
        def forecast_hourly(self):
            """Return forecast hourly."""
            return FORECAST

    return MockSimpleNWS
