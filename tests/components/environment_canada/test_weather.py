"""Test weather."""

import json

from tests.common import load_fixture
from homeassistant.components.environment_canada.weather import get_forecast
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch


def test_forecast_daily() -> None:
    """Test basic forecast."""

    ec_data = json.loads(
        load_fixture("environment_canada/current_conditions_data.json")
    )

    # Remove the previous day's night forecast.
    del ec_data["daily_forecasts"][0]

    mock = MagicMock()
    mock.daily_forecasts = ec_data["daily_forecasts"]

    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2022, 10, 4, 1, tzinfo=UTC),
    ):
        forecast = get_forecast(mock, False)
        assert forecast == [
            {
                "datetime": "2022-10-04T01:00:00+00:00",
                "native_temperature": 18,
                "native_templow": 3,
                "precipitation_probability": 0,
                "condition": "sunny",
            },
            {
                "datetime": "2022-10-05T01:00:00+00:00",
                "native_temperature": 20,
                "native_templow": 9,
                "precipitation_probability": 0,
                "condition": "sunny",
            },
            {
                "datetime": "2022-10-06T01:00:00+00:00",
                "native_temperature": 20,
                "native_templow": 7,
                "precipitation_probability": 0,
                "condition": "partlycloudy",
            },
            {
                "datetime": "2022-10-07T01:00:00+00:00",
                "native_temperature": 13,
                "native_templow": 1,
                "precipitation_probability": 40,
                "condition": "rainy",
            },
            {
                "datetime": "2022-10-08T01:00:00+00:00",
                "native_temperature": 10,
                "native_templow": 3,
                "precipitation_probability": 0,
                "condition": "partlycloudy",
            },
        ]


def test_forecast_daily_with_some_previous_days_data() -> None:
    """Test basic forecast."""

    ec_data = json.loads(
        load_fixture("environment_canada/current_conditions_data.json")
    )
    mock = MagicMock()
    mock.daily_forecasts = ec_data["daily_forecasts"]

    with patch(
        "homeassistant.util.dt.now",
        return_value=datetime(2022, 10, 4, 1, tzinfo=UTC),
    ):
        forecast = get_forecast(mock, False)
        assert forecast == [
            {
                "datetime": "2022-10-03T01:00:00+00:00",
                "native_temperature": None,
                "native_templow": -1,
                "precipitation_probability": 0,
                "condition": "clear-night",
            },
            {
                "datetime": "2022-10-04T01:00:00+00:00",
                "native_temperature": 18,
                "native_templow": 3,
                "precipitation_probability": 0,
                "condition": "sunny",
            },
            {
                "datetime": "2022-10-05T01:00:00+00:00",
                "native_temperature": 20,
                "native_templow": 9,
                "precipitation_probability": 0,
                "condition": "sunny",
            },
            {
                "datetime": "2022-10-06T01:00:00+00:00",
                "native_temperature": 20,
                "native_templow": 7,
                "precipitation_probability": 0,
                "condition": "partlycloudy",
            },
            {
                "datetime": "2022-10-07T01:00:00+00:00",
                "native_temperature": 13,
                "native_templow": 1,
                "precipitation_probability": 40,
                "condition": "rainy",
            },
            {
                "datetime": "2022-10-08T01:00:00+00:00",
                "native_temperature": 10,
                "native_templow": 3,
                "precipitation_probability": 0,
                "condition": "partlycloudy",
            },
        ]
