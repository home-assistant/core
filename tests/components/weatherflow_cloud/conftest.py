"""Common fixtures for the WeatherflowCloud tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientResponseError
import pytest


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.weatherflow_cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_get_stations() -> Generator[AsyncMock, None, None]:
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
def mock_get_stations_500_error() -> Generator[AsyncMock, None, None]:
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
def mock_get_stations_401_error() -> Generator[AsyncMock, None, None]:
    """Mock get_stations with a sequence of responses."""
    side_effects = [ClientResponseError(Mock(), (), status=401), True, True, True]

    with patch(
        "weatherflow4py.api.WeatherFlowRestAPI.async_get_stations",
        side_effect=side_effects,
    ) as mock_get_stations:
        yield mock_get_stations
