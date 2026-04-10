"""Tests for La Marzocco Bluetooth connection."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from bleak.backends.device import BLEDevice
from freezegun.api import FrozenDateTimeFactory
from pylamarzocco.const import MachineMode, ModelName, WidgetType
from pylamarzocco.exceptions import BluetoothConnectionFailed, RequestNotSuccessful
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


async def test_bluetooth_coordinator_updates_based_on_websocket_state(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
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
    """Test entities with bt_offline_mode=True remain available when cloud coordinators fail."""
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
    """Test entities become unavailable when cloud fails and no bluetooth coordinator exists."""
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


async def test_bluetooth_coordinator_handles_connection_failure(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_ble_device_from_address: MagicMock,
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
async def test_setup_through_bluetooth_only(
    hass: HomeAssistant,
    mock_config_entry_bluetooth: MockConfigEntry,
    mock_lamarzocco_bluetooth: MagicMock,
    mock_ble_device_from_address: MagicMock,
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
    device = device_registry.async_get_device(
        {(DOMAIN, mock_lamarzocco_bluetooth.serial_number)}
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


async def test_manual_offline_mode(
    hass: HomeAssistant,
    mock_lamarzocco: MagicMock,
    mock_config_entry_bluetooth: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    mock_ble_device_from_address: MagicMock,
) -> None:
    """Test that manual offline mode successfully sets up and updates entities via Bluetooth, and marks non-Bluetooth entities as unavailable."""

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
async def test_bluetooth_is_set_from_discovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_lamarzocco: MagicMock,
    mock_cloud_client: MagicMock,
    mock_ble_device: BLEDevice | None,
    has_client: bool,
    mock_ble_device_from_address: MagicMock,
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


async def test_disconnect_on_stop(
    hass: HomeAssistant,
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
