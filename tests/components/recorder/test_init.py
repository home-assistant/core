"""The tests for the Recorder component."""
# pylint: disable=protected-access
from datetime import datetime, timedelta
import unittest

import pytest

from homeassistant.components.recorder import (
    CONFIG_SCHEMA,
    DOMAIN,
    Recorder,
    run_information,
    run_information_from_instance,
    run_information_with_session,
)
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.models import Events, RecorderRuns, States
from homeassistant.components.recorder.util import session_scope
from homeassistant.const import MATCH_ALL, STATE_LOCKED, STATE_UNLOCKED
from homeassistant.core import Context, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .common import wait_recording_done

from tests.async_mock import patch
from tests.common import (
    async_fire_time_changed,
    get_test_home_assistant,
    init_recorder_component,
)


class TestRecorder(unittest.TestCase):
    """Test the recorder module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)
        self.hass.start()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_saving_state(self):
        """Test saving and restoring a state."""
        entity_id = "test.recorder"
        state = "restoring_from_db"
        attributes = {"test_attr": 5, "test_attr_10": "nice"}

        self.hass.states.set(entity_id, state, attributes)

        wait_recording_done(self.hass)

        with session_scope(hass=self.hass) as session:
            db_states = list(session.query(States))
            assert len(db_states) == 1
            assert db_states[0].event_id > 0
            state = db_states[0].to_native()

        assert state == _state_empty_context(self.hass, entity_id)

    def test_saving_event(self):
        """Test saving and restoring an event."""
        event_type = "EVENT_TEST"
        event_data = {"test_attr": 5, "test_attr_10": "nice"}

        events = []

        @callback
        def event_listener(event):
            """Record events from eventbus."""
            if event.event_type == event_type:
                events.append(event)

        self.hass.bus.listen(MATCH_ALL, event_listener)

        self.hass.bus.fire(event_type, event_data)

        wait_recording_done(self.hass)

        assert len(events) == 1
        event = events[0]

        self.hass.data[DATA_INSTANCE].block_till_done()

        with session_scope(hass=self.hass) as session:
            db_events = list(session.query(Events).filter_by(event_type=event_type))
            assert len(db_events) == 1
            db_event = db_events[0].to_native()

        assert event.event_type == db_event.event_type
        assert event.data == db_event.data
        assert event.origin == db_event.origin

        # Recorder uses SQLite and stores datetimes as integer unix timestamps
        assert event.time_fired.replace(microsecond=0) == db_event.time_fired.replace(
            microsecond=0
        )


@pytest.fixture
def hass_recorder():
    """Home Assistant fixture with in-memory recorder."""
    hass = get_test_home_assistant()

    def setup_recorder(config=None):
        """Set up with params."""
        init_recorder_component(hass, config)
        hass.start()
        hass.block_till_done()
        hass.data[DATA_INSTANCE].block_till_done()
        return hass

    yield setup_recorder
    hass.stop()


def _add_entities(hass, entity_ids):
    """Add entities."""
    attributes = {"test_attr": 5, "test_attr_10": "nice"}
    for idx, entity_id in enumerate(entity_ids):
        hass.states.set(entity_id, f"state{idx}", attributes)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        return [st.to_native() for st in session.query(States)]


def _add_events(hass, events):
    with session_scope(hass=hass) as session:
        session.query(Events).delete(synchronize_session=False)
    for event_type in events:
        hass.bus.fire(event_type)
    wait_recording_done(hass)

    with session_scope(hass=hass) as session:
        return [ev.to_native() for ev in session.query(Events)]


def _state_empty_context(hass, entity_id):
    # We don't restore context unless we need it by joining the
    # events table on the event_id for state_changed events
    state = hass.states.get(entity_id)
    state.context = Context(id=None)
    return state


# pylint: disable=redefined-outer-name,invalid-name
def test_saving_state_include_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"domains": "test2"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_empty_context(hass, "test2.recorder") == states[0]


def test_saving_state_include_domains_globs(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"include": {"domains": "test2", "entity_globs": "*.included_*"}}
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test3.included_entity"]
    )
    assert len(states) == 2
    assert _state_empty_context(hass, "test2.recorder") == states[0]
    assert _state_empty_context(hass, "test3.included_entity") == states[1]


def test_saving_state_incl_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"include": {"entities": "test2.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_empty_context(hass, "test2.recorder") == states[0]


def test_saving_event_exclude_event_type(hass_recorder):
    """Test saving and restoring an event."""
    hass = hass_recorder({"exclude": {"event_types": "test"}})
    events = _add_events(hass, ["test", "test2"])
    assert len(events) == 1
    assert events[0].event_type == "test2"


def test_saving_state_exclude_domains(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"domains": "test"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_empty_context(hass, "test2.recorder") == states[0]


def test_saving_state_exclude_domains_globs(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder(
        {"exclude": {"domains": "test", "entity_globs": "*.excluded_*"}}
    )
    states = _add_entities(
        hass, ["test.recorder", "test2.recorder", "test2.excluded_entity"]
    )
    assert len(states) == 1
    assert _state_empty_context(hass, "test2.recorder") == states[0]


def test_saving_state_exclude_entities(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder({"exclude": {"entities": "test.recorder"}})
    states = _add_entities(hass, ["test.recorder", "test2.recorder"])
    assert len(states) == 1
    assert _state_empty_context(hass, "test2.recorder") == states[0]


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
    assert _state_empty_context(hass, "test.ok") == states[0]
    assert _state_empty_context(hass, "test.ok").state == "state2"


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
    assert _state_empty_context(hass, "test.ok") == states[0]
    assert _state_empty_context(hass, "test.ok").state == "state2"


def test_saving_state_and_removing_entity(hass, hass_recorder):
    """Test saving the state of a removed entity."""
    hass = hass_recorder()
    entity_id = "lock.mine"
    hass.states.set(entity_id, STATE_LOCKED)
    hass.states.set(entity_id, STATE_UNLOCKED)
    hass.states.async_remove(entity_id)

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


def test_recorder_setup_failure():
    """Test some exceptions."""
    hass = get_test_home_assistant()

    with patch.object(Recorder, "_setup_connection") as setup, patch(
        "homeassistant.components.recorder.time.sleep"
    ):
        setup.side_effect = ImportError("driver not found")
        rec = Recorder(
            hass,
            auto_purge=True,
            keep_days=7,
            commit_interval=1,
            uri="sqlite://",
            db_max_retries=10,
            db_retry_wait=3,
            entity_filter=CONFIG_SCHEMA({DOMAIN: {}}),
            exclude_t=[],
        )
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
    assert recorder_config["purge_keep_days"] == 10


def test_auto_purge(hass_recorder):
    """Test saving and restoring a state."""
    hass = hass_recorder()

    original_tz = dt_util.DEFAULT_TIME_ZONE

    tz = dt_util.get_time_zone("Europe/Copenhagen")
    dt_util.set_default_time_zone(tz)

    now = dt_util.utcnow()
    test_time = tz.localize(datetime(now.year + 1, 1, 1, 4, 12, 0))
    async_fire_time_changed(hass, test_time)

    with patch(
        "homeassistant.components.recorder.purge.purge_old_data", return_value=True
    ) as purge_old_data:
        for delta in (-1, 0, 1):
            async_fire_time_changed(hass, test_time + timedelta(seconds=delta))
            hass.block_till_done()
            hass.data[DATA_INSTANCE].block_till_done()

        assert len(purge_old_data.mock_calls) == 1

    dt_util.set_default_time_zone(original_tz)


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


def test_run_information(hass_recorder):
    """Ensure run_information returns expected data."""
    before_start_recording = dt_util.utcnow()
    hass = hass_recorder()
    run_info = run_information_from_instance(hass)
    assert isinstance(run_info, RecorderRuns)
    assert run_info.closed_incorrect is False

    with session_scope(hass=hass) as session:
        run_info = run_information_with_session(session)
        assert isinstance(run_info, RecorderRuns)
        assert run_info.closed_incorrect is False

    run_info = run_information(hass)
    assert isinstance(run_info, RecorderRuns)
    assert run_info.closed_incorrect is False

    hass.states.set("test.two", "on", {})
    wait_recording_done(hass)
    run_info = run_information(hass)
    assert isinstance(run_info, RecorderRuns)
    assert run_info.closed_incorrect is False

    run_info = run_information(hass, before_start_recording)
    assert run_info is None

    run_info = run_information(hass, dt_util.utcnow())
    assert isinstance(run_info, RecorderRuns)
    assert run_info.closed_incorrect is False


class CannotSerializeMe:
    """A class that the JSONEncoder cannot serialize."""
