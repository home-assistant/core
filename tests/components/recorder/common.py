"""Common test utils for working with recorder."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import partial
import importlib
import sys
import time
from typing import Any, Literal, cast
from unittest.mock import MagicMock, patch, sentinel

from freezegun import freeze_time
from sqlalchemy import create_engine, select
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.selectable import Select

from homeassistant import core as ha
from homeassistant.components import recorder
from homeassistant.components.recorder import (
    Recorder,
    core,
    get_instance,
    migration,
    statistics,
)
from homeassistant.components.recorder.db_schema import (
    Events,
    EventTypes,
    RecorderRuns,
    States,
    StatesMeta,
)
from homeassistant.components.recorder.tasks import RecorderTask, StatisticsTask
from homeassistant.const import UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, State
import homeassistant.util.dt as dt_util

from . import db_schema_0

DEFAULT_PURGE_TASKS = 3
CREATE_ENGINE_TARGET = "homeassistant.components.recorder.core.create_engine"


@dataclass
class BlockRecorderTask(RecorderTask):
    """A task to block the recorder for testing only."""

    event: asyncio.Event
    seconds: float

    def run(self, instance: Recorder) -> None:
        """Block the recorders event loop."""
        instance.hass.loop.call_soon_threadsafe(self.event.set)
        time.sleep(self.seconds)


@dataclass
class ForceReturnConnectionToPool(RecorderTask):
    """Force return connection to pool."""

    def run(self, instance: Recorder) -> None:
        """Handle the task."""
        instance.event_session.commit()


async def async_block_recorder(hass: HomeAssistant, seconds: float) -> None:
    """Block the recorders event loop for testing.

    Returns as soon as the recorder has started the block.

    Does not wait for the block to finish.
    """
    event = asyncio.Event()
    get_instance(hass).queue_task(BlockRecorderTask(event, seconds))
    await event.wait()


def do_adhoc_statistics(hass: HomeAssistant, **kwargs: Any) -> None:
    """Trigger an adhoc statistics run."""
    if not (start := kwargs.get("start")):
        start = statistics.get_start_time()
    get_instance(hass).queue_task(StatisticsTask(start, False))


def wait_recording_done(hass: HomeAssistant) -> None:
    """Block till recording is done."""
    hass.block_till_done()
    trigger_db_commit(hass)
    hass.block_till_done()
    recorder.get_instance(hass).block_till_done()
    hass.block_till_done()


def trigger_db_commit(hass: HomeAssistant) -> None:
    """Force the recorder to commit."""
    recorder.get_instance(hass)._async_commit(dt_util.utcnow())


async def async_wait_recording_done(hass: HomeAssistant) -> None:
    """Async wait until recording is done."""
    await hass.async_block_till_done()
    async_trigger_db_commit(hass)
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    await hass.async_block_till_done()


async def async_wait_purge_done(
    hass: HomeAssistant, max_number: int | None = None
) -> None:
    """Wait for max number of purge events.

    Because a purge may insert another PurgeTask into
    the queue after the WaitTask finishes, we need up to
    a maximum number of WaitTasks that we will put into the
    queue.
    """
    if not max_number:
        max_number = DEFAULT_PURGE_TASKS
    for _ in range(max_number + 1):
        await async_wait_recording_done(hass)


@ha.callback
def async_trigger_db_commit(hass: HomeAssistant) -> None:
    """Force the recorder to commit. Async friendly."""
    recorder.get_instance(hass)._async_commit(dt_util.utcnow())


async def async_recorder_block_till_done(hass: HomeAssistant) -> None:
    """Non blocking version of recorder.block_till_done()."""
    await hass.async_add_executor_job(recorder.get_instance(hass).block_till_done)


def corrupt_db_file(test_db_file):
    """Corrupt an sqlite3 database file."""
    with open(test_db_file, "w+") as fhandle:
        fhandle.seek(200)
        fhandle.write("I am a corrupt db" * 100)


def create_engine_test(*args, **kwargs):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    engine = create_engine(*args, **kwargs)
    db_schema_0.Base.metadata.create_all(engine)
    return engine


def run_information_with_session(
    session: Session, point_in_time: datetime | None = None
) -> RecorderRuns | None:
    """Return information about current run from the database."""
    recorder_runs = RecorderRuns

    query = session.query(recorder_runs)
    if point_in_time:
        query = query.filter(
            (recorder_runs.start < point_in_time) & (recorder_runs.end > point_in_time)
        )

    if (res := query.first()) is not None:
        session.expunge(res)
        return cast(RecorderRuns, res)
    return res


def statistics_during_period(
    hass: HomeAssistant,
    start_time: datetime,
    end_time: datetime | None = None,
    statistic_ids: set[str] | None = None,
    period: Literal["5minute", "day", "hour", "week", "month"] = "hour",
    units: dict[str, str] | None = None,
    types: set[Literal["last_reset", "max", "mean", "min", "state", "sum"]]
    | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Call statistics_during_period with defaults for simpler tests."""
    if statistic_ids is not None and not isinstance(statistic_ids, set):
        statistic_ids = set(statistic_ids)
    if types is None:
        types = {"last_reset", "max", "mean", "min", "state", "sum"}
    return statistics.statistics_during_period(
        hass, start_time, end_time, statistic_ids, period, units, types
    )


def assert_states_equal_without_context(state: State, other: State) -> None:
    """Assert that two states are equal, ignoring context."""
    assert_states_equal_without_context_and_last_changed(state, other)
    assert state.last_changed == other.last_changed
    assert state.last_reported == other.last_reported


def assert_states_equal_without_context_and_last_changed(
    state: State, other: State
) -> None:
    """Assert that two states are equal, ignoring context and last_changed."""
    assert state.state == other.state
    assert state.attributes == other.attributes
    assert state.last_updated == other.last_updated


def assert_multiple_states_equal_without_context_and_last_changed(
    states: Iterable[State], others: Iterable[State]
) -> None:
    """Assert that multiple states are equal, ignoring context and last_changed."""
    states_list = list(states)
    others_list = list(others)
    assert len(states_list) == len(others_list)
    for i, state in enumerate(states_list):
        assert_states_equal_without_context_and_last_changed(state, others_list[i])


def assert_multiple_states_equal_without_context(
    states: Iterable[State], others: Iterable[State]
) -> None:
    """Assert that multiple states are equal, ignoring context."""
    states_list = list(states)
    others_list = list(others)
    assert len(states_list) == len(others_list)
    for i, state in enumerate(states_list):
        assert_states_equal_without_context(state, others_list[i])


def assert_events_equal_without_context(event: Event, other: Event) -> None:
    """Assert that two events are equal, ignoring context."""
    assert event.data == other.data
    assert event.event_type == other.event_type
    assert event.origin == other.origin
    assert event.time_fired == other.time_fired


def assert_dict_of_states_equal_without_context(
    states: dict[str, list[State]], others: dict[str, list[State]]
) -> None:
    """Assert that two dicts of states are equal, ignoring context."""
    assert len(states) == len(others)
    for entity_id, state in states.items():
        assert_multiple_states_equal_without_context(state, others[entity_id])


def assert_dict_of_states_equal_without_context_and_last_changed(
    states: dict[str, list[State]], others: dict[str, list[State]]
) -> None:
    """Assert that two dicts of states are equal, ignoring context and last_changed."""
    assert len(states) == len(others)
    for entity_id, state in states.items():
        assert_multiple_states_equal_without_context_and_last_changed(
            state, others[entity_id]
        )


async def async_record_states(hass: HomeAssistant):
    """Record some test states."""
    return await hass.async_add_executor_job(record_states, hass)


def record_states(hass):
    """Record some test states.

    We inject a bunch of state updates temperature sensors.
    """
    mp = "media_player.test"
    sns1 = "sensor.test1"
    sns2 = "sensor.test2"
    sns3 = "sensor.test3"
    sns4 = "sensor.test4"
    sns1_attr = {
        "device_class": "temperature",
        "state_class": "measurement",
        "unit_of_measurement": UnitOfTemperature.CELSIUS,
    }
    sns2_attr = {
        "device_class": "humidity",
        "state_class": "measurement",
        "unit_of_measurement": "%",
    }
    sns3_attr = {"device_class": "temperature"}
    sns4_attr = {}

    def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.set(entity_id, state, **kwargs)
        wait_recording_done(hass)
        return hass.states.get(entity_id)

    zero = dt_util.utcnow()
    one = zero + timedelta(seconds=1 * 5)
    two = one + timedelta(seconds=15 * 5)
    three = two + timedelta(seconds=30 * 5)
    four = three + timedelta(seconds=15 * 5)

    states = {mp: [], sns1: [], sns2: [], sns3: [], sns4: []}
    with freeze_time(one) as freezer:
        states[mp].append(
            set_state(mp, "idle", attributes={"media_title": str(sentinel.mt1)})
        )
        states[sns1].append(set_state(sns1, "10", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "10", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "10", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "10", attributes=sns4_attr))

        freezer.move_to(one + timedelta(microseconds=1))
        states[mp].append(
            set_state(mp, "YouTube", attributes={"media_title": str(sentinel.mt2)})
        )

        freezer.move_to(two)
        states[sns1].append(set_state(sns1, "15", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "15", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "15", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "15", attributes=sns4_attr))

        freezer.move_to(three)
        states[sns1].append(set_state(sns1, "20", attributes=sns1_attr))
        states[sns2].append(set_state(sns2, "20", attributes=sns2_attr))
        states[sns3].append(set_state(sns3, "20", attributes=sns3_attr))
        states[sns4].append(set_state(sns4, "20", attributes=sns4_attr))

    return zero, four, states


def convert_pending_states_to_meta(instance: Recorder, session: Session) -> None:
    """Convert pending states to use states_metadata."""
    entity_ids: set[str] = set()
    states: set[States] = set()
    states_meta_objects: dict[str, StatesMeta] = {}
    for session_object in session:
        if isinstance(session_object, States):
            entity_ids.add(session_object.entity_id)
            states.add(session_object)

    entity_id_to_metadata_ids = instance.states_meta_manager.get_many(
        entity_ids, session, True
    )

    for state in states:
        entity_id = state.entity_id
        state.entity_id = None
        state.attributes = None
        state.event_id = None
        if metadata_id := entity_id_to_metadata_ids.get(entity_id):
            state.metadata_id = metadata_id
            continue
        if entity_id not in states_meta_objects:
            states_meta_objects[entity_id] = StatesMeta(entity_id=entity_id)
        state.states_meta_rel = states_meta_objects[entity_id]


def convert_pending_events_to_event_types(instance: Recorder, session: Session) -> None:
    """Convert pending events to use event_type_ids."""
    event_types: set[str] = set()
    events: set[Events] = set()
    event_types_objects: dict[str, EventTypes] = {}
    for session_object in session:
        if isinstance(session_object, Events):
            event_types.add(session_object.event_type)
            events.add(session_object)

    event_type_to_event_type_ids = instance.event_type_manager.get_many(
        event_types, session, True
    )
    manually_added_event_types: list[str] = []

    for event in events:
        event_type = event.event_type
        event.event_type = None
        event.event_data = None
        event.origin = None
        if event_type_id := event_type_to_event_type_ids.get(event_type):
            event.event_type_id = event_type_id
            continue
        if event_type not in event_types_objects:
            event_types_objects[event_type] = EventTypes(event_type=event_type)
            manually_added_event_types.append(event_type)
        event.event_type_rel = event_types_objects[event_type]

    for event_type in manually_added_event_types:
        instance.event_type_manager._non_existent_event_types.pop(event_type, None)


def create_engine_test_for_schema_version_postfix(
    *args, schema_version_postfix: str, **kwargs
):
    """Test version of create_engine that initializes with old schema.

    This simulates an existing db with the old schema.
    """
    schema_module = get_schema_module_path(schema_version_postfix)
    importlib.import_module(schema_module)
    old_db_schema = sys.modules[schema_module]
    engine = create_engine(*args, **kwargs)
    old_db_schema.Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            recorder.db_schema.StatisticsRuns(start=statistics.get_start_time())
        )
        session.add(
            recorder.db_schema.SchemaChanges(
                schema_version=old_db_schema.SCHEMA_VERSION
            )
        )
        session.commit()
    return engine


def get_schema_module_path(schema_version_postfix: str) -> str:
    """Return the path to the schema module."""
    return f"tests.components.recorder.db_schema_{schema_version_postfix}"


@contextmanager
def old_db_schema(schema_version_postfix: str) -> Iterator[None]:
    """Fixture to initialize the db with the old schema."""
    schema_module = get_schema_module_path(schema_version_postfix)
    importlib.import_module(schema_module)
    old_db_schema = sys.modules[schema_module]

    with (
        patch.object(recorder, "db_schema", old_db_schema),
        patch.object(
            recorder.migration, "SCHEMA_VERSION", old_db_schema.SCHEMA_VERSION
        ),
        patch.object(core, "StatesMeta", old_db_schema.StatesMeta),
        patch.object(core, "EventTypes", old_db_schema.EventTypes),
        patch.object(core, "EventData", old_db_schema.EventData),
        patch.object(core, "States", old_db_schema.States),
        patch.object(core, "Events", old_db_schema.Events),
        patch.object(core, "StateAttributes", old_db_schema.StateAttributes),
        patch.object(migration.EntityIDMigration, "task", core.RecorderTask),
        patch(
            CREATE_ENGINE_TARGET,
            new=partial(
                create_engine_test_for_schema_version_postfix,
                schema_version_postfix=schema_version_postfix,
            ),
        ),
    ):
        yield


async def async_attach_db_engine(hass: HomeAssistant) -> None:
    """Attach a database engine to the recorder."""
    instance = recorder.get_instance(hass)

    def _mock_setup_recorder_connection():
        with instance.engine.connect() as connection:
            instance._setup_recorder_connection(
                connection._dbapi_connection, MagicMock()
            )

    await instance.async_add_executor_job(_mock_setup_recorder_connection)


def select_event_type_ids(event_types: tuple[str, ...]) -> Select:
    """Generate a select for event type ids.

    This query is intentionally not a lambda statement as it is used inside
    other lambda statements.
    """
    return select(EventTypes.event_type_id).where(
        EventTypes.event_type.in_(event_types),
    )
