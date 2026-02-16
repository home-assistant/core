"""OpenDisplay test fixtures."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.opendisplay.const import DOMAIN

from . import DEVICE_CONFIG, FIRMWARE_VERSION, TEST_ADDRESS, TEST_TITLE

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_ble_device


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture(autouse=True)
def mock_ble_device() -> Generator[None]:
    """Mock the BLE device being visible and address present."""
    ble_device = generate_ble_device(TEST_ADDRESS, TEST_TITLE)
    with (
        patch(
            "homeassistant.components.opendisplay.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.opendisplay.image.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.opendisplay.entity.bluetooth.async_address_present",
            return_value=True,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_opendisplay_device() -> Generator[None]:
    """Mock the OpenDisplayDevice for setup entry."""
    mock_device = AsyncMock()
    mock_device.read_firmware_version = AsyncMock(return_value=FIRMWARE_VERSION)
    mock_device.interrogate = AsyncMock(return_value=DEVICE_CONFIG)
    mock_device.__aenter__ = AsyncMock(return_value=mock_device)
    mock_device.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.opendisplay.OpenDisplayDevice",
        return_value=mock_device,
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )
