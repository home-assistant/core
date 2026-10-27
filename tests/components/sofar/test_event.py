"""Tests for the Sofar event platform."""

from collections.abc import Generator
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from modbus_connection import ModbusError
from modbus_connection.mock import MockModbusConnection
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
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import CoreState, Event, EventStateChangedData, HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import (
    FAULT_LOG_REGISTER,
    MOCK_ENTRY_DATA,
    MOCK_MODEL,
    MOCK_SERIAL,
    seed_fault_log,
)

ENTITY_ID = "event.4_4_ktlx_g3_fault"

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


def _handled_entry(handled: list[int | str] | None) -> MockConfigEntry:
    """Mock a Sofar config entry from a run that handled up to ``handled``."""
    return MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={**MOCK_ENTRY_DATA, LAST_HANDLED_FAULT: handled},
        title=MOCK_MODEL,
    )


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
    seed_fault_log(
        mock_connection.for_unit(1),
        GRID_OVERFREQUENCY,
        FAN_1_FAULT,
        GRID_OVER_VOLTAGE,
    )
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

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
    seed_fault_log(unit, GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == [("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00")]

    seed_fault_log(unit, GRID_OVER_VOLTAGE_AGAIN, GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

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
            _handled_entry([1, "2026-10-09T17:01:23"]),
            [
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="stored_entry_in_log",
        ),
        pytest.param(
            _handled_entry([169, "2026-10-01T09:00:00"]),
            [
                ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
                ("fan_1_fault", 169, "2026-10-09T17:01:23-07:00"),
                ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
            ],
            id="stored_entry_rotated_out",
        ),
        pytest.param(
            _handled_entry(None),
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
    seed_fault_log(
        mock_connection.for_unit(1), GRID_OVERFREQUENCY, FAN_1_FAULT, GRID_OVER_VOLTAGE
    )
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == expected


@pytest.mark.usefixtures("mock_get_unit")
async def test_entries_wait_until_home_assistant_runs(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test entries logged while down fire once triggers can see them."""
    entry = _handled_entry([1, "2026-10-09T17:01:23"])
    seed_fault_log(mock_connection.for_unit(1), GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    hass.set_state(CoreState.starting)
    entry.add_to_hass(hass)
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == []

    hass.set_state(CoreState.running)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == [("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00")]


@pytest.mark.usefixtures("mock_get_unit")
async def test_entries_found_by_first_good_read_do_not_fire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a log unread at setup fires only what is logged after it answers."""
    unit = mock_connection.for_unit(1)
    seed_fault_log(unit, GRID_OVER_VOLTAGE)
    unit.fail_read(FAULT_LOG_REGISTER, ModbusError("busy"))
    # A stored log keeps its entity even though setup cannot read it.
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MOCK_SERIAL,
        data={**MOCK_ENTRY_DATA, HAS_FAULT_LOG: True},
        title=MOCK_MODEL,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    unit.fail_read(FAULT_LOG_REGISTER, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    seed_fault_log(unit, GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        hass.states.get(ENTITY_ID).attributes[ATTR_EVENT_TYPE] == "grid_overfrequency"
    )


@pytest.mark.usefixtures("init_integration")
async def test_time_zone_change_does_not_refire(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_connection: MockModbusConnection,
) -> None:
    """Test a new time zone leaves handled entries handled."""
    events = async_capture_events(hass, EVENT_STATE_CHANGED)
    seed_fault_log(mock_connection.for_unit(1), GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.config.async_update(time_zone="Europe/Amsterdam")
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

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
    seed_fault_log(unit, GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    unit.fail_read(FAULT_LOG_REGISTER, ModbusError("busy"))
    seed_fault_log(unit, GRID_OVERFREQUENCY, GRID_OVER_VOLTAGE)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == [("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00")]

    unit.fail_read(FAULT_LOG_REGISTER, None)
    freezer.tick(timedelta(seconds=SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert _fired(events) == [
        ("grid_over_voltage", 1, "2026-10-09T17:01:23-07:00"),
        ("grid_overfrequency", 3, "2026-10-09T18:30:05-07:00"),
    ]
    # The first fault after recovery still runs its automation.
    assert calls == [ENTITY_ID]
