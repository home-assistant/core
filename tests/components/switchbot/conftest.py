"""Define fixtures available for all tests."""
import sys
from unittest.mock import MagicMock, patch

from pytest import fixture


class MocGetSwitchbotDevices:
    """Scan for all Switchbot devices and return by type."""

    def __init__(self, interface=None) -> None:
        """Get switchbot devices class constructor."""
        self._interface = interface
        self._all_services_data = True

    def discover(self, retry=0, scan_timeout=0):
        """Mock discover."""
        return self._all_services_data

    def get_device_data(self, mac):
        """Return data for specific device."""
        return self._all_services_data


class MocNotConnectedError(Exception):
    """Mock exception."""


module = type(sys)("switchbot")
module.GetSwitchbotDevices = MocGetSwitchbotDevices
module.NotConnectedError = MocNotConnectedError
sys.modules["switchbot"] = module


@fixture
def switchbot_config_flow(hass):
    """Mock the bluepy api for easier config flow testing."""
    with patch.object(MocGetSwitchbotDevices, "discover", return_value=True), patch(
        "homeassistant.components.switchbot.config_flow.GetSwitchbotDevices"
    ) as mock_switchbot:
        instance = mock_switchbot.return_value

        instance.discover = MagicMock(return_value=True)
        instance.get_device_data = MagicMock(return_value=True)

        yield mock_switchbot
