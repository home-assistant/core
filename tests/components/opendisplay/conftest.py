"""OpenDisplay test fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

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
    """Mock the BLE device being visible."""
    ble_device = generate_ble_device(TEST_ADDRESS, TEST_TITLE)
    with (
        patch(
            "homeassistant.components.opendisplay.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.opendisplay.config_flow.async_ble_device_from_address",
            return_value=ble_device,
        ),
        patch(
            "homeassistant.components.opendisplay.services.async_ble_device_from_address",
            return_value=ble_device,
        ),
    ):
        yield


@pytest.fixture(autouse=True)
def mock_opendisplay_device() -> Generator[MagicMock]:
    """Mock the OpenDisplayDevice for setup entry."""
    with (
        patch(
            "homeassistant.components.opendisplay.OpenDisplayDevice",
            autospec=True,
        ) as mock_device_init,
        patch(
            "homeassistant.components.opendisplay.config_flow.OpenDisplayDevice",
            new=mock_device_init,
        ),
        patch(
            "homeassistant.components.opendisplay.services.OpenDisplayDevice",
            new=mock_device_init,
        ),
    ):
        mock_device = mock_device_init.return_value
        mock_device.__aenter__.return_value = mock_device
        mock_device.read_firmware_version.return_value = FIRMWARE_VERSION
        mock_device.config = DEVICE_CONFIG
        mock_device.is_flex = True
        yield mock_device


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )
