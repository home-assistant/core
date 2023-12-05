"""Provide common fixtures for tests."""
from unittest.mock import Mock, patch

import pytest


class MockAQClientSuccess:
    """Mock for AQClient that simulates a successful response."""

    def __init__(self, *args, **kwargs):
        """Initialize the mock AQClient."""
        pass

    def get_device(self):
        """Simulate getting device data from AQClient."""
        return Mock(sensors=["pm25", "o3"], locality="Valid Location")


@pytest.fixture
def mock_aq_client():
    """Fixture to create a basic mock AQClient."""
    with patch("homeassistant.components.openAQ.config_flow.AQClient") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_aq_client_no_sensors():
    """Fixture to create a mock AQClient where get_device returns an empty sensors list."""
    with patch("homeassistant.components.openAQ.config_flow.AQClient") as mock_client:
        mock_client.return_value.get_device = Mock(return_value=Mock(sensors=[]))
        yield mock_client.return_value


@pytest.fixture
def mock_aq_client_valid_data():
    """Fixture to create a mock AQClient with valid data."""
    with patch(
        "homeassistant.components.openAQ.config_flow.AQClient", new=MockAQClientSuccess
    ):
        yield
