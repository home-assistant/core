"""The tests for the IPMA weather component."""
from collections import namedtuple
from datetime import datetime, timezone
from unittest.mock import patch

from freezegun import freeze_time

from homeassistant.components.weather import (
    ATTR_FORECAST,
    ATTR_FORECAST_CONDITION,
    ATTR_FORECAST_PRECIPITATION_PROBABILITY,
    ATTR_FORECAST_TEMP,
    ATTR_FORECAST_TEMP_LOW,
    ATTR_FORECAST_TIME,
    ATTR_FORECAST_WIND_BEARING,
    ATTR_FORECAST_WIND_SPEED,
    ATTR_WEATHER_HUMIDITY,
    ATTR_WEATHER_PRESSURE,
    ATTR_WEATHER_TEMPERATURE,
    ATTR_WEATHER_WIND_BEARING,
    ATTR_WEATHER_WIND_SPEED,
    DOMAIN as WEATHER_DOMAIN,
)
from homeassistant.const import STATE_UNKNOWN

from tests.common import MockConfigEntry

TEST_CONFIG = {
    "name": "HomeTown",
    "latitude": "40.00",
    "longitude": "-8.00",
    "mode": "daily",
}

TEST_CONFIG_HOURLY = {
    "name": "HomeTown",
    "latitude": "40.00",
    "longitude": "-8.00",
    "mode": "hourly",
}


class MockLocation:
    """Mock Location from pyipma."""

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
                    datetime(2020, 1, 15, 1, 0, 0, tzinfo=timezone.utc),
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
                    datetime(2020, 1, 15, 2, 0, 0, tzinfo=timezone.utc),
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

    @property
    def name(self):
        """Mock location."""
        return "HomeTown"

    @property
    def station(self):
        """Mock station."""
        return "HomeTown Station"

    @property
    def station_latitude(self):
        """Mock latitude."""
        return 0

    @property
    def global_id_local(self):
        """Mock global identifier of the location."""
        return 1130600

    @property
    def id_station(self):
        """Mock identifier of the station."""
        return 1200545

    @property
    def station_longitude(self):
        """Mock longitude."""
        return 0


class MockBadLocation(MockLocation):
    """Mock Location with unresponsive api."""

    async def observation(self, api):
        """Mock Observation."""
        return None

    async def forecast(self, api, period):
        """Mock Forecast."""
        return []


async def test_setup_config_flow(hass):
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) == 18.0
    assert data.get(ATTR_WEATHER_HUMIDITY) == 71
    assert data.get(ATTR_WEATHER_PRESSURE) == 1000.0
    assert data.get(ATTR_WEATHER_WIND_SPEED) == 3.94
    assert data.get(ATTR_WEATHER_WIND_BEARING) == "NW"
    assert state.attributes.get("friendly_name") == "HomeTown"


async def test_daily_forecast(hass):
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_TIME) == datetime(2020, 1, 16, 0, 0, 0)
    assert forecast.get(ATTR_FORECAST_CONDITION) == "rainy"
    assert forecast.get(ATTR_FORECAST_TEMP) == 16.2
    assert forecast.get(ATTR_FORECAST_TEMP_LOW) == 10.6
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == "100.0"
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 10.0
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == "S"


@freeze_time("2020-01-14 23:00:00")
async def test_hourly_forecast(hass):
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG_HOURLY)
        await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == "rainy"
    assert forecast.get(ATTR_FORECAST_TEMP) == 12.0
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 80.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 32.7
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == "S"


async def test_failed_get_observation_forecast(hass):
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockBadLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        await hass.config_entries.async_forward_entry_setup(entry, WEATHER_DOMAIN)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == STATE_UNKNOWN

    data = state.attributes
    assert data.get(ATTR_WEATHER_TEMPERATURE) is None
    assert data.get(ATTR_WEATHER_HUMIDITY) is None
    assert data.get(ATTR_WEATHER_PRESSURE) is None
    assert data.get(ATTR_WEATHER_WIND_SPEED) is None
    assert data.get(ATTR_WEATHER_WIND_BEARING) is None
    assert state.attributes.get("friendly_name") == "HomeTown"
