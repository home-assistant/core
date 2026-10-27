"""Tests for the Sofar event platform."""

from collections.abc import Generator
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection, MockModbusUnit
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    async_capture_events,
    async_fire_time_changed,
    snapshot_platform,
)
from pytest_homeassistant.components.common import arm_trigger
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.sofar.const import (
    DOMAIN,
    HAS_FAULT_LOG,
    LAST_HANDLED_FAULT,
    SCAN_INTERVAL,
)
from homeassistant.const import EVENT_STATE_CHANGED, Platform
from homeassistant.core import CoreState, Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_ENTRY_DATA, MOCK_MODEL, MOCK_SERIAL

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


def _handled_entry(*entries: tuple[int, datetime]) -> MockConfigEntry:
    """Mock a Sofar config entry from a run that handled ``entries``."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={
            **MOCK_ENTRY_DATA,
            LAST_HANDLED_FAULT: [
                [fault_id, when.isoformat()] for fault_id, when in entries
            ],
        },
        title=MOCK_MODEL,
    )


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
    ("entry", "expected"),
    [
        pytest.param(
            MockConfigEntry(domain=DOMAIN, unique_id=MOCK_SERIAL, data=MOCK_ENTRY_DATA),
            [],
            id="first_run",
        ),
        pytest.param(
            _handled_entry(GRID_OVER_VOLTAGE),
            [
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="stored_entry_in_log",
        ),
        pytest.param(
            _handled_entry((169, datetime(2026, 10, 1, 9, 0, 0))),
            [
                ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="stored_entry_rotated_out",
        ),
        pytest.param(
            _handled_entry(),
            [
                ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="stored_empty_log",
        ),
    ],
)
@pytest.mark.usefixtures("mock_get_unit")
async def test_setup_fires_only_entries_logged_since_last_run(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    entry: MockConfigEntry,
    expected: list[tuple[str, int, str]],
) -> None:
    """Test a restart fires what was logged since the last run, no more."""
    _seed_log(
        mock_connection.for_unit(1), GRID_OVERFREQUENCY, FAN_1_FAULT, GRID_OVER_VOLTAGE
    )
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)

    assert _fired(events) == expected


@pytest.mark.usefixtures("mock_get_unit")
async def test_entries_wait_until_home_assistant_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test entries logged while down fire once triggers can see them."""
    entry = _handled_entry(GRID_OVER_VOLTAGE)
    _seed_log(mock_connection.for_unit(1), GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    hass.set_state(CoreState.starting)
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)

    assert _fired(events) == []

    hass.set_state(CoreState.running)
    await _poll(hass, freezer)

    assert _fired(events) == [("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00")]


async def test_newest_handled_entry_is_stored(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
    init_integration: MockConfigEntry,
) -> None:
    """Test only the newest handled entry is kept in the config entry."""
    _seed_log(mock_connection.for_unit(1), GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)

    assert init_integration.data[LAST_HANDLED_FAULT] == [[3, "2026-10-09T18:30:05"]]


@pytest.mark.usefixtures("mock_get_unit")
async def test_entries_found_by_first_good_read_do_not_fire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test entries found when a known log first answers count as known."""
    unit = mock_connection.for_unit(1)
    _seed_log(unit, GRID_OVER_VOLTAGE)
    unit.fail_read(FAULT_LOG_REGISTER, ModbusError("busy"))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={**MOCK_ENTRY_DATA, HAS_FAULT_LOG: True},
        title=MOCK_MODEL,
    )
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    await _poll(hass, freezer)
    unit.fail_read(FAULT_LOG_REGISTER, None)
    await _poll(hass, freezer)

    assert _fired(events) == []

    _seed_log(unit, GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)

    assert _fired(events) == [("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00")]


@pytest.mark.usefixtures("init_integration")
async def test_time_zone_change_does_not_refire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a new time zone leaves handled entries handled."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    _seed_log(mock_connection.for_unit(1), GRID_OVER_VOLTAGE)
    await _poll(hass, freezer)
    await hass.config.async_update(time_zone="Europe/Amsterdam")
    await _poll(hass, freezer)

    assert _fired(events) == [("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00")]


@pytest.mark.usefixtures("init_integration")
async def test_entry_logged_during_failed_read_fires_after_it(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a failed read neither replays old entries nor loses new ones."""
    unit = mock_connection.for_unit(1)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    calls: list[str] = []
    await arm_trigger(
        hass,
        "event.received",
        {"event_type": ["grid_overfrequency"]},
        {"entity_id": ENTITY_ID},
        calls,
    )
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
    # The first fault after recovery still runs its automation.
    assert calls == [ENTITY_ID]
