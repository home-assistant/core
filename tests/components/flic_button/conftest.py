"""Flic Button test fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    DeviceType,
)
from homeassistant.const import CONF_ADDRESS, Platform

from . import (
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    create_flic2_service_info,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Flic Button config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({FLIC2_SERIAL})",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.FLIC2.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


@pytest.fixture
def mock_flic_client() -> Generator[MagicMock]:
    """Mock FlicClient for testing."""
    with patch(
        "homeassistant.components.flic_button.FlicClient", autospec=True
    ) as mock_client_class:
        mock_client = mock_client_class.return_value

        # Basic properties
        mock_client.address = FLIC2_ADDRESS
        mock_client.is_connected = True
        mock_client.is_duo = False
        mock_client.is_twist = False
        mock_client.ble_device = create_flic2_service_info().device

        # Mock capabilities
        mock_capabilities = MagicMock()
        mock_capabilities.button_count = 1
        mock_capabilities.has_rotation = False
        mock_capabilities.has_selector = False
        mock_capabilities.has_frame_header = True
        mock_client.capabilities = mock_capabilities

        # Mock handler
        mock_handler = MagicMock()
        mock_handler.capabilities = mock_capabilities
        mock_client.handler = mock_handler

        # Async methods
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock()
        mock_client.full_verify_pairing = AsyncMock(
            return_value=(
                TEST_PAIRING_ID,
                TEST_PAIRING_KEY,
                FLIC2_SERIAL,
                TEST_BATTERY_LEVEL,
                TEST_SIG_BITS,
                None,
                10,
            )
        )
        mock_client.quick_verify = AsyncMock()
        mock_client.init_button_events = AsyncMock()
        mock_client.get_firmware_version = AsyncMock(return_value=10)
        mock_client.get_battery_level = AsyncMock(return_value=TEST_BATTERY_LEVEL)
        mock_client.get_battery_voltage = AsyncMock(
            return_value=TEST_BATTERY_LEVEL * 3.6 / 1024.0
        )
        mock_client.get_name = AsyncMock(return_value=("", 0))
        mock_client.set_name = AsyncMock(return_value=("", 0))
        mock_client.device_type = DeviceType.FLIC2

        # Event callbacks
        mock_client.on_button_event = None
        mock_client.on_rotate_event = None
        mock_client.on_selector_change = None
        mock_client.on_disconnect = None

        yield mock_client


@pytest.fixture
def mock_ble_device_from_address() -> Generator[MagicMock]:
    """Mock async_ble_device_from_address."""
    service_info = create_flic2_service_info()
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device,
    ) as mock:
        yield mock


@pytest.fixture
def platforms() -> list[Platform]:
    """Return list of platforms to test."""
    return [Platform.EVENT]
