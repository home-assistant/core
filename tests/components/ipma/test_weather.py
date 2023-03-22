"""The tests for the IPMA weather component."""
from datetime import datetime
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
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from . import MockLocation

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


class MockBadLocation(MockLocation):
    """Mock Location with unresponsive api."""

    async def observation(self, api):
        """Mock Observation."""
        return None

    async def forecast(self, api, period):
        """Mock Forecast."""
        return []


async def test_setup_config_flow(hass: HomeAssistant) -> None:
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
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


async def test_daily_forecast(hass: HomeAssistant) -> None:
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
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
async def test_hourly_forecast(hass: HomeAssistant) -> None:
    """Test for successfully getting daily forecast."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG_HOURLY)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("weather.hometown")
    assert state.state == "rainy"

    forecast = state.attributes.get(ATTR_FORECAST)[0]
    assert forecast.get(ATTR_FORECAST_CONDITION) == "rainy"
    assert forecast.get(ATTR_FORECAST_TEMP) == 12.0
    assert forecast.get(ATTR_FORECAST_PRECIPITATION_PROBABILITY) == 80.0
    assert forecast.get(ATTR_FORECAST_WIND_SPEED) == 32.7
    assert forecast.get(ATTR_FORECAST_WIND_BEARING) == "S"


async def test_failed_get_observation_forecast(hass: HomeAssistant) -> None:
    """Test for successfully setting up the IPMA platform."""
    with patch(
        "pyipma.location.Location.get",
        return_value=MockBadLocation(),
    ):
        entry = MockConfigEntry(domain="ipma", data=TEST_CONFIG)
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
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
