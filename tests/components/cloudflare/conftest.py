"""Define fixtures available for all tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.util.location import LocationInfo

from . import get_mock_client

LOCATION_PATCH_TARGET = (
    "homeassistant.components.cloudflare.coordinator.async_detect_location_info"
)


@pytest.fixture
def cfupdate() -> Generator[MagicMock]:
    """Mock the CloudflareUpdater for easier testing."""
    mock_cfupdate = get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.coordinator.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api


@pytest.fixture
def cfupdate_flow() -> Generator[MagicMock]:
    """Mock the CloudflareUpdater for easier config flow testing."""
    mock_cfupdate = get_mock_client()
    with patch(
        "homeassistant.components.cloudflare.config_flow.pycfdns.Client",
        return_value=mock_cfupdate,
    ) as mock_api:
        yield mock_api


@pytest.fixture
def location_info() -> Generator[None]:
    """Mock the LocationInfo for easier testing."""
    with patch(
        LOCATION_PATCH_TARGET,
        return_value=LocationInfo(
            "0.0.0.0",
            "US",
            "USD",
            "CA",
            "California",
            "San Diego",
            "92122",
            "America/Los_Angeles",
            32.8594,
            -117.2073,
            True,
        ),
    ):
        yield
