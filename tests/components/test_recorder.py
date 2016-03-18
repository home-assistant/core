"""The tests for the Recorder component."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import os

from homeassistant.const import MATCH_ALL
from homeassistant.components import recorder

from tests.common import get_test_home_assistant


class TestRecorder(unittest.TestCase):
    """Test the chromecast module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        recorder.setup(self.hass, {})
        self.hass.start()
        recorder._INSTANCE.block_till_done()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        recorder._INSTANCE.block_till_done()
        os.remove(self.hass.config.path(recorder.DB_FILE))

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

        self.assertEqual(events, db_events)
