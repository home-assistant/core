"""Test data purging."""
import json
from datetime import datetime, timedelta
import unittest

from homeassistant.components import recorder
from homeassistant.components.recorder.const import DATA_INSTANCE
from homeassistant.components.recorder.purge import purge_old_data
from homeassistant.components.recorder.models import States, Events
from homeassistant.components.recorder.util import session_scope
from tests.common import get_test_home_assistant, init_recorder_component


class TestRecorderPurge(unittest.TestCase):
    """Base class for common recorder tests."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)
        self.hass.start()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def _add_test_states(self):
        """Add multiple states to the db for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        attributes = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

        with recorder.session_scope(hass=self.hass) as session:
            for event_id in range(5):
                if event_id < 3:
                    timestamp = five_days_ago
                    state = 'purgeme'
                else:
                    timestamp = now
                    state = 'dontpurgeme'

                session.add(States(
                    entity_id='test.recorder2',
                    domain='sensor',
                    state=state,
                    attributes=json.dumps(attributes),
                    last_changed=timestamp,
                    last_updated=timestamp,
                    created=timestamp,
                    event_id=event_id + 1000
                ))

    def _add_test_events(self):
        """Add a few events for testing."""
        now = datetime.now()
        five_days_ago = now - timedelta(days=5)
        event_data = {'test_attr': 5, 'test_attr_10': 'nice'}

        self.hass.block_till_done()
        self.hass.data[DATA_INSTANCE].block_till_done()

        with recorder.session_scope(hass=self.hass) as session:
            for event_id in range(5):
                if event_id < 2:
                    timestamp = five_days_ago
                    event_type = 'EVENT_TEST_PURGE'
                else:
                    timestamp = now
                    event_type = 'EVENT_TEST'

                session.add(Events(
                    event_type=event_type,
                    event_data=json.dumps(event_data),
                    origin='LOCAL',
                    created=timestamp,
                    time_fired=timestamp,
                ))

    def test_purge_old_states(self):
        """Test deleting old states."""
        self._add_test_states()
        # make sure we start with 5 states
        with session_scope(hass=self.hass) as session:
            states = session.query(States)
            self.assertEqual(states.count(), 5)

            # run purge_old_data()
            purge_old_data(self.hass.data[DATA_INSTANCE], 4)

            # we should only have 2 states left after purging
            self.assertEqual(states.count(), 2)

    def test_purge_old_events(self):
        """Test deleting old events."""
        self._add_test_events()

        with session_scope(hass=self.hass) as session:
            events = session.query(Events).filter(
                Events.event_type.like("EVENT_TEST%"))
            self.assertEqual(events.count(), 5)

            # run purge_old_data()
            purge_old_data(self.hass.data[DATA_INSTANCE], 4)

            # now we should only have 3 events left
            self.assertEqual(events.count(), 3)
