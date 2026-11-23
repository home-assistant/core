"""Test the Flic Button integration init."""

from unittest.mock import MagicMock

from bleak import BleakError
from pyflic_ble import DeviceType, FlicAuthenticationError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.flic_button.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import FLIC2_ADDRESS, FLIC2_SERIAL, create_flic2_service_info, setup_integration


def _fire_state_callbacks(mock_flic_client: MagicMock) -> None:
    """Pass the client state to every registered state callback."""
    for call in mock_flic_client.register_state_callback.call_args_list:
        call.args[0](mock_flic_client.state)


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


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
async def test_firmware_version_set_when_connected(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
) -> None:
    """Test the device is created at setup and gets its firmware version on connect."""
    mock_flic_client.state.connected = False
    mock_flic_client.state.firmware_version = None
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FLIC2_ADDRESS), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_BLUETOOTH, FLIC2_ADDRESS)}
    assert device.manufacturer == "Shortcut Labs"
    assert device.model == "Flic 2"
    assert device.serial_number == FLIC2_SERIAL
    assert device.sw_version is None

    mock_flic_client.state.connected = True
    mock_flic_client.state.firmware_version = 11
    _fire_state_callbacks(mock_flic_client)
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "11"


@pytest.mark.usefixtures(
    "mock_no_ble_device_from_address", "mock_bluetooth_register_callback"
)
async def test_firmware_version_kept_on_reload_out_of_range(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_flic_client: MagicMock,
) -> None:
    """Test a reload while the button is out of range keeps the firmware version."""
    await setup_integration(hass, mock_config_entry)
    _fire_state_callbacks(mock_flic_client)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, FLIC2_ADDRESS), mock_config_entry.entry_id
    )
    assert device is not None
    assert device.sw_version == "10"

    # Out of range, the client doesn't know the firmware version
    mock_flic_client.state.connected = False
    mock_flic_client.state.firmware_version = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get(device.id)
    assert device is not None
    assert device.sw_version == "10"
