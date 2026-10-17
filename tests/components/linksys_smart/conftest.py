"""Fixtures for Linksys Smart Wi-Fi."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from jnap import GetDeviceInfoResponse, GetDevicesResponse
import pytest

SERIAL = "38U10M37B21541"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.linksys_smart.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_jnap_client() -> Generator[AsyncMock]:
    """Mock the JNAPClient used by the config flow and coordinator."""
    with patch(
        "homeassistant.components.linksys_smart.util.JNAPClient",
        autospec=True,
    ) as mock_client_cls:
        client = mock_client_cls.return_value
        client.get_device_info.return_value = GetDeviceInfoResponse(
            description="Velop AX4200 WiFi 6 System", serial_number=SERIAL
        )
        client.get_devices.return_value = GetDevicesResponse(devices=[])
        yield client
