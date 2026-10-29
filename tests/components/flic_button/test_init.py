"""Test the Flic Button integration init."""

from unittest.mock import MagicMock

from bleak import BleakError
from pyflic_ble import DeviceType, FlicAuthenticationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from . import create_flic2_service_info, setup_integration


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
) -> None:
    """Test successful setup entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_flic_client.start.assert_called_once()


async def test_setup_entry_device_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_no_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
) -> None:
    """Test setup entry when device is not available (BLE device not found)."""
    await setup_integration(hass, mock_config_entry)

    # Entry should still load (device will connect when available)
    assert mock_config_entry.state is ConfigEntryState.LOADED
    # start() should not be called when no BLE device available
    mock_flic_client.start.assert_not_called()


@pytest.mark.parametrize(
    "side_effect",
    [
        pytest.param(BleakError("Connection failed"), id="bleak_error"),
        pytest.param(
            FlicAuthenticationError("Quick verify timeout"), id="verify_timeout"
        ),
    ],
)
async def test_setup_entry_initial_connection_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
    side_effect: Exception,
) -> None:
    """Test setup entry retries and stops the client when connection fails."""
    mock_flic_client.start.side_effect = side_effect

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_flic_client.stop.assert_called_once()


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
) -> None:
    """Test unloading entry."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_flic_client.stop.assert_called_once()


@pytest.mark.parametrize("device_type", [DeviceType.TWIST])
async def test_setup_entry_with_twist_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_no_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
) -> None:
    """Test setup entry with Twist device type."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_bluetooth_callback_sets_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
    mock_no_ble_device_from_address: MagicMock,
    mock_bluetooth_register_callback: MagicMock,
) -> None:
    """Test Bluetooth callback updates BLE device on the client."""
    await setup_integration(hass, mock_config_entry)

    # The bluetooth callback is the second positional arg passed to register
    bt_callback = mock_bluetooth_register_callback.call_args[0][1]

    service_info = create_flic2_service_info()
    bt_callback(service_info, MagicMock())

    mock_flic_client.set_ble_device.assert_called_once_with(service_info.device)
