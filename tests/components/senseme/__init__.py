"""Tests for the SenseME integration."""

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

from aiosenseme import SensemeDevice, SensemeDiscovery

from homeassistant.components.senseme import config_flow

MOCK_NAME = "Haiku Fan"
MOCK_UUID = "77a6b7b3-925d-4695-a415-76d76dca4444"
MOCK_ADDRESS = "127.0.0.1"

MOCK_DEVICE = MagicMock(auto_spec=SensemeDevice)
MOCK_DEVICE.name = MOCK_NAME
MOCK_DEVICE.uuid = MOCK_UUID
MOCK_DEVICE.address = MOCK_ADDRESS
MOCK_DEVICE.get_device_info = {
    "name": MOCK_NAME,
    "uuid": MOCK_UUID,
    "mac": "20:F8:5E:92:5A:75",
    "address": MOCK_ADDRESS,
    "base_model": "FAN,HAIKU,HSERIES",
    "has_light": False,
    "has_sensor": True,
    "is_fan": True,
    "is_light": False,
}


def _patch_discovery(device=None, no_device=None):
    """Patch discovery."""
    mock_senseme_discovery = MagicMock(auto_spec=SensemeDiscovery)
    if not no_device:
        mock_senseme_discovery.devices = [device or MOCK_DEVICE]

    @contextmanager
    def _patcher():

        with patch.object(config_flow, "DISCOVER_TIMEOUT", 0), patch(
            "homeassistant.components.senseme.discovery.SensemeDiscovery",
            return_value=mock_senseme_discovery,
        ):
            yield

    return _patcher()
