"""OpenDisplay test fixtures."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.opendisplay.const import CONF_ENCRYPTION_KEY, DOMAIN

from . import (
    BUTTON_DEVICE_CONFIG,
    DEVICE_CONFIG,
    ENCRYPTION_KEY,
    FIRMWARE_VERSION,
    TEST_ADDRESS,
    TEST_TITLE,
    make_binary_inputs,
    make_button_device_config,
)

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
def mock_button_config_entry(mock_opendisplay_device: MagicMock) -> MockConfigEntry:
    """Create a mock config entry for a device with one button configured."""
    mock_opendisplay_device.config = BUTTON_DEVICE_CONFIG
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )


@pytest.fixture
def mock_two_button_config_entry(mock_opendisplay_device: MagicMock) -> MockConfigEntry:
    """Create a mock config entry for a device with two buttons configured."""
    mock_opendisplay_device.config = make_button_device_config(
        [make_binary_inputs(input_flags=0x03)]
    )
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )


@pytest.fixture
def mock_three_button_config_entry(
    mock_opendisplay_device: MagicMock,
) -> MockConfigEntry:
    """Create a mock config entry for a device with three buttons configured."""
    mock_opendisplay_device.config = make_button_device_config(
        [make_binary_inputs(input_flags=0x07)]
    )
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_ADDRESS,
        title=TEST_TITLE,
        data={},
    )


@pytest.fixture
def mock_multi_instance_config_entry(
    mock_opendisplay_device: MagicMock,
) -> MockConfigEntry:
    """Create a mock config entry with two binary_inputs instances.

    Instance 0: byte_index=0, buttons 0 and 1 active → Button 1, Button 2
    Instance 1: byte_index=1, button 0 active        → Button 3
    """
    mock_opendisplay_device.config = make_button_device_config(
        [
            make_binary_inputs(instance_number=0, byte_index=0, input_flags=0x03),
            make_binary_inputs(instance_number=1, byte_index=1, input_flags=0x01),
        ]
    )
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
