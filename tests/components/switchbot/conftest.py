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
            "e78943999999": {
                "mac_address": "e7:89:43:99:99:99",
                "isEncrypted": False,
                "model": "H",
                "data": {
                    "switchMode": "true",
                    "isOn": "true",
                    "battery": 91,
                    "rssi": -71,
                },
                "modelName": "WoHand",
            },
            "e78943909090": {
                "mac_address": "e7:89:43:90:90:90",
                "isEncrypted": False,
                "model": "c",
                "data": {
                    "calibration": True,
                    "battery": 74,
                    "inMotion": False,
                    "position": 100,
                    "lightLevel": 2,
                    "deviceChain": 1,
                    "rssi": -73,
                },
                "modelName": "WoCurtain",
            },
            "ffffff19ffff": {
                "mac_address": "ff:ff:ff:19:ff:ff",
                "isEncrypted": False,
                "model": "m",
                "rawAdvData": "000d6d00",
            },
        }
        self._curtain_all_services_data = {
            "mac_address": "e7:89:43:90:90:90",
            "isEncrypted": False,
            "model": "c",
            "data": {
                "calibration": True,
                "battery": 74,
                "position": 100,
                "lightLevel": 2,
                "rssi": -73,
            },
            "modelName": "WoCurtain",
        }
        self._unsupported_device = {
            "mac_address": "test",
            "isEncrypted": False,
            "model": "HoN",
            "data": {
                "switchMode": "true",
                "isOn": "true",
                "battery": 91,
                "rssi": -71,
            },
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

        yield mock_switchbot
