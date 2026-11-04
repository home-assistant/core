"""Tests for the A Better Routeplanner device tracker platform."""

from unittest.mock import MagicMock

from aioabrp import ConnectionEvent, ConnectionState, Location, Telemetry
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abrp.const import DOMAIN
from homeassistant.const import (
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    EVENT_STATE_CHANGED,
    STATE_NOT_HOME,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
    SENSOR_TEST_SUB,
    build_metric_value,
    fire_connection,
    fire_frame,
)

TRACKER_ENTITY_ID = "device_tracker.rivian_r2_2027_standard_long_range_location"
TRACKER_ENTITY_ID_2 = "device_tracker.rivian_r1s_2024_quad_max_location"
# Not in the mocked garage, so the stream never subscribes to it.
_ABSENT_VEHICLE_ID = 999999999999
_AWAY = Location(lat=59.3293, lon=18.0686)
_MOVED = Location(lat=57.7089, lon=11.9746)


def _location_frame(location: Location) -> Telemetry:
    return Telemetry(location=build_metric_value(location))


def _soc_frame() -> Telemetry:
    return Telemetry(soc=build_metric_value(85.0))


def _tracker_changes(events: list[Event[EventStateChangedData]]) -> int:
    return sum(event.data["entity_id"] == TRACKER_ENTITY_ID for event in events)


@pytest.mark.usefixtures("mock_abrp_client")
async def test_device_tracker_snapshot(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    mock_telemetry_stream: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Entity registry + state snapshot for a vehicle's tracker."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()

    await snapshot_platform(
        hass, entity_registry, snapshot, config_entry_with_vehicles.entry_id
    )


@pytest.mark.parametrize(
    ("active_vehicle_id", "expected_entity_id", "other_vehicle_id", "other_entity_id"),
    [
        pytest.param(
            MOCK_VEHICLE_ID,
            TRACKER_ENTITY_ID,
            MOCK_VEHICLE_ID_2,
            TRACKER_ENTITY_ID_2,
            id="vehicle_a_active",
        ),
        pytest.param(
            MOCK_VEHICLE_ID_2,
            TRACKER_ENTITY_ID_2,
            MOCK_VEHICLE_ID,
            TRACKER_ENTITY_ID,
            id="vehicle_b_active",
        ),
    ],
)
@pytest.mark.usefixtures("mock_abrp_client")
async def test_tracker_created_per_vehicle_on_first_position(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
    active_vehicle_id: int,
    expected_entity_id: str,
    other_vehicle_id: int,
    other_entity_id: str,
) -> None:
    """A vehicle's tracker appears on its first position, linked to its device."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(mock_telemetry_stream, active_vehicle_id, _soc_frame())
    fire_frame(mock_telemetry_stream, _ABSENT_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("device_tracker") == []

    for _ in range(2):
        fire_frame(mock_telemetry_stream, active_vehicle_id, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("device_tracker") == [expected_entity_id]
    # HA would otherwise reject a re-created entity, so only the log shows it.
    assert "already exists" not in caplog.text

    entity_entry = entity_registry.async_get(expected_entity_id)
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, f"{SENSOR_TEST_SUB}_{active_vehicle_id}"),
        config_entry_with_vehicles.entry_id,
    )
    assert device is not None
    assert entity_entry.device_id == device.id

    fire_frame(mock_telemetry_stream, other_vehicle_id, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("device_tracker")) == sorted(
        [expected_entity_id, other_entity_id]
    )


@pytest.mark.usefixtures("mock_abrp_client")
async def test_tracker_unavailable_after_auth_failure(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """A terminal stream auth failure hides the position until a reconnect."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()

    fire_connection(
        mock_telemetry_stream, ConnectionEvent(ConnectionState.AUTH_FAILED, "401")
    )
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER_ENTITY_ID).state == STATE_UNAVAILABLE

    fire_connection(mock_telemetry_stream, ConnectionEvent(ConnectionState.CONNECTED))
    await hass.async_block_till_done()
    assert hass.states.get(TRACKER_ENTITY_ID).state == STATE_NOT_HOME


@pytest.mark.usefixtures("mock_abrp_client")
async def test_tracker_skips_unchanged_positions(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Frames without a new position change no state; a new position does."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()

    # A forced write of an unchanged state would still fire state_changed.
    changed = async_capture_events(hass, EVENT_STATE_CHANGED)

    for vehicle_id in (MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2):
        fire_frame(mock_telemetry_stream, vehicle_id, _soc_frame())
    await hass.async_block_till_done()
    assert _tracker_changes(changed) == 0

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_MOVED))
    await hass.async_block_till_done()
    assert _tracker_changes(changed) == 1
    state = hass.states.get(TRACKER_ENTITY_ID)
    assert (state.attributes[ATTR_LATITUDE], state.attributes[ATTR_LONGITUDE]) == (
        _MOVED.lat,
        _MOVED.lon,
    )
