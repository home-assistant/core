"""Common fixtures for the AccuWeather tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.accuweather.const import DOMAIN

from tests.common import load_json_array_fixture, load_json_object_fixture


@pytest.fixture
def mock_accuweather_client() -> Generator[AsyncMock]:
    """Mock a AccuWeather client."""
    current = load_json_object_fixture("current_conditions_data.json", DOMAIN)
    forecast = load_json_array_fixture("forecast_data.json", DOMAIN)
    location = load_json_object_fixture("location_data.json", DOMAIN)

    with (
        patch(
            "homeassistant.components.accuweather.AccuWeather", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.accuweather.config_flow.AccuWeather",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.async_get_location.return_value = location
        client.async_get_current_conditions.return_value = current
        client.async_get_daily_forecast.return_value = forecast
        client.location_key = "0123456"
        client.requests_remaining = 10

        yield client
