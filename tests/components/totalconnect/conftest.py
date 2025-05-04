"""Configure py.test."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from total_connect_client import TotalConnectClient
from total_connect_client.location import TotalConnectLocation

from .common import LOCATION_ID


@pytest.fixture
def mock_location() -> Generator[TotalConnectLocation]:
    """Create a mock TotalConnectLocation."""
    with patch(
        "total_connect_client.location.TotalConnectLocation", autospec=True
    ) as location:
        location.location_id = LOCATION_ID
        location.set_usercode.return_value = True
        yield location


@pytest.fixture
def mock_client(
    mock_location: TotalConnectLocation,
) -> Generator[TotalConnectClient]:
    """Mock a TotalConnectClient for config flow testing."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient",
        autospec=True,
    ) as client:
        client.return_value.get_number_locations.return_value = 1
        client.return_value.locations = {mock_location.location_id: mock_location}
        yield client
