"""OpenDisplay test fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.opendisplay.const import CONF_ENCRYPTION_KEY, DOMAIN

from . import DEVICE_CONFIG, ENCRYPTION_KEY, FIRMWARE_VERSION, TEST_ADDRESS, TEST_TITLE

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


@pytest.fixture
def mock_opendisplay_device_class() -> Generator[MagicMock]:
    """Yield the OpenDisplayDevice class mock (for asserting constructor args)."""
    with (
        patch(
            "homeassistant.components.opendisplay.OpenDisplayDevice",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.opendisplay.config_flow.OpenDisplayDevice",
            new=mock_class,
        ),
        patch(
            "homeassistant.components.opendisplay.services.OpenDisplayDevice",
            new=mock_class,
        ),
    ):
        mock_device = mock_class.return_value
        mock_device.__aenter__.return_value = mock_device
        mock_device.read_firmware_version.return_value = FIRMWARE_VERSION
        mock_device.config = DEVICE_CONFIG
        mock_device.is_flex = True
        yield mock_class


@pytest.fixture(autouse=True)
def mock_opendisplay_device(mock_opendisplay_device_class: MagicMock) -> MagicMock:
    """Mock the OpenDisplayDevice for setup entry; yields the instance mock."""
    return mock_opendisplay_device_class.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Create a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )


@pytest.fixture
def mock_encrypted_config_entry() -> MockConfigEntry:
    """Create a mock config entry with an encryption key."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={CONF_ENCRYPTION_KEY: ENCRYPTION_KEY},
    )
