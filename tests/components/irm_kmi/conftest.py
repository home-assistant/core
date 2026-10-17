"""Fixtures for the IRM KMI integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.irm_kmi.const import DOMAIN
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LOCATION,
    CONF_UNIQUE_ID,
)

from .const import CURRENT_WEATHER

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Brussels",
        domain=DOMAIN,
        data={
            CONF_LOCATION: {ATTR_LATITUDE: 50.84, ATTR_LONGITUDE: 4.35},
            CONF_UNIQUE_ID: "brussels be",
        },
        unique_id="brussels be",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.irm_kmi.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_config_flow_forecast() -> Generator[AsyncMock]:
    """Mock the config flow forecast fetch for a location in Belgium."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        return_value={"cityName": "Brussels", "country": "BE"},
    ) as get_forecasts_coord:
        yield get_forecasts_coord


@pytest.fixture
def mock_irm_kmi_api() -> Generator[MagicMock]:
    """Return a mocked IRM KMI client serving parsed data."""
    with patch(
        "homeassistant.components.irm_kmi.IrmKmiApiClientHa", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.get_country.return_value = "BE"
        irm_kmi.get_current_weather.return_value = CURRENT_WEATHER
        irm_kmi.get_daily_forecast.return_value = []
        irm_kmi.get_hourly_forecast.return_value = []
        yield irm_kmi


@pytest.fixture
def forecast_fixture() -> str:
    """Return the name of the recorded forecast to serve."""
    return "forecast.json"


@pytest.fixture
def mock_get_forecasts_coord(forecast_fixture: str) -> Generator[AsyncMock]:
    """Mock get_forecasts_coord() to return a recorded forecast."""
    with patch(
        "homeassistant.components.irm_kmi.IrmKmiApiClientHa.get_forecasts_coord",
        return_value=load_json_object_fixture(forecast_fixture, DOMAIN),
    ) as get_forecasts_coord:
        yield get_forecasts_coord
