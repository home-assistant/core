"""Fixtures for the IRM KMI integration tests."""

from __future__ import annotations

from collections.abc import Generator
import json
from unittest.mock import MagicMock, patch

from irm_kmi_api import IrmKmiApiError
import pytest

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.const import CONF_ZONE

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    entry = MockConfigEntry(
        title="Home",
        domain=DOMAIN,
        data={CONF_ZONE: "zone.home", CONF_LANGUAGE_OVERRIDE: "none"},
        unique_id="zone.home",
    )
    entry.runtime_data = MagicMock()
    return entry


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
        return_value={"cityName": "Brussels"},
    ):
        yield


@pytest.fixture
def mock_get_forecast_out_benelux():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it returns something outside Benelux."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        return_value={"cityName": "Outside the Benelux (Brussels)"},
    ):
        yield


@pytest.fixture
def mock_get_forecast_api_error():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it raises an error."""
    with patch(
        "homeassistant.components.irm_kmi.config_flow.IrmKmiApiClient.get_forecasts_coord",
        side_effet=IrmKmiApiError,
    ):
        return


@pytest.fixture
def mock_get_forecast_api_error_repair():
    """Mock a call to IrmKmiApiClient.get_forecasts_coord() so that it raises an error."""
    with patch(
        "homeassistant.components.irm_kmi.repairs.IrmKmiApiClient.get_forecasts_coord",
        side_effet=IrmKmiApiError,
    ):
        return


@pytest.fixture
def mock_irm_kmi_api(request: pytest.FixtureRequest) -> Generator[None, MagicMock]:
    """Return a mocked IrmKmi api client."""
    fixture: str = "forecast.json"

    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.types.IrmKmiApiClientHa", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.get_forecasts_coord.return_value = forecast
        yield irm_kmi


@pytest.fixture
def mock_irm_kmi_api_repair_in_benelux(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock]:
    """Return a mocked IrmKmi api client."""
    fixture: str = "forecast.json"

    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.repairs.IrmKmiApiClient", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.get_forecasts_coord.return_value = forecast
        yield irm_kmi


@pytest.fixture
def mock_irm_kmi_api_repair_out_of_benelux(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock]:
    """Return a mocked IrmKmi api client."""
    fixture: str = "forecast_out_of_benelux.json"

    forecast = json.loads(load_fixture(fixture, "irm_kmi"))
    with patch(
        "homeassistant.components.irm_kmi.repairs.IrmKmiApiClient", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.get_forecasts_coord.return_value = forecast
        yield irm_kmi


@pytest.fixture
def mock_exception_irm_kmi_api(
    request: pytest.FixtureRequest,
) -> Generator[None, MagicMock]:
    """Return a mocked IrmKmi api client that will raise an error upon refreshing data."""
    with patch(
        "homeassistant.components.irm_kmi.types.IrmKmiApiClientHa", autospec=True
    ) as irm_kmi_api_mock:
        irm_kmi = irm_kmi_api_mock.return_value
        irm_kmi.refresh_forecasts_coord.side_effect = IrmKmiApiError
        yield irm_kmi
