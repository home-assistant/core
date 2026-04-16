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
    TEST_BATTERY_LEVEL,
    TEST_PAIRING_ID,
    TEST_PAIRING_KEY,
    TEST_SIG_BITS,
    TWIST_ADDRESS,
    TWIST_SERIAL,
    create_flic2_service_info,
    create_mock_flic_client,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.client is mock_client
    mock_client.start.assert_called_once()


async def test_setup_entry_device_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry when device is not available (BLE device not found)."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,  # Device not available
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry should still load (device will connect when available)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # start() should not be called when no BLE device available
    mock_client.start.assert_not_called()


async def test_setup_entry_initial_connection_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup entry raises ConfigEntryNotReady when connection fails."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()
    mock_client.start = AsyncMock(side_effect=BleakError("Connection failed"))

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unloading entry."""
    mock_config_entry.add_to_hass(hass)

    service_info = create_flic2_service_info()
    mock_client = create_mock_flic_client()

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=service_info.device,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED

        # Unload the entry
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_called_once()


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

    mock_client = create_mock_flic_client(
        address=TWIST_ADDRESS,
        serial_number=TWIST_SERIAL,
        is_twist=True,
    )

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            return_value=lambda: None,
        ),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED


async def test_bluetooth_callback_sets_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test Bluetooth callback updates BLE device on the client."""
    mock_config_entry.add_to_hass(hass)

    mock_client = create_mock_flic_client()
    bt_callback = None

    def capture_bt_register(hass_inner, callback, matcher, mode):
        nonlocal bt_callback
        bt_callback = callback
        return lambda: None

    with (
        patch(
            "homeassistant.components.bluetooth.async_ble_device_from_address",
            return_value=None,
        ),
        patch(
            "homeassistant.components.flic_button.FlicClient",
            return_value=mock_client,
        ),
        patch(
            "homeassistant.components.flic_button.bluetooth.async_register_callback",
            side_effect=capture_bt_register,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert bt_callback is not None

    # Simulate Bluetooth advertisement
    service_info = create_flic2_service_info()
    bt_callback(service_info, MagicMock())

    mock_client.set_ble_device.assert_called_once_with(service_info.device)
