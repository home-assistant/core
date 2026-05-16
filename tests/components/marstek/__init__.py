"""Tests for the Marstek integration."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

from pymarstek.data_parser import (
    merge_device_status,
    parse_es_mode_response,
    parse_pv_status_response,
)

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

    async def send_request_mock(message, *args, **kwargs):
        """Mock send_request to return appropriate response based on method."""
        try:
            if isinstance(message, str):
                msg = json.loads(message)
            else:
                msg = message
            method = msg.get("method", "")
            if method == "ES.GetMode":
                return MOCK_ES_MODE_RESPONSE
            if method == "PV.GetStatus":
                return MOCK_PV_STATUS_RESPONSE
        except (json.JSONDecodeError, KeyError, AttributeError, TypeError):
            pass
        return MOCK_ES_MODE_RESPONSE

    async def pause_polling_mock(*args, **kwargs):
        pass

    async def resume_polling_mock(*args, **kwargs):
        pass

    async def get_device_status_mock(*args, **kwargs):
        """Mock get_device_status method."""
        es_data = parse_es_mode_response(MOCK_ES_MODE_RESPONSE)
        pv_data = parse_pv_status_response(MOCK_PV_STATUS_RESPONSE)
        return merge_device_status(
            es_mode_data=es_data,
            pv_status_data=pv_data,
            device_ip=TEST_HOST,
            last_update=0.0,
        )

    # Prevent _listen_for_responses from being called
    mock_client._listen_task = None
    mock_client._loop = None
    mock_client._socket = None
    mock_client._pending_requests = {}
    mock_client._response_cache = {}

    mock_client.async_setup = AsyncMock(side_effect=async_setup_mock)
    mock_client.async_cleanup = AsyncMock(side_effect=async_cleanup_mock)
    mock_client.send_request = AsyncMock(side_effect=send_request_mock)
    mock_client.get_device_status = AsyncMock(side_effect=get_device_status_mock)
    mock_client.send_broadcast_request = AsyncMock(return_value=[])
    mock_client.discover_devices = AsyncMock(return_value=[])
    mock_client.pause_polling = AsyncMock(side_effect=pause_polling_mock)
    mock_client.resume_polling = AsyncMock(side_effect=resume_polling_mock)
    mock_client.is_polling_paused = MagicMock(return_value=False)
    mock_client.clear_discovery_cache = MagicMock()
    return mock_client
