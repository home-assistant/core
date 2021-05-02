"""Test data purging."""
from datetime import datetime, timedelta
import json
import sqlite3
from unittest.mock import MagicMock, patch

from sqlalchemy.exc import DatabaseError, OperationalError
from sqlalchemy.orm.session import Session

from homeassistant.components import recorder
from homeassistant.components.recorder.models import Events, RecorderRuns, States
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .common import (
    async_recorder_block_till_done,
    async_wait_purge_done,
    async_wait_recording_done,
    async_wait_recording_done_without_instance,
)
from .conftest import SetupRecorderInstanceT


async def test_purge_old_states(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old states."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_states(hass, instance)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6
        assert states[0].old_state_id is None
        assert states[-1].old_state_id == states[-2].state_id

        events = session.query(Events).filter(Events.event_type == "state_changed")
        assert events.count() == 6

        # run purge_old_data()
        finished = purge_old_data(instance, 4, repack=False)
        assert not finished
        assert states.count() == 2

        states_after_purge = session.query(States)
        assert states_after_purge[1].old_state_id == states_after_purge[0].state_id
        assert states_after_purge[0].old_state_id is None

        finished = purge_old_data(instance, 4, repack=False)
        assert finished
        assert states.count() == 2


async def test_purge_old_states_encouters_database_corruption(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test database image image is malformed while deleting old states."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_states(hass, instance)
    await async_wait_recording_done_without_instance(hass)

    sqlite3_exception = DatabaseError("statement", {}, [])
    sqlite3_exception.__cause__ = sqlite3.DatabaseError()

    with patch(
        "homeassistant.components.recorder.move_away_broken_database"
    ) as move_away, patch(
        "homeassistant.components.recorder.purge.purge_old_data",
        side_effect=sqlite3_exception,
    ):
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, {"keep_days": 0}
        )
        await hass.async_block_till_done()
        await async_wait_recording_done_without_instance(hass)

    assert move_away.called

    # Ensure the whole database was reset due to the database error
    with session_scope(hass=hass) as session:
        states_after_purge = session.query(States)
        assert states_after_purge.count() == 0


async def test_purge_old_states_encounters_temporary_mysql_error(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog,
):
    """Test retry on specific mysql operational errors."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_states(hass, instance)
    await async_wait_recording_done_without_instance(hass)

    mysql_exception = OperationalError("statement", {}, [])
    mysql_exception.orig = MagicMock(args=(1205, "retryable"))

    with patch(
        "homeassistant.components.recorder.purge.time.sleep"
    ) as sleep_mock, patch(
        "homeassistant.components.recorder.purge._purge_old_recorder_runs",
        side_effect=[mysql_exception, None],
    ), patch.object(
        instance.engine.dialect, "name", "mysql"
    ):
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, {"keep_days": 0}
        )
        await hass.async_block_till_done()
        await async_wait_recording_done_without_instance(hass)
        await async_wait_recording_done_without_instance(hass)

    assert "retrying" in caplog.text
    assert sleep_mock.called


async def test_purge_old_states_encounters_operational_error(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog,
):
    """Test error on operational errors that are not mysql does not retry."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_states(hass, instance)
    await async_wait_recording_done_without_instance(hass)

    exception = OperationalError("statement", {}, [])

    with patch(
        "homeassistant.components.recorder.purge._purge_old_recorder_runs",
        side_effect=exception,
    ):
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, {"keep_days": 0}
        )
        await hass.async_block_till_done()
        await async_wait_recording_done_without_instance(hass)
        await async_wait_recording_done_without_instance(hass)

    assert "retrying" not in caplog.text
    assert "Error purging history" in caplog.text


async def test_purge_old_events(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old events."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_events(hass, instance)

    with session_scope(hass=hass) as session:
        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        # run purge_old_data()
        finished = purge_old_data(instance, 4, repack=False)
        assert not finished
        assert events.count() == 2

        # we should only have 2 events left
        finished = purge_old_data(instance, 4, repack=False)
        assert finished
        assert events.count() == 2


async def test_purge_old_recorder_runs(
    hass: HomeAssistant, async_setup_recorder_instance: SetupRecorderInstanceT
):
    """Test deleting old recorder runs keeps current run."""
    instance = await async_setup_recorder_instance(hass)

    await _add_test_recorder_runs(hass, instance)

    # make sure we start with 7 recorder runs
    with session_scope(hass=hass) as session:
        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7

        # run purge_old_data()
        finished = purge_old_data(instance, 0, repack=False)
        assert not finished

        finished = purge_old_data(instance, 0, repack=False)
        assert finished
        assert recorder_runs.count() == 1


async def test_purge_method(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
    caplog,
):
    """Test purge method."""
    instance = await async_setup_recorder_instance(hass)

    service_data = {"keep_days": 4}
    await _add_test_events(hass, instance)
    await _add_test_states(hass, instance)
    await _add_test_recorder_runs(hass, instance)
    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    # make sure we start with 6 states
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 6

        events = session.query(Events).filter(Events.event_type.like("EVENT_TEST%"))
        assert events.count() == 6

        recorder_runs = session.query(RecorderRuns)
        assert recorder_runs.count() == 7
        runs_before_purge = recorder_runs.all()

        await hass.async_block_till_done()
        await async_wait_purge_done(hass, instance)

        # run purge method - no service data, use defaults
        await hass.services.async_call("recorder", "purge")
        await hass.async_block_till_done()

        # Small wait for recorder thread
        await async_wait_purge_done(hass, instance)

        # only purged old events
        assert states.count() == 4
        assert events.count() == 4

        # run purge method - correct service data
        await hass.services.async_call("recorder", "purge", service_data=service_data)
        await hass.async_block_till_done()

        # Small wait for recorder thread
        await async_wait_purge_done(hass, instance)

        # we should only have 2 states left after purging
        assert states.count() == 2

        # now we should only have 2 events left
        assert events.count() == 2

        # now we should only have 3 recorder runs left
        runs = recorder_runs.all()
        assert runs[0] == runs_before_purge[0]
        assert runs[1] == runs_before_purge[5]
        assert runs[2] == runs_before_purge[6]

        assert "EVENT_TEST_PURGE" not in (event.event_type for event in events.all())

        # run purge method - correct service data, with repack
        service_data["repack"] = True
        await hass.services.async_call("recorder", "purge", service_data=service_data)
        await hass.async_block_till_done()
        await async_wait_purge_done(hass, instance)
        assert "Vacuuming SQL DB to free space" in caplog.text


async def test_purge_edge_case(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
):
    """Test states and events are purged even if they occurred shortly before purge_before."""

    async def _add_db_entries(hass: HomeAssistant, timestamp: datetime) -> None:
        with recorder.session_scope(hass=hass) as session:
            session.add(
                Events(
                    event_id=1001,
                    event_type="EVENT_TEST_PURGE",
                    event_data="{}",
                    origin="LOCAL",
                    created=timestamp,
                    time_fired=timestamp,
                )
            )
            session.add(
                States(
                    entity_id="test.recorder2",
                    domain="sensor",
                    state="purgeme",
                    attributes="{}",
                    last_changed=timestamp,
                    last_updated=timestamp,
                    created=timestamp,
                    event_id=1001,
                )
            )

    instance = await async_setup_recorder_instance(hass, None)
    await async_wait_purge_done(hass, instance)

    service_data = {"keep_days": 2}
    timestamp = dt_util.utcnow() - timedelta(days=2, minutes=1)

    await _add_db_entries(hass, timestamp)
    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 1

        events = session.query(Events).filter(Events.event_type == "EVENT_TEST_PURGE")
        assert events.count() == 1

        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert states.count() == 0
        assert events.count() == 0


async def test_purge_filtered_states(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
):
    """Test filtered states are purged."""
    config: ConfigType = {"exclude": {"entities": ["sensor.excluded"]}}
    instance = await async_setup_recorder_instance(hass, config)
    assert instance.entity_filter("sensor.excluded") is False

    def _add_db_entries(hass: HomeAssistant) -> None:
        with recorder.session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_and_state_changed_event(
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
                    domain="sensor",
                    state="purgeme",
                    attributes="{}",
                    last_changed=timestamp,
                    last_updated=timestamp,
                    created=timestamp,
                )
            )
            # Add states and state_changed events that should be keeped
            timestamp = dt_util.utcnow() - timedelta(days=2)
            for event_id in range(200, 210):
                _add_state_and_state_changed_event(
                    session,
                    "sensor.keep",
                    "keep",
                    timestamp,
                    event_id,
                )
            # Add states with linked old_state_ids that need to be handled
            timestamp = dt_util.utcnow() - timedelta(days=0)
            state_1 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=1,
            )
            timestamp = dt_util.utcnow() - timedelta(days=4)
            state_2 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=2,
            )
            state_3 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=62,  # keep
            )
            session.add_all((state_1, state_2, state_3))
            # Add event that should be keeped
            session.add(
                Events(
                    event_id=100,
                    event_type="EVENT_KEEP",
                    event_data="{}",
                    origin="LOCAL",
                    created=timestamp,
                    time_fired=timestamp,
                )
            )

    service_data = {"keep_days": 10}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        states = session.query(States)
        assert states.count() == 74

        events_state_changed = session.query(Events).filter(
            Events.event_type == EVENT_STATE_CHANGED
        )
        events_keep = session.query(Events).filter(Events.event_type == "EVENT_KEEP")
        assert events_state_changed.count() == 70
        assert events_keep.count() == 1

        # Normal purge doesn't remove excluded entities
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert states.count() == 74
        assert events_state_changed.count() == 70
        assert events_keep.count() == 1

        # Test with 'apply_filter' = True
        service_data["apply_filter"] = True
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert states.count() == 13
        assert events_state_changed.count() == 10
        assert events_keep.count() == 1

        states_sensor_excluded = session.query(States).filter(
            States.entity_id == "sensor.excluded"
        )
        assert states_sensor_excluded.count() == 0

        assert session.query(States).get(72).old_state_id is None
        assert session.query(States).get(73).old_state_id is None
        assert session.query(States).get(74).old_state_id == 62  # should have been kept


async def test_purge_filtered_events(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
):
    """Test filtered events are purged."""
    config: ConfigType = {"exclude": {"event_types": ["EVENT_PURGE"]}}
    instance = await async_setup_recorder_instance(hass, config)

    def _add_db_entries(hass: HomeAssistant) -> None:
        with recorder.session_scope(hass=hass) as session:
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
                            created=timestamp,
                            time_fired=timestamp,
                        )
                    )

            # Add states and state_changed events that should be keeped
            timestamp = dt_util.utcnow() - timedelta(days=1)
            for event_id in range(200, 210):
                _add_state_and_state_changed_event(
                    session,
                    "sensor.keep",
                    "keep",
                    timestamp,
                    event_id,
                )

    service_data = {"keep_days": 10}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        events_purge = session.query(Events).filter(Events.event_type == "EVENT_PURGE")
        events_keep = session.query(Events).filter(
            Events.event_type == EVENT_STATE_CHANGED
        )
        states = session.query(States)

        assert events_purge.count() == 60
        assert events_keep.count() == 10
        assert states.count() == 10

        # Normal purge doesn't remove excluded events
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert events_purge.count() == 60
        assert events_keep.count() == 10
        assert states.count() == 10

        # Test with 'apply_filter' = True
        service_data["apply_filter"] = True
        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert events_purge.count() == 0
        assert events_keep.count() == 10
        assert states.count() == 10


async def test_purge_filtered_events_state_changed(
    hass: HomeAssistant,
    async_setup_recorder_instance: SetupRecorderInstanceT,
):
    """Test filtered state_changed events are purged. This should also remove all states."""
    config: ConfigType = {"exclude": {"event_types": [EVENT_STATE_CHANGED]}}
    instance = await async_setup_recorder_instance(hass, config)
    # Assert entity_id is NOT excluded
    assert instance.entity_filter("sensor.excluded") is True

    def _add_db_entries(hass: HomeAssistant) -> None:
        with recorder.session_scope(hass=hass) as session:
            # Add states and state_changed events that should be purged
            for days in range(1, 4):
                timestamp = dt_util.utcnow() - timedelta(days=days)
                for event_id in range(1000, 1020):
                    _add_state_and_state_changed_event(
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
                        created=timestamp,
                        time_fired=timestamp,
                    )
                )
            # Add states with linked old_state_ids that need to be handled
            timestamp = dt_util.utcnow() - timedelta(days=0)
            state_1 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=1,
            )
            timestamp = dt_util.utcnow() - timedelta(days=4)
            state_2 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=2,
            )
            state_3 = States(
                entity_id="sensor.linked_old_state_id",
                domain="sensor",
                state="keep",
                attributes="{}",
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                old_state_id=62,  # keep
            )
            session.add_all((state_1, state_2, state_3))

    service_data = {"keep_days": 10, "apply_filter": True}
    _add_db_entries(hass)

    with session_scope(hass=hass) as session:
        events_keep = session.query(Events).filter(Events.event_type == "EVENT_KEEP")
        events_purge = session.query(Events).filter(
            Events.event_type == EVENT_STATE_CHANGED
        )
        states = session.query(States)

        assert events_keep.count() == 10
        assert events_purge.count() == 60
        assert states.count() == 63

        await hass.services.async_call(
            recorder.DOMAIN, recorder.SERVICE_PURGE, service_data
        )
        await hass.async_block_till_done()

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        await async_recorder_block_till_done(hass, instance)
        await async_wait_purge_done(hass, instance)

        assert events_keep.count() == 10
        assert events_purge.count() == 0
        assert states.count() == 3

        assert session.query(States).get(61).old_state_id is None
        assert session.query(States).get(62).old_state_id is None
        assert session.query(States).get(63).old_state_id == 62  # should have been kept


async def _add_test_states(hass: HomeAssistant, instance: recorder.Recorder):
    """Add multiple states to the db for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    attributes = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
        old_state_id = None
        for event_id in range(6):
            if event_id < 2:
                timestamp = eleven_days_ago
                state = "autopurgeme"
            elif event_id < 4:
                timestamp = five_days_ago
                state = "purgeme"
            else:
                timestamp = utcnow
                state = "dontpurgeme"

            event = Events(
                event_type="state_changed",
                event_data="{}",
                origin="LOCAL",
                created=timestamp,
                time_fired=timestamp,
            )
            session.add(event)
            session.flush()
            state = States(
                entity_id="test.recorder2",
                domain="sensor",
                state=state,
                attributes=json.dumps(attributes),
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                event_id=event.event_id,
                old_state_id=old_state_id,
            )
            session.add(state)
            session.flush()
            old_state_id = state.state_id


async def _add_test_events(hass: HomeAssistant, instance: recorder.Recorder):
    """Add a few events for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)
    event_data = {"test_attr": 5, "test_attr_10": "nice"}

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
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
                    created=timestamp,
                    time_fired=timestamp,
                )
            )


async def _add_test_recorder_runs(hass: HomeAssistant, instance: recorder.Recorder):
    """Add a few recorder_runs for testing."""
    utcnow = dt_util.utcnow()
    five_days_ago = utcnow - timedelta(days=5)
    eleven_days_ago = utcnow - timedelta(days=11)

    await hass.async_block_till_done()
    await async_wait_recording_done(hass, instance)

    with recorder.session_scope(hass=hass) as session:
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


def _add_state_and_state_changed_event(
    session: Session,
    entity_id: str,
    state: str,
    timestamp: datetime,
    event_id: int,
) -> None:
    """Add state and state_changed event to database for testing."""
    session.add(
        States(
            entity_id=entity_id,
            domain="sensor",
            state=state,
            attributes="{}",
            last_changed=timestamp,
            last_updated=timestamp,
            created=timestamp,
            event_id=event_id,
        )
    )
    session.add(
        Events(
            event_id=event_id,
            event_type=EVENT_STATE_CHANGED,
            event_data="{}",
            origin="LOCAL",
            created=timestamp,
            time_fired=timestamp,
        )
    )
