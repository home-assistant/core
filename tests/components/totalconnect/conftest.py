"""Configure py.test."""

from collections.abc import Generator
from unittest.mock import patch

import pytest
from total_connect_client import TotalConnectClient


@pytest.fixture
def mock_client() -> Generator[TotalConnectClient]:
    """Mock a TotalConnectClient for config flow testing."""
    with patch(
        "homeassistant.components.totalconnect.config_flow.TotalConnectClient",
        autospec=True,
    ) as client_mock:
        yield client_mock
