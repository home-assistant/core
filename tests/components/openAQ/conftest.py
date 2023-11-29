"""Define test fixtures for openAQ."""
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_aq_client():
    """Return a mocked AQClient."""
    with patch("homeassistant.components.openAQ.aq_client.AQClient") as mock_client:
        mock_instance = MagicMock()
        mock_instance.get_device.return_value = MagicMock(sensors=[], locality="")
        mock_client.return_value = mock_instance
        yield mock_client
