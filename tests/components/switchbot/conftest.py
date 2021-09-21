"""Define fixtures available for all tests."""
import sys
from unittest.mock import MagicMock, patch

from pytest import fixture


class MocGetSwitchbotDevices:
    """Scan for all Switchbot devices and return by type."""

    def __init__(self, interface=None) -> None:
        """Get switchbot devices class constructor."""
        self._interface = interface
        self._all_services_data = {
            "mac_address": "e7:89:43:99:99:99",
            "Flags": "06",
            "Manufacturer": "5900e78943d9fe7c",
            "Complete 128b Services": "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
            "data": {
                "switchMode": "true",
                "isOn": "true",
                "battery": 91,
                "rssi": -71,
            },
            "model": "H",
            "modelName": "WoHand",
        }
        self._curtain_all_services_data = {
            "mac_address": "e7:89:43:90:90:90",
            "Flags": "06",
            "Manufacturer": "5900e78943d9fe7c",
            "Complete 128b Services": "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
            "data": {
                "calibration": True,
                "battery": 74,
                "position": 100,
                "lightLevel": 2,
                "rssi": -73,
            },
            "model": "c",
            "modelName": "WoCurtain",
        }
        self._unsupported_device = {
            "mac_address": "test",
            "Flags": "06",
            "Manufacturer": "5900e78943d9fe7c",
            "Complete 128b Services": "cba20d00-224d-11e6-9fb8-0002a5d5c51b",
            "data": {
                "switchMode": "true",
                "isOn": "true",
                "battery": 91,
                "rssi": -71,
            },
            "model": "HoN",
            "modelName": "WoOther",
        }

    def discover(self, retry=0, scan_timeout=0):
        """Mock discover."""
        return self._all_services_data

    def get_device_data(self, mac=None):
        """Return data for specific device."""
        if mac == "e7:89:43:99:99:99":
            return self._all_services_data
        if mac == "test":
            return self._unsupported_device
        if mac == "e7:89:43:90:90:90":
            return self._curtain_all_services_data

        return None


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
