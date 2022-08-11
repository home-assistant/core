"""Inels switch testing."""
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture(autouse=True)
def setup(request):
    """Test setting up creates mqtt connection and device."""
    with patch(
        "inelsmqtt.InelsMqtt", return_value=MagicMock()
    ) as mock_inels_mqtt, patch(
        "inelsmqtt.device.Device",
        return_value=Mock(
            mqtt=mock_inels_mqtt,
            state_topic="inels/status/7777888/02/458745",
            title="mock-switch",
        ),
    ):
        yield
