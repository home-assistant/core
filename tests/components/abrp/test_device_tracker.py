"""Tests for the A Better Routeplanner device tracker platform."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from aioabrp import ConnectionEvent, ConnectionState, Location, MetricValue, Telemetry
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import EVENT_STATE_CHANGED, STATE_NOT_HOME, STATE_UNAVAILABLE
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import (
    MOCK_VEHICLE_ID,
    MOCK_VEHICLE_ID_2,
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
_REPORTED = datetime(2026, 11, 9, 7, 0, tzinfo=UTC)


def _location_frame(location: Location, time: datetime = _REPORTED) -> Telemetry:
    return Telemetry(location=MetricValue(value=location, time=time, provider=None))


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


@pytest.mark.usefixtures("mock_abrp_client")
async def test_tracker_created_per_vehicle_on_first_position(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A vehicle's tracker appears on its first position, once per vehicle."""
    await setup_integration(hass, config_entry_with_vehicles)

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _soc_frame())
    fire_frame(mock_telemetry_stream, _ABSENT_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("device_tracker") == []

    for _ in range(2):
        fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert hass.states.async_entity_ids("device_tracker") == [TRACKER_ENTITY_ID]
    # HA would otherwise reject a re-created entity, so only the log shows it.
    assert "already exists" not in caplog.text

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID_2, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert sorted(hass.states.async_entity_ids("device_tracker")) == sorted(
        [TRACKER_ENTITY_ID, TRACKER_ENTITY_ID_2]
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
async def test_tracker_writes_only_new_position_reports(
    hass: HomeAssistant,
    config_entry_with_vehicles: MockConfigEntry,
    mock_telemetry_stream: MagicMock,
) -> None:
    """Each new position report is written; other frames and replays are not."""
    await setup_integration(hass, config_entry_with_vehicles)
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()
    changed = async_capture_events(hass, EVENT_STATE_CHANGED)

    for vehicle_id in (MOCK_VEHICLE_ID, MOCK_VEHICLE_ID_2):
        fire_frame(mock_telemetry_stream, vehicle_id, _soc_frame())
    # A reconnect replays the last report with its original timestamp.
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY))
    await hass.async_block_till_done()
    assert _tracker_changes(changed) == 0

    later = _REPORTED + timedelta(minutes=1)
    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_AWAY, later))
    await hass.async_block_till_done()
    assert _tracker_changes(changed) == 1

    fire_frame(mock_telemetry_stream, MOCK_VEHICLE_ID, _location_frame(_MOVED, later))
    await hass.async_block_till_done()
    assert _tracker_changes(changed) == 2
