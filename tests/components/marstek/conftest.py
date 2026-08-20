"""Fixtures for Marstek integration tests."""

import pytest

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.const import CONF_HOST

from . import (
    TEST_BLE_MAC,
    TEST_DEVICE_TYPE,
    TEST_HOST,
    TEST_MAC,
    TEST_VERSION,
    TEST_WIFI_MAC,
    TEST_WIFI_NAME,
)

from tests.common import MockConfigEntry


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
        },
        unique_id=TEST_MAC,
    )
