"""The tests for the Recorder component."""
# pylint: disable=protected-access
import json
from datetime import datetime, timedelta
import unittest

from homeassistant.const import MATCH_ALL
from homeassistant.components import recorder
from homeassistant.bootstrap import _setup_component
from tests.common import get_test_home_assistant


class TestRecorder(unittest.TestCase):
    """Test the recorder module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        db_uri = 'sqlite://'  # In memory DB
        _setup_component(self.hass, recorder.DOMAIN, {
            recorder.DOMAIN: {recorder.CONF_DB_URL: db_uri}})
        self.hass.start()
        recorder._verify_instance()
        self.session = recorder.Session()
        recorder._INSTANCE.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        recorder._INSTANCE.shutdown(None)
        self.hass.stop()
        assert recorder._INSTANCE is None

    def _add_test_states(self):
        """Add multiple states to the db for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        for event_id in range(5):
            if event_id < 3:
                timestamp = five_days_ago
                state = 'purgeme'
            else:
                timestamp = now
                state = 'dontpurgeme'

            self.session.add(recorder.get_model('States')(
                entity_id='test.recorder2',
                domain='sensor',
                state=state,
                attributes=json.dumps(attributes),
                last_changed=timestamp,
                last_updated=timestamp,
                created=timestamp,
                event_id=event_id + 1000
            ))

        self.session.commit()

    def _add_test_events(self):
        """Add a few events for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()
        for event_id in range(5):
            if event_id < 2:
                timestamp = five_days_ago
                event_type = 'EVENT_TEST_PURGE'
            else:
                timestamp = now
                event_type = 'EVENT_TEST'

            self.session.add(recorder.get_model('Events')(
                event_type=event_type,
                event_data=json.dumps(event_data),
                origin='LOCAL',
                created=timestamp,
                time_fired=timestamp,
            ))

    def test_saving_state(self):
        """Test saving and restoring a state."""
        entity_id = 'test.recorder'
        state = 'restoring_from_db'
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.states.set(entity_id, state, attributes)

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        db_states = recorder.query('States')
        states = recorder.execute(db_states)

        assert db_states[0].event_id is not None

        self.assertEqual(1, len(states))
        self.assertEqual(self.hass.states.get(entity_id), states[0])

    def test_saving_event(self):
        """Test saving and restoring an event."""
        event_type = 'EVENT_TEST'
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        events = []

        def event_listener(event):
            """Record events from eventbus."""
            if event.event_type == event_type:
                events.append(event)

        self.hass.bus.listen(MATCH_ALL, event_listener)

        self.hass.bus.fire(event_type, event_data)

        self.hass.block_till_done()
        recorder._INSTANCE.block_till_done()

        db_events = recorder.execute(
            recorder.query('Events').filter_by(
                event_type=event_type))

        assert len(events) == 1
        assert len(db_events) == 1

        event = events[0]
        db_event = db_events[0]

        assert event.event_type == db_event.event_type
        assert event.data == db_event.data
        assert event.origin == db_event.origin

        # Recorder uses SQLite and stores datetimes as integer unix timestamps
        assert event.time_fired.replace(microsecond=0) == \
            db_event.time_fired.replace(microsecond=0)

    def test_purge_old_states(self):
        """Test deleting old states."""
        self._add_test_states()
        # make sure we start with 5 states
        states = recorder.query('States')
        self.assertEqual(states.count(), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # we should only have 2 states left after purging
        self.assertEqual(states.count(), 2)

    def test_purge_old_events(self):
        """Test deleting old events."""
        self._add_test_events()
        events = recorder.query('Events').filter(
            recorder.get_model('Events').event_type.like("EVENT_TEST%"))
        self.assertEqual(events.count(), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # now we should only have 3 events left
        self.assertEqual(events.count(), 3)

    def test_purge_disabled(self):
        """Test leaving purge_days disabled."""
        self._add_test_states()
        self._add_test_events()
        # make sure we start with 5 states and events
        states = recorder.query('States')
        events = recorder.query('Events').filter(
            recorder.get_model('Events').event_type.like("EVENT_TEST%"))
        self.assertEqual(states.count(), 5)
        self.assertEqual(events.count(), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = None
        recorder._INSTANCE._purge_old_data()

        # we should have all of our states still
        self.assertEqual(states.count(), 5)
        self.assertEqual(events.count(), 5)
