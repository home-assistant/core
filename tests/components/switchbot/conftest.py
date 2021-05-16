"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

from pytest import fixture
from switchbot import SwitchbotDevice


@fixture
def switchbot_config_flow(hass):
    """Mock the bluepy api for easier config flow testing."""
    with patch.object(SwitchbotDevice, "_connect", return_value=True), patch(
        "homeassistant.components.switchbot.config_flow.SwitchbotDevice"
    ) as mock_switchbot:
        instance = mock_switchbot.return_value = SwitchbotDevice(mac="test")

        # pylint: disable=protected-access
        instance._connect = MagicMock(return_value=True)

        yield mock_switchbot
