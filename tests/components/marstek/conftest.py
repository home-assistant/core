"""Fixtures for Marstek tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.marstek.const import DOMAIN

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_DEVICE_TYPE = "ES5"
TEST_VERSION = 1
TEST_WIFI_NAME = "TestWiFi"
TEST_WIFI_MAC = "AA:BB:CC:DD:EE:FF"
TEST_BLE_MAC = "11:22:33:44:55:66"

MOCK_DEVICE_INFO = {
    "id": 0,
    "device": TEST_DEVICE_TYPE,
    "ver": TEST_VERSION,
    "wifi_name": TEST_WIFI_NAME,
    "ip": TEST_HOST,
    "wifi_mac": TEST_WIFI_MAC,
    "ble_mac": TEST_BLE_MAC,
}

MOCK_DISCOVERY_RESPONSE = {
    "id": 1,
    "result": MOCK_DEVICE_INFO,
}


def create_mock_udp_client() -> MagicMock:
    """Create a mocked MarstekUDPClient."""
    mock_client = MagicMock()

    async def async_setup_mock() -> None:
        pass

    async def async_cleanup_mock() -> None:
        pass

    async def send_request_mock(*args, **kwargs) -> dict[str, object]:
        return {"id": 1, "result": {}}

    async def get_device_info_mock(*args, **kwargs) -> dict[str, object]:
        return MOCK_DEVICE_INFO.copy()

    async def get_device_status_mock(*args, **kwargs) -> dict[str, object]:
        return {
            "battery_soc": 85,
            "battery_power": 1300,
            "device_mode": "Manual",
            "battery_status": "Charging",
            "device_ip": TEST_HOST,
            "pv1_power": 500,
            "pv1_voltage": 48,
            "pv1_current": 10,
            "pv1_state": 1,
        }

    async def pause_polling_mock(*args, **kwargs) -> None:
        pass

    async def resume_polling_mock(*args, **kwargs) -> None:
        pass

    mock_client.async_setup = AsyncMock(side_effect=async_setup_mock)
    mock_client.async_cleanup = AsyncMock(side_effect=async_cleanup_mock)
    mock_client.send_request = AsyncMock(side_effect=send_request_mock)
    mock_client.get_device_info = AsyncMock(side_effect=get_device_info_mock)
    mock_client.get_device_status = AsyncMock(side_effect=get_device_status_mock)
    mock_client.send_broadcast_request = AsyncMock(return_value=[])
    mock_client.discover_devices = AsyncMock(return_value=[])
    mock_client.pause_polling = AsyncMock(side_effect=pause_polling_mock)
    mock_client.resume_polling = AsyncMock(side_effect=resume_polling_mock)
    mock_client.is_polling_paused = MagicMock(return_value=False)
    mock_client.clear_discovery_cache = MagicMock()
    mock_client.get_discovery_cache = MagicMock(return_value=None)
    mock_client.set_broadcast_addresses = MagicMock()
    mock_client._socket = MagicMock()
    return mock_client


@pytest.fixture(autouse=True)
def mock_udp_client() -> Generator[MagicMock]:
    """Mock the Marstek UDP client factory."""
    mock_client = create_mock_udp_client()
    with (
        patch(
            "homeassistant.components.marstek.async_create_udp_client",
            new=AsyncMock(return_value=mock_client),
        ),
        patch(
            "homeassistant.components.marstek.config_flow.async_create_udp_client",
            new=AsyncMock(return_value=mock_client),
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a Marstek config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_HOST})",
        unique_id=TEST_MAC,
        data={
            "host": TEST_HOST,
            "mac": TEST_MAC,
            "device_type": TEST_DEVICE_TYPE,
            "version": TEST_VERSION,
            "wifi_name": TEST_WIFI_NAME,
            "wifi_mac": TEST_WIFI_MAC,
            "ble_mac": TEST_BLE_MAC,
        },
    )
