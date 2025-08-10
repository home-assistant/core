"""Common fixtures for the WeatherflowCloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from aiohttp import ClientResponseError
import pytest
from weatherflow4py.api import WeatherFlowRestAPI
from weatherflow4py.models.rest.forecast import WeatherDataForecastREST
from weatherflow4py.models.rest.observation import ObservationStationREST
from weatherflow4py.models.rest.stations import StationsResponseREST
from weatherflow4py.models.rest.unified import WeatherFlowDataREST
from weatherflow4py.ws import WeatherFlowWebsocketAPI

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
def mock_rest_api():
    """Mock rest api."""
    fixtures = {
        "stations": StationsResponseREST.from_json(
            load_fixture("stations.json", DOMAIN)
        ),
        "forecast": WeatherDataForecastREST.from_json(
            load_fixture("forecast.json", DOMAIN)
        ),
        "observation": ObservationStationREST.from_json(
            load_fixture("station_observation.json", DOMAIN)
        ),
    }

    # Create device_station_map
    device_station_map = {
        device.device_id: station.station_id
        for station in fixtures["stations"].stations
        for device in station.devices
    }

    # Prepare mock data
    data = {
        24432: WeatherFlowDataREST(
            weather=fixtures["forecast"],
            observation=fixtures["observation"],
            station=fixtures["stations"].stations[0],
            device_observations=None,
        )
    }

    mock_api = AsyncMock(spec=WeatherFlowRestAPI)
    mock_api.get_all_data.return_value = data
    mock_api.async_get_stations.return_value = fixtures["stations"]
    mock_api.device_station_map = device_station_map
    mock_api.api_token = MOCK_API_TOKEN

    # Apply patches
    with (
        patch(
            "homeassistant.components.weatherflow_cloud.WeatherFlowRestAPI",
            return_value=mock_api,
        ) as _,
        patch(
            "homeassistant.components.weatherflow_cloud.coordinator.WeatherFlowRestAPI",
            return_value=mock_api,
        ) as _,
    ):
        yield mock_api


@pytest.fixture
def mock_stations_data(mock_rest_api):
    """Mock stations data for coordinator tests."""
    return mock_rest_api.async_get_stations.return_value


@pytest.fixture
async def mock_websocket_api():
    """Mock WeatherFlowWebsocketAPI."""
    mock_websocket = AsyncMock()
    mock_websocket.send = AsyncMock()
    mock_websocket.recv = AsyncMock()

    mock_ws_instance = AsyncMock(spec=WeatherFlowWebsocketAPI)
    mock_ws_instance.connect = AsyncMock()
    mock_ws_instance.send_message = AsyncMock()
    mock_ws_instance.register_callback = MagicMock()
    mock_ws_instance.websocket = mock_websocket

    with (
        patch(
            "homeassistant.components.weatherflow_cloud.coordinator.WeatherFlowWebsocketAPI",
            return_value=mock_ws_instance,
        ),
        patch(
            "homeassistant.components.weatherflow_cloud.WeatherFlowWebsocketAPI",
            return_value=mock_ws_instance,
        ),
        patch(
            "weatherflow4py.ws.WeatherFlowWebsocketAPI", return_value=mock_ws_instance
        ),
    ):
        # mock_connect.return_value = mock_websocket
        yield mock_ws_instance
