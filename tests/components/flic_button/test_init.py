"""Test the Flic Button integration init."""

from unittest.mock import AsyncMock, MagicMock, patch

from bleak import BleakError

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
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant

from . import (
    FLIC2_ADDRESS,
    FLIC2_SERIAL,
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_flic2_service_info,
)

from tests.common import MockConfigEntry


def _create_mock_coordinator(
    address: str = FLIC2_ADDRESS,
    serial_number: str = FLIC2_SERIAL,
    connected: bool = True,
    is_duo: bool = False,
    is_twist: bool = False,
) -> MagicMock:
    """Create a mock coordinator with proper string attributes."""
    mock_coordinator = MagicMock()
    mock_coordinator.async_connect = AsyncMock()
    mock_coordinator.async_disconnect = AsyncMock()
    mock_coordinator.connected = connected
    mock_coordinator.serial_number = serial_number
    mock_coordinator.is_duo = is_duo
    mock_coordinator.is_twist = is_twist
    mock_coordinator.model_name = "Flic 2"
    mock_coordinator.device_type = DeviceType.FLIC2
    mock_coordinator.last_update_success = True

    # Create client with real string address
    mock_client = MagicMock()
    mock_client.address = address
    mock_client.is_connected = connected
    mock_coordinator.client = mock_client

    # Mock capabilities
    mock_capabilities = MagicMock()
    mock_capabilities.button_count = 2 if is_duo else 1
    mock_capabilities.has_rotation = is_duo or is_twist
    mock_capabilities.has_selector = is_twist
    mock_coordinator.capabilities = mock_capabilities

    # Battery data
    battery_voltage = TEST_BATTERY_LEVEL * 3.6 / 1024.0
    mock_coordinator.data = {"battery_voltage": battery_voltage}

    # Firmware version
    mock_coordinator.firmware_version = None

    # Firmware update state
    mock_coordinator.latest_firmware_version = None
    mock_coordinator.firmware_download_url = None
    mock_coordinator.firmware_update_in_progress = False
    mock_coordinator.firmware_update_percentage = None

    # Async methods that may be awaited during setup
    mock_coordinator.async_load_slot_values = AsyncMock()

    return mock_coordinator


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_coordinator = _create_mock_coordinator()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.address = FLIC2_ADDRESS

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is mock_coordinator


async def test_setup_entry_device_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry when device is not available (BLE device not found)."""
    mock_config_entry.add_to_hass(hass)

    mock_coordinator = _create_mock_coordinator()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,  # Device not available
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.address = FLIC2_ADDRESS

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still load (device will connect when available)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_setup_entry_initial_connection_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry when initial connection fails (retries later)."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_coordinator = _create_mock_coordinator()
    mock_coordinator.async_connect = AsyncMock(
        side_effect=BleakError("Connection failed")
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.address = FLIC2_ADDRESS

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still load (will retry when device is available)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_coordinator = _create_mock_coordinator()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ) as mock_client_class,
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        mock_client = mock_client_class.return_value
        mock_client.address = FLIC2_ADDRESS

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload the entry
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_coordinator.async_disconnect.assert_called_once()


async def test_setup_entry_with_twist_device(
    hass: HomeAssistant,
) -> None:
    """Test setup entry with Twist device type."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Flic Twist ({TWIST_SERIAL})",
        unique_id=TWIST_ADDRESS,
        data={
            CONF_ADDRESS: TWIST_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: TWIST_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: DeviceType.TWIST.value,
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = _create_mock_coordinator(
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        is_twist=True,
    )
    mock_coordinator.model_name = "Flic Twist"
    mock_coordinator.device_type = DeviceType.TWIST

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_with_invalid_device_type(
    hass: HomeAssistant,
) -> None:
    """Test setup entry with invalid device type falls back to FLIC2."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flic 2",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_DEVICE_TYPE: "invalid_type",  # Invalid device type
            CONF_SIG_BITS: TEST_SIG_BITS,
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = _create_mock_coordinator()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Should still load successfully with fallback
    assert entry.state is ConfigEntryState.LOADED


async def test_setup_entry_without_device_type(
    hass: HomeAssistant,
) -> None:
    """Test setup entry without device_type (older config entries)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Flic 2",
        unique_id=FLIC2_ADDRESS,
        data={
            CONF_ADDRESS: FLIC2_ADDRESS,
            CONF_PAIRING_ID: TEST_PAIRING_ID,
            CONF_PAIRING_KEY: TEST_PAIRING_KEY.hex(),
            CONF_SERIAL_NUMBER: FLIC2_SERIAL,
            CONF_BATTERY_LEVEL: TEST_BATTERY_LEVEL,
            CONF_SIG_BITS: TEST_SIG_BITS,
            # No CONF_DEVICE_TYPE
        },
    )
    entry.add_to_hass(hass)

    mock_coordinator = _create_mock_coordinator()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
        ),
        patch(
            "homeassistant.components.flic_button.FlicCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
