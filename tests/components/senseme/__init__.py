"""Tests for the SenseME integration."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from aiosenseme import SensemeDevice, SensemeDiscovery

from homeassistant.components.senseme import config_flow

MOCK_NAME = "Haiku Fan"
MOCK_UUID = "77a6b7b3-925d-4695-a415-76d76dca4444"
MOCK_ADDRESS = "127.0.0.1"
MOCK_MAC = "20:F8:5E:92:5A:75"


def _mock_device():
    device = MagicMock(auto_spec=SensemeDevice)
    device.async_update = AsyncMock()
    device.model = "Haiku Fan"
    device.fan_speed_max = 7
    device.mac = "aa:bb:cc:dd:ee:ff"
    device.fan_dir = "REV"
    device.has_light = True
    device.is_light = False
    device.light_brightness = 50
    device.room_name = "Main"
    device.room_type = "Main"
    device.fw_version = "1"
    device.fan_autocomfort = "COOLING"
    device.fan_smartmode = "OFF"
    device.fan_whoosh_mode = "on"
    device.name = MOCK_NAME
    device.uuid = MOCK_UUID
    device.address = MOCK_ADDRESS
    device.get_device_info = {
        "name": MOCK_NAME,
        "uuid": MOCK_UUID,
        "mac": MOCK_ADDRESS,
        "address": MOCK_ADDRESS,
        "base_model": "FAN,HAIKU,HSERIES",
        "has_light": False,
        "has_sensor": True,
        "is_fan": True,
        "is_light": False,
    }
    return device


device_alternate_ip = MagicMock(auto_spec=SensemeDevice)
device_alternate_ip.async_update = AsyncMock()
device_alternate_ip.model = "Haiku Fan"
device_alternate_ip.fan_speed_max = 7
device_alternate_ip.mac = "aa:bb:cc:dd:ee:ff"
device_alternate_ip.fan_dir = "REV"
device_alternate_ip.room_name = "Main"
device_alternate_ip.room_type = "Main"
device_alternate_ip.fw_version = "1"
device_alternate_ip.fan_autocomfort = "on"
device_alternate_ip.fan_smartmode = "on"
device_alternate_ip.fan_whoosh_mode = "on"
device_alternate_ip.name = MOCK_NAME
device_alternate_ip.uuid = MOCK_UUID
device_alternate_ip.address = "127.0.0.8"
device_alternate_ip.get_device_info = {
    "name": MOCK_NAME,
    "uuid": MOCK_UUID,
    "mac": "20:F8:5E:92:5A:75",
    "address": "127.0.0.8",
    "base_model": "FAN,HAIKU,HSERIES",
    "has_light": False,
    "has_sensor": True,
    "is_fan": True,
    "is_light": False,
}


device2 = MagicMock(auto_spec=SensemeDevice)
device2.async_update = AsyncMock()
device2.model = "Haiku Fan"
device2.fan_speed_max = 7
device2.mac = "aa:bb:cc:dd:ee:ff"
device2.fan_dir = "FWD"
device2.room_name = "Main"
device2.room_type = "Main"
device2.fw_version = "1"
device2.fan_autocomfort = "on"
device2.fan_smartmode = "on"
device2.fan_whoosh_mode = "on"
device2.name = "Device 2"
device2.uuid = "uuid2"
device2.address = "127.0.0.2"
device2.get_device_info = {
    "name": "Device 2",
    "uuid": "uuid2",
    "mac": "20:F8:5E:92:5A:76",
    "address": "127.0.0.2",
    "base_model": "FAN,HAIKU,HSERIES",
    "has_light": True,
    "has_sensor": True,
    "is_fan": True,
    "is_light": False,
}

device_no_uuid = MagicMock(auto_spec=SensemeDevice)
device_no_uuid.uuid = None


MOCK_DEVICE = _mock_device()
MOCK_DEVICE_ALTERNATE_IP = device_alternate_ip
MOCK_DEVICE2 = device2
MOCK_DEVICE_NO_UUID = device_no_uuid


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


def _patch_device(device=None, no_device=False):
    async def _device_mocker(*args, **kwargs):
        if no_device:
            return False, None
        if device:
            return True, device
        return True, _mock_device()

    return patch(
        "homeassistant.components.senseme.async_get_device_by_device_info",
        new=_device_mocker,
    )
