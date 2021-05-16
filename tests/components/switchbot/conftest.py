"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

# pylint: disable=import-error
from bluepy.btle import Peripheral
from pytest import fixture


@fixture
def switchbot_config_flow(hass):
    """Mock the bluepy api for easier config flow testing."""
    with patch.object(Peripheral, "connect", return_value=True), patch(
        "homeassistant.components.switchbot.config_flow.btle.Peripheral"
    ) as mock_switchbot:
        instance = mock_switchbot.return_value = Peripheral()

        instance.connect = MagicMock(return_value=True)

        yield mock_switchbot
