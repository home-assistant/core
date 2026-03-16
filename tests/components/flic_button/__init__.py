"""Tests for the Flic Button integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.bluetooth.models import BluetoothServiceInfoBleak
from homeassistant.components.flic_button.const import (
    CONF_BATTERY_LEVEL,
    CONF_DEVICE_TYPE,
    CONF_PAIRING_ID,
    CONF_PAIRING_KEY,
    CONF_SERIAL_NUMBER,
    CONF_SIG_BITS,
    DOMAIN,
    FLIC_SERVICE_UUID,
    TWIST_SERVICE_UUID,
    DeviceType,
)
from homeassistant.const import CONF_ADDRESS

from tests.common import MockConfigEntry
from tests.components.bluetooth import generate_advertisement_data, generate_ble_device

# Test Bluetooth address
FLIC2_ADDRESS = "AA:BB:CC:DD:EE:F0"
DUO_ADDRESS = "AA:BB:CC:DD:EE:F1"
TWIST_ADDRESS = "AA:BB:CC:DD:EE:F2"

# Test serial numbers (prefix determines device type)
FLIC2_SERIAL = "B12345"
DUO_SERIAL = "D12345"
TWIST_SERIAL = "T12345"

# Test pairing credentials
TEST_PAIRING_ID = 12345
TEST_PAIRING_KEY = bytes(16)  # 16 zero bytes
TEST_SIG_BITS = 0
TEST_BATTERY_LEVEL = 800  # Raw battery level (0-1024)
TEST_BUTTON_UUID = bytes(16)  # 16 zero bytes for testing


def create_flic2_service_info() -> BluetoothServiceInfoBleak:
    """Create a Flic 2 BluetoothServiceInfoBleak for testing."""
    return BluetoothServiceInfoBleak(
        name="Flic 2",
        address=FLIC2_ADDRESS,
        device=generate_ble_device(
            address=FLIC2_ADDRESS,
            name="Flic 2",
        ),
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[FLIC_SERVICE_UUID],
        source="local",
        advertisement=generate_advertisement_data(
            local_name="Flic 2",
            service_uuids=[FLIC_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=-127,
    )


def create_duo_service_info() -> BluetoothServiceInfoBleak:
    """Create a Flic Duo BluetoothServiceInfoBleak for testing."""
    return BluetoothServiceInfoBleak(
        name="Flic Duo",
        address=DUO_ADDRESS,
        device=generate_ble_device(
            address=DUO_ADDRESS,
            name="Flic Duo",
        ),
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[FLIC_SERVICE_UUID],
        source="local",
        advertisement=generate_advertisement_data(
            local_name="Flic Duo",
            service_uuids=[FLIC_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=-127,
    )


def create_twist_service_info() -> BluetoothServiceInfoBleak:
    """Create a Flic Twist BluetoothServiceInfoBleak for testing."""
    return BluetoothServiceInfoBleak(
        name="Flic Twist",
        address=TWIST_ADDRESS,
        device=generate_ble_device(
            address=TWIST_ADDRESS,
            name="Flic Twist",
        ),
        rssi=-60,
        manufacturer_data={},
        service_data={},
        service_uuids=[TWIST_SERVICE_UUID],
        source="local",
        advertisement=generate_advertisement_data(
            local_name="Flic Twist",
            service_uuids=[TWIST_SERVICE_UUID],
        ),
        connectable=True,
        time=0,
        tx_power=-127,
    )


def create_mock_config_entry(
    address: str = FLIC2_ADDRESS,
    serial_number: str = FLIC2_SERIAL,
    device_type: DeviceType = DeviceType.FLIC2,
    unique_id: str | None = None,
) -> MockConfigEntry:
    """Create a mock config entry for Flic Button."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic 2 ({serial_number})",
        unique_id=unique_id or address,
        data={
            CONF_ADDRESS: address,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: serial_number,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: device_type.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )


def patch_async_setup_entry(return_value: bool = True):
    """Patch async_setup_entry to return given value."""
    return patch(
        "homeassistant.components.flic_button.async_setup_entry",
        return_value=return_value,
    )


def patch_async_ble_device_from_address(
    service_info: BluetoothServiceInfoBleak | None,
):
    """Patch async_ble_device_from_address to return given BLE device."""
    return patch(
        "homeassistant.components.bluetooth.async_ble_device_from_address",
        return_value=service_info.device if service_info else None,
    )


def create_mock_flic_client(
    address: str = FLIC2_ADDRESS,
    serial_number: str = FLIC2_SERIAL,
    is_duo: bool = False,
    is_twist: bool = False,
    connected: bool = True,
) -> MagicMock:
    """Create a mock FlicClient for testing."""
    mock_client = MagicMock()
    mock_client.address = address
    mock_client.is_connected = connected
    mock_client.is_duo = is_duo
    mock_client.is_twist = is_twist

    # Mock capabilities
    mock_capabilities = MagicMock()
    mock_capabilities.button_count = 2 if is_duo else 1
    mock_capabilities.has_rotation = is_duo or is_twist
    mock_capabilities.has_selector = is_twist
    mock_capabilities.has_frame_header = not is_twist
    mock_client.capabilities = mock_capabilities

    # Mock device type
    if is_duo:
        mock_client.device_type = DeviceType.DUO
    elif is_twist:
        mock_client.device_type = DeviceType.TWIST
    else:
        mock_client.device_type = DeviceType.FLIC2

    # Mock state
    mock_state = MagicMock()
    mock_state.connected = connected
    mock_state.battery_voltage = 3.3 if connected else None
    mock_state.firmware_version = None
    mock_state.device_name = None
    mock_client.state = mock_state

    # Mock async methods
    mock_client.start = AsyncMock()
    mock_client.stop = AsyncMock()
    mock_client.connect = AsyncMock()
    mock_client.disconnect = AsyncMock()
    mock_client.full_verify_pairing = AsyncMock(
        return_value=(
            TEST_PAIRING_ID,
            TEST_PAIRING_KEY,
            serial_number,
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
    mock_client.set_ble_device = MagicMock()

    # Mock callback registration methods - capture registered callbacks
    mock_client.register_button_event_callback = MagicMock(return_value=lambda: None)
    mock_client.register_rotate_event_callback = MagicMock(return_value=lambda: None)
    mock_client.register_state_callback = MagicMock(return_value=lambda: None)

    return mock_client
