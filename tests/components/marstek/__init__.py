"""Tests for the Marstek integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

# Test constants
TEST_HOST = "192.168.1.100"
TEST_MAC = "AA:BB:CC:DD:EE:FF"
TEST_DEVICE_TYPE = "ES5"
TEST_VERSION = 1
TEST_WIFI_NAME = "TestWiFi"
TEST_WIFI_MAC = "AA:BB:CC:DD:EE:FF"
TEST_BLE_MAC = "11:22:33:44:55:66"

# Mock device responses
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

MOCK_ES_MODE_RESPONSE = {
    "id": 2,
    "result": {
        "mode": "Manual",
        "bat_soc": 85,
        "ongrid_power": -1300,
    },
}

MOCK_PV_STATUS_RESPONSE = {
    "id": 3,
    "result": {
        "pv1_power": 500,
        "pv1_voltage": 48,
        "pv1_current": 10,
        "pv1_state": 1,
        "pv2_power": 0,
        "pv2_voltage": 0,
        "pv2_current": 0,
        "pv2_state": 0,
        "pv3_power": 0,
        "pv3_voltage": 0,
        "pv3_current": 0,
        "pv3_state": 0,
        "pv4_power": 0,
        "pv4_voltage": 0,
        "pv4_current": 0,
        "pv4_state": 0,
    },
}


def create_mock_udp_client() -> MagicMock:
    """Create a mocked MarstekUDPClient."""
    mock_client = MagicMock()

    # Create async functions that actually work with create_task
    async def async_setup_mock():
        pass

    async def async_cleanup_mock():
        pass

    async def send_request_mock(*args, **kwargs):
        return {"id": 1, "result": {}}

    async def pause_polling_mock(*args, **kwargs):
        pass

    async def resume_polling_mock(*args, **kwargs):
        pass

    mock_client.async_setup = AsyncMock(side_effect=async_setup_mock)
    mock_client.async_cleanup = AsyncMock(side_effect=async_cleanup_mock)
    mock_client.send_request = AsyncMock(side_effect=send_request_mock)
    mock_client.send_broadcast_request = AsyncMock(return_value=[])
    mock_client.discover_devices = AsyncMock(return_value=[])
    mock_client.pause_polling = AsyncMock(side_effect=pause_polling_mock)
    mock_client.resume_polling = AsyncMock(side_effect=resume_polling_mock)
    mock_client.is_polling_paused = MagicMock(return_value=False)
    mock_client.clear_discovery_cache = MagicMock()
    mock_client._socket = MagicMock()
    return mock_client
