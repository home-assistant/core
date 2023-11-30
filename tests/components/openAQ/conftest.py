"""Provide common openAQ fixtures."""
from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_aq_client():
    """Fixture to create a basic mock AQClient."""
    with patch("homeassistant.components.openAQ.aq_client.AQClient") as mock_client:
        yield mock_client.return_value


@pytest.fixture
def mock_aq_client_for_config_flow(mock_aq_client):
    """Fixture to provide mocked AQClient with predefined data for config flow tests."""
    # Define standard mocked responses
    mock_aq_client.get_device.side_effect = [
        # Successful data retrieval
        AsyncMock(
            return_value=Mock(
                sensors=[
                    {
                        "type": "pm25",
                        "value": 15,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                    {
                        "type": "pm10",
                        "value": 20,
                        "last_updated": "2023-11-30T12:00:00",
                    },
                ],
                locality="Example City",
            )
        ),
        # Location not found
        AsyncMock(return_value=Mock(sensors=[], locality="")),
        # Invalid API key (assuming exception handling)
        AsyncMock(side_effect=Exception("Invalid API key")),
        # No sensor data available
        AsyncMock(return_value=Mock(sensors=[], locality="Example City")),
        # Add more scenarios as required
    ]
    return mock_aq_client
