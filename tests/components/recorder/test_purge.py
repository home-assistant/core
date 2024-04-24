"""Test data purging."""

from datetime import datetime, timedelta
import json
import sqlite3
from unittest.mock import patch

from freezegun import freeze_time
import pytest
from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm.session import Session
from voluptuous.error import MultipleInvalid

from homeassistant.components import recorder
from homeassistant.components.recorder.const import SupportedDialect
from homeassistant.components.recorder.db_schema import (
    Events,
    EventTypes,
    RecorderRuns,
    StateAttributes,
    States,
    StatesMeta,
    StatisticsRuns,
    StatisticsShortTerm,
)
from homeassistant.components.recorder.history import get_significant_states
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.queries import select_event_type_ids
from homeassistant.components.recorder.services import (
    SERVICE_PURGE,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.components.recorder.tasks import PurgeTask
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import EVENT_STATE_CHANGED, EVENT_THEMES_UPDATED, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .common import (
    async_recorder_block_till_done,
    async_wait_purge_done,
    async_wait_recording_done,
    convert_pending_events_to_event_types,
    convert_pending_states_to_meta,
)

from tests.typing import RecorderInstanceGenerator

TEST_EVENT_TYPES = (
    "EVENT_TEST_AUTOPURGE",
    "EVENT_TEST_PURGE",
    "EVENT_TEST",
    "EVENT_TEST_AUTOPURGE_WITH_EVENT_DATA",
    "EVENT_TEST_PURGE_WITH_EVENT_DATA",
    "EVENT_TEST_WITH_EVENT_DATA",
)


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


async def test_purge_big_database(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting 2/3 old states from a big database."""

    instance = await async_setup_recorder_instance(hass)

    for _ in range(12):
        await _add_test_states(hass, wait_recording_done=False)
    await async_wait_recording_done(hass)

    with (
        patch.object(instance, "max_bind_vars", 72),
        patch.object(instance.database_engine, "max_bind_vars", 72),
        session_scope(hass=hass) as session,
    ):
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 72
        assert state_attributes.count() == 3

        purge_before = dt_util.utcnow() - timedelta(days=4)

        finished = purge_old_data(
            instance,
            purge_before,
            states_batch_size=1,
            events_batch_size=1,
            repack=False,
        )
        assert not finished
        assert states.count() == 24
        assert state_attributes.count() == 1


async def test_purge_old_states(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old states."""
    instance = await async_setup_recorder_instance(hass)

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

    await _add_test_states(hass)
    await async_wait_recording_done(hass)

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with (
        patch(
            "homeassistant.components.recorder.core.move_away_broken_database"
        ) as move_away,
        patch(
            "homeassistant.components.recorder.purge.purge_old_data",
            side_effect=sqlite3_exception,
        ),
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

    await _add_test_states(hass)
    await async_wait_recording_done(hass)

    mysql_exception = OperationalError("statement", {}, [])
    mysql_exception.orig = Exception(1205, "retryable")

    with (
        patch("homeassistant.components.recorder.util.time.sleep") as sleep_mock,
        patch(
            "homeassistant.components.recorder.purge._purge_old_recorder_runs",
            side_effect=[mysql_exception, None],
        ),
        patch.object(instance.engine.dialect, "name", "mysql"),
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

    await _add_test_events(hass)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
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
        all_events = events.all()
        assert events.count() == 2, f"Should have 2 events left: {all_events}"

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


@pytest.mark.parametrize("use_sqlite", [True, False], indirect=True)
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

        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
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
        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
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
        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
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


@pytest.mark.parametrize("use_sqlite", [True, False], indirect=True)
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
            instance = recorder.get_instance(hass)
            convert_pending_events_to_event_types(instance, session)
            convert_pending_states_to_meta(instance, session)

    await async_setup_recorder_instance(hass, None)
    await async_wait_purge_done(hass)

    service_data = {"keep_days": 2}
    timestamp = dt_util.utcnow() - timedelta(days=2, minutes=1)

    await _add_db_entries(hass, timestamp)
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 1

        state_attributes = session.query(StateAttributes)
        assert state_attributes.count() == 1

        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
        assert events.count() == 1

    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 0
        events = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
        )
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
            convert_pending_events_to_event_types(instance, session)
            convert_pending_states_to_meta(instance, session)

    instance = await async_setup_recorder_instance(hass, None)
    await async_wait_purge_done(hass)

    service_data = {"keep_days": 2}

    # Force multiple purge batches to be run
    rows = 999
    cutoff = dt_util.utcnow() - timedelta(days=service_data["keep_days"])
    await _add_db_entries(hass, cutoff, rows)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
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
        assert (
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids(("PURGE",))))
            .count()
            == rows - 1
        )
        assert (
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids(("KEEP",))))
            .count()
            == 1
        )

    instance.queue_task(PurgeTask(cutoff, repack=False, apply_filter=False))
    await hass.async_block_till_done()
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        session.query(Events)
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
        assert (
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids(("PURGE",))))
            .count()
            == 0
        )
        assert (
            session.query(Events)
            .filter(Events.event_type_id.in_(select_event_type_ids(("KEEP",))))
            .count()
            == 1
        )

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


@pytest.mark.parametrize("use_sqlite", [True, False], indirect=True)
async def test_purge_filtered_states(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    use_sqlite: bool,
) -> None:
    """Test filtered states are purged."""
    config: ConfigType = {"exclude": {"entities": ["sensor.excluded"]}}
    instance = await async_setup_recorder_instance(hass, config)
    assert instance.entity_filter("sensor.excluded") is False

    def _add_db_entries(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_with_state_attributes(
                        session,
                        "sensor.excluded",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
            # Add state **without** state_changed event that should be purged
            timestamp = dt_util.utcnow() - timedelta(days=1)
            session.add(
                States(
                    entity_id="sensor.excluded",
                    state="purgeme",
                    attributes="{}",
                    last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                    last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            # Add states and state_changed events that should be keeped
            timestamp = dt_util.utcnow() - timedelta(days=2)
            for event_id in range(200, 210):
                _add_state_with_state_attributes(
                    session,
                    "sensor.keep",
                    "keep",
                    timestamp,
                    event_id,
                )
            # Add states with linked old_state_ids that need to be handled
            timestamp = dt_util.utcnow() - timedelta(days=0)
            state_attrs = StateAttributes(
                hash=0,
                shared_attrs=json.dumps(
                    {"sensor.linked_old_state_id": "sensor.linked_old_state_id"}
                ),
            )
            state_1 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=1,
                state_attributes=state_attrs,
            )
            timestamp = dt_util.utcnow() - timedelta(days=4)
            state_2 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=2,
                state_attributes=state_attrs,
            )
            state_3 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=62,  # keep
                state_attributes=state_attrs,
            )
            session.add_all((state_attrs, state_1, state_2, state_3))
            # Add event that should be keeped
            session.add(
                Events(
                    event_id=100,
                    event_type="EVENT_KEEP",
                    event_data="{}",
                    origin="LOCAL",
                    time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            convert_pending_states_to_meta(instance, session)
            convert_pending_events_to_event_types(instance, session)

    service_data = {"keep_days": 10}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 74
        events_keep = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_KEEP",)))
        )
        assert events_keep.count() == 1

    # Normal purge doesn't remove excluded entities
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 74
        events_keep = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_KEEP",)))
        )
        assert events_keep.count() == 1

    # Test with 'apply_filter' = True
    service_data["apply_filter"] = True
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 13
        events_keep = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_KEEP",)))
        )
        assert events_keep.count() == 1

        states_sensor_excluded = (
            session.query(States)
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
            .filter(StatesMeta.entity_id == "sensor.excluded")
        )
        assert states_sensor_excluded.count() == 0

        assert (
            session.query(States).filter(States.state_id == 72).first().old_state_id
            is None
        )
        assert (
            session.query(States).filter(States.state_id == 72).first().attributes_id
            == 71
        )
        assert (
            session.query(States).filter(States.state_id == 73).first().old_state_id
            is None
        )
        assert (
            session.query(States).filter(States.state_id == 73).first().attributes_id
            == 71
        )

        final_keep_state = session.query(States).filter(States.state_id == 74).first()
        assert final_keep_state.old_state_id == 62  # should have been kept
        assert final_keep_state.attributes_id == 71

        assert session.query(StateAttributes).count() == 11

    # Do it again to make sure nothing changes
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        final_keep_state = session.query(States).filter(States.state_id == 74).first()
        assert final_keep_state.old_state_id == 62  # should have been kept
        assert final_keep_state.attributes_id == 71

        assert session.query(StateAttributes).count() == 11

    service_data = {"keep_days": 0}
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        remaining = list(session.query(States))
        for state in remaining:
            assert state.event_id is None
        assert len(remaining) == 0
        assert session.query(StateAttributes).count() == 0


@pytest.mark.parametrize("use_sqlite", [True, False], indirect=True)
async def test_purge_filtered_states_to_empty(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    use_sqlite: bool,
) -> None:
    """Test filtered states are purged all the way to an empty db."""
    config: ConfigType = {"exclude": {"entities": ["sensor.excluded"]}}
    instance = await async_setup_recorder_instance(hass, config)
    assert instance.entity_filter("sensor.excluded") is False

    def _add_db_entries(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_with_state_attributes(
                        session,
                        "sensor.excluded",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
            convert_pending_states_to_meta(instance, session)

    service_data = {"keep_days": 10}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 60
        assert state_attributes.count() == 60

    # Test with 'apply_filter' = True
    service_data["apply_filter"] = True
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 0
        assert state_attributes.count() == 0

    # Do it again to make sure nothing changes
    # Why do we do this? Should we check the end result?
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)


@pytest.mark.parametrize("use_sqlite", [True, False], indirect=True)
async def test_purge_without_state_attributes_filtered_states_to_empty(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
    use_sqlite: bool,
) -> None:
    """Test filtered legacy states without state attributes are purged all the way to an empty db."""
    config: ConfigType = {"exclude": {"entities": ["sensor.old_format"]}}
    instance = await async_setup_recorder_instance(hass, config)
    assert instance.entity_filter("sensor.old_format") is False

    def _add_db_entries(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            # in the legacy format
            timestamp = dt_util.utcnow() - timedelta(days=5)
            event_id = 1021
            session.add(
                States(
                    entity_id="sensor.old_format",
                    state=STATE_ON,
                    attributes=json.dumps({"old": "not_using_state_attributes"}),
                    last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                    last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                    event_id=event_id,
                    state_attributes=None,
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
            session.add(
                Events(
                    event_id=event_id + 1,
                    event_type=EVENT_THEMES_UPDATED,
                    event_data="{}",
                    origin="LOCAL",
                    time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            convert_pending_states_to_meta(instance, session)
            convert_pending_events_to_event_types(instance, session)

    service_data = {"keep_days": 10}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 1
        assert state_attributes.count() == 0

    # Test with 'apply_filter' = True
    service_data["apply_filter"] = True
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        state_attributes = session.query(StateAttributes)
        assert states.count() == 0
        assert state_attributes.count() == 0

    # Do it again to make sure nothing changes
    # Why do we do this? Should we check the end result?
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)


async def test_purge_filtered_events(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> None:
    """Test filtered events are purged."""
    config: ConfigType = {"exclude": {"event_types": ["EVENT_PURGE"]}}
    instance = await async_setup_recorder_instance(hass, config)
    await async_wait_recording_done(hass)

    def _add_db_entries(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    session.add(
                        Events(
                            event_id=event_id * days,
                            event_type="EVENT_PURGE",
                            event_data="{}",
                            origin="LOCAL",
                            time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                        )
                    )

            # Add states and state_changed events that should be keeped
            timestamp = dt_util.utcnow() - timedelta(days=1)
            for event_id in range(200, 210):
                _add_state_with_state_attributes(
                    session,
                    "sensor.keep",
                    "keep",
                    timestamp,
                    event_id,
                )
            convert_pending_events_to_event_types(instance, session)
            convert_pending_states_to_meta(instance, session)

    service_data = {"keep_days": 10}
    await instance.async_add_executor_job(_add_db_entries, hass)
    await async_wait_recording_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        events_purge = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_PURGE",)))
        )
        states = session.query(States)
        assert events_purge.count() == 60
        assert states.count() == 10

    # Normal purge doesn't remove excluded events
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        events_purge = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_PURGE",)))
        )
        states = session.query(States)
        assert events_purge.count() == 60
        assert states.count() == 10

    # Test with 'apply_filter' = True
    service_data["apply_filter"] = True
    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    await async_recorder_block_till_done(hass)
    await async_wait_purge_done(hass)

    with session_scope(hass=hass, read_only=True) as session:
        events_purge = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_PURGE",)))
        )
        states = session.query(States)
        assert events_purge.count() == 0
        assert states.count() == 10


async def test_purge_filtered_events_state_changed(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> None:
    """Test filtered state_changed events are purged. This should also remove all states."""
    config: ConfigType = {
        "exclude": {
            "event_types": ["excluded_event"],
            "entities": ["sensor.excluded", "sensor.old_format"],
        }
    }
    instance = await async_setup_recorder_instance(hass, config)
    # Assert entity_id is NOT excluded
    assert instance.entity_filter("sensor.excluded") is False
    assert instance.entity_filter("sensor.old_format") is False
    assert instance.entity_filter("sensor.keep") is True
    assert "excluded_event" in instance.exclude_event_types

    def _add_db_entries(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_with_state_attributes(
                        session,
                        "sensor.excluded",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
            # Add events that should be keeped
            timestamp = dt_util.utcnow() - timedelta(days=1)
            for event_id in range(200, 210):
                session.add(
                    Events(
                        event_id=event_id,
                        event_type="EVENT_KEEP",
                        event_data="{}",
                        origin="LOCAL",
                        time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                    )
                )
            # Add states with linked old_state_ids that need to be handled
            timestamp = dt_util.utcnow() - timedelta(days=0)
            state_1 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=1,
            )
            timestamp = dt_util.utcnow() - timedelta(days=4)
            state_2 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=2,
            )
            state_3 = States(
                entity_id="sensor.linked_old_state_id",
                state="keep",
                attributes="{}",
                last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                old_state_id=62,  # keep
            )
            session.add_all((state_1, state_2, state_3))
            session.add(
                Events(
                    event_id=231,
                    event_type="excluded_event",
                    event_data="{}",
                    origin="LOCAL",
                    time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            session.add(
                States(
                    entity_id="sensor.old_format",
                    state="remove",
                    attributes="{}",
                    last_changed_ts=dt_util.utc_to_timestamp(timestamp),
                    last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                )
            )
            convert_pending_events_to_event_types(instance, session)
            convert_pending_states_to_meta(instance, session)

    service_data = {"keep_days": 10, "apply_filter": True}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        events_keep = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_KEEP",)))
        )
        events_purge = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("excluded_event",)))
        )
        states = session.query(States)

        assert events_keep.count() == 10
        assert events_purge.count() == 1
        assert states.count() == 64

    await hass.services.async_call(recorder.DOMAIN, SERVICE_PURGE, service_data)
    await hass.async_block_till_done()

    for _ in range(4):
        await async_recorder_block_till_done(hass)
        await async_wait_purge_done(hass)

    with session_scope(hass=hass) as session:
        events_keep = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("EVENT_KEEP",)))
        )
        events_purge = session.query(Events).filter(
            Events.event_type_id.in_(select_event_type_ids(("excluded_event",)))
        )
        states = session.query(States)

        assert events_keep.count() == 10
        assert events_purge.count() == 0
        assert states.count() == 3

        assert (
            session.query(States).filter(States.state_id == 61).first().old_state_id
            is None
        )
        assert (
            session.query(States).filter(States.state_id == 62).first().old_state_id
            is None
        )
        assert (
            session.query(States).filter(States.state_id == 63).first().old_state_id
            == 62
        )  # should have been kept


async def test_purge_entities(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test purging of specific entities."""
    instance = await async_setup_recorder_instance(hass)

    async def _purge_entities(hass, entity_ids, domains, entity_globs):
        service_data = {
            "entity_id": entity_ids,
            "domains": domains,
            "entity_globs": entity_globs,
        }

        await hass.services.async_call(
            recorder.DOMAIN, SERVICE_PURGE_ENTITIES, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass)
        await async_wait_purge_done(hass)

    def _add_purge_records(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_with_state_attributes(
                        session,
                        "sensor.purge_entity",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(10000, 10020):
                    _add_state_with_state_attributes(
                        session,
                        "purge_domain.entity",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(100000, 100020):
                    _add_state_with_state_attributes(
                        session,
                        "binary_sensor.purge_glob",
                        "purgeme",
                        timestamp,
                        event_id * days,
                    )
            convert_pending_states_to_meta(instance, session)
            convert_pending_events_to_event_types(instance, session)

    def _add_keep_records(hass: HomeAssistant) -> None:
        with session_scope(hass=hass) as session:
            # Add states and state_changed events that should be kept
            timestamp = dt_util.utcnow() - timedelta(days=2)
            for event_id in range(200, 210):
                _add_state_with_state_attributes(
                    session,
                    "sensor.keep",
                    "keep",
                    timestamp,
                    event_id,
                )
            convert_pending_states_to_meta(instance, session)
            convert_pending_events_to_event_types(instance, session)

    _add_purge_records(hass)
    _add_keep_records(hass)

    # Confirm standard service call
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 190

    await _purge_entities(hass, "sensor.purge_entity", "purge_domain", "*purge_glob")

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 10

        states_sensor_kept = (
            session.query(States)
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
            .filter(StatesMeta.entity_id == "sensor.keep")
        )
        assert states_sensor_kept.count() == 10

    _add_purge_records(hass)

    # Confirm each parameter purges only the associated records
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 190

    await _purge_entities(hass, "sensor.purge_entity", [], [])

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 130

    await _purge_entities(hass, [], "purge_domain", [])

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 70

    await _purge_entities(hass, [], [], "*purge_glob")

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 10

        states_sensor_kept = (
            session.query(States)
            .outerjoin(StatesMeta, States.metadata_id == StatesMeta.metadata_id)
            .filter(StatesMeta.entity_id == "sensor.keep")
        )
        assert states_sensor_kept.count() == 10

        # sensor.keep should remain in the StatesMeta table
        states_meta_remain = session.query(StatesMeta).filter(
            StatesMeta.entity_id == "sensor.keep"
        )
        assert states_meta_remain.count() == 1

        # sensor.purge_entity should be removed from the StatesMeta table
        states_meta_remain = session.query(StatesMeta).filter(
            StatesMeta.entity_id == "sensor.purge_entity"
        )
        assert states_meta_remain.count() == 0

    _add_purge_records(hass)

    # Confirm calling service without arguments is invalid
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 190

    with pytest.raises(MultipleInvalid):
        await _purge_entities(hass, [], [], [])

    with session_scope(hass=hass, read_only=True) as session:
        states = session.query(States)
        assert states.count() == 190

        states_meta_remain = session.query(StatesMeta)
        assert states_meta_remain.count() == 4


async def _add_test_states(hass: HomeAssistant, wait_recording_done: bool = True):
    """Add multiple states to the db for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    base_attributes = {"test_attr": 5, "test_attr_10": "nice"}

    async def set_state(entity_id, state, **kwargs):
        """Set the state."""
        hass.states.async_set(entity_id, state, **kwargs)
        if wait_recording_done:
            await hass.async_block_till_done()
            await async_wait_recording_done(hass)

    with freeze_time() as freezer:
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

            freezer.move_to(timestamp)
            await set_state("test.recorder2", state, attributes=attributes)


async def _add_test_events(hass: HomeAssistant, iterations: int = 1):
    """Add a few events for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}
    # Make sure recording is done before freezing time
    # because the time freeze can affect the recorder
    # thread as well can cause the test to fail
    await async_wait_recording_done(hass)

    with freeze_time() as freezer:
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
                freezer.move_to(timestamp)
                hass.bus.async_fire(event_type, event_data)

    await async_wait_recording_done(hass)


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


def _add_state_with_state_attributes(
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


@pytest.mark.timeout(30)
async def test_purge_many_old_events(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old events."""
    old_events_count = 5
    instance = await async_setup_recorder_instance(hass)

    with (
        patch.object(instance, "max_bind_vars", old_events_count),
        patch.object(instance.database_engine, "max_bind_vars", old_events_count),
    ):
        await _add_test_events(hass, old_events_count)

        with session_scope(hass=hass) as session:
            events = session.query(Events).filter(
                Events.event_type_id.in_(select_event_type_ids(TEST_EVENT_TYPES))
            )
            assert events.count() == old_events_count * 6

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
            assert events.count() == old_events_count * 3

            # we should only have 2 groups of events left
            finished = purge_old_data(
                instance,
                purge_before,
                repack=False,
                states_batch_size=3,
                events_batch_size=3,
            )
            assert finished
            assert events.count() == old_events_count * 2

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


async def test_purge_old_events_purges_the_event_type_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old events purges event type ids."""
    instance = await async_setup_recorder_instance(hass)
    assert instance.event_type_manager.active is True

    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    far_past = utcnow - timedelta(days=1000)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _insert_events():
        with session_scope(hass=hass) as session:
            event_type_test_auto_purge = EventTypes(event_type="EVENT_TEST_AUTOPURGE")
            event_type_test_purge = EventTypes(event_type="EVENT_TEST_PURGE")
            event_type_test = EventTypes(event_type="EVENT_TEST")
            event_type_unused = EventTypes(event_type="EVENT_TEST_UNUSED")
            session.add_all(
                (
                    event_type_test_auto_purge,
                    event_type_test_purge,
                    event_type_test,
                    event_type_unused,
                )
            )
            session.flush()
            for _ in range(5):
                for event_id in range(6):
                    if event_id < 2:
                        timestamp = eleven_days_ago
                        event_type = event_type_test_auto_purge
                    elif event_id < 4:
                        timestamp = five_days_ago
                        event_type = event_type_test_purge
                    else:
                        timestamp = utcnow
                        event_type = event_type_test

                    session.add(
                        Events(
                            event_type=None,
                            event_type_id=event_type.event_type_id,
                            time_fired_ts=dt_util.utc_to_timestamp(timestamp),
                        )
                    )
            return instance.event_type_manager.get_many(
                [
                    "EVENT_TEST_AUTOPURGE",
                    "EVENT_TEST_PURGE",
                    "EVENT_TEST",
                    "EVENT_TEST_UNUSED",
                ],
                session,
            )

    event_type_to_id = await instance.async_add_executor_job(_insert_events)
    test_event_type_ids = event_type_to_id.values()
    with session_scope(hass=hass) as session:
        events = session.query(Events).where(
            Events.event_type_id.in_(test_event_type_ids)
        )
        event_types = session.query(EventTypes).where(
            EventTypes.event_type_id.in_(test_event_type_ids)
        )

        assert events.count() == 30
        assert event_types.count() == 4

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            far_past,
            repack=False,
        )
        assert finished
        assert events.count() == 30
        # We should remove the unused event type
        assert event_types.count() == 3

        assert "EVENT_TEST_UNUSED" not in instance.event_type_manager._id_map

        # we should only have 10 events left since
        # only one event type was recorded now
        finished = purge_old_data(
            instance,
            utcnow,
            repack=False,
        )
        assert finished
        assert events.count() == 10
        assert event_types.count() == 1

        # Purge everything
        finished = purge_old_data(
            instance,
            utcnow + timedelta(seconds=1),
            repack=False,
        )
        assert finished
        assert events.count() == 0
        assert event_types.count() == 0


async def test_purge_old_states_purges_the_state_metadata_ids(
    async_setup_recorder_instance: RecorderInstanceGenerator, hass: HomeAssistant
) -> None:
    """Test deleting old states purges state metadata_ids."""
    instance = await async_setup_recorder_instance(hass)
    assert instance.states_meta_manager.active is True

    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    far_past = utcnow - timedelta(days=1000)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass)

    def _insert_states():
        with session_scope(hass=hass) as session:
            states_meta_sensor_one = StatesMeta(entity_id="sensor.one")
            states_meta_sensor_two = StatesMeta(entity_id="sensor.two")
            states_meta_sensor_three = StatesMeta(entity_id="sensor.three")
            states_meta_sensor_unused = StatesMeta(entity_id="sensor.unused")
            session.add_all(
                (
                    states_meta_sensor_one,
                    states_meta_sensor_two,
                    states_meta_sensor_three,
                    states_meta_sensor_unused,
                )
            )
            session.flush()
            for _ in range(5):
                for event_id in range(6):
                    if event_id < 2:
                        timestamp = eleven_days_ago
                        metadata_id = states_meta_sensor_one.metadata_id
                    elif event_id < 4:
                        timestamp = five_days_ago
                        metadata_id = states_meta_sensor_two.metadata_id
                    else:
                        timestamp = utcnow
                        metadata_id = states_meta_sensor_three.metadata_id

                    session.add(
                        States(
                            metadata_id=metadata_id,
                            state="any",
                            last_updated_ts=dt_util.utc_to_timestamp(timestamp),
                        )
                    )
            return instance.states_meta_manager.get_many(
                ["sensor.one", "sensor.two", "sensor.three", "sensor.unused"],
                session,
                True,
            )

    entity_id_to_metadata_id = await instance.async_add_executor_job(_insert_states)
    test_metadata_ids = entity_id_to_metadata_id.values()
    with session_scope(hass=hass) as session:
        states = session.query(States).where(States.metadata_id.in_(test_metadata_ids))
        states_meta = session.query(StatesMeta).where(
            StatesMeta.metadata_id.in_(test_metadata_ids)
        )

        assert states.count() == 30
        assert states_meta.count() == 4

        # run purge_old_data()
        finished = purge_old_data(
            instance,
            far_past,
            repack=False,
        )
        assert finished
        assert states.count() == 30
        # We should remove the unused entity_id
        assert states_meta.count() == 3

        assert "sensor.unused" not in instance.event_type_manager._id_map

        # we should only have 10 states left since
        # only one event type was recorded now
        finished = purge_old_data(
            instance,
            utcnow,
            repack=False,
        )
        assert finished
        assert states.count() == 10
        assert states_meta.count() == 1

        # Purge everything
        finished = purge_old_data(
            instance,
            utcnow + timedelta(seconds=1),
            repack=False,
        )
        assert finished
        assert states.count() == 0
        assert states_meta.count() == 0


async def test_purge_entities_keep_days(
    async_setup_recorder_instance: RecorderInstanceGenerator,
    hass: HomeAssistant,
) -> None:
    """Test purging states with an entity filter and keep_days."""
    instance = await async_setup_recorder_instance(hass, {})
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
