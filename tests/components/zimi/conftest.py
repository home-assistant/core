"""Test fixtures for Zimi component."""

from unittest.mock import MagicMock, patch

import pytest

INPUT_MAC = "aa:bb:cc:dd:ee:ff"


API_INFO = {
    "brand": "Zimi",
    "network_name": "Test Network",
    "firmware_version": "1.1.1",
}


@pytest.fixture
def mock_api():
    """Mock the API with defaults."""
    with patch("homeassistant.components.zimi.async_connect_to_controller") as mock:
        mock_api = mock.return_value
        mock_api.describe = MagicMock()
        mock_api.disconnect = MagicMock()
        mock_api.connect.return_value = True
        mock_api.mac = INPUT_MAC
        mock_api.brand = API_INFO["brand"]
        mock_api.network_name = API_INFO["network_name"]
        mock_api.firmware_version = API_INFO["firmware_version"]

        yield mock_api
