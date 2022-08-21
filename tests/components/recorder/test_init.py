"""The tests for the Recorder component."""
from __future__ import annotations

# pylint: disable=protected-access
import asyncio
from datetime import datetime, timedelta
import sqlite3
import threading
from typing import cast
from unittest.mock import Mock, patch

import pytest
from sqlalchemy.exc import DatabaseError, OperationalError, SQLAlchemyError

from homeassistant.components import recorder
from homeassistant.components.recorder import (
    CONF_AUTO_PURGE,
    CONF_AUTO_REPACK,
    CONF_COMMIT_INTERVAL,
    CONF_DB_URL,
    CONFIG_SCHEMA,
    DOMAIN,
    SQLITE_URL_PREFIX,
    Recorder,
    get_instance,
)
from homeassistant.components.recorder.const import KEEPALIVE_TIME
from homeassistant.components.recorder.db_schema import (
    SCHEMA_VERSION,
    EventData,
    Events,
    RecorderRuns,
    StateAttributes,
    States,
    StatisticsRuns,
)
from homeassistant.components.recorder.models import process_timestamp
from homeassistant.components.recorder.services import (
    SERVICE_DISABLE,
    SERVICE_ENABLE,
    SERVICE_PURGE,
    SERVICE_PURGE_ENTITIES,
)
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import (
    EVENT_HOMEASSISTANT_FINAL_WRITE,
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_HOMEASSISTANT_STOP,
    MATCH_ALL,
    STATE_LOCKED,
    STATE_UNLOCKED,
)
from homeassistant.core import CoreState, Event, HomeAssistant, callback
from homeassistant.helpers import recorder as recorder_helper
from homeassistant.setup import async_setup_component, setup_component
from homeassistant.util import dt as dt_util

from .common import (
    async_block_recorder,
    async_wait_recording_done,
    corrupt_db_file,
    run_information_with_session,
    wait_recording_done,
)

from tests.common import (
    SetupRecorderInstanceT,
    async_fire_time_changed,
    fire_time_changed,
    get_test_home_assistant,
)


def _default_recorder(hass):
    """Return a recorder with reasonable defaults."""
    return Recorder(
        hass,
        auto_purge=True,
        auto_repack=True,
        keep_days=7,
        commit_interval=1,
        uri="sqlite://",
        db_max_retries=10,
        db_retry_wait=3,
        entity_filter=CONFIG_SCHEMA({DOMAIN: {}}),
        exclude_t=[],
        exclude_attributes_by_domain={},
    )


async def test_shutdown_before_startup_finishes(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT, tmp_path
):
    """Test shutdown before recorder starts is clean."""

    # On-disk database because this test does not play nice with the
    # MutexPool
    config = {
        recorder.CONF_DB_URL: "sqlite:///" + str(tmp_path / "pytest.db"),
        recorder.CONF_COMMIT_INTERVAL: 1,
    }
    hass.state = CoreState.not_running

    recorder_helper.async_initialize_recorder(hass)
    hass.create_task(async_setup_recorder_instance(hass, config))
    await recorder_helper.async_wait_recorder(hass)
    instance = get_instance(hass)

    session = await hass.async_add_executor_job(instance.get_session)

    with patch.object(instance, "engine"):
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
        await hass.async_stop()

    run_info = await hass.async_add_executor_job(run_information_with_session, session)

    assert run_info.run_id == 1
    assert run_info.start is not None
    assert run_info.end is not None


async def test_canceled_before_startup_finishes(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog: pytest.LogCaptureFixture,
):
    """Test recorder shuts down when its startup future is canceled out from under it."""
    hass.state = CoreState.not_running
    recorder_helper.async_initialize_recorder(hass)
    hass.create_task(async_setup_recorder_instance(hass))
    await recorder_helper.async_wait_recorder(hass)

    instance = get_instance(hass)
    instance._hass_started.cancel()
    with patch.object(instance, "engine"):
        await hass.async_block_till_done()
        await hass.async_add_executor_job(instance.join)
    assert (
        "Recorder startup was externally canceled before it could complete"
        in caplog.text
    )


async def test_shutdown_closes_connections(hass, recorder_mock):
    """Test shutdown closes connections."""

    hass.state = CoreState.not_running

    instance = get_instance(hass)
    await instance.async_db_ready
    await hass.async_block_till_done()
    pool = instance.engine.pool
    pool.shutdown = Mock()

    def _ensure_connected():
        with session_scope(hass=hass) as session:
            list(session.query(States))

    await instance.async_add_executor_job(_ensure_connected)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert len(pool.shutdown.mock_calls) == 1
    with pytest.raises(RuntimeError):
        assert instance.get_session()


async def test_state_gets_saved_when_set_before_start_event(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test we can record an event when starting with not running."""

    hass.state = CoreState.not_running

    recorder_helper.async_initialize_recorder(hass)
    hass.create_task(async_setup_recorder_instance(hass))
    await recorder_helper.async_wait_recorder(hass)

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, state, attributes)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None


async def test_saving_state(hass: HomeAssistant, recorder_mock):
    """Test saving and restoring a state."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, state, attributes)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = []
        for db_state, db_state_attributes in session.query(States, StateAttributes):
            db_states.append(db_state)
            state = db_state.to_native()
            state.attributes = db_state_attributes.to_native()
        assert len(db_states) == 1
        assert db_states[0].event_id is None

    assert state == _state_with_context(hass, entity_id)


async def test_saving_many_states(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test we expire after many commits."""
    instance = await async_setup_recorder_instance(
        hass, {recorder.CONF_COMMIT_INTERVAL: 0}
    )

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    with patch.object(instance.event_session, "expire_all") as expire_all, patch.object(
        recorder.core, "EXPIRE_AFTER_COMMITS", 2
    ):
        for _ in range(3):
            hass.states.async_set(entity_id, "on", attributes)
            await async_wait_recording_done(hass)
            hass.states.async_set(entity_id, "off", attributes)
            await async_wait_recording_done(hass)

    assert expire_all.called

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 6
        assert db_states[0].event_id is None


async def test_saving_state_with_intermixed_time_changes(
    hass: HomeAssistant, recorder_mock
):
    """Test saving states with intermixed time changes."""
    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    attributes2 = {"test_attr": 10, "test_attr_10": "mean"}

    for _ in range(KEEPALIVE_TIME + 1):
        async_fire_time_changed(hass, dt_util.utcnow())
    hass.states.async_set(entity_id, state, attributes)
    for _ in range(KEEPALIVE_TIME + 1):
        async_fire_time_changed(hass, dt_util.utcnow())
    hass.states.async_set(entity_id, state, attributes2)

    await async_wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 2
        assert db_states[0].event_id is None


def test_saving_state_with_exception(hass, hass_recorder, caplog):
    """Test saving and restoring a state."""
    hass = hass_recorder()

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    def _throw_if_state_in_session(*args, **kwargs):
        for obj in get_instance(hass).event_session:
            if isinstance(obj, States):
                raise OperationalError(
                    "insert the state", "fake params", "forced to fail"
                )

    with patch("time.sleep"), patch.object(
        get_instance(hass).event_session,
        "flush",
        side_effect=_throw_if_state_in_session,
    ):
        hass.states.set(entity_id, "fail", attributes)
        wait_recording_done(hass)

    assert "Error executing query" in caplog.text
    assert "Error saving events" not in caplog.text

    caplog.clear()
    hass.states.set(entity_id, state, attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) >= 1

    assert "Error executing query" not in caplog.text
    assert "Error saving events" not in caplog.text


def test_saving_state_with_sqlalchemy_exception(hass, hass_recorder, caplog):
    """Test saving state when there is an SQLAlchemyError."""
    hass = hass_recorder()

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    def _throw_if_state_in_session(*args, **kwargs):
        for obj in get_instance(hass).event_session:
            if isinstance(obj, States):
                raise SQLAlchemyError(
                    "insert the state", "fake params", "forced to fail"
                )

    with patch("time.sleep"), patch.object(
        get_instance(hass).event_session,
        "flush",
        side_effect=_throw_if_state_in_session,
    ):
        hass.states.set(entity_id, "fail", attributes)
        wait_recording_done(hass)

    assert "SQLAlchemyError error processing task" in caplog.text

    caplog.clear()
    hass.states.set(entity_id, state, attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) >= 1

    assert "Error executing query" not in caplog.text
    assert "Error saving events" not in caplog.text
    assert "SQLAlchemyError error processing task" not in caplog.text


async def test_force_shutdown_with_queue_of_writes_that_generate_exceptions(
    hass, async_setup_recorder_instance, caplog
):
    """Test forcing shutdown."""
    instance = await async_setup_recorder_instance(hass)

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    await async_wait_recording_done(hass)

    with patch.object(instance, "db_retry_wait", 0.05), patch.object(
        instance.event_session,
        "flush",
        side_effect=OperationalError(
            "insert the state", "fake params", "forced to fail"
        ),
    ):
        for _ in range(100):
            hass.states.async_set(entity_id, "on", attributes)
            hass.states.async_set(entity_id, "off", attributes)

        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        hass.bus.async_fire(EVENT_HOMEASSISTANT_FINAL_WRITE)
        await hass.async_block_till_done()

    assert "Error executing query" in caplog.text
    assert "Error saving events" not in caplog.text


def test_saving_event(hass, hass_recorder):
    """Test saving and restoring an event."""
    hass = hass_recorder()

    event_type = "EVENT_TEST"
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    events = []

    @callback
    def event_listener(event):
        """Record events from eventbus."""
        if event.event_type == event_type:
            events.append(event)

    hass.bus.listen(MATCH_ALL, event_listener)

    hass.bus.fire(event_type, event_data)

    wait_recording_done(hass)

    assert len(events) == 1
    event: Event = events[0]

    get_instance(hass).block_till_done()
    events: list[Event] = []

    with session_scope(hass=hass) as session:
        for select_event, event_data in (
            session.query(Events, EventData)
            .filter_by(event_type=event_type)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
        ):
            select_event = cast(Events, select_event)
            event_data = cast(EventData, event_data)

            native_event = select_event.to_native()
            native_event.data = event_data.to_native()
            events.append(native_event)

    db_event = events[0]

    assert event.event_type == db_event.event_type
    assert event.data == db_event.data
    assert event.origin == db_event.origin

    # Recorder uses SQLite and stores datetimes as integer unix timestamps
    assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
        microsecond=0
    )


def test_saving_state_with_commit_interval_zero(hass_recorder):
    """Test saving a state with a commit interval of zero."""
    hass = hass_recorder({"commit_interval": 0})
    get_instance(hass).commit_interval == 0

    entity_id = "test.recorder"
    state = "restoring_from_db"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.set(entity_id, state, attributes)

    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None


def _add_entities(hass, entity_ids):
    """Add entities."""
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    for idx, entity_id in enumerate(entity_ids):
        hass.states.set(entity_id, f"state{idx}", attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = []
        for state, state_attributes in session.query(States, StateAttributes).outerjoin(
            StateAttributes, States.attributes_id == StateAttributes.attributes_id
        ):
            native_state = state.to_native()
            native_state.attributes = state_attributes.to_native()
            states.append(native_state)
        return states


def _add_events(hass, events):
    with session_scope(hass=hass) as session:
        session.query(Events).delete(synchronize_session=False)
    for event_type in events:
        hass.bus.fire(event_type)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        events = []
        for event, event_data in session.query(Events, EventData).outerjoin(
            EventData, Events.data_id == EventData.data_id
        ):
            event = cast(Events, event)
            event_data = cast(EventData, event_data)

            native_event = event.to_native()
            if event_data:
                native_event.data = event_data.to_native()
            events.append(native_event)
        return events


def _state_with_context(hass, entity_id):
    # We don't restore context unless we need it by joining the
    # events table on the event_id for state_changed events
    return hass.states.get(entity_id)


def test_setup_without_migration(hass_recorder):
    """Verify the schema version without a migration."""
    hass = hass_recorder()
    assert recorder.get_instance(hass).schema_version == SCHEMA_VERSION


# pylint: disable=redefined-outer-name,invalid-name
def test_saving_state_include_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"domains": "test2"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder") == states[0]


def test_saving_state_include_domains_globs(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"include": {"domains": "test2", "entity_globs": "*.included_*"}}
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test3.included_entity"]
    )
    assert len(states) == 2
    assert _state_with_context(hass, "test2.recorder") == states[0]
    assert _state_with_context(hass, "test3.included_entity") == states[1]


def test_saving_state_incl_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"entities": "test2.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder") == states[0]


def test_saving_event_exclude_event_type(hass_recorder):
    """Test saving and restoring an event."""
    hass = hass_recorder(
        {
            "exclude": {
                "event_types": [
                    "service_registered",
                    "homeassistant_start",
                    "component_loaded",
                    "core_config_updated",
                    "homeassistant_started",
                    "test",
                ]
            }
        }
    )
    events = _add_events(hass, ["test", "test2"])
    assert len(events) == 1
    assert events[0].event_type == "test2"


def test_saving_state_exclude_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"domains": "test"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder") == states[0]


def test_saving_state_exclude_domains_globs(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"exclude": {"domains": "test", "entity_globs": "*.excluded_*"}}
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test2.excluded_entity"]
    )
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder") == states[0]


def test_saving_state_exclude_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"entities": "test.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_with_context(hass, "test2.recorder") == states[0]


def test_saving_state_exclude_domain_include_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"include": {"entities": "test.recorder"}, "exclude": {"domains": "test"}}
    )
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 2


def test_saving_state_exclude_domain_glob_include_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {
            "include": {"entities": ["test.recorder", "test.excluded_entity"]},
            "exclude": {"domains": "test", "entity_globs": "*._excluded_*"},
        }
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test.excluded_entity"]
    )
    assert len(states) == 3


def test_saving_state_include_domain_exclude_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"exclude": {"entities": "test.recorder"}, "include": {"domains": "test"}}
    )
    states = _add_entities(hass, ["test.recorder", "test2.recorder", "test.ok"])
    assert len(states) == 1
    assert _state_with_context(hass, "test.ok") == states[0]
    assert _state_with_context(hass, "test.ok").state == "state2"


def test_saving_state_include_domain_glob_exclude_entity(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {
            "exclude": {"entities": ["test.recorder", "test2.included_entity"]},
            "include": {"domains": "test", "entity_globs": "*._included_*"},
        }
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test.ok", "test2.included_entity"]
    )
    assert len(states) == 1
    assert _state_with_context(hass, "test.ok") == states[0]
    assert _state_with_context(hass, "test.ok").state == "state2"


def test_saving_state_and_removing_entity(hass, hass_recorder):
    """Test saving the state of a removed entity."""
    hass = hass_recorder()
    entity_id = "lock.mine"
    hass.states.set(entity_id, STATE_LOCKED)
    hass.states.set(entity_id, STATE_UNLOCKED)
    hass.states.remove(entity_id)

    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = list(session.query(States))
        assert len(states) == 3
        assert states[0].entity_id == entity_id
        assert states[0].state == STATE_LOCKED
        assert states[1].entity_id == entity_id
        assert states[1].state == STATE_UNLOCKED
        assert states[2].entity_id == entity_id
        assert states[2].state is None


def test_recorder_setup_failure(hass):
    """Test some exceptions."""
    recorder_helper.async_initialize_recorder(hass)
    with patch.object(Recorder, "_setup_connection") as setup, patch(
        "homeassistant.components.recorder.core.time.sleep"
    ):
        setup.side_effect = ImportError("driver not found")
        rec = _default_recorder(hass)
        rec.async_initialize()
        rec.start()
        rec.join()

    hass.stop()


def test_recorder_setup_failure_without_event_listener(hass):
    """Test recorder setup failure when the event listener is not setup."""
    recorder_helper.async_initialize_recorder(hass)
    with patch.object(Recorder, "_setup_connection") as setup, patch(
        "homeassistant.components.recorder.core.time.sleep"
    ):
        setup.side_effect = ImportError("driver not found")
        rec = _default_recorder(hass)
        rec.start()
        rec.join()

    hass.stop()


async def test_defaults_set(hass):
    """Test the config defaults are set."""
    recorder_config = None

    async def mock_setup(hass, config):
        """Mock setup."""
        nonlocal recorder_config
        recorder_config = config["recorder"]
        return True

    with patch("homeassistant.components.recorder.async_setup", side_effect=mock_setup):
        assert await async_setup_component(hass, "history", {})

    assert recorder_config is not None
    # pylint: disable=unsubscriptable-object
    assert recorder_config["auto_purge"]
    assert recorder_config["auto_repack"]
    assert recorder_config["purge_keep_days"] == 10


def run_tasks_at_time(hass, test_time):
    """Advance the clock and wait for any callbacks to finish."""
    fire_time_changed(hass, test_time)
    hass.block_till_done()
    get_instance(hass).block_till_done()


@pytest.mark.parametrize("enable_nightly_purge", [True])
def test_auto_purge(hass_recorder):
    """Test periodic purge scheduling."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data, patch(
        "homeassistant.components.recorder.tasks.periodic_db_cleanups"
    ) as periodic_db_cleanups:
        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()

        # Advance one day, and the purge task should run again
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()

        # Advance less than one full day.  The alarm should not yet fire.
        test_time = test_time + timedelta(hours=23)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 0

        # Advance to the next day and fire the alarm again
        test_time = test_time + timedelta(hours=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        assert len(periodic_db_cleanups.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


@pytest.mark.parametrize("enable_nightly_purge", [True])
def test_auto_purge_auto_repack_on_second_sunday(hass_recorder):
    """Test periodic purge scheduling does a repack on the 2nd sunday."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.core.is_second_sunday", return_value=True
    ), patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data, patch(
        "homeassistant.components.recorder.tasks.periodic_db_cleanups"
    ) as periodic_db_cleanups:
        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is True  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


@pytest.mark.parametrize("enable_nightly_purge", [True])
def test_auto_purge_auto_repack_disabled_on_second_sunday(hass_recorder):
    """Test periodic purge scheduling does not auto repack on the 2nd sunday if disabled."""
    hass = hass_recorder({CONF_AUTO_REPACK: False})

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.core.is_second_sunday", return_value=True
    ), patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data, patch(
        "homeassistant.components.recorder.tasks.periodic_db_cleanups"
    ) as periodic_db_cleanups:
        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is False  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


@pytest.mark.parametrize("enable_nightly_purge", [True])
def test_auto_purge_no_auto_repack_on_not_second_sunday(hass_recorder):
    """Test periodic purge scheduling does not do a repack unless its the 2nd sunday."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Purging is scheduled to happen at 4:12am every day. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.core.is_second_sunday",
        return_value=False,
    ), patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data, patch(
        "homeassistant.components.recorder.tasks.periodic_db_cleanups"
    ) as periodic_db_cleanups:
        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 1
        args, _ = purge_old_data.call_args_list[0]
        assert args[2] is False  # repack
        assert len(periodic_db_cleanups.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


@pytest.mark.parametrize("enable_nightly_purge", [True])
def test_auto_purge_disabled(hass_recorder):
    """Test periodic db cleanup still run when auto purge is disabled."""
    hass = hass_recorder({CONF_AUTO_PURGE: False})

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Purging is scheduled to happen at 4:12am every day. We want
    # to verify that when auto purge is disabled periodic db cleanups
    # are still scheduled
    #
    # The clock is started at 4:15am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 15, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data, patch(
        "homeassistant.components.recorder.tasks.periodic_db_cleanups"
    ) as periodic_db_cleanups:
        # Advance one day, and the purge task should run
        test_time = test_time + timedelta(days=1)
        run_tasks_at_time(hass, test_time)
        assert len(purge_old_data.mock_calls) == 0
        assert len(periodic_db_cleanups.mock_calls) == 1

        purge_old_data.reset_mock()
        periodic_db_cleanups.reset_mock()

    dt_util.set_default_time_zone(original_tz)


@pytest.mark.parametrize("enable_statistics", [True])
def test_auto_statistics(hass_recorder):
    """Test periodic statistics scheduling."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    # Statistics is scheduled to happen every 5 minutes. Exercise this behavior by
    # firing time changed events and advancing the clock around this time. Pick an
    # arbitrary year in the future to avoid boundary conditions relative to the current
    # date.
    #
    # The clock is started at 4:16am then advanced forward below
    now = dt_util.utcnow()
    test_time = datetime(now.year + 2, 1, 1, 4, 16, 0, tzinfo=tz)
    run_tasks_at_time(hass, test_time)

    with patch(
        "homeassistant.components.recorder.statistics.compile_statistics",
        return_value=True,
    ) as compile_statistics:
        # Advance 5 minutes, and the statistics task should run
        test_time = test_time + timedelta(minutes=5)
        run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1

        compile_statistics.reset_mock()

        # Advance 5 minutes, and the statistics task should run again
        test_time = test_time + timedelta(minutes=5)
        run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1

        compile_statistics.reset_mock()

        # Advance less than 5 minutes. The task should not run.
        test_time = test_time + timedelta(minutes=3)
        run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 0

        # Advance 5 minutes, and the statistics task should run again
        test_time = test_time + timedelta(minutes=5)
        run_tasks_at_time(hass, test_time)
        assert len(compile_statistics.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


def test_statistics_runs_initiated(hass_recorder):
    """Test statistics_runs is initiated when DB is created."""
    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=now
    ):
        hass = hass_recorder()

        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            statistics_runs = list(session.query(StatisticsRuns))
            assert len(statistics_runs) == 1
            last_run = process_timestamp(statistics_runs[0].start)
            assert process_timestamp(last_run) == now.replace(
                minute=now.minute - now.minute % 5, second=0, microsecond=0
            ) - timedelta(minutes=5)


def test_compile_missing_statistics(tmpdir):
    """Test missing statistics are compiled on startup."""
    now = dt_util.utcnow().replace(minute=0, second=0, microsecond=0)
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow", return_value=now
    ):

        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        hass.start()
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            statistics_runs = list(session.query(StatisticsRuns))
            assert len(statistics_runs) == 1
            last_run = process_timestamp(statistics_runs[0].start)
            assert last_run == now - timedelta(minutes=5)

        wait_recording_done(hass)
        wait_recording_done(hass)
        hass.stop()

    with patch(
        "homeassistant.components.recorder.core.dt_util.utcnow",
        return_value=now + timedelta(hours=1),
    ):

        hass = get_test_home_assistant()
        recorder_helper.async_initialize_recorder(hass)
        setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
        hass.start()
        wait_recording_done(hass)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            statistics_runs = list(session.query(StatisticsRuns))
            assert len(statistics_runs) == 13  # 12 5-minute runs
            last_run = process_timestamp(statistics_runs[1].start)
            assert last_run == now

        wait_recording_done(hass)
        wait_recording_done(hass)
        hass.stop()


def test_saving_sets_old_state(hass_recorder):
    """Test saving sets old state."""
    hass = hass_recorder()

    hass.states.set("test.one", "on", {})
    hass.states.set("test.two", "on", {})
    wait_recording_done(hass)
    hass.states.set("test.one", "off", {})
    hass.states.set("test.two", "off", {})
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = list(session.query(States))
        assert len(states) == 4

        assert states[0].entity_id == "test.one"
        assert states[1].entity_id == "test.two"
        assert states[2].entity_id == "test.one"
        assert states[3].entity_id == "test.two"

        assert states[0].old_state_id is None
        assert states[1].old_state_id is None
        assert states[2].old_state_id == states[0].state_id
        assert states[3].old_state_id == states[1].state_id


def test_saving_state_with_serializable_data(hass_recorder, caplog):
    """Test saving data that cannot be serialized does not crash."""
    hass = hass_recorder()

    hass.bus.fire("bad_event", {"fail": CannotSerializeMe()})
    hass.states.set("test.one", "on", {"fail": CannotSerializeMe()})
    wait_recording_done(hass)
    hass.states.set("test.two", "on", {})
    wait_recording_done(hass)
    hass.states.set("test.two", "off", {})
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = list(session.query(States))
        assert len(states) == 2

        assert states[0].entity_id == "test.two"
        assert states[1].entity_id == "test.two"
        assert states[0].old_state_id is None
        assert states[1].old_state_id == states[0].state_id

    assert "State is not JSON serializable" in caplog.text


def test_has_services(hass_recorder):
    """Test the services exist."""
    hass = hass_recorder()

    assert hass.services.has_service(DOMAIN, SERVICE_DISABLE)
    assert hass.services.has_service(DOMAIN, SERVICE_ENABLE)
    assert hass.services.has_service(DOMAIN, SERVICE_PURGE)
    assert hass.services.has_service(DOMAIN, SERVICE_PURGE_ENTITIES)


def test_service_disable_events_not_recording(hass, hass_recorder):
    """Test that events are not recorded when recorder is disabled using service."""
    hass = hass_recorder()

    assert hass.services.call(
        DOMAIN,
        SERVICE_DISABLE,
        {},
        blocking=True,
    )

    event_type = "EVENT_TEST"

    events = []

    @callback
    def event_listener(event):
        """Record events from eventbus."""
        if event.event_type == event_type:
            events.append(event)

    hass.bus.listen(MATCH_ALL, event_listener)

    event_data1 = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.fire(event_type, event_data1)
    wait_recording_done(hass)

    assert len(events) == 1
    event = events[0]

    with session_scope(hass=hass) as session:
        db_events = list(session.query(Events).filter_by(event_type=event_type))
        assert len(db_events) == 0

    assert hass.services.call(
        DOMAIN,
        SERVICE_ENABLE,
        {},
        blocking=True,
    )

    event_data2 = {"attr_one": 5, "attr_two": "nice"}
    hass.bus.fire(event_type, event_data2)
    wait_recording_done(hass)

    assert len(events) == 2
    assert events[0] != events[1]
    assert events[0].data != events[1].data

    db_events = []
    with session_scope(hass=hass) as session:
        for select_event, event_data in (
            session.query(Events, EventData)
            .filter_by(event_type=event_type)
            .outerjoin(EventData, Events.data_id == EventData.data_id)
        ):
            select_event = cast(Events, select_event)
            event_data = cast(EventData, event_data)

            native_event = select_event.to_native()
            native_event.data = event_data.to_native()
            db_events.append(native_event)

    assert len(db_events) == 1
    db_event = db_events[0]
    event = events[1]

    assert event.event_type == db_event.event_type
    assert event.data == db_event.data
    assert event.origin == db_event.origin
    assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
        microsecond=0
    )


def test_service_disable_states_not_recording(hass, hass_recorder):
    """Test that state changes are not recorded when recorder is disabled using service."""
    hass = hass_recorder()

    assert hass.services.call(
        DOMAIN,
        SERVICE_DISABLE,
        {},
        blocking=True,
    )

    hass.states.set("test.one", "on", {})
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        assert len(list(session.query(States))) == 0

    assert hass.services.call(
        DOMAIN,
        SERVICE_ENABLE,
        {},
        blocking=True,
    )

    hass.states.set("test.two", "off", {})
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_states = list(session.query(States))
        assert len(db_states) == 1
        assert db_states[0].event_id is None
        assert db_states[0].to_native() == _state_with_context(hass, "test.two")


def test_service_disable_run_information_recorded(tmpdir):
    """Test that runs are still recorded when recorder is disabled."""
    test_db_file = tmpdir.mkdir("sqlite").join("test_run_info.db")
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
    hass.start()
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_run_info = list(session.query(RecorderRuns))
        assert len(db_run_info) == 1
        assert db_run_info[0].start is not None
        assert db_run_info[0].end is None

    assert hass.services.call(
        DOMAIN,
        SERVICE_DISABLE,
        {},
        blocking=True,
    )

    wait_recording_done(hass)
    hass.stop()

    hass = get_test_home_assistant()
    recorder_helper.async_initialize_recorder(hass)
    setup_component(hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl}})
    hass.start()
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        db_run_info = list(session.query(RecorderRuns))
        assert len(db_run_info) == 2
        assert db_run_info[0].start is not None
        assert db_run_info[0].end is not None
        assert db_run_info[1].start is not None
        assert db_run_info[1].end is None

    hass.stop()


class CannotSerializeMe:
    """A class that the JSONEncoder cannot serialize."""


async def test_database_corruption_while_running(hass, tmpdir, caplog):
    """Test we can recover from sqlite3 db corruption."""

    def _create_tmpdir_for_test_db():
        return tmpdir.mkdir("sqlite").join("test.db")

    test_db_file = await hass.async_add_executor_job(_create_tmpdir_for_test_db)
    dburl = f"{SQLITE_URL_PREFIX}//{test_db_file}"

    recorder_helper.async_initialize_recorder(hass)
    assert await async_setup_component(
        hass, DOMAIN, {DOMAIN: {CONF_DB_URL: dburl, CONF_COMMIT_INTERVAL: 0}}
    )
    await hass.async_block_till_done()
    caplog.clear()

    original_start_time = get_instance(hass).run_history.recording_start

    hass.states.async_set("test.lost", "on", {})

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with patch.object(
        get_instance(hass).event_session,
        "close",
        side_effect=OperationalError("statement", {}, []),
    ):
        await async_wait_recording_done(hass)
        await hass.async_add_executor_job(corrupt_db_file, test_db_file)
        await async_wait_recording_done(hass)

        with patch.object(
            get_instance(hass).event_session,
            "commit",
            side_effect=[sqlite3_exception, None],
        ):
            # This state will not be recorded because
            # the database corruption will be discovered
            # and we will have to rollback to recover
            hass.states.async_set("test.one", "off", {})
            await async_wait_recording_done(hass)

    assert "Unrecoverable sqlite3 database corruption detected" in caplog.text
    assert "The system will rename the corrupt database file" in caplog.text
    assert "Connected to recorder database" in caplog.text

    # This state should go into the new database
    hass.states.async_set("test.two", "on", {})
    await async_wait_recording_done(hass)

    def _get_last_state():
        with session_scope(hass=hass) as session:
            db_states = list(session.query(States))
            assert len(db_states) == 1
            assert db_states[0].event_id is None
            return db_states[0].to_native()

    state = await hass.async_add_executor_job(_get_last_state)
    assert state.entity_id == "test.two"
    assert state.state == "on"

    new_start_time = get_instance(hass).run_history.recording_start
    assert original_start_time < new_start_time

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()
    hass.stop()


def test_entity_id_filter(hass_recorder):
    """Test that entity ID filtering filters string and list."""
    hass = hass_recorder(
        {"include": {"domains": "hello"}, "exclude": {"domains": "hidden_domain"}}
    )

    for idx, data in enumerate(
        (
            {},
            {"entity_id": "hello.world"},
            {"entity_id": ["hello.world"]},
            {"entity_id": ["hello.world", "hidden_domain.person"]},
            {"entity_id": {"unexpected": "data"}},
        )
    ):
        hass.bus.fire("hello", data)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            db_events = list(session.query(Events).filter_by(event_type="hello"))
            assert len(db_events) == idx + 1, data

    for data in (
        {"entity_id": "hidden_domain.person"},
        {"entity_id": ["hidden_domain.person"]},
    ):
        hass.bus.fire("hello", data)
        wait_recording_done(hass)

        with session_scope(hass=hass) as session:
            db_events = list(session.query(Events).filter_by(event_type="hello"))
            # Keep referring idx + 1, as no new events are being added
            assert len(db_events) == idx + 1, data


async def test_database_lock_and_unlock(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    tmp_path,
):
    """Test writing events during lock getting written after unlocking."""
    # Use file DB, in memory DB cannot do write locks.
    config = {
        recorder.CONF_COMMIT_INTERVAL: 0,
        recorder.CONF_DB_URL: "sqlite:///" + str(tmp_path / "pytest.db"),
    }
    await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()

    def _get_db_events():
        with session_scope(hass=hass) as session:
            return list(session.query(Events).filter_by(event_type=event_type))

    instance = get_instance(hass)

    assert await instance.lock_database()

    assert not await instance.lock_database()

    event_type = "EVENT_TEST"
    event_data = {"test_attr": 5, "test_attr_10": "nice"}
    hass.bus.async_fire(event_type, event_data)
    task = asyncio.create_task(async_wait_recording_done(hass))

    # Recording can't be finished while lock is held
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), timeout=1)
        db_events = await hass.async_add_executor_job(_get_db_events)
        assert len(db_events) == 0

    assert instance.unlock_database()

    await task
    db_events = await hass.async_add_executor_job(_get_db_events)
    assert len(db_events) == 1


async def test_database_lock_and_overflow(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    tmp_path,
):
    """Test writing events during lock leading to overflow the queue causes the database to unlock."""
    # Use file DB, in memory DB cannot do write locks.
    config = {
        recorder.CONF_COMMIT_INTERVAL: 0,
        recorder.CONF_DB_URL: "sqlite:///" + str(tmp_path / "pytest.db"),
    }
    await async_setup_recorder_instance(hass, config)
    await hass.async_block_till_done()

    def _get_db_events():
        with session_scope(hass=hass) as session:
            return list(session.query(Events).filter_by(event_type=event_type))

    instance = get_instance(hass)

    with patch.object(recorder.core, "MAX_QUEUE_BACKLOG", 1), patch.object(
        recorder.core, "DB_LOCK_QUEUE_CHECK_TIMEOUT", 0.1
    ):
        await instance.lock_database()

        event_type = "EVENT_TEST"
        event_data = {"test_attr": 5, "test_attr_10": "nice"}
        hass.bus.fire(event_type, event_data)

        # Check that this causes the queue to overflow and write succeeds
        # even before unlocking.
        await async_wait_recording_done(hass)

        db_events = await hass.async_add_executor_job(_get_db_events)
        assert len(db_events) == 1

        assert not instance.unlock_database()


async def test_database_lock_timeout(hass, recorder_mock):
    """Test locking database timeout when recorder stopped."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)

    instance = get_instance(hass)

    class BlockQueue(recorder.tasks.RecorderTask):
        event: threading.Event = threading.Event()

        def run(self, instance: Recorder) -> None:
            self.event.wait()

    block_task = BlockQueue()
    instance.queue_task(block_task)
    with patch.object(recorder.core, "DB_LOCK_TIMEOUT", 0.1):
        try:
            with pytest.raises(TimeoutError):
                await instance.lock_database()
        finally:
            instance.unlock_database()
            block_task.event.set()


async def test_database_lock_without_instance(hass, recorder_mock):
    """Test database lock doesn't fail if instance is not initialized."""
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)

    instance = get_instance(hass)
    with patch.object(instance, "engine", None):
        try:
            assert await instance.lock_database()
        finally:
            assert instance.unlock_database()


async def test_in_memory_database(hass, caplog):
    """Test connecting to an in-memory recorder is not allowed."""
    assert not await async_setup_component(
        hass, recorder.DOMAIN, {recorder.DOMAIN: {recorder.CONF_DB_URL: "sqlite://"}}
    )
    assert "In-memory SQLite database is not supported" in caplog.text


async def test_database_connection_keep_alive(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog: pytest.LogCaptureFixture,
):
    """Test we keep alive socket based dialects."""
    with patch("homeassistant.components.recorder.Recorder.dialect_name"):
        instance = await async_setup_recorder_instance(hass)
        # We have to mock this since we don't have a mock
        # MySQL server available in tests.
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
        await instance.async_recorder_ready.wait()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=recorder.core.KEEPALIVE_TIME)
    )
    await async_wait_recording_done(hass)
    assert "Sending keepalive" in caplog.text


async def test_database_connection_keep_alive_disabled_on_sqlite(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog: pytest.LogCaptureFixture,
):
    """Test we do not do keep alive for sqlite."""
    instance = await async_setup_recorder_instance(hass)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await instance.async_recorder_ready.wait()

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=recorder.core.KEEPALIVE_TIME)
    )
    await async_wait_recording_done(hass)
    assert "Sending keepalive" not in caplog.text


def test_deduplication_event_data_inside_commit_interval(hass_recorder, caplog):
    """Test deduplication of event data inside the commit interval."""
    hass = hass_recorder()

    for _ in range(10):
        hass.bus.fire("this_event", {"de": "dupe"})
    wait_recording_done(hass)
    for _ in range(10):
        hass.bus.fire("this_event", {"de": "dupe"})
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        events = list(
            session.query(Events)
            .filter(Events.event_type == "this_event")
            .outerjoin(EventData, (Events.data_id == EventData.data_id))
        )
        assert len(events) == 20
        first_data_id = events[0].data_id
        assert all(event.data_id == first_data_id for event in events)


# Patch STATE_ATTRIBUTES_ID_CACHE_SIZE since otherwise
# the CI can fail because the test takes too long to run
@patch("homeassistant.components.recorder.core.STATE_ATTRIBUTES_ID_CACHE_SIZE", 5)
def test_deduplication_state_attributes_inside_commit_interval(hass_recorder, caplog):
    """Test deduplication of state attributes inside the commit interval."""
    hass = hass_recorder()

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.set(entity_id, "on", attributes)
    hass.states.set(entity_id, "off", attributes)

    # Now exaust the cache to ensure we go back to the db
    for attr_id in range(5):
        hass.states.set(entity_id, "on", {"test_attr": attr_id})
        hass.states.set(entity_id, "off", {"test_attr": attr_id})

    wait_recording_done(hass)
    for _ in range(5):
        hass.states.set(entity_id, "on", attributes)
        hass.states.set(entity_id, "off", attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        states = list(
            session.query(States)
            .filter(States.entity_id == entity_id)
            .outerjoin(
                StateAttributes, (States.attributes_id == StateAttributes.attributes_id)
            )
        )
        assert len(states) == 22
        first_attributes_id = states[0].attributes_id
        last_attributes_id = states[-1].attributes_id
        assert first_attributes_id == last_attributes_id


async def test_async_block_till_done(hass, async_setup_recorder_instance):
    """Test we can block until recordering is done."""
    instance = await async_setup_recorder_instance(hass)
    await async_wait_recording_done(hass)

    entity_id = "test.recorder"
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    hass.states.async_set(entity_id, "on", attributes)
    hass.states.async_set(entity_id, "off", attributes)

    def _fetch_states():
        with session_scope(hass=hass) as session:
            return list(session.query(States).filter(States.entity_id == entity_id))

    await async_block_recorder(hass, 0.1)
    await instance.async_block_till_done()
    states = await instance.async_add_executor_job(_fetch_states)
    assert len(states) == 2
    await hass.async_block_till_done()
