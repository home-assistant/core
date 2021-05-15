"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

from bluepy import btle
from pytest import fixture


@fixture
def switchbot_config_flow(hass):
    """Mock the bluepy api for easier config flow testing."""
    with patch.object(btle, "Peripheral", return_value=True), patch(
        "homeassistant.components.switchbot.config_flow.btle"
    ) as mock_switchbot:
        instance = mock_switchbot.return_value

        instance.Peripheral = MagicMock(return_value=True)

        yield mock_switchbot
