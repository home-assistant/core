"""Test the Teslemetry binary sensor platform."""

from collections.abc import Generator
from datetime import timedelta
import time
from unittest.mock import AsyncMock, MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from habluetooth import CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
import pytest
from syrupy.assertion import SnapshotAssertion
from tesla_fleet_api.tesla.vehicle.bluetooth import VehicleBluetooth
from teslemetry_stream import Signal

from homeassistant.components.bluetooth.const import UNAVAILABLE_TRACK_SECONDS
from homeassistant.components.bluetooth.manager import HomeAssistantBluetoothManager
from homeassistant.components.teslemetry.const import DOMAIN, SUBENTRY_TYPE_VEHICLE
from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    assert_entities,
    assert_entities_alt,
    mock_ble_config_entry,
    setup_ble_platform,
    setup_platform,
)
from .const import ADDRESS, VEHICLE_DATA_ALT, VIN

from tests.common import async_fire_time_changed
from tests.components.bluetooth import (
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the binary sensor entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor_refresh(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    freezer: FrozenDateTimeFactory,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the binary sensor entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    # Refresh
    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    freezer.tick(VEHICLE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensors_streaming(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the binary sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.FD_WINDOW: "WindowStateOpened",
                Signal.FP_WINDOW: "INVALID_VALUE",
                Signal.RD_WINDOW: "WindowStateClosed",
                Signal.RP_WINDOW: "WindowStatePartiallyOpen",
                Signal.DOOR_STATE: {
                    "DoorState": {
                        "DriverFront": True,
                        "DriverRear": False,
                        "PassengerFront": False,
                        "PassengerRear": False,
                        "TrunkFront": False,
                        "TrunkRear": False,
                    }
                },
                Signal.DRIVER_SEAT_BELT: None,
                Signal.REAR_DEFROST_ENABLED: True,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values with concrete assertions
    assert hass.states.get("binary_sensor.test_front_driver_window").state == "on"
    assert hass.states.get("binary_sensor.test_front_passenger_window").state == "off"
    assert hass.states.get("binary_sensor.test_rear_driver_window").state == "off"
    assert hass.states.get("binary_sensor.test_rear_passenger_window").state == "on"
    assert hass.states.get("binary_sensor.test_front_driver_door").state == "off"
    assert hass.states.get("binary_sensor.test_front_passenger_door").state == "off"
    assert hass.states.get("binary_sensor.test_driver_seat_belt").state == "off"
    assert hass.states.get("binary_sensor.test_rear_defroster").state == "on"


async def test_binary_sensors_connectivity(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the binary sensor entities with streaming are correct."""

    freezer.move_to("2024-01-01 00:00:00+00:00")

    await setup_platform(hass, [Platform.BINARY_SENSOR])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "status": "CONNECTED",
            "networkInterface": "cellular",
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "status": "DISCONNECTED",
            "networkInterface": "wifi",
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Assert the entities have correct state with concrete assertions
    assert hass.states.get("binary_sensor.test_cellular").state == "on"
    assert hass.states.get("binary_sensor.test_wi_fi").state == "off"


BLE_NAME = "Sdcdcb1a343110fbaC"
PRESENCE_ENTITY_ID = "binary_sensor.test_bluetooth"
SESSION_ENTITY_ID = "binary_sensor.test_bluetooth_session"


@pytest.fixture
def mock_ble_vehicle() -> Generator[VehicleBluetooth]:
    """Back the paired vehicle with a real VehicleBluetooth that never signs."""
    vehicle = VehicleBluetooth(MagicMock(), VIN, key=False, keepalive_interval=None)
    with patch("homeassistant.components.teslemetry.helpers.TeslaBluetooth") as parent:
        parent.return_value.get_private_key = AsyncMock()
        parent.return_value.vehicles.createBluetooth.return_value = vehicle
        yield vehicle


def inject_vehicle_advertisement(hass: HomeAssistant) -> None:
    """Make the Bluetooth stack hear one advertisement from the vehicle."""
    inject_advertisement(
        hass,
        generate_ble_device(ADDRESS, BLE_NAME),
        generate_advertisement_data(local_name=BLE_NAME),
    )


async def drop_vehicle_from_stack(hass: HomeAssistant, start_monotonic: float) -> None:
    """Advance past the stale and unavailable windows with nothing discovered."""
    advance = (
        CONNECTABLE_FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS
        + UNAVAILABLE_TRACK_SECONDS
        + 1
    )
    with (
        patch_bluetooth_time(start_monotonic + advance),
        patch_all_discovered_devices([]),
    ):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=advance))
        await hass.async_block_till_done()


@pytest.mark.usefixtures(
    "enable_bluetooth", "mock_ble_vehicle", "entity_registry_enabled_by_default"
)
@pytest.mark.parametrize(
    "entity_id",
    [PRESENCE_ENTITY_ID, SESSION_ENTITY_ID],
)
async def test_bluetooth_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    entity_id: str,
) -> None:
    """Tests that the Bluetooth binary sensor entities are correct."""
    await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

    assert entity_registry.async_get(entity_id) == snapshot(name=f"{entity_id}-entry")
    assert hass.states.get(entity_id) == snapshot(name=f"{entity_id}-state")


@pytest.mark.usefixtures("enable_bluetooth")
async def test_bluetooth_binary_sensor(
    hass: HomeAssistant, mock_ble_vehicle: VehicleBluetooth
) -> None:
    """Tests that the Bluetooth binary sensor follows the stack's presence history.

    Tracking presence must never connect to or actively probe the vehicle, so the
    same run asserts no BLE link was opened and no active scan was requested.
    """
    start_monotonic = time.monotonic()
    with (
        patch(
            "tesla_fleet_api.tesla.vehicle.bluetooth.establish_connection"
        ) as mock_establish_connection,
        patch.object(
            HomeAssistantBluetoothManager, "async_register_active_scan"
        ) as mock_register_active_scan,
    ):
        await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

        # Nothing heard yet, so the stack cannot see the vehicle.
        assert hass.states.get(PRESENCE_ENTITY_ID).state == STATE_OFF

        inject_vehicle_advertisement(hass)
        await hass.async_block_till_done()
        assert hass.states.get(PRESENCE_ENTITY_ID).state == STATE_ON

        await drop_vehicle_from_stack(hass, start_monotonic)
        assert hass.states.get(PRESENCE_ENTITY_ID).state == STATE_OFF

    mock_establish_connection.assert_not_called()
    mock_register_active_scan.assert_not_called()
    assert mock_ble_vehicle.get_device() is None


@pytest.mark.usefixtures("enable_bluetooth", "mock_ble_vehicle")
async def test_bluetooth_binary_sensor_already_in_range(hass: HomeAssistant) -> None:
    """Tests that a vehicle the stack already knows about starts on."""
    inject_vehicle_advertisement(hass)
    await hass.async_block_till_done()

    await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

    assert hass.states.get(PRESENCE_ENTITY_ID).state == STATE_ON


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "mock_legacy")
async def test_bluetooth_binary_sensors_need_a_paired_vehicle(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that a vehicle without a Bluetooth subentry gets no Bluetooth sensors."""
    await setup_platform(hass, [Platform.BINARY_SENSOR])

    assert entity_registry.async_get(PRESENCE_ENTITY_ID) is None
    assert entity_registry.async_get(SESSION_ENTITY_ID) is None


@pytest.mark.usefixtures("enable_bluetooth", "mock_ble_vehicle")
async def test_bluetooth_session_binary_sensor_disabled_by_default(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the Bluetooth session binary sensor is disabled by default."""
    await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

    assert (entry := entity_registry.async_get(SESSION_ENTITY_ID))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(SESSION_ENTITY_ID) is None


@pytest.mark.usefixtures("enable_bluetooth", "entity_registry_enabled_by_default")
async def test_bluetooth_session_binary_sensor(
    hass: HomeAssistant, mock_ble_vehicle: VehicleBluetooth
) -> None:
    """Tests that the Bluetooth session binary sensor follows the BLE link."""
    await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

    assert hass.states.get(SESSION_ENTITY_ID).state == STATE_OFF

    client = MagicMock()
    client.is_connected = True
    client.start_notify = AsyncMock()
    client.disconnect = AsyncMock()
    mock_ble_vehicle.set_device(generate_ble_device(ADDRESS, BLE_NAME))
    with patch(
        "tesla_fleet_api.tesla.vehicle.bluetooth.establish_connection",
        AsyncMock(return_value=client),
    ):
        await mock_ble_vehicle.connect()
    await hass.async_block_till_done()
    assert hass.states.get(SESSION_ENTITY_ID).state == STATE_ON

    await mock_ble_vehicle.disconnect()
    await hass.async_block_till_done()
    assert hass.states.get(SESSION_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("enable_bluetooth", "entity_registry_enabled_by_default")
async def test_bluetooth_session_binary_sensor_without_key(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that a failed key load keeps the session entity, unavailable.

    The entities are gated on the subentry rather than on the Bluetooth backend,
    so a key load failure cannot look like an unpaired vehicle to the stale
    entity cleanup and cost the user a customised registry entry.
    """
    entry = mock_ble_config_entry()
    entry.add_to_hass(hass)
    existing = entity_registry.async_get_or_create(
        Platform.BINARY_SENSOR,
        DOMAIN,
        f"{VIN}-bluetooth_session",
        config_entry=entry,
        suggested_object_id="test_bluetooth_session",
    )
    entity_registry.async_update_entity(existing.entity_id, name="Garage link")

    with (
        patch(
            "homeassistant.components.teslemetry.PLATFORMS", [Platform.BINARY_SENSOR]
        ),
        patch(
            "homeassistant.components.teslemetry.helpers.TeslaBluetooth"
        ) as mock_parent,
    ):
        mock_parent.return_value.get_private_key = AsyncMock(
            side_effect=OSError("disk gone")
        )
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert (survived := entity_registry.async_get(SESSION_ENTITY_ID))
    assert survived.id == existing.id
    assert survived.name == "Garage link"
    assert hass.states.get(SESSION_ENTITY_ID).state == STATE_UNAVAILABLE
    assert hass.states.get(PRESENCE_ENTITY_ID).state == STATE_OFF


@pytest.mark.usefixtures("enable_bluetooth", "mock_ble_vehicle")
async def test_bluetooth_binary_sensors_removed_with_subentry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Tests that removing the Bluetooth subentry removes both entities."""
    entry = await setup_ble_platform(hass, [Platform.BINARY_SENSOR])

    assert entity_registry.async_get(PRESENCE_ENTITY_ID)
    assert entity_registry.async_get(SESSION_ENTITY_ID)

    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_VEHICLE)[0].subentry_id
    with patch(
        "homeassistant.components.teslemetry.PLATFORMS", [Platform.BINARY_SENSOR]
    ):
        assert hass.config_entries.async_remove_subentry(entry, subentry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get(PRESENCE_ENTITY_ID) is None
    assert entity_registry.async_get(SESSION_ENTITY_ID) is None
