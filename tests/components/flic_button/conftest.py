"""Flic Button test fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pyflic_ble import DeviceType
import pytest

from homeassistant.components.flic_button.const import (
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
)
from homeassistant.const import CONF_ADDRESS

from . import (
    ADDRESS_FOR_DEVICE_TYPE,
    MODEL_NAME_FOR_DEVICE_TYPE,
    SERIAL_FOR_DEVICE_TYPE,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    service_info_for_device_type,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_bluetooth(enable_bluetooth: None) -> None:
    """Auto mock bluetooth."""


@pytest.fixture
def device_type() -> DeviceType:
    """Return the device type under test (override via parametrization)."""
    return DeviceType.FLIC2


@pytest.fixture
def mock_config_entry(device_type: DeviceType) -> MockConfigEntry:
    """Return a mock Flic Button config entry."""
    address = ADDRESS_FOR_DEVICE_TYPE[device_type]
    serial = SERIAL_FOR_DEVICE_TYPE[device_type]
    model = MODEL_NAME_FOR_DEVICE_TYPE[device_type]
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"{model} ({serial})",
        unique_id=address,
        data={
            CONF_ADDRESS: address,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: serial,
            CONF_DEVICE_TYPE: device_type.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.flic_button.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_flic_client(device_type: DeviceType) -> Generator[MagicMock]:
    """Mock FlicClient for the runtime integration and the config flow."""
    address = ADDRESS_FOR_DEVICE_TYPE[device_type]
    serial = SERIAL_FOR_DEVICE_TYPE[device_type]
    service_info = service_info_for_device_type(device_type)

    with (
        patch(
            "homeassistant.components.flic_button.FlicClient", autospec=True
        ) as mock_client_class,
        patch(
            "homeassistant.components.flic_button.config_flow.FlicClient",
            new=mock_client_class,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.address = address
        mock_client.is_connected = True
        mock_client.is_duo = device_type is DeviceType.DUO
        mock_client.is_twist = device_type is DeviceType.TWIST
        mock_client.ble_device = service_info.device
        mock_client.device_type = device_type

        mock_capabilities = MagicMock()
        mock_capabilities.button_count = 2 if device_type is DeviceType.DUO else 1
        mock_capabilities.has_rotation = device_type in (
            DeviceType.DUO,
            DeviceType.TWIST,
        )
        mock_capabilities.has_selector = device_type is DeviceType.TWIST
        mock_capabilities.has_frame_header = device_type is not DeviceType.TWIST
        mock_client.capabilities = mock_capabilities
        mock_client.handler = MagicMock(capabilities=mock_capabilities)

        mock_state = MagicMock()
        mock_state.connected = True
        mock_state.battery_voltage = TEST_BATTERY_LEVEL * 3.6 / 1024.0
        mock_state.firmware_version = 10
        mock_state.device_name = None
        mock_client.state = mock_state

        mock_client.full_verify_pairing.return_value = (
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            serial,
            TEST_BATTERY_LEVEL,
            TEST_SIG_BITS,
            None,
            10,
        )
        mock_client.get_firmware_version.return_value = 10
        mock_client.get_battery_level.return_value = TEST_BATTERY_LEVEL
        mock_client.get_battery_voltage.return_value = TEST_BATTERY_LEVEL * 3.6 / 1024.0
        mock_client.get_name.return_value = ("", 0)
        mock_client.set_name.return_value = ("", 0)

        mock_client.register_button_event_callback.return_value = lambda: None
        mock_client.register_rotate_event_callback.return_value = lambda: None
        mock_client.register_state_callback.return_value = lambda: None

        yield mock_client


@pytest.fixture
def mock_ble_device_from_address(
    device_type: DeviceType,
) -> Generator[MagicMock]:
    """Mock async_ble_device_from_address to return a matching BLE device."""
    service_info = service_info_for_device_type(device_type)
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device,
    ) as mock:
        yield mock


@pytest.fixture
def mock_no_ble_device_from_address() -> Generator[MagicMock]:
    """Mock async_ble_device_from_address to return None."""
    with patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=None,
    ) as mock:
        yield mock


@pytest.fixture
def mock_bluetooth_register_callback() -> Generator[MagicMock]:
    """Mock bluetooth.async_register_callback to capture and return a no-op."""
    with patch(
        "homeassistant.components.flic_button.bluetooth.async_register_callback",
        return_value=lambda: None,
    ) as mock:
        yield mock
