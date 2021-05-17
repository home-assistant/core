"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

from pytest import fixture


# Mock pyswitchbot
class SwitchbotDevice:
    """Mock."""

    def __init__(self, mac, password=None) -> None:
        """Init moc class."""
        self._password = password
        self._mac = mac

    def _connect(self):
        """Mock class."""
        return bool(self._mac)

    def _disconnect(self):
        """Mock class."""
        return bool(self._mac)


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
