"""Fixtures for System Nexa 2 integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sn2 import InformationData, InformationUpdate, OnOffSetting

from homeassistant.components.systemnexa2.const import DOMAIN
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry


@pytest.fixture
def mock_system_nexa_2_device() -> Generator[MagicMock]:
    """Mock the System Nexa 2 API."""
    with (
        patch("homeassistant.components.systemnexa2.coordinator.Device") as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name="Test Device",
            model="Test Model",
            unique_id="test_device_id",
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=-50,
            wifi_ssid="Test WiFi SSID",
            dimmable=False,
        )

        # Create mock OnOffSettings
        mock_setting_433mhz = MagicMock(spec=OnOffSetting)
        mock_setting_433mhz.name = "433Mhz"
        mock_setting_433mhz.enable = AsyncMock()
        mock_setting_433mhz.disable = AsyncMock()
        mock_setting_433mhz.is_enabled = MagicMock(return_value=True)

        mock_setting_cloud = MagicMock(spec=OnOffSetting)
        mock_setting_cloud.name = "Cloud Access"
        mock_setting_cloud.enable = AsyncMock()
        mock_setting_cloud.disable = AsyncMock()
        mock_setting_cloud.is_enabled = MagicMock(return_value=False)

        device.settings = [mock_setting_433mhz, mock_setting_cloud]
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(information=device.info_data)
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        device.turn_on = AsyncMock()
        device.turn_off = AsyncMock()
        device.toggle = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))
        mock_device.initiate_device = AsyncMock(return_value=device)

        yield mock_device


@pytest.fixture
def mock_system_nexa_2_device_timeout() -> Generator[MagicMock]:
    """Mock an System Nexa 2 device with connection issues."""
    with (
        patch("homeassistant.components.systemnexa2.coordinator.Device") as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name="Test Device",
            model="Test Model",
            unique_id="test_device_id",
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=-50,
            wifi_ssid="Test WiFi SSID",
            dimmable=False,
        )
        device.settings = []
        device.get_info = AsyncMock()
        device.get_info.side_effect = TimeoutError
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))
        mock_device.initiate_device = AsyncMock(return_value=device)

        yield mock_device


@pytest.fixture
def mock_system_nexa_2_device_unknown_error() -> Generator[MagicMock]:
    """Mock an System Nexa 2 device with connection issues."""
    with (
        patch("homeassistant.components.systemnexa2.coordinator.Device") as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name="Test Device",
            model="Test Model",
            unique_id="test_device_id",
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=-50,
            wifi_ssid="Test WiFi SSID",
            dimmable=False,
        )
        device.settings = []
        device.get_info = AsyncMock()
        device.get_info.side_effect = RuntimeError
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))
        mock_device.initiate_device = AsyncMock(return_value=device)

        yield mock_device


@pytest.fixture
def mock_system_nexa_2_device_unsupported() -> Generator[MagicMock]:
    """Mock an unsupported System Nexa 2 device."""
    with (
        patch("homeassistant.components.systemnexa2.coordinator.Device") as mock_device,
        patch(
            "homeassistant.components.systemnexa2.config_flow.Device", new=mock_device
        ),
    ):
        device = mock_device.return_value
        device.info_data = InformationData(
            name="Test Device",
            model="Test Model",
            unique_id="test_device_id",
            sw_version="Test Model Version",
            hw_version="Test HW Version",
            wifi_dbm=-50,
            wifi_ssid="Test WiFi SSID",
            dimmable=False,
        )
        device.settings = []
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(information=device.info_data)
        device.connect = AsyncMock()
        device.disconnect = AsyncMock()
        mock_device.is_device_supported = MagicMock(return_value=(False, "Err"))
        mock_device.initiate_device = AsyncMock(return_value=device)
        yield mock_device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "192.168.1.100"},
        unique_id="test_device_id",
    )


@pytest.fixture
def mock_patch_get_host():
    """Mock call to socket gethostbyname function."""
    with patch(
        "homeassistant.components.systemnexa2.config_flow.socket.gethostbyname",
        return_value="192.168.1.1",
    ) as get_host_mock:
        yield get_host_mock
