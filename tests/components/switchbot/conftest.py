"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

import pygatt
from pytest import fixture


@fixture
def switchbot_config_flow(hass):
    """Mock the bluepy api for easier config flow testing."""
    with patch.object(pygatt, "GATTToolBackend", return_value=True), patch(
        "homeassistant.components.switchbot.config_flow.pygatt.GATTToolBackend"
    ) as mock_switchbot:
        instance = mock_switchbot.return_value

        instance.GATTToolBackend = MagicMock(return_value=True)

        yield mock_switchbot
