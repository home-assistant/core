"""Fixtures for the IRM KMI integration tests."""

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from irm_kmi_api import IrmKmiApiError
import pytest

from homeassistant.components.irm_kmi.const import DOMAIN
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    CONF_LOCATION,
    CONF_UNIQUE_ID,
)

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Home",
        domain=DOMAIN,
        data={
            CONF_LOCATION: {ATTR_LATITUDE: 50.84, ATTR_LONGITUDE: 4.35},
            CONF_UNIQUE_ID: "city country",
        },
        unique_id="50.84-4.35",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[None]:
    """Mock setting up a config entry."""
    with patch("homeassistant.components.irm_kmi.async_setup_entry", return_value=True):
        yield


@pytest.fixture
def mock_get_forecast_in_benelux():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it returns something valid and in the Benelux."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        return_value={"cityName": "Brussels", "country": "BE"},
    ):
        yield


@pytest.fixture
def mock_get_forecast_out_benelux_then_in_belgium():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it returns something outside Benelux."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        side_effect=[
            {"cityName": "Outside the Benelux (Brussels)", "country": "BE"},
            {"cityName": "Brussels", "country": "BE"},
        ],
    ):
        yield


@pytest.fixture
def mock_get_forecast_api_error():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it raises an error."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        side_effect=IrmKmiApiError,
    ):
        yield


@pytest.fixture
def mock_irm_kmi_api(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Return a mocked IrmKmi api client."""
    fixture: str = "forecast.json"

    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.IrmKmiApiClientHa", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.get_forecasts_coord.return_value = forecast
        yield irm_kmi


@pytest.fixture
def mock_irm_kmi_api_nl():
    """Mock a call to IrmKmiApiClientHa.get_forecasts_coord() to return a forecast in The Netherlands."""
    fixture: str = "forecast_nl.json"
    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.coordinator.IrmKmiApiClientHa.get_forecasts_coord",
        return_value=forecast,
    ):
        yield


@pytest.fixture
def mock_irm_kmi_api_high_low_temp():
    """Mock a call to IrmKmiApiClientHa.get_forecasts_coord() to return high_low_temp.json forecast."""
    fixture: str = "high_low_temp.json"
    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.coordinator.IrmKmiApiClientHa.get_forecasts_coord",
        return_value=forecast,
    ):
        yield


@pytest.fixture
def mock_exception_irm_kmi_api(request: pytest.FixtureRequest) -> Generator[MagicMock]:
    """Return a mocked IrmKmi api client that will raise an error upon refreshing data."""
    with patch(
        "homeassistant.components.irm_kmi.IrmKmiApiClientHa", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.refresh_forecasts_coord.side_effect = IrmKmiApiError
        yield irm_kmi
