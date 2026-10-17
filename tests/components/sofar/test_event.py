"""Tests for the Sofar event platform."""

from collections.abc import Generator
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.sofar.const import SCAN_INTERVAL
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State
from homeassistant.helpers import entity_registry as er

ENTITY_ID = "event.4_4_ktlx_g3_fault"
FAULT_LOG_REGISTER = 0x1480

# Log entries as (fault id, inverter clock).
GRID_OVER_VOLTAGE = (1, datetime(2026, 10, 9, 17, 1, 23))
FAN_1_FAULT = (169, datetime(2026, 10, 9, 17, 1, 23))
GRID_OVERFREQUENCY = (3, datetime(2026, 10, 9, 18, 30, 5))
GRID_OVER_VOLTAGE_AGAIN = (1, datetime(2026, 10, 10, 7, 45, 0))


@pytest.fixture(autouse=True)
def platforms() -> Generator[None]:
    """Set up only the event platform."""
    with patch("homeassistant.components.sofar.PLATFORMS", [Platform.EVENT]):
        yield


def _seed_log(unit: MockModbusUnit, *entries: tuple[int, datetime]) -> None:
    """Write the inverter's fault log, newest entry first."""
    for number, (fault_id, when) in enumerate(entries):
        address = FAULT_LOG_REGISTER + 4 * number
        unit.holding[address] = fault_id
        unit.holding[address + 1] = (when.year - 2000) << 8 | when.month
        unit.holding[address + 2] = when.day << 8 | when.hour
        unit.holding[address + 3] = when.minute << 8 | when.second


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the readings coordinator poll once."""
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


def _fired(events: list[Event[EventStateChangedData]]) -> list[tuple[str, int, str]]:
    """Every event the entity showed, as fault key, id and log time."""
    # Keyed by timestamp, so returning from unavailable is not an event.
    return list(
        {
            state.state: (
                state.attributes[ATTR_EVENT_TYPE],
                state.attributes["fault_id"],
                state.attributes["occurred_at"],
            )
            for event in events
            if event.data["entity_id"] == ENTITY_ID
            and (state := event.data["new_state"]) is not None
            and state.attributes.get(ATTR_EVENT_TYPE) is not None
        }.values()
    )


async def test_all_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    init_integration: MockConfigEntry,
) -> None:
    """Test all entities match their snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, init_integration.entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_new_entries_fire_one_event_each_oldest_first(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test entries logged between polls fire in the order they happened."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    _seed_log(
        mock_connection.for_unit(1),
        GRID_OVERFREQUENCY,
        FAN_1_FAULT,
        GRID_OVER_VOLTAGE,
    )
    await _poll(hass, freezer)

    assert _fired(events) == [
        ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
        ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
        ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
    ]
    state = hass.states.get(ENTITY_ID)
    assert state is not None
    assert state.attributes["category"] == "grid"


@pytest.mark.usefixtures("init_integration")
async def test_entry_fires_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test an entry fires once, and the same fault logged again refires."""
    unit = mock_connection.for_unit(1)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    _seed_log(unit, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)
    await _poll(hass, freezer)

    assert _fired(events) == [("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00")]

    _seed_log(unit, GRID_OVER_VOLTAGE_AGAIN, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)

    assert _fired(events) == [
        ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
        ("grid_over_voltage", 1, "2026-10-10T07:45:00-07:00"),
    ]


@pytest.mark.parametrize(
    ("restored", "expected"),
    [
        pytest.param([], [], id="nothing_restored"),
        pytest.param(
            [{"fault_id": 169, "occurred_at": "2026-10-09T17:01:23-07:00"}],
            [
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="restored_entry_in_log",
        ),
        pytest.param(
            [{"fault_id": 169, "occurred_at": "2026-10-01T09:00:00-07:00"}],
            [("fan_1_fault", 169, "2026-10-01T09:00:00-07:00")],
            id="restored_entry_out_of_log",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_fires_only_entries_since_restored_event(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
    restored: list[dict[str, Any]],
    expected: list[tuple[str, int, str]],
) -> None:
    """Test a restart fires only what was logged since the restored event."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(ENTITY_ID, "2026-10-09T17:01:33.000+00:00"),
                {
                    "last_event_type": "fan_1_fault",
                    "last_event_attributes": attributes,
                },
            )
            for attributes in restored
        ],
    )
    _seed_log(
        mock_connection.for_unit(1), GRID_OVERFREQUENCY, FAN_1_FAULT, GRID_OVER_VOLTAGE
    )
    mock_config_entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)

    assert _fired(events) == expected


@pytest.mark.usefixtures("mock_get_unit")
async def test_entries_found_by_first_good_read_do_not_fire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test entries found when the log first answers count as known."""
    unit = mock_connection.for_unit(1)
    _seed_log(unit, GRID_OVER_VOLTAGE)
    unit.fail_read(FAULT_LOG_REGISTER, ModbusError("busy"))
    mock_config_entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)
    unit.fail_read(FAULT_LOG_REGISTER, None)
    await _poll(hass, freezer)

    assert _fired(events) == []


@pytest.mark.usefixtures("init_integration")
async def test_entry_logged_during_failed_read_fires_after_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed read neither replays old entries nor loses new ones."""
    unit = mock_connection.for_unit(1)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    _seed_log(unit, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)
    unit.fail_read(FAULT_LOG_REGISTER, ModbusError("busy"))
    _seed_log(unit, GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)

    assert _fired(events) == [("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00")]

    unit.fail_read(FAULT_LOG_REGISTER, None)
    await _poll(hass, freezer)

    assert _fired(events) == [
        ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
        ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
    ]
