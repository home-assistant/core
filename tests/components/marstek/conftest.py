"""Fixtures for Marstek integration tests."""

from __future__ import annotations

from unittest.mock import MagicMock

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
        unique_id=TEST_MAC,
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
