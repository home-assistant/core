"""Common fixtures for the Google Weather tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from google_weather_api import (
    CurrentConditionsResponse,
    DailyForecastResponse,
    HourlyForecastResponse,
)
import pytest

from homeassistant.components.google_weather.const import DOMAIN
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.google_weather.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return the default mocked config entry."""
    config_entry = MockConfigEntry(
        title="Google Weather",
        domain=DOMAIN,
        data={
            CONF_API_KEY: "test-api-key",
        },
        subentries_data=[
            ConfigSubentryDataWithId(
                data={
                    CONF_LATITUDE: 10.1,
                    CONF_LONGITUDE: 20.1,
                },
                subentry_type="location",
                title="Home",
                subentry_id="home-subentry-id",
                unique_id=None,
            )
        ],
    )
    config_entry.add_to_hass(hass)
    return config_entry


@pytest.fixture
def mock_google_weather_api() -> Generator[AsyncMock]:
    """Mock Google Weather API."""
    current_conditions = CurrentConditionsResponse.from_dict(
        load_json_object_fixture("current_conditions.json", DOMAIN)
    )
    daily_forecast = DailyForecastResponse.from_dict(
        load_json_object_fixture("daily_forecast.json", DOMAIN)
    )
    hourly_forecast = HourlyForecastResponse.from_dict(
        load_json_object_fixture("hourly_forecast.json", DOMAIN)
    )

    with (
        patch(
            "homeassistant.components.google_weather.GoogleWeatherApi", autospec=True
        ) as mock_api,
        patch(
            "homeassistant.components.google_weather.config_flow.GoogleWeatherApi",
            new=mock_api,
        ),
    ):
        api = mock_api.return_value
        api.async_get_current_conditions.return_value = current_conditions
        api.async_get_daily_forecast.return_value = daily_forecast
        api.async_get_hourly_forecast.return_value = hourly_forecast

        yield api
