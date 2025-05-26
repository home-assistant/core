"""Common fixtures for the WeatherflowCloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
import pytest
from weatherflow4py.models.rest.forecast import WeatherDataForecastREST
from weatherflow4py.models.rest.observation import ObservationStationREST
from weatherflow4py.models.rest.stations import StationsResponseREST
from weatherflow4py.models.rest.unified import WeatherFlowDataREST

from homeassistant.components.weatherflow_cloud.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.weatherflow_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_get_stations() -> Generator[AsyncMock]:
    """Mock get_stations with a sequence of responses."""
    side_effects = [
        True,
    ]

    with patch(
        "weatherflow4py.api.WeatherFlowRestAPI.async_get_stations",
        side_effect=side_effects,
    ) as mock_get_stations:
        yield mock_get_stations


@pytest.fixture
def mock_get_stations_500_error() -> Generator[AsyncMock]:
    """Mock get_stations with a sequence of responses."""
    side_effects = [
        ClientResponseError(Mock(), (), status=500),
        True,
    ]

    with patch(
        "weatherflow4py.api.WeatherFlowRestAPI.async_get_stations",
        side_effect=side_effects,
    ) as mock_get_stations:
        yield mock_get_stations


@pytest.fixture
def mock_get_stations_401_error() -> Generator[AsyncMock]:
    """Mock get_stations with a sequence of responses."""
    side_effects = [ClientResponseError(Mock(), (), status=401), True, True, True]

    with patch(
        "weatherflow4py.api.WeatherFlowRestAPI.async_get_stations",
        side_effect=side_effects,
    ) as mock_get_stations:
        yield mock_get_stations


MOCK_API_TOKEN = "1234567890"


@pytest.fixture
async def mock_config_entry() -> MockConfigEntry:
    """Fixture for MockConfigEntry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_TOKEN: MOCK_API_TOKEN},
        version=1,
    )


@pytest.fixture
def mock_api():
    """Fixture for Mock WeatherFlowRestAPI."""
    get_stations_response_data = StationsResponseREST.from_json(
        load_fixture("stations.json", DOMAIN)
    )
    get_forecast_response_data = WeatherDataForecastREST.from_json(
        load_fixture("forecast.json", DOMAIN)
    )
    get_observation_response_data = ObservationStationREST.from_json(
        load_fixture("station_observation.json", DOMAIN)
    )

    data = {
        24432: WeatherFlowDataREST(
            weather=get_forecast_response_data,
            observation=get_observation_response_data,
            station=get_stations_response_data.stations[0],
            device_observations=None,
        )
    }

    with patch(
        "homeassistant.components.weatherflow_cloud.coordinator.WeatherFlowRestAPI",
        autospec=True,
    ) as mock_api_class:
        # Create an instance of AsyncMock for the API
        mock_api = AsyncMock()
        mock_api.get_all_data.return_value = data
        # Patch the class to return our mock_api instance
        mock_api_class.return_value = mock_api

        yield mock_api
