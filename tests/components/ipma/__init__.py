"""Tests for the IPMA component."""
from collections import namedtuple
from datetime import UTC, datetime

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_MODE, CONF_NAME

ENTRY_CONFIG = {
    CONF_NAME: "Home Town",
    CONF_LATITUDE: "1",
    CONF_LONGITUDE: "2",
    CONF_MODE: "hourly",
}


class MockLocation:
    """Mock Location from pyipma."""

    async def fire_risk(self, api):
        """Mock Fire Risk."""
        RCM = namedtuple(
            "RCM",
            [
                "dico",
                "rcm",
                "coordinates",
            ],
        )
        return RCM("some place", 3, (0, 0))

    async def uv_risk(self, api):
        """Mock UV Index."""
        UV = namedtuple(
            "UV",
            ["idPeriodo", "intervaloHora", "data", "globalIdLocal", "iUv"],
        )
        return UV(0, "0", datetime.now(), 0, 5.7)

    async def observation(self, api):
        """Mock Observation."""
        Observation = namedtuple(
            "Observation",
            [
                "accumulated_precipitation",
                "humidity",
                "pressure",
                "radiation",
                "temperature",
                "wind_direction",
                "wind_intensity_km",
            ],
        )

        return Observation(0.0, 71.0, 1000.0, 0.0, 18.0, "NW", 3.94)

    async def forecast(self, api, period):
        """Mock Forecast."""
        Forecast = namedtuple(
            "Forecast",
            [
                "feels_like_temperature",
                "forecast_date",
                "forecasted_hours",
                "humidity",
                "max_temperature",
                "min_temperature",
                "precipitation_probability",
                "temperature",
                "update_date",
                "weather_type",
                "wind_direction",
                "wind_strength",
            ],
        )

        WeatherType = namedtuple("WeatherType", ["id", "en", "pt"])

        if period == 24:
            return [
                Forecast(
                    None,
                    datetime(2020, 1, 16, 0, 0, 0),
                    24,
                    None,
                    16.2,
                    10.6,
                    "100.0",
                    13.4,
                    "2020-01-15T07:51:00",
                    WeatherType(9, "Rain/showers", "Chuva/aguaceiros"),
                    "S",
                    "10",
                ),
            ]
        if period == 1:
            return [
                Forecast(
                    "7.7",
                    datetime(2020, 1, 15, 1, 0, 0, tzinfo=UTC),
                    1,
                    "86.9",
                    12.0,
                    None,
                    80.0,
                    10.6,
                    "2020-01-15T02:51:00",
                    WeatherType(10, "Light rain", "Chuva fraca ou chuvisco"),
                    "S",
                    "32.7",
                ),
                Forecast(
                    "5.7",
                    datetime(2020, 1, 15, 2, 0, 0, tzinfo=UTC),
                    1,
                    "86.9",
                    12.0,
                    None,
                    80.0,
                    10.6,
                    "2020-01-15T02:51:00",
                    WeatherType(1, "Clear sky", "C\u00e9u limpo"),
                    "S",
                    "32.7",
                ),
            ]

    name = "HomeTown"
    station = "HomeTown Station"
    station_latitude = 0
    station_longitude = 0
    global_id_local = 1130600
    id_station = 1200545
