"""Test the Teslemetry binary sensor platform."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.teslemetry.coordinator import VEHICLE_INTERVAL
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, setup_platform
from .const import VEHICLE_DATA_ALT

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_binary_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()

    # Reload the entry
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Assert the entities restored their values
    for entity_id in (
        "binary_sensor.test_front_driver_window",
        "binary_sensor.test_front_passenger_window",
        "binary_sensor.test_rear_driver_window",
        "binary_sensor.test_rear_passenger_window",
        "binary_sensor.test_front_driver_door",
        "binary_sensor.test_front_passenger_door",
        "binary_sensor.test_driver_seat_belt",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-state")


async def test_binary_sensors_connectivity(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
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

    # Assert the entities restored their values
    for entity_id in (
        "binary_sensor.test_cellular",
        "binary_sensor.test_wifi",
    ):
        state = hass.states.get(entity_id)
        assert state.state == snapshot(name=f"{entity_id}-state")
