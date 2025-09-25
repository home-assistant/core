"""Fixtures for Meteo.lt integration tests."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from meteo_lt import Forecast, MeteoLtAPI, Place
import pytest

from homeassistant.components.meteo_lt.const import CONF_PLACE_CODE, DOMAIN

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture(autouse=True)
def mock_meteo_lt_api():
    """Mock MeteoLtAPI with fixture data."""
    with (
        patch("meteo_lt.MeteoLtAPI", autospec=True) as mock_api_class,
        patch(
            "homeassistant.components.meteo_lt.coordinator.MeteoLtAPI", autospec=True
        ) as mock_coord_api_class,
        patch(
            "homeassistant.components.meteo_lt.MeteoLtAPI", autospec=True
        ) as mock_init_api_class,
    ):
        mock_api = AsyncMock(spec=MeteoLtAPI)
        mock_api_class.return_value = mock_api
        mock_coord_api_class.return_value = mock_api
        mock_init_api_class.return_value = mock_api

        # Load fixture data
        fixture_path = Path(__file__).parent / "fixtures"

        with open(fixture_path / "places.json", encoding="utf-8") as f:
            places_data = json.load(f)

        forecast_data = load_json_object_fixture("forecast.json", DOMAIN)

        mock_places = [Place.from_dict(place_data) for place_data in places_data]
        mock_api.places = mock_places
        mock_api.fetch_places.return_value = None

        mock_forecast = Forecast.from_dict(forecast_data)
        mock_api.get_forecast.return_value = mock_forecast

        # Mock get_nearest_place to return Vilnius
        mock_api.get_nearest_place.return_value = mock_places[0]

        yield mock_api


@pytest.fixture(name="config_entry")
def get_config_entry():
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Vilnius",
        data={CONF_PLACE_CODE: "vilnius"},
        unique_id="vilnius",
    )
