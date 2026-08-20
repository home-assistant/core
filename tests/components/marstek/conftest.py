"""Fixtures for Marstek tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.marstek.const import DOMAIN

from tests.common import MockConfigEntry

from . import create_mock_udp_client
from . import (
    TEST_BLE_MAC,
    TEST_DEVICE_TYPE,
    TEST_HOST,
    TEST_MAC,
    TEST_VERSION,
    TEST_WIFI_MAC,
    TEST_WIFI_NAME,
)


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
