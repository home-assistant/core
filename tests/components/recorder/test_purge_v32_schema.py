"""Test data purging."""

from datetime import datetime, timedelta
import json
import sqlite3
from unittest.mock import MagicMock, patch

from freezegun import freeze_time
import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm.session import Session

from homeassistant.components import recorder
from homeassistant.components.recorder import migration
from homeassistant.components.recorder.const import (
    SQLITE_MAX_BIND_VARS,
    SupportedDialect,
)
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.services import (
    SERVICE_PURGE,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.components.recorder.tasks import PurgeTask
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .common import (
    async_recorder_block_till_done,
    async_wait_purge_done,
    async_wait_recording_done,
    old_db_schema,
)

from tests.components.recorder.db_schema_32 import (
    EventData,
    Events,
    RecorderRuns,
    StateAttributes,
    States,
    StatisticsRuns,
    StatisticsShortTerm,
)
from tests.typing import RecorderInstanceGenerator


@pytest.fixture(autouse=True)
def db_schema_32():
    """Fixture to initialize the db with the old schema 32."""
    with old_db_schema("32"):
        yield


@pytest.fixture(name="use_sqlite")
def mock_use_sqlite(request):
    """Pytest fixture to switch purge method."""
    with patch(
        "homeassistant.components.recorder.core.Recorder.dialect_name",
        return_value=SupportedDialect.SQLITE
        if request.param
        else SupportedDialect.MYSQL,
    ):
        yield


async def _async_attach_db_engine(hass: HomeAssistant) -> None:
    """Attach a database engine to the recorder."""
    instance = recorder.get_instance(hass)

    def _mock_setup_recorder_connection():
        with instance.engine.connect() as connection:
            instance._setup_recorder_connection(
                connection._dbapi_connection, MagicMock()
            )

    await instance.async_add_executor_job(_mock_setup_recorder_connection)


async def test_purge_old_states(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old states."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_states(hass)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)

        assert states.count() == 6
        assert states[0].old_state_id is None
        assert states[5].old_state_id == states[4].state_id
        assert state_attributes.count() == 3

        events = session.query(Events).filter(Events.event_type == "state_changed")
        assert events.count() == 0
        assert "test.recorder2" in instance.states_manager._last_committed_id

        purge_before = dt_util.utcnow() - timedelta(days=4)

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            purge_before,
            states_batch_size=1,
            events_batch_size=1,
            repack=False,
        )
        assert not finished
        assert states.count() == 2
        assert state_attributes.count() == 1

        assert "test.recorder2" in instance.states_manager._last_committed_id

        states_after_purge = list(session.query(States))
        # Since these states are deleted in batches, we can't guarantee the order
        # but we can look them up by state
        state_map_by_state = {state.state: state for state in states_after_purge}
        dontpurgeme_5 = state_map_by_state["dontpurgeme_5"]
        dontpurgeme_4 = state_map_by_state["dontpurgeme_4"]

        assert dontpurgeme_5.old_state_id == dontpurgeme_4.state_id
        assert dontpurgeme_4.old_state_id is None

        finished = purge_old_data(instance, purge_before, repack=False)
        assert finished
        assert states.count() == 2
        assert state_attributes.count() == 1

        assert "test.recorder2" in instance.states_manager._last_committed_id

        # run purge_old_data again
        purge_before = dt_util.utcnow()
        finished = purge_old_data(
            instance,
            purge_before,
            states_batch_size=1,
            events_batch_size=1,
            repack=False,
        )
        assert not finished
        assert states.count() == 0
        assert state_attributes.count() == 0

        assert "test.recorder2" not in instance.states_manager._last_committed_id

    # Add some more states
    await _add_test_states(hass)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6
        assert states[0].old_state_id is None
        assert states[5].old_state_id == states[4].state_id

        events = session.query(Events).filter(Events.event_type == "state_changed")
        assert events.count() == 0
        assert "test.recorder2" in instance.states_manager._last_committed_id

        state_attributes = session.query(StateAttributes)
        assert state_attributes.count() == 3


async def test_purge_old_states_encouters_database_corruption(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
) -> None:
    """Test database image image is malformed while deleting old states."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        # This test is specific for SQLite, wiping the database on error only happens
        # with SQLite.
        return

    await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_states(hass)
    await async_wait_recording_done(hass)

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with patch(
        "homeassistant.components.recorder.core.move_away_broken_database"
    ) as move_away, patch(
        "homeassistant.components.recorder.purge.purge_old_data",
        side_effect=sqlite3_exception,
    ):
        await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, {"keep_days": 0})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

    assert move_away.called

    # Ensure the whole database was reset due to the database error
    with session_scope(hass=hass) as session:
        states_after_purge = session.query(States)
        assert states_after_purge.count() == 0


async def test_purge_old_states_encounters_temporary_mysql_error(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test retry on specific mysql operational errors."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_states(hass)
    await async_wait_recording_done(hass)

    mysql_exception = OperationalError("statement", {}, [])
    mysql_exception.orig = Exception(1205, "retryable")

    with patch(
        "homeassistant.components.recorder.util.time.sleep"
    ) as sleep_mock, patch(
        "homeassistant.components.recorder.purge._purge_old_recorder_runs",
        side_effect=[mysql_exception, None],
    ), patch.object(
        instance.engine.dialect, "name", "mysql"
    ):
        await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, {"keep_days": 0})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

    assert "retrying" in caplog.text
    assert sleep_mock.called


async def test_purge_old_states_encounters_operational_error(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error on operational errors that are not mysql does not retry."""
    await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_states(hass)
    await async_wait_recording_done(hass)

    exception = OperationalError("statement", {}, [])

    with patch(
        "homeassistant.components.recorder.purge._purge_old_recorder_runs",
        side_effect=exception,
    ):
        await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, {"keep_days": 0})
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
        await async_wait_recording_done(hass)

    assert "retrying" not in caplog.text
    assert "Error executing purge" in caplog.text


async def test_purge_old_events(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old events."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_events(hass)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        purge_before = dt_util.utcnow() - timedelta(days=4)

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        assert not finished
        assert events.count() == 2

        # we should only have 2 events left
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        assert finished
        assert events.count() == 2


async def test_purge_old_recorder_runs(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old recorder runs keeps current run."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_recorder_runs(hass)

    # make sure we start with 7 recorder runs
    with session_scope(hass=hass) as session:
        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        purge_before = dt_util.utcnow()

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        assert not finished

        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        assert finished
        assert recorder_runs.count() == 1


async def test_purge_old_statistics_runs(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old statistics runs keeps the latest run."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_statistics_runs(hass)

    # make sure we start with 7 statistics runs
    with session_scope(hass=hass) as session:
        statistics_runs = session.query(StatisticsRuns)
        assert statistics_runs.count() == 7

        purge_before = dt_util.utcnow()

        # run purge_old_data()
        finished = purge_old_data(instance, purge_before, repack=False)
        assert not finished

        finished = purge_old_data(instance, purge_before, repack=False)
        assert finished
        assert statistics_runs.count() == 1


@pytest.mark.parametrize("use_sqlite", (True, False), indirect=True)
async def test_purge_method(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    use_sqlite: bool,
) -> None:
    """Test purge method."""

    def assert_recorder_runs_equal(run1, run2):
        assert run1.run_id == run2.run_id
        assert run1.start == run2.start
        assert run1.end == run2.end
        assert run1.closed_incorrect == run2.closed_incorrect
        assert run1.created == run2.created

    def assert_statistic_runs_equal(run1, run2):
        assert run1.run_id == run2.run_id
        assert run1.start == run2.start

    await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    service_data = {"keep_days": 4}
    await _add_test_events(hass)
    await _add_test_states(hass)
    await _add_test_statistics(hass)
    await _add_test_recorder_runs(hass)
    await _add_test_statistics_runs(hass)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6

        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        statistics = session.query(StatisticsShortTerm)
        assert statistics.count() == 6

        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7
        runs_before_purge = recorder_runs.all()

        statistics_runs = session.query(StatisticsRuns).order_by(StatisticsRuns.run_id)
        assert statistics_runs.count() == 7
        statistic_runs_before_purge = statistics_runs.all()

        for itm in runs_before_purge:
            session.expunge(itm)
        for itm in statistic_runs_before_purge:
            session.expunge(itm)

    await hass.async_block_till_done()
    await async_wait_purge_done(hass)

    # run purge method - no service data, use defaults
    await hass.services.async_call("recorder", "purge")
    await hass.async_block_till_done()

    # Small wait for recorder thread
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        statistics = session.query(StatisticsShortTerm)

        # only purged old states, events and statistics
        assert states.count() == 4
        assert events.count() == 4
        assert statistics.count() == 4

    # run purge method - correct service data
    await hass.services.async_call("recorder", "purge", service_data=service_data)
    await hass.async_block_till_done()

    # Small wait for recorder thread
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        statistics = session.query(StatisticsShortTerm)
        recorder_runs = session.query(RecorderRuns)
        statistics_runs = session.query(StatisticsRuns)

        # we should only have 2 states, events and statistics left after purging
        assert states.count() == 2
        assert events.count() == 2
        assert statistics.count() == 2

        # now we should only have 3 recorder runs left
        runs = recorder_runs.all()
        assert_recorder_runs_equal(runs[0], runs_before_purge[0])
        assert_recorder_runs_equal(runs[1], runs_before_purge[5])
        assert_recorder_runs_equal(runs[2], runs_before_purge[6])

        # now we should only have 3 statistics runs left
        runs = statistics_runs.all()
        assert_statistic_runs_equal(runs[0], statistic_runs_before_purge[0])
        assert_statistic_runs_equal(runs[1], statistic_runs_before_purge[5])
        assert_statistic_runs_equal(runs[2], statistic_runs_before_purge[6])

        assert "EVENT_TEST_PURGE" not in (event.event_type for event in events.all())

    # run purge method - correct service data, with repack
    service_data["repack"] = True
    await hass.services.async_call("recorder", "purge", service_data=service_data)
    await hass.async_block_till_done()
    await async_wait_purge_done(hass)
    assert (
        "Vacuuming SQL DB to free space" in caplog.text
        or "Optimizing SQL DB to free space" in caplog.text
    )


@pytest.mark.parametrize("use_sqlite", (True, False), indirect=True)
async def test_purge_edge_case(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    use_sqlite: bool,
) -> None:
    """Test states and events are purged even if they occurred shortly before purge_before."""

    async def _add_db_entries(hass: HomeAssistant, timestamp: datetime) -> None:
        with session_scope(hass=hass) as session:
            session.add(
                Events(
                    event_id=1001,
                    event_type="EVENT_TEST_PURGE",
                    event_data="{}",
                    origin="LOCAL",
                    time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            session.add(
                States(
                    entity_id="test.recorder2",
                    state="purgeme",
                    attributes="{}",
                    last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                    last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                    event_id=1001,
                    attributes_id=1002,
                )
            )
            session.add(
                StateAttributes(
                    shared_attrs="{}",
                    hash=1234,
                    attributes_id=1002,
                )
            )

    await async_setup_recorder_instance(hass, None)
    await _async_attach_db_engine(hass)

    await async_wait_purge_done(hass)

    service_data = {"keep_days": 2}
    timestamp = dt_util.utcnow() - timedelta(days=2, minutes=1)

    await _add_db_entries(hass, timestamp)
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 1

        state_attributes = session.query(StateAttributes)
        assert state_attributes.count() == 1

        events = session.query(Events).filter(Events.event_type == "EVENT_TEST_PURGE")
        assert events.count() == 1

    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 0
        events = session.query(Events).filter(Events.event_type == "EVENT_TEST_PURGE")
        assert events.count() == 0


async def test_purge_cutoff_date(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> None:
    """Test states and events are purged only if they occurred before "now() - keep_days"."""

    async def _add_db_entries(hass: HomeAssistant, cutoff: datetime, rows: int) -> None:
        timestamp_keep = cutoff
        timestamp_purge = cutoff - timedelta(microseconds=1)

        with session_scope(hass=hass) as session:
            session.add(
                Events(
                    event_id=1000,
                    event_type="KEEP",
                    event_data="{}",
                    origin="LOCAL",
                    time_fired_ts=dt_util.utc_to_timestamp(timestamp_keep),
                )
            )
            session.add(
                States(
                    entity_id="test.cutoff",
                    state="keep",
                    attributes="{}",
                    last_changed_ts=dt_util.utc_to_timestamp(timestamp_keep),
                    last_updated_ts=dt_util.utc_to_timestamp(timestamp_keep),
                    event_id=1000,
                    attributes_id=1000,
                )
            )
            session.add(
                StateAttributes(
                    shared_attrs="{}",
                    hash=1234,
                    attributes_id=1000,
                )
            )
            for row in range(1, rows):
                session.add(
                    Events(
                        event_id=1000 + row,
                        event_type="PURGE",
                        event_data="{}",
                        origin="LOCAL",
                        time_fired_ts=dt_util.utc_to_timestamp(timestamp_purge),
                    )
                )
                session.add(
                    States(
                        entity_id="test.cutoff",
                        state="purge",
                        attributes="{}",
                        last_changed_ts=dt_util.utc_to_timestamp(timestamp_purge),
                        last_updated_ts=dt_util.utc_to_timestamp(timestamp_purge),
                        event_id=1000 + row,
                        attributes_id=1000 + row,
                    )
                )
                session.add(
                    StateAttributes(
                        shared_attrs="{}",
                        hash=1234,
                        attributes_id=1000 + row,
                    )
                )

    instance = await async_setup_recorder_instance(hass, None)
    await _async_attach_db_engine(hass)

    await async_wait_purge_done(hass)

    service_data = {"keep_days": 2}

    # Force multiple purge batches to be run
    rows = SQLITE_MAX_BIND_VARS + 1
    cutoff = dt_util.utcnow() - timedelta(days=service_data["keep_days"])
    await _add_db_entries(hass, cutoff, rows)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        events = session.query(Events)
        assert states.filter(States.state == "purge").count() == rows - 1
        assert states.filter(States.state == "keep").count() == 1
        assert (
            state_attributes.outerjoin(
                States, StateAttributes.attributes_id == States.attributes_id
            )
            .filter(States.state == "keep")
            .count()
            == 1
        )
        assert events.filter(Events.event_type == "PURGE").count() == rows - 1
        assert events.filter(Events.event_type == "KEEP").count() == 1

    instance.queue_task(PurgeTask(cutoff, repack=False, apply_filter=False))
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        events = session.query(Events)
        assert states.filter(States.state == "purge").count() == 0
        assert (
            state_attributes.outerjoin(
                States, StateAttributes.attributes_id == States.attributes_id
            )
            .filter(States.state == "purge")
            .count()
            == 0
        )
        assert states.filter(States.state == "keep").count() == 1
        assert (
            state_attributes.outerjoin(
                States, StateAttributes.attributes_id == States.attributes_id
            )
            .filter(States.state == "keep")
            .count()
            == 1
        )
        assert events.filter(Events.event_type == "PURGE").count() == 0
        assert events.filter(Events.event_type == "KEEP").count() == 1

    # Make sure we can purge everything
    instance.queue_task(PurgeTask(dt_util.utcnow(), repack=False, apply_filter=False))
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 0
        assert state_attributes.count() == 0

    # Make sure we can purge everything when the db is already empty
    instance.queue_task(PurgeTask(dt_util.utcnow(), repack=False, apply_filter=False))
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 0
        assert state_attributes.count() == 0


async def _add_test_states(hass: HomeAssistant):
    """Add multiple states to the db for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    base_attributes = {"test_attr": 5, "test_attr_10": "nice"}

    async def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

    for event_id in range(6):
        if event_id < 2:
            timestamp = eleven_days_ago
            state = f"autopurgeme_{event_id}"
            attributes = {"autopurgeme": True, **base_attributes}
        elif event_id < 4:
            timestamp = five_days_ago
            state = f"purgeme_{event_id}"
            attributes = {"purgeme": True, **base_attributes}
        else:
            timestamp = utcnow
            state = f"dontpurgeme_{event_id}"
            attributes = {"dontpurgeme": True, **base_attributes}

        with freeze_time(timestamp):
            await set_state("test.recorder2", state, attributes=attributes)


async def _add_test_events(hass: HomeAssistant, iterations: int = 1):
    """Add a few events for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        for _ in range(iterations):
            for event_id in range(6):
                if event_id < 2:
                    timestamp = eleven_days_ago
                    event_type = "EVENT_TEST_AUTOPURGE"
                elif event_id < 4:
                    timestamp = five_days_ago
                    event_type = "EVENT_TEST_PURGE"
                else:
                    timestamp = utcnow
                    event_type = "EVENT_TEST"

                session.add(
                    Events(
                        event_type=event_type,
                        event_data=json.dumps(event_data),
                        origin="LOCAL",
                        time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                    )
                )


async def _add_events_with_event_data(hass: HomeAssistant, iterations: int = 1):
    """Add a few events with linked event_data for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        for _ in range(iterations):
            for event_id in range(6):
                if event_id < 2:
                    timestamp = eleven_days_ago
                    event_type = "EVENT_TEST_AUTOPURGE_WITH_EVENT_DATA"
                    shared_data = '{"type":{"EVENT_TEST_AUTOPURGE_WITH_EVENT_DATA"}'
                elif event_id < 4:
                    timestamp = five_days_ago
                    event_type = "EVENT_TEST_PURGE_WITH_EVENT_DATA"
                    shared_data = '{"type":{"EVENT_TEST_PURGE_WITH_EVENT_DATA"}'
                else:
                    timestamp = utcnow
                    event_type = "EVENT_TEST_WITH_EVENT_DATA"
                    shared_data = '{"type":{"EVENT_TEST_WITH_EVENT_DATA"}'

                event_data = EventData(hash=1234, shared_data=shared_data)

                session.add(
                    Events(
                        event_type=event_type,
                        origin="LOCAL",
                        time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                        event_data_rel=event_data,
                    )
                )


async def _add_test_statistics(hass: HomeAssistant):
    """Add multiple statistics to the db for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                state = "-11"
            elif event_id < 4:
                timestamp = five_days_ago
                state = "-5"
            else:
                timestamp = utcnow
                state = "0"

            session.add(
                StatisticsShortTerm(
                    start_ts=timestamp.timestamp(),
                    state=state,
                )
            )


async def _add_test_recorder_runs(hass: HomeAssistant):
    """Add a few recorder_runs for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        for rec_id in range(6):
            if rec_id < 2:
                timestamp = eleven_days_ago
            elif rec_id < 4:
                timestamp = five_days_ago
            else:
                timestamp = utcnow

            session.add(
                RecorderRuns(
                    start=timestamp,
                    created=dt_util.utcnow(),
                    end=timestamp + timedelta(days=1),
                )
            )


async def _add_test_statistics_runs(hass: HomeAssistant):
    """Add a few recorder_runs for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        for rec_id in range(6):
            if rec_id < 2:
                timestamp = eleven_days_ago
            elif rec_id < 4:
                timestamp = five_days_ago
            else:
                timestamp = utcnow

            session.add(
                StatisticsRuns(
                    start=timestamp,
                )
            )


def _add_state_without_event_linkage(
    session: Session,
    entity_id: str,
    state: str,
    timestamp: datetime,
):
    state_attrs = StateAttributes(
        hash=1234, shared_attrs=json.dumps({entity_id: entity_id})
    )
    session.add(state_attrs)
    session.add(
        States(
            entity_id=entity_id,
            state=state,
            attributes=None,
            last_changed_ts=dt_util.utc_to_timestamp(timestamp),
            last_updated_ts=dt_util.utc_to_timestamp(timestamp),
            event_id=None,
            state_attributes=state_attrs,
        )
    )


def _add_state_and_state_changed_event(
    session: Session,
    entity_id: str,
    state: str,
    timestamp: datetime,
    event_id: int,
) -> None:
    """Add state and state_changed event to database for testing."""
    state_attrs = StateAttributes(
        hash=event_id, shared_attrs=json.dumps({entity_id: entity_id})
    )
    session.add(state_attrs)
    session.add(
        States(
            entity_id=entity_id,
            state=state,
            attributes=None,
            last_changed_ts=dt_util.utc_to_timestamp(timestamp),
            last_updated_ts=dt_util.utc_to_timestamp(timestamp),
            event_id=event_id,
            state_attributes=state_attrs,
        )
    )
    session.add(
        Events(
            event_id=event_id,
            event_type=EVENT_STATE_CHANGED,
            event_data="{}",
            origin="LOCAL",
            time_fired_ts=dt_util.utc_to_timestamp(timestamp),
        )
    )


async def test_purge_many_old_events(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old events."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await _add_test_events(hass, SQLITE_MAX_BIND_VARS)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == SQLITE_MAX_BIND_VARS * 6

        purge_before = dt_util.utcnow() - timedelta(days=4)

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            states_batch_size=3,
            events_batch_size=3,
        )
        assert not finished
        assert events.count() == SQLITE_MAX_BIND_VARS * 3

        # we should only have 2 groups of events left
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            states_batch_size=3,
            events_batch_size=3,
        )
        assert finished
        assert events.count() == SQLITE_MAX_BIND_VARS * 2

        # we should now purge everything
        finished = purge_old_data(
            instance,
            dt_util.utcnow(),
            repack=False,
            states_batch_size=20,
            events_batch_size=20,
        )
        assert finished
        assert events.count() == 0


async def test_purge_can_mix_legacy_and_new_format(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test purging with legacy and new events."""
    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await async_wait_recording_done(hass)
    # New databases are no longer created with the legacy events index
    assert instance.use_legacy_events_index is False

    def _recreate_legacy_events_index():
        """Recreate the legacy events index since its no longer created on new instances."""
        migration._create_index(instance.get_session, "states", "ix_states_event_id")
        instance.use_legacy_events_index = True

    await instance.async_add_executor_job(_recreate_legacy_events_index)
    assert instance.use_legacy_events_index is True

    utcnow = dt_util.utcnow()
    eleven_days_ago = utcnow - timedelta(days=11)

    with session_scope(hass=hass) as session:
        broken_state_no_time = States(
            event_id=None,
            entity_id="orphened.state",
            last_updated_ts=None,
            last_changed_ts=None,
        )
        session.add(broken_state_no_time)
        start_id = 50000
        for event_id in range(start_id, start_id + 50):
            _add_state_and_state_changed_event(
                session,
                "sensor.excluded",
                "purgeme",
                eleven_days_ago,
                event_id,
            )
    await _add_test_events(hass, 50)
    await _add_events_with_event_data(hass, 50)
    with session_scope(hass=hass) as session:
        for _ in range(50):
            _add_state_without_event_linkage(
                session, "switch.random", "on", eleven_days_ago
            )
        states_with_event_id = session.query(States).filter(
            States.event_id.is_not(None)
        )
        states_without_event_id = session.query(States).filter(
            States.event_id.is_(None)
        )

        assert states_with_event_id.count() == 50
        assert states_without_event_id.count() == 51

        purge_before = dt_util.utcnow() - timedelta(days=4)
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
        )
        assert not finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 51
        # At this point all the legacy states are gone
        # and we switch methods
        purge_before = dt_util.utcnow() - timedelta(days=4)
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        # Since we only allow one iteration, we won't
        # check if we are finished this loop similar
        # to the legacy method
        assert not finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=100,
            states_batch_size=100,
        )
        assert finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1
        _add_state_without_event_linkage(
            session, "switch.random", "on", eleven_days_ago
        )
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 2
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
        )
        assert finished
        # The broken state without a timestamp
        # does not prevent future purges. Its ignored.
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1


async def test_purge_can_mix_legacy_and_new_format_with_detached_state(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    recorder_db_url: str,
) -> None:
    """Test purging with legacy and new events with a detached state."""
    if recorder_db_url.startswith(("mysql://", "postgresql://")):
        return pytest.skip("This tests disables foreign key checks on SQLite")

    instance = await async_setup_recorder_instance(hass)
    await _async_attach_db_engine(hass)

    await async_wait_recording_done(hass)
    # New databases are no longer created with the legacy events index
    assert instance.use_legacy_events_index is False

    def _recreate_legacy_events_index():
        """Recreate the legacy events index since its no longer created on new instances."""
        migration._create_index(instance.get_session, "states", "ix_states_event_id")
        instance.use_legacy_events_index = True

    await instance.async_add_executor_job(_recreate_legacy_events_index)
    assert instance.use_legacy_events_index is True

    with session_scope(hass=hass) as session:
        session.execute(text("PRAGMA foreign_keys = OFF"))

    utcnow = dt_util.utcnow()
    eleven_days_ago = utcnow - timedelta(days=11)

    with session_scope(hass=hass) as session:
        broken_state_no_time = States(
            event_id=None,
            entity_id="orphened.state",
            last_updated_ts=None,
            last_changed_ts=None,
        )
        session.add(broken_state_no_time)
        detached_state_deleted_event_id = States(
            event_id=99999999999,
            entity_id="event.deleted",
            last_updated_ts=1,
            last_changed_ts=None,
        )
        session.add(detached_state_deleted_event_id)
        detached_state_deleted_event_id.last_changed = None
        detached_state_deleted_event_id.last_changed_ts = None
        detached_state_deleted_event_id.last_updated = None
        detached_state_deleted_event_id = States(
            event_id=99999999999,
            entity_id="event.deleted.no_time",
            last_updated_ts=None,
            last_changed_ts=None,
        )
        detached_state_deleted_event_id.last_changed = None
        detached_state_deleted_event_id.last_changed_ts = None
        detached_state_deleted_event_id.last_updated = None
        detached_state_deleted_event_id.last_updated_ts = None
        session.add(detached_state_deleted_event_id)
        start_id = 50000
        for event_id in range(start_id, start_id + 50):
            _add_state_and_state_changed_event(
                session,
                "sensor.excluded",
                "purgeme",
                eleven_days_ago,
                event_id,
            )
    with session_scope(hass=hass) as session:
        session.execute(
            update(States)
            .where(States.entity_id == "event.deleted.no_time")
            .values(last_updated_ts=None)
        )

    await _add_test_events(hass, 50)
    await _add_events_with_event_data(hass, 50)
    with session_scope(hass=hass) as session:
        for _ in range(50):
            _add_state_without_event_linkage(
                session, "switch.random", "on", eleven_days_ago
            )
        states_with_event_id = session.query(States).filter(
            States.event_id.is_not(None)
        )
        states_without_event_id = session.query(States).filter(
            States.event_id.is_(None)
        )

        assert states_with_event_id.count() == 52
        assert states_without_event_id.count() == 51

        purge_before = dt_util.utcnow() - timedelta(days=4)
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
        )
        assert not finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 51
        # At this point all the legacy states are gone
        # and we switch methods
        purge_before = dt_util.utcnow() - timedelta(days=4)
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=1,
            states_batch_size=1,
        )
        # Since we only allow one iteration, we won't
        # check if we are finished this loop similar
        # to the legacy method
        assert not finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
            events_batch_size=100,
            states_batch_size=100,
        )
        assert finished
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1
        _add_state_without_event_linkage(
            session, "switch.random", "on", eleven_days_ago
        )
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 2
        finished = purge_old_data(
            instance,
            purge_before,
            repack=False,
        )
        assert finished
        # The broken state without a timestamp
        # does not prevent future purges. Its ignored.
        assert states_with_event_id.count() == 0
        assert states_without_event_id.count() == 1


async def test_purge_entities_keep_days(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> None:
    """Test purging states with an entity filter and keep_days."""
    instance = await async_setup_recorder_instance(hass, {})
    await _async_attach_db_engine(hass)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)
    start = dt_util.utcnow()
    two_days_ago = start - timedelta(days=2)
    one_week_ago = start - timedelta(days=7)
    one_month_ago = start - timedelta(days=30)
    with freeze_time(one_week_ago):
        hass.states.async_set("sensor.keep", "initial")
        hass.states.async_set("sensor.purge", "initial")

    await async_wait_recording_done(hass)

    with freeze_time(two_days_ago):
        hass.states.async_set("sensor.purge", "two_days_ago")

    await async_wait_recording_done(hass)

    hass.states.async_set("sensor.purge", "now")
    hass.states.async_set("sensor.keep", "now")
    await async_recorder_block_till_done(hass)

    states = await instance.async_add_executor_job(
        get_significant_states,
        hass,
        one_month_ago,
        None,
        ["sensor.keep", "sensor.purge"],
    )
    assert len(states["sensor.keep"]) == 2
    assert len(states["sensor.purge"]) == 3

    await hass.services.async_call(
        recorder.DOMAIN,
        SERVICE_PURGE_ENTITIES,
        {
            "entity_id": "sensor.purge",
            "keep_days": 1,
        },
    )
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    states = await instance.async_add_executor_job(
        get_significant_states,
        hass,
        one_month_ago,
        None,
        ["sensor.keep", "sensor.purge"],
    )
    assert len(states["sensor.keep"]) == 2
    assert len(states["sensor.purge"]) == 1

    await hass.services.async_call(
        recorder.DOMAIN,
        SERVICE_PURGE_ENTITIES,
        {
            "entity_id": "sensor.purge",
        },
    )
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    states = await instance.async_add_executor_job(
        get_significant_states,
        hass,
        one_month_ago,
        None,
        ["sensor.keep", "sensor.purge"],
    )
    assert len(states["sensor.keep"]) == 2
    assert "sensor.purge" not in states
