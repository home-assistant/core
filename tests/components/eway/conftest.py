"""Test configuration for Eway integration."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.config_entries import ConfigEntry

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Import from the integration using relative path
try:
    from homeassistant.components.eway.const import (
        CONF_DEVICE_ID,
        CONF_DEVICE_MODEL,
        CONF_DEVICE_SN,
        CONF_KEEPALIVE,
        CONF_MQTT_HOST,
        CONF_MQTT_PASSWORD,
        CONF_MQTT_PORT,
        CONF_MQTT_USERNAME,
        CONF_SCAN_INTERVAL,
        DOMAIN,
    )
except ImportError:
    # Fallback to direct import from const.py
    from homeassistant.components.eway.const import (
        CONF_DEVICE_ID,
        CONF_DEVICE_MODEL,
        CONF_DEVICE_SN,
        CONF_KEEPALIVE,
        CONF_MQTT_HOST,
        CONF_MQTT_PASSWORD,
        CONF_MQTT_PORT,
        CONF_MQTT_USERNAME,
        CONF_SCAN_INTERVAL,
        DOMAIN,
    )


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Return a mock config entry."""
    return ConfigEntry(
        version=1,
        minor_version=1,
        domain=DOMAIN,
        title="Test Eway Inverter",
        data={
            CONF_MQTT_HOST: "test.mqtt.broker",
            CONF_MQTT_PORT: 1883,
            CONF_MQTT_USERNAME: "test_user",
            CONF_MQTT_PASSWORD: "test_password",
            CONF_DEVICE_ID: "test_device_id",
            CONF_DEVICE_SN: "test_device_sn",
            CONF_DEVICE_MODEL: "test_model",
            CONF_SCAN_INTERVAL: 30,
            CONF_KEEPALIVE: 60,
        },
        options={},
        source="user",
        entry_id="test_entry_id",
        unique_id="test_unique_id",
        discovery_keys={},
        subentries_data={},
    )


@pytest.fixture
def mock_device_info() -> dict[str, Any]:
    """Return mock device info data."""
    return {
        "netFirmVer": 1.2,
        "appFirmVer": 2.1,
        "wifiSsid": "TestWiFi",
        "ip": "192.168.1.100",
        "wifiIsNormal": 0,
        "isLock": 0,
        "board": [{"id": 1, "type": "inverter"}],
    }


@pytest.fixture
def mock_device_data() -> list[dict[str, Any]]:
    """Return mock device data."""
    return [
        {
            "sort": 1,
            "inputVoltage": 240.5,
            "InputCurrent": 5.2,
            "gridVoltage": 230.1,
            "gridFreq": 50.0,
            "genPower": 1250.0,
            "genPowerToDay": 5500,
            "genPowerTotal": 12500,
            "temperature": 45.2,
            "errCode": 0,
            "duration": 3600,
        }
    ]


class MockDeviceInfo:
    """Mock DeviceInfo class."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize with device data."""
        self.net_firm_ver = data.get("netFirmVer", 0.0)
        self.app_firm_ver = data.get("appFirmVer", 0.0)
        self.wifi_ssid = data.get("wifiSsid", "")
        self.ip = data.get("ip", "")
        self.wifi_is_normal = data.get("wifiIsNormal", 1)
        self.is_lock = data.get("isLock", 1)
        self.board = data.get("board", [])

    @classmethod
    def from_dict(cls, data: dict) -> MockDeviceInfo:
        """Create MockDeviceData instance from dictionary.

        Args:
            data: Dictionary containing device data.

        Returns:
            MockDeviceData: New instance created from the provided data.

        """
        return cls(data)


class MockDeviceData:
    """Mock DeviceData class."""

    def __init__(self, data: dict[str, Any]) -> None:
        """Initialize MockDeviceData with device data.

        Args:
        data: Dictionary containing device data with keys like 'sort',
              'inputVoltage', 'InputCurrent', etc.

        """
        self.sort = data.get("sort", 0)
        self.input_voltage = data.get("inputVoltage", 0.0)
        self.input_current = data.get("InputCurrent", 0.0)
        self.grid_voltage = data.get("gridVoltage", 0.0)
        self.grid_freq = data.get("gridFreq", 0.0)
        self.gen_power = data.get("genPower", 0.0)
        self.gen_power_today = data.get("genPowerToDay", 0)
        self.gen_power_total = data.get("genPowerTotal", 0)
        self.temperature = data.get("temperature", 0.0)
        self.err_code = data.get("errCode", 0)
        self.duration = data.get("duration", 0)

    @classmethod
    def from_dict(cls, data: dict) -> MockDeviceData:
        """Create MockDeviceData instance from dictionary.

        Args:
            data: Dictionary containing device data.

        Returns:
            MockDeviceData: New instance created from the provided data.

        """
        return cls(data)


class MockDeviceMQTTClient:
    """Mock MQTT client for testing."""

    def __init__(self, *args, **kwargs) -> None:
        """Initialize MockDeviceMQTTClient with connection parameters.

        Args:
            *args: Variable length argument list (unused).
            **kwargs: Arbitrary keyword arguments including:
                device_model (str): Device model name, defaults to 'test_model'.
                device_sn (str): Device serial number, defaults to 'test_sn'.
                broker_host (str): MQTT broker host, defaults to 'localhost'.
                broker_port (int): MQTT broker port, defaults to 1883.
                username (str): MQTT username, defaults to 'test'.
                password (str): MQTT password, defaults to 'test'.
                keepalive (int): MQTT keepalive interval, defaults to 60.
                use_tls (bool): Whether to use TLS, defaults to True.

        """
        self.device_model = kwargs.get("device_model", "test_model")
        self.device_sn = kwargs.get("device_sn", "test_sn")
        self.broker_host = kwargs.get("broker_host", "localhost")
        self.broker_port = kwargs.get("broker_port", 1883)
        self.username = kwargs.get("username", "test")
        self.password = kwargs.get("password", "test")
        self.keepalive = kwargs.get("keepalive", 60)
        self.use_tls = kwargs.get("use_tls", True)

        self.is_connected = False
        self.device_info_callbacks = {}
        self.device_data_callbacks = {}

        # Mock data for testing
        self._mock_device_info = None
        self._mock_device_data = None

        self.connect = AsyncMock(return_value=True)
        self.request_device_data_and_wait = AsyncMock()
        self.request_device_info_and_wait = AsyncMock()
        self.disconnect = AsyncMock()
        self.subscribe_device_info = AsyncMock()
        self.subscribe_device_data = AsyncMock()
        self.start_monitoring = AsyncMock()

    async def disconnect(self):
        """Mock disconnect method."""
        self.is_connected = False

    async def subscribe_device_info(self, device_id: str, device_sn: str, callback):
        """Mock subscribe device info."""
        device_key = f"{device_id}_{device_sn}"
        self.device_info_callbacks[device_key] = callback

    async def subscribe_device_data(self, device_id: str, device_sn: str, callback):
        """Mock subscribe device data."""
        device_key = f"{device_id}_{device_sn}"
        self.device_data_callbacks[device_key] = callback

    async def request_device_info_and_wait(
        self, device_id: str, device_sn: str, timeout: float = 10.0
    ):
        """Mock request device info."""
        if self._mock_device_info:
            return MockDeviceInfo.from_dict(self._mock_device_info)
        return None

    async def request_device_data_and_wait(
        self, device_id: str, device_sn: str, timeout: float = 10.0
    ):
        """Mock request device data."""
        if self._mock_device_data:
            return [MockDeviceData.from_dict(data) for data in self._mock_device_data]
        return None

    def set_mock_device_info(self, device_info: dict[str, Any]):
        """Set mock device info for testing."""
        self._mock_device_info = device_info

    def set_mock_device_data(self, device_data: list[dict[str, Any]]):
        """Set mock device data for testing."""
        self._mock_device_data = device_data

    async def start_monitoring(
        self,
        device_id: str,
        device_sn: str,
        data_callback,
        info_callback,
        data_interval: int = 60,
    ):
        """Mock start monitoring method."""
        # Store callbacks for potential use in tests
        device_key = f"{device_id}_{device_sn}"
        self.device_data_callbacks[device_key] = data_callback
        self.device_info_callbacks[device_key] = info_callback

        # Optionally simulate immediate callback execution
        if self._mock_device_data:
            device_data_list = [
                MockDeviceData.from_dict(data) for data in self._mock_device_data
            ]
            await data_callback(device_data_list)

        if self._mock_device_info:
            device_info = MockDeviceInfo.from_dict(self._mock_device_info)
            await info_callback(device_info)


@pytest.fixture
def mock_mqtt_client():
    """Return a mock MQTT client."""
    return MockDeviceMQTTClient()


@pytest.fixture
def mock_aioeway_module(mock_mqtt_client, mock_device_info, mock_device_data):
    """Mock the aioeway module."""
    mock_mqtt_client.set_mock_device_info(mock_device_info)
    mock_mqtt_client.set_mock_device_data(mock_device_data)

    with patch(
        "homeassistant.components.eway.coordinator.device_mqtt_client"
    ) as mock_device_mqtt_client:
        mock_device_mqtt_client.DeviceMQTTClient.return_value = mock_mqtt_client
        mock_device_mqtt_client.DeviceInfo = MockDeviceInfo
        mock_device_mqtt_client.DeviceData = MockDeviceData
        yield mock_device_mqtt_client


@pytest.fixture
def mock_aioeway_import():
    """Mock aioeway import in config_flow."""
    with patch(
        "homeassistant.components.eway.config_flow.device_mqtt_client"
    ) as mock_device_mqtt_client:
        mock_client = MockDeviceMQTTClient()
        mock_device_mqtt_client.DeviceMQTTClient.return_value = mock_client
        yield mock_device_mqtt_client
