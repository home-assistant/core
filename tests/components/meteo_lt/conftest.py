"""Fixtures for Meteo.lt integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from meteo_lt import Forecast, MeteoLtAPI, Place
import pytest

from homeassistant.components.meteo_lt.const import CONF_PLACE_CODE, DOMAIN

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)


@pytest.fixture(autouse=True)
def mock_meteo_lt_api() -> Generator[AsyncMock]:
    """Mock MeteoLtAPI with fixture data."""
    with (
        patch(
            "homeassistant.components.meteo_lt.coordinator.MeteoLtAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.meteo_lt.config_flow.MeteoLtAPI",
            new=mock_api_class,
        ),
    ):
        mock_api = AsyncMock(spec=MeteoLtAPI)
        mock_api_class.return_value = mock_api

        places_data = load_json_array_fixture("places.json", DOMAIN)
        forecast_data = load_json_object_fixture("forecast.json", DOMAIN)

        mock_places = [Place.from_dict(place_data) for place_data in places_data]
        mock_api.places = mock_places
        mock_api.fetch_places.return_value = None

        # Create mock forecast with proper structure
        mock_forecast = AsyncMock(spec=Forecast)

        # Parse forecast timestamps from the fixture data
        forecast_timestamps = []
        for ts_data in forecast_data.get("forecastTimestamps", []):
            timestamp = AsyncMock()
            timestamp.datetime = (
                ts_data.get("forecastTimeUtc", "").replace(" ", "T") + ":00"
            )
            timestamp.temperature = ts_data.get("airTemperature")
            timestamp.temperature_low = None  # Not provided in hourly data
            timestamp.apparent_temperature = ts_data.get("feelsLikeTemperature")
            timestamp.humidity = ts_data.get("relativeHumidity")
            timestamp.pressure = ts_data.get("seaLevelPressure")
            timestamp.wind_speed = ts_data.get("windSpeed")
            timestamp.wind_bearing = ts_data.get("windDirection")
            timestamp.wind_gust_speed = ts_data.get("windGust")
            timestamp.cloud_coverage = ts_data.get("cloudCover")
            timestamp.condition = ts_data.get("conditionCode")
            timestamp.precipitation = ts_data.get("totalPrecipitation")
            forecast_timestamps.append(timestamp)

        mock_forecast.forecast_timestamps = forecast_timestamps
        mock_forecast.current_conditions = AsyncMock()
        mock_forecast.current_conditions.temperature = 10.9
        mock_forecast.current_conditions.apparent_temperature = 10.9
        mock_forecast.current_conditions.humidity = 71
        mock_forecast.current_conditions.pressure = 1033
        mock_forecast.current_conditions.wind_speed = 2
        mock_forecast.current_conditions.wind_bearing = 20
        mock_forecast.current_conditions.wind_gust_speed = 6
        mock_forecast.current_conditions.cloud_coverage = 1
        mock_forecast.current_conditions.condition = "clear"

        mock_api.get_forecast.return_value = mock_forecast

        # Mock get_nearest_place to return Vilnius
        mock_api.get_nearest_place.return_value = mock_places[0]

        yield mock_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.meteo_lt.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Vilnius",
        data={CONF_PLACE_CODE: "vilnius"},
        unique_id="vilnius",
    )
