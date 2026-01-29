"""Fixtures for Marstek integration tests."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import (
    MOCK_DEVICE_INFO,
    MOCK_ES_MODE_RESPONSE,
    MOCK_PV_STATUS_RESPONSE,
    TEST_BLE_MAC,
    TEST_DEVICE_TYPE,
    TEST_HOST,
    TEST_MAC,
    TEST_VERSION,
    TEST_WIFI_MAC,
    TEST_WIFI_NAME,
    create_mock_udp_client,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    return


@pytest.fixture(autouse=True)
def mock_socket():
    """Mock socket globally to prevent SocketBlockedError."""
    with patch("socket.socket") as mock_sock:
        mock_instance = MagicMock()
        mock_sock.return_value = mock_instance
        mock_instance.bind = MagicMock()
        mock_instance.setsockopt = MagicMock()
        mock_instance.setblocking = MagicMock()
        mock_instance.sendto = MagicMock()
        mock_instance.close = MagicMock()
        mock_instance.getsockname = MagicMock(return_value=("0.0.0.0", 30000))
        # Make socket appear non-blocking for asyncio
        mock_instance.getblocking = MagicMock(return_value=False)
        yield mock_instance


@pytest.fixture
def mock_udp_client() -> MagicMock:
    """Mock UDP client fixture."""
    return create_mock_udp_client()


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Marstek {TEST_DEVICE_TYPE} v{TEST_VERSION} ({TEST_HOST})",
        data={
            CONF_HOST: TEST_HOST,
            "mac": TEST_MAC,
            "device_type": TEST_DEVICE_TYPE,
            "version": TEST_VERSION,
            "wifi_name": TEST_WIFI_NAME,
            "wifi_mac": TEST_WIFI_MAC,
            "ble_mac": TEST_BLE_MAC,
            "model": TEST_DEVICE_TYPE,
            "firmware": str(TEST_VERSION),
        },
        unique_id=TEST_HOST,
    )


@pytest.fixture
def mock_device_info() -> dict:
    """Create mock device info."""
    return MOCK_DEVICE_INFO.copy()


@pytest.fixture
def mock_discovery_response(mock_device_info: dict) -> dict:
    """Create mock discovery response."""
    return {
        "id": 1,
        "result": mock_device_info,
    }


@pytest.fixture
def mock_es_mode_response() -> dict:
    """Create mock ES.GetMode response."""
    return MOCK_ES_MODE_RESPONSE.copy()


@pytest.fixture
def mock_pv_status_response() -> dict:
    """Create mock PV.GetStatus response."""
    return MOCK_PV_STATUS_RESPONSE.copy()
