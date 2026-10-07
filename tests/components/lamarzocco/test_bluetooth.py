"""Tests for La Marzocco Bluetooth connection."""

import asyncio
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
from unittest.mock import MagicMock, PropertyMock, patch

from bleak.backends.device import BLEDevice
from bleak.exc import BleakError
from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import MachineMode, MachineState, ModelName, WidgetType
from pylamarzocco.exceptions import BluetoothConnectionFailed, RequestNotSuccessful
from pylamarzocco.models import BluetoothMachineTelemetry
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.lamarzocco.const import CONF_OFFLINE_MODE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import async_init_integration, get_bluetooth_service_info

from tests.common import MockConfigEntry, async_fire_time_changed

# Entities with bt_offline_mode=True
BLUETOOTH_ONLY_BASE_ENTITIES = [
    ("binary_sensor", "water_tank_empty"),
    ("switch", ""),
    ("switch", "steam_boiler"),
    ("number", "coffee_target_temperature"),
    ("switch", "smart_standby_enabled"),
    ("number", "smart_standby_time"),
]

MICRA_BT_OFFLINE_ENTITIES = [
    *BLUETOOTH_ONLY_BASE_ENTITIES,
    ("select", "steam_level"),
]

GS3_BT_OFFLINE_ENTITIES = [
    *BLUETOOTH_ONLY_BASE_ENTITIES,
    ("number", "steam_target_temperature"),
]


def build_entity_id(
    platform: str,
    serial_number: str,
    entity_suffix: str,
) -> str:
    """Build full entity ID."""
    if entity_suffix:
        return f"{platform}.{serial_number}_{entity_suffix}"
    return f"{platform}.{serial_number}"


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_bluetooth_coordinator_updates_based_on_websocket_state(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator updates based on websocket connection state."""
    mock_lamarzocco.websocket.connected = False

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

    mock_lamarzocco.dashboard.connected = False

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lamarzocco.get_dashboard_from_bluetooth.called


@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        (ModelName.LINEA_MICRA, MICRA_BT_OFFLINE_ENTITIES),
        (ModelName.GS3_AV, GS3_BT_OFFLINE_ENTITIES),
    ],
)
async def test_bt_offline_mode_entity_available_when_cloud_fails(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    device_fixture: ModelName,
    entities: list[tuple[str, str]],
) -> None:
    """Test bt_offline_mode entities stay available when cloud fails."""
    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Check all entities are initially available
    for entity_id in entities:
        state = hass.states.get(
            build_entity_id(entity_id[0], mock_lamarzocco.serial_number, entity_id[1])
        )
        assert state
        assert state.state != STATE_UNAVAILABLE

    # Simulate cloud coordinator failures
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.get_dashboard.side_effect = RequestNotSuccessful("")

    # Trigger update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # All bt_offline_mode entities should still be available
    for entity_id in entities:
        state = hass.states.get(
            build_entity_id(entity_id[0], mock_lamarzocco.serial_number, entity_id[1])
        )
        assert state
        assert state.state != STATE_UNAVAILABLE


async def test_entity_without_bt_becomes_unavailable_when_cloud_fails_no_bt(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test entities become unavailable when cloud fails without BT."""
    await async_init_integration(hass, mock_config_entry)

    # Water tank sensor (even with bt_offline_mode=True, needs BT coordinator to work)
    water_tank_sensor = (
        f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty"
    )
    state = hass.states.get(water_tank_sensor)
    assert state
    # Initially should be available
    initial_state = state.state
    assert initial_state != STATE_UNAVAILABLE

    # Simulate cloud coordinator failures without bluetooth fallback
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.ensure_token_valid.side_effect = RequestNotSuccessful("")

    # Trigger update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Water tank sensor should become unavailable because cloud failed and no BT
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_bluetooth_coordinator_handles_connection_failure(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator handles connection failures gracefully."""
    # Start with websocket terminated to ensure Bluetooth coordinator is active
    mock_lamarzocco.websocket.connected = False

    await async_init_integration(hass, mock_config_entry_bluetooth)

    # Water tank sensor has bt_offline_mode=True
    water_tank_sensor = (
        f"binary_sensor.{mock_lamarzocco.serial_number}_water_tank_empty"
    )
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state != STATE_UNAVAILABLE

    # Simulate Bluetooth connection failure
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.dashboard.connected = False
    mock_lamarzocco.get_dashboard_from_bluetooth.side_effect = (
        BluetoothConnectionFailed("")
    )

    # Trigger Bluetooth coordinator update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # now it should be unavailable due to BT failure
    state = hass.states.get(water_tank_sensor)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_bluetooth_coordinator_triggers_entity_updates(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Bluetooth coordinator updates trigger entity state updates."""
    mock_lamarzocco.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ].mode = MachineMode.STANDBY
    await async_init_integration(hass, mock_config_entry_bluetooth)

    main_switch = f"switch.{mock_lamarzocco.serial_number}"
    state = hass.states.get(main_switch)
    assert state
    assert state.state == STATE_OFF

    # Simulate Bluetooth update changing machine mode to brewing
    mock_lamarzocco.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ].mode = MachineMode.BREWING_MODE
    mock_lamarzocco.websocket.connected = False
    mock_lamarzocco.dashboard.connected = False

    # Trigger Bluetooth coordinator update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify entity state was updated
    state = hass.states.get(main_switch)
    assert state
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        (ModelName.LINEA_MICRA, MICRA_BT_OFFLINE_ENTITIES),
        (ModelName.GS3_AV, GS3_BT_OFFLINE_ENTITIES),
    ],
)
@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_setup_through_bluetooth_only(
    hass: HomeAssistant,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_lamarzocco_bluetooth: MagicMock,
    mock_cloud_client: MagicMock,
    device_registry: dr.DeviceRegistry,
    device_fixture: ModelName,
    entities: list[tuple[str, str]],
    snapshot: SnapshotAssertion,
) -> None:
    """Test we can setup without a cloud connection."""

    # Simulate cloud connection failures
    mock_cloud_client.get_thing_settings.side_effect = RequestNotSuccessful("")
    mock_cloud_client.async_get_access_token.side_effect = RequestNotSuccessful("")
    mock_lamarzocco_bluetooth.get_dashboard.side_effect = RequestNotSuccessful("")
    mock_lamarzocco_bluetooth.get_coffee_and_flush_counter.side_effect = (
        RequestNotSuccessful("")
    )
    mock_lamarzocco_bluetooth.get_schedule.side_effect = RequestNotSuccessful("")
    mock_lamarzocco_bluetooth.get_settings.side_effect = RequestNotSuccessful("")

    await async_init_integration(hass, mock_config_entry_bluetooth)
    assert mock_config_entry_bluetooth.state is ConfigEntryState.LOADED

    # Check all Bluetooth entities are available
    for entity_id in entities:
        entity = build_entity_id(
            entity_id[0], mock_lamarzocco_bluetooth.serial_number, entity_id[1]
        )
        state = hass.states.get(entity)
        assert state
        assert state.state != STATE_UNAVAILABLE
        assert state == snapshot(name=entity)

    # snapshot device
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_lamarzocco_bluetooth.serial_number),
        mock_config_entry_bluetooth.entry_id,
    )
    assert device
    assert device == snapshot(
        name=f"device_bluetooth_{mock_lamarzocco_bluetooth.serial_number}"
    )


async def test_manual_offline_mode_no_bluetooth_device(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test manual offline mode with no Bluetooth device found."""

    mock_config_entry_bluetooth.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry_bluetooth, options={CONF_OFFLINE_MODE: True}
    )
    await hass.config_entries.async_setup(mock_config_entry_bluetooth.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry_bluetooth.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_manual_offline_mode(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test manual offline mode updates entities via Bluetooth."""

    mock_config_entry_bluetooth.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry_bluetooth, options={CONF_OFFLINE_MODE: True}
    )
    await hass.config_entries.async_setup(mock_config_entry_bluetooth.entry_id)
    await hass.async_block_till_done()

    main_switch = f"switch.{mock_lamarzocco.serial_number}"
    state = hass.states.get(main_switch)
    assert state
    assert state.state == STATE_ON

    # Simulate Bluetooth update changing machine mode to standby
    mock_lamarzocco.dashboard.config[
        WidgetType.CM_MACHINE_STATUS
    ].mode = MachineMode.STANDBY

    # Trigger Bluetooth coordinator update
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    # Verify entity state was updated
    state = hass.states.get(main_switch)
    assert state
    assert state.state == STATE_OFF

    # verify other entities are unavailable
    sample_entities = (
        f"binary_sensor.{mock_lamarzocco.serial_number}_backflush_active",
        f"update.{mock_lamarzocco.serial_number}_gateway_firmware",
    )
    for entity_id in sample_entities:
        state = hass.states.get(entity_id)
        assert state
        assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("mock_ble_device", "has_client"),
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
@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_bluetooth_is_set_from_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    mock_ble_device: BLEDevice | None,
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
    ):
        mock_machine_class.return_value = mock_lamarzocco
        await async_init_integration(hass, mock_config_entry)
    discovery.assert_called_once()
    assert mock_machine_class.call_count == 1
    _, kwargs = mock_machine_class.call_args
    assert (kwargs["bluetooth_client"] is not None) == has_client

    assert mock_config_entry.data["mac"] == service_info.address
    assert mock_config_entry.data["token"] == "token"


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_disconnect_on_stop(
    hass: HomeAssistant,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_bluetooth_client: MagicMock,
) -> None:
    """Test we close the connection with the La Marzocco when Home Assistant stops."""
    await async_init_integration(hass, mock_config_entry_bluetooth)
    await hass.async_block_till_done()

    assert mock_config_entry_bluetooth.state is ConfigEntryState.LOADED

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_bluetooth_client.disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_updates_brew_active(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_websocket_terminated: PropertyMock,
) -> None:
    """Test shot timer updates are pushed to the brewing entities."""
    mock_websocket_terminated.return_value = True
    await async_init_integration(hass, mock_config_entry_bluetooth)

    mock_lamarzocco.connect_bluetooth_shot_counter.assert_awaited_once()
    update_callback = mock_lamarzocco.connect_bluetooth_shot_counter.call_args.args[0]

    brew_active = f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    state = hass.states.get(brew_active)
    assert state
    assert state.state == STATE_UNAVAILABLE

    mock_lamarzocco.bluetooth_shot_counter_active = True
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]
    machine_status.status = MachineState.BREWING
    machine_status.brewing_start_time = datetime(2026, 1, 1, tzinfo=UTC)
    update_callback(None)
    await hass.async_block_till_done()

    state = hass.states.get(brew_active)
    assert state
    assert state.state == STATE_ON
    state = hass.states.get(
        f"sensor.{mock_lamarzocco.serial_number}_brewing_start_time"
    )
    assert state
    assert state.state == "2026-01-01T00:00:00+00:00"


@pytest.mark.parametrize(
    "exception", [BluetoothConnectionFailed(""), BleakError(""), TimeoutError()]
)
@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_retried_after_failure(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    exception: Exception,
) -> None:
    """Test the shot timer is retried after a connection failure."""
    mock_lamarzocco.connect_bluetooth_shot_counter.side_effect = [exception, True]
    await async_init_integration(hass, mock_config_entry_bluetooth)
    assert mock_lamarzocco.connect_bluetooth_shot_counter.await_count == 1

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_lamarzocco.connect_bluetooth_shot_counter.await_count == 2


@pytest.mark.parametrize(
    ("shot_counter_supported", "attempts"),
    [
        pytest.param(False, 1, id="unsupported"),
        pytest.param(True, 2, id="supported"),
    ],
)
@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_characteristic_missing(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    shot_counter_supported: bool,
    attempts: int,
) -> None:
    """Test a missing characteristic is only retried if the cloud reports support."""
    mock_lamarzocco.dashboard.shot_counter_supported = shot_counter_supported
    mock_lamarzocco.connect_bluetooth_shot_counter.side_effect = [False, True]
    await async_init_integration(hass, mock_config_entry_bluetooth)

    for _ in range(2):
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_lamarzocco.connect_bluetooth_shot_counter.await_count == attempts


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_retry_backoff(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failed starts are retried after 1, then 5, then 15 minutes."""
    mock_connect = mock_lamarzocco.connect_bluetooth_shot_counter
    mock_connect.side_effect = BluetoothConnectionFailed("")
    await async_init_integration(hass, mock_config_entry_bluetooth)
    config_coordinator = mock_config_entry_bluetooth.runtime_data.config_coordinator
    assert mock_connect.await_count == 1

    for delay, attempts in (
        (timedelta(seconds=61), 2),
        (timedelta(seconds=61), 2),
        (timedelta(minutes=4), 3),
        (timedelta(minutes=10), 3),
        (timedelta(minutes=5, seconds=1), 4),
    ):
        # cloud updates don't retry early either
        config_coordinator.async_set_updated_data(None)
        freezer.tick(delay)
        async_fire_time_changed(hass)
        await hass.async_block_till_done(wait_background_tasks=True)
        assert mock_connect.await_count == attempts


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_unexpected_error(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an unexpected shot timer error is logged and retried later."""
    mock_lamarzocco.connect_bluetooth_shot_counter.side_effect = [
        ValueError("boom"),
        True,
    ]
    await async_init_integration(hass, mock_config_entry_bluetooth)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert "Error in the Bluetooth shot timer" in caplog.text

    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_lamarzocco.connect_bluetooth_shot_counter.await_count == 2


@pytest.mark.usefixtures("mock_lamarzocco")
async def test_bluetooth_client_refreshes_ble_device(
    hass: HomeAssistant,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
    mock_ble_device: BLEDevice,
) -> None:
    """Test the Bluetooth client gets the most recent BLE device on reconnect."""
    with patch(
        "homeassistant.components.lamarzocco.LaMarzoccoBluetoothClient"
    ) as bt_client_cls:
        await async_init_integration(hass, mock_config_entry_bluetooth)

    ble_device_callback = bt_client_cls.call_args.kwargs["ble_device_callback"]

    # keep the setup device if it's currently not seen
    mock_ble_device_from_address.return_value = None
    assert ble_device_callback() is mock_ble_device

    new_device = BLEDevice("00:00:00:00:00:00", "proxy", details={"path": "new"})
    mock_ble_device_from_address.return_value = new_device
    assert ble_device_callback() is new_device

    # keep the last seen device, not the setup device
    mock_ble_device_from_address.return_value = None
    assert ble_device_callback() is new_device


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_only_connected_outside_standby(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
) -> None:
    """Test the shot timer follows the machine leaving and entering standby."""
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]
    machine_status.mode = MachineMode.STANDBY
    await async_init_integration(hass, mock_config_entry_bluetooth)
    config_coordinator = mock_config_entry_bluetooth.runtime_data.config_coordinator

    mock_lamarzocco.connect_bluetooth_shot_counter.assert_not_called()

    # machine turned on, reported by the cloud
    machine_status.mode = MachineMode.BREWING_MODE
    config_coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    mock_lamarzocco.connect_bluetooth_shot_counter.assert_awaited_once()

    # further updates don't connect again
    config_coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    mock_lamarzocco.connect_bluetooth_shot_counter.assert_awaited_once()
    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_not_called()

    # back to standby
    machine_status.mode = MachineMode.STANDBY
    config_coordinator.async_set_updated_data(None)
    await hass.async_block_till_done()
    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_awaited_once()


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_follows_bluetooth_mode_offline(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the shot timer starts once a Bluetooth poll reports the machine on."""
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]
    machine_status.mode = MachineMode.STANDBY
    mock_lamarzocco.websocket.connected = False
    await async_init_integration(hass, mock_config_entry_bluetooth)
    mock_lamarzocco.connect_bluetooth_shot_counter.assert_not_called()

    machine_status.mode = MachineMode.ECO_MODE
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_lamarzocco.connect_bluetooth_shot_counter.assert_awaited_once()


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_connect_updates_entities(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_websocket_terminated: PropertyMock,
) -> None:
    """Test brewing entities become available as soon as the shot timer connects."""
    mock_websocket_terminated.return_value = True
    finish_connect = asyncio.Event()

    async def slow_connect(*_: Any) -> bool:
        await finish_connect.wait()
        mock_lamarzocco.bluetooth_shot_counter_active = True
        return True

    mock_lamarzocco.connect_bluetooth_shot_counter.side_effect = slow_connect
    await async_init_integration(hass, mock_config_entry_bluetooth)

    brew_active = f"binary_sensor.{mock_lamarzocco.serial_number}_brewing_active"
    state = hass.states.get(brew_active)
    assert state
    assert state.state == STATE_UNAVAILABLE

    finish_connect.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get(brew_active)
    assert state
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_catches_up_on_mode_change_while_connecting(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
) -> None:
    """Test a standby during a slow connect disconnects once the connect is done."""
    connecting = asyncio.Event()
    finish_connect = asyncio.Event()

    async def slow_connect(*_: Any) -> bool:
        connecting.set()
        await finish_connect.wait()
        return True

    mock_lamarzocco.connect_bluetooth_shot_counter.side_effect = slow_connect
    await async_init_integration(hass, mock_config_entry_bluetooth)
    await connecting.wait()
    config_coordinator = mock_config_entry_bluetooth.runtime_data.config_coordinator

    # the machine goes to standby while still connecting
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]
    machine_status.mode = MachineMode.STANDBY
    config_coordinator.async_set_updated_data(None)
    await hass.async_block_till_done(wait_background_tasks=False)
    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_not_called()

    finish_connect.set()
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_awaited_once()


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_power_cycles_with_listener_feedback(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test switching off stops the shot timer once, it recursed with 2.5.1."""
    await async_init_integration(hass, mock_config_entry_bluetooth)
    config_coordinator = mock_config_entry_bluetooth.runtime_data.config_coordinator
    update_callback = mock_lamarzocco.connect_bluetooth_shot_counter.call_args.args[0]
    # pylamarzocco 2.5.1 called the update callback while stopping
    mock_lamarzocco.disconnect_bluetooth_shot_counter.side_effect = lambda: (
        update_callback(None)
    )
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]

    for _ in range(2):
        machine_status.mode = MachineMode.STANDBY
        config_coordinator.async_set_updated_data(None)
        await hass.async_block_till_done(wait_background_tasks=True)
        machine_status.mode = MachineMode.BREWING_MODE
        config_coordinator.async_set_updated_data(None)
        await hass.async_block_till_done(wait_background_tasks=True)

    assert mock_lamarzocco.disconnect_bluetooth_shot_counter.await_count == 2
    assert mock_lamarzocco.connect_bluetooth_shot_counter.await_count == 3
    assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


@pytest.mark.usefixtures("mock_ble_device_from_address")
async def test_shot_timer_stops_on_bluetooth_standby(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
) -> None:
    """Test a machine mode over Bluetooth stops the shot timer without the cloud."""
    await async_init_integration(hass, mock_config_entry_bluetooth)
    telemetry_callback = mock_lamarzocco.connect_bluetooth_shot_counter.call_args.args[
        1
    ]
    machine_status = mock_lamarzocco.dashboard.config[WidgetType.CM_MACHINE_STATUS]

    # pylamarzocco applies the machine mode to the dashboard before calling back
    machine_status.mode = MachineMode.STANDBY
    telemetry_callback(BluetoothMachineTelemetry(steam_boiler_temperature=130))
    await hass.async_block_till_done(wait_background_tasks=True)
    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_not_called()

    telemetry_callback(BluetoothMachineTelemetry(machine_mode=MachineMode.STANDBY))
    await hass.async_block_till_done(wait_background_tasks=True)

    mock_lamarzocco.disconnect_bluetooth_shot_counter.assert_awaited_once()
    state = hass.states.get(f"switch.{mock_lamarzocco.serial_number}")
    assert state
    assert state.state == STATE_OFF
