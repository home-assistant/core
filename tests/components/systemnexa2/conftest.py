"""Fixtures for System Nexa 2 integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sn2 import InformationData, InformationUpdate


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
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(
            information=InformationData(
                name="Test Device",
                model="Test Model",
                unique_id="test_device_id",
                sw_version="Test Model Version",
                hw_version="Test HW Version",
                wifi_dbm=-50,
                wifi_ssid="Test WiFi SSID",
                dimmable=False,
            )
        )
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))

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
        device.get_info = AsyncMock()
        device.get_info.side_effect = RuntimeError
        mock_device.is_device_supported = MagicMock(return_value=(True, ""))

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
        device.get_info = AsyncMock()
        device.get_info.return_value = InformationUpdate(
            information=InformationData(
                name="Test Device",
                model="Test Model",
                unique_id="test_device_id",
                sw_version="Test Model Version",
                hw_version="Test HW Version",
                wifi_dbm=-50,
                wifi_ssid="Test WiFi SSID",
                dimmable=False,
            )
        )
        mock_device.is_device_supported = MagicMock(return_value=(False, "Err"))
        yield mock_device
