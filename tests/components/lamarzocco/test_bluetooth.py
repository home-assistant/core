"""Tests for La Marzocco Bluetooth connection."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.backends.device import BLEDevice
from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import ModelName, WidgetType
from pylamarzocco.exceptions import BluetoothConnectionFailed, RequestNotSuccessful
import pytest

from homeassistant.components.lamarzocco.const import CONF_USE_BLUETOOTH
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

from . import async_init_integration, get_bluetooth_service_info


async def test_bluetooth_coordinator_setup(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test Bluetooth coordinator is set up correctly."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Verify Bluetooth coordinator was created
    assert mock_config_entry_bluetooth.runtime_data.bluetooth_coordinator is not None
    assert mock_lamarzocco.get_model_info_from_bluetooth.called


async def test_bluetooth_coordinator_disabled_when_option_false(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test Bluetooth coordinator is not created when disabled in options."""
    mock_config_entry_bluetooth.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry_bluetooth, options={CONF_USE_BLUETOOTH: False}
    )

    await hass.config_entries.async_setup(mock_config_entry_bluetooth.entry_id)
    await hass.async_block_till_done()

    # Verify Bluetooth coordinator was not created
    assert mock_config_entry_bluetooth.runtime_data.bluetooth_coordinator is None


async def test_bluetooth_coordinator_updates_based_on_websocket_state(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator updates based on websocket connection state."""
    await async_init_integration(hass, mock_config_entry_bluetooth)
    await hass.async_block_till_done()

    # Reset call count after initial setup
    mock_lamarzocco.get_dashboard_from_bluetooth.reset_mock()

    # Test 1: When websocket is connected, Bluetooth should skip updates
    mock_lamarzocco.websocket.connected = True
    mock_lamarzocco.dashboard.connected = True

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert not mock_lamarzocco.get_dashboard_from_bluetooth.called

    # Test 2: When websocket is disconnected, Bluetooth should update
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.dashboard.connected = False

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lamarzocco.get_dashboard_from_bluetooth.called


async def test_bt_offline_mode_entity_available_when_cloud_fails(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities with bt_offline_mode=True remain available when cloud coordinators fail."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Entities with bt_offline_mode=True
    bt_offline_entities = [
        f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty",
        f"switch.{mock_lamarzocco.serial_number}",  # main switch
        f"switch.{mock_lamarzocco.serial_number}_steam_boiler",
        f"switch.{mock_lamarzocco.serial_number}_smart_standby",
        f"select.{mock_lamarzocco.serial_number}_steam_level",
        f"number.{mock_lamarzocco.serial_number}_coffee_target_temperature",
        f"number.{mock_lamarzocco.serial_number}_smart_standby_time",
    ]

    # Check all entities are initially available
    for entity_id in bt_offline_entities:
        state = hass.states.get(entity_id)
        if state:  # Entity may not exist if not supported by model
            assert state.state != STATE_UNAVAILABLE

    # Simulate cloud coordinator failures
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.get_dashboard.side_effect = RequestNotSuccessful("")

    # Trigger update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # All bt_offline_mode entities should still be available
    for entity_id in bt_offline_entities:
        state = hass.states.get(entity_id)
        if state:  # Entity may not exist if not supported by model
            assert state.state != STATE_UNAVAILABLE


async def test_entity_without_bt_becomes_unavailable_when_cloud_fails_no_bt(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_cloud_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when cloud fails and no bluetooth coordinator exists."""
    await async_init_integration(hass, mock_config_entry)

    # Verify no bluetooth coordinator was created
    assert mock_config_entry.runtime_data.bluetooth_coordinator is None

    # Water tank sensor (even with bt_offline_mode=True, needs BT coordinator to work)
    water_tank_sensor = f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty"
    state = hass.states.get(water_tank_sensor)
    assert state
    # Initially should be available
    initial_state = state.state
    assert initial_state != STATE_UNAVAILABLE

    # Simulate cloud coordinator failures without bluetooth fallback
    mock_lamarzocco.websocket.connected = False
    mock_cloud_client.async_get_access_token.side_effect = RequestNotSuccessful("")

    # Trigger update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Water tank sensor should become unavailable because cloud failed and no BT
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_bluetooth_coordinator_handles_connection_failure(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator handles connection failures gracefully."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Water tank sensor has bt_offline_mode=True
    water_tank_sensor = f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty"
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Simulate Bluetooth connection failure
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.dashboard.connected = False
    mock_lamarzocco.get_dashboard_from_bluetooth.side_effect = (
        BluetoothConnectionFailed("")
    )

    # Trigger update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify Bluetooth entity becomes unavailable when BT connection fails
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_no_bluetooth_coordinator_without_mac(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test no Bluetooth coordinator is created when MAC address is not available."""
    await async_init_integration(hass, mock_config_entry)

    # Verify Bluetooth coordinator was not created
    assert mock_config_entry.runtime_data.bluetooth_coordinator is None


async def test_bluetooth_coordinator_triggers_entity_updates(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator updates trigger entity state updates."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Water tank sensor with bt_offline_mode
    water_tank_sensor = f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty"

    # Set initial state - no water issue
    mock_lamarzocco.dashboard.config[WidgetType.CM_NO_WATER] = False

    state = hass.states.get(water_tank_sensor)
    assert state

    # Simulate Bluetooth update adding water issue
    mock_lamarzocco.dashboard.config[WidgetType.CM_NO_WATER] = True
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.dashboard.connected = False

    # Trigger Bluetooth coordinator update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify entity state was updated
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("ble_device", "has_client"),
    [
        (None, False),
        (
            BLEDevice(
                address="aa:bb:cc:dd:ee:ff",
                name="name",
                details={},
            ),
            True,
        ),
    ],
)
async def test_bluetooth_is_set_from_discovery(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    ble_device: BLEDevice | None,
    has_client: bool,
) -> None:
    """Check we can fill a device from discovery info."""
    service_info = get_bluetooth_service_info(
        ModelName.GS3_MP, mock_lamarzocco.serial_number
    )
    mock_cloud_client.get_thing_settings.return_value.ble_auth_token = "token"
    with (
        patch(
            "homeassistant.components.lamarzocco.async_discovered_service_info",
            return_value=[service_info],
        ) as discovery,
        patch(
            "homeassistant.components.lamarzocco.LaMarzoccoMachine"
        ) as mock_machine_class,
        patch(
            "homeassistant.components.lamarzocco.async_ble_device_from_address",
            return_value=ble_device,
        ),
    ):
        mock_machine_class.return_value = mock_lamarzocco
        await async_init_integration(hass, mock_config_entry)
    discovery.assert_called_once()
    assert mock_machine_class.call_count == 1
    _, kwargs = mock_machine_class.call_args
    assert (kwargs["bluetooth_client"] is not None) == has_client

    assert mock_config_entry.data["mac"] == service_info.address
    assert mock_config_entry.data["token"] == "token"


async def test_disconnect_on_stop(
    hass: HomeAssistant,
    mock_websocket_terminated: bool,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test we close the connection with the La Marzocco when Home Assistant stops."""
    await async_init_integration(hass, mock_config_entry_bluetooth)
    await hass.async_block_till_done()

    assert mock_config_entry_bluetooth.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_bluetooth_client.disconnect.assert_awaited_once()
