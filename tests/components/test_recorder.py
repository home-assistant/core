"""The tests for the Recorder component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import time
import json
from unittest.mock import patch

from homeassistant.const import MATCH_ALL
from homeassistant.components import recorder

from tests.common import get_test_home_assistant


class TestRecorder(unittest.TestCase):
    """Test the recorder module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        with patch('homeassistant.core.Config.path', return_value=':memory:'):
            recorder.setup(self.hass, {})
        self.hass.start()
        recorder._INSTANCE.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        recorder._INSTANCE.block_till_done()

    def _add_test_states(self):
        """Add multiple states to the db for testing."""
        now = int(time.time())
        five_days_ago = now - (60*60*24*5)
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.pool.block_till_done()
        recorder._INSTANCE.block_till_done()
        for event_id in range(5):
            if event_id < 3:
                timestamp = five_days_ago
                state = 'purgeme'
            else:
                timestamp = now
                state = 'dontpurgeme'
            recorder.query("INSERT INTO states ("
                           "entity_id, domain, state, attributes,"
                           "last_changed, last_updated, created,"
                           "utc_offset, event_id)"
                           "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                           ('test.recorder2', 'sensor', state,
                            json.dumps(attributes), timestamp, timestamp,
                            timestamp, -18000, event_id + 1000))

    def _add_test_events(self):
        """Add a few events for testing."""
        now = int(time.time())
        five_days_ago = now - (60*60*24*5)
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.pool.block_till_done()
        recorder._INSTANCE.block_till_done()
        for event_id in range(5):
            if event_id < 2:
                timestamp = five_days_ago
                event_type = 'EVENT_TEST_PURGE'
            else:
                timestamp = now
                event_type = 'EVENT_TEST'
            recorder.query("INSERT INTO events"
                           "(event_type, event_data, origin, created,"
                           "time_fired, utc_offset)"
                           "VALUES (?, ?, ?, ?, ?, ?)",
                           (event_type, json.dumps(event_data), 'LOCAL',
                            timestamp, timestamp, -18000))

    def test_saving_state(self):
        """Test saving and restoring a state."""
        entity_id = 'test.recorder'
        state = 'restoring_from_db'
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.states.set(entity_id, state, attributes)

        self.hass.pool.block_till_done()
        recorder._INSTANCE.block_till_done()

        states = recorder.query_states('SELECT * FROM states')

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

        self.hass.pool.block_till_done()
        recorder._INSTANCE.block_till_done()

        db_events = recorder.query_events(
            'SELECT * FROM events WHERE event_type = ?', (event_type, ))

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
        states = recorder.query_states('SELECT * FROM states')
        self.assertEqual(len(states), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # we should only have 2 states left after purging
        states = recorder.query_states('SELECT * FROM states')
        self.assertEqual(len(states), 2)

    def test_purge_old_events(self):
        """Test deleting old events."""
        self._add_test_events()
        events = recorder.query_events('SELECT * FROM events WHERE '
                                       'event_type LIKE "EVENT_TEST%"')
        self.assertEqual(len(events), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = 4
        recorder._INSTANCE._purge_old_data()

        # now we should only have 3 events left
        events = recorder.query_events('SELECT * FROM events WHERE '
                                       'event_type LIKE "EVENT_TEST%"')
        self.assertEqual(len(events), 3)

    def test_purge_disabled(self):
        """Test leaving purge_days disabled."""
        self._add_test_states()
        self._add_test_events()
        # make sure we start with 5 states and events
        states = recorder.query_states('SELECT * FROM states')
        events = recorder.query_events('SELECT * FROM events WHERE '
                                       'event_type LIKE "EVENT_TEST%"')
        self.assertEqual(len(states), 5)
        self.assertEqual(len(events), 5)

        # run purge_old_data()
        recorder._INSTANCE.purge_days = None
        recorder._INSTANCE._purge_old_data()

        # we should have all of our states still
        states = recorder.query_states('SELECT * FROM states')
        events = recorder.query_events('SELECT * FROM events WHERE '
                                       'event_type LIKE "EVENT_TEST%"')
        self.assertEqual(len(states), 5)
        self.assertEqual(len(events), 5)
