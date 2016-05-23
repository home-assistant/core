"""The tests for the logbook component."""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from datetime import timedelta

import homeassistant.core as ha
from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.util.dt as dt_util
from homeassistant.components import logbook

from tests.common import mock_http_component, get_test_home_assistant


class TestComponentLogbook(unittest.TestCase):
    """Test the History component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_http_component(self.hass)
        self.assertTrue(logbook.setup(self.hass, {}))

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_service_call_create_logbook_entry(self):
        """Test if service call create log book entry."""
        calls = []

        def event_listener(event):
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
        self.hass.services.call(logbook.DOMAIN, 'log', {
            logbook.ATTR_NAME: 'Alarm',
            logbook.ATTR_MESSAGE: 'is triggered',
            logbook.ATTR_DOMAIN: 'switch',
            logbook.ATTR_ENTITY_ID: 'switch.test_switch'
        }, True)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        last_call = calls[-1]

        self.assertEqual('Alarm', last_call.data.get(logbook.ATTR_NAME))
        self.assertEqual('is triggered', last_call.data.get(
            logbook.ATTR_MESSAGE))
        self.assertEqual('switch', last_call.data.get(logbook.ATTR_DOMAIN))
        self.assertEqual('switch.test_switch', last_call.data.get(
            logbook.ATTR_ENTITY_ID))

    def test_service_call_create_log_book_entry_no_message(self):
        """Test if service call create log book entry without message."""
        calls = []

        def event_listener(event):
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
        self.hass.services.call(logbook.DOMAIN, 'log', {}, True)
        self.hass.pool.block_till_done()

        self.assertEqual(0, len(calls))

    def test_humanify_filter_sensor(self):
        """Test humanify filter too frequent sensor values."""
        entity_id = 'sensor.bla'

        pointA = dt_util.utcnow().replace(minute=2)
        pointB = pointA.replace(minute=5)
        pointC = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id, 20)
        eventC = self.create_state_changed_event(pointC, entity_id, 30)

        entries = list(logbook.humanify((eventA, eventB, eventC)))

        self.assertEqual(2, len(entries))
        self.assert_entry(
            entries[0], pointB, 'bla', domain='sensor', entity_id=entity_id)

        self.assert_entry(
            entries[1], pointC, 'bla', domain='sensor', entity_id=entity_id)

    def test_entry_to_dict(self):
        """Test conversion of entry to dict."""
        entry = logbook.Entry(
            dt_util.utcnow(), 'Alarm', 'is triggered', 'switch', 'test_switch'
        )
        data = entry.as_dict()
        self.assertEqual('Alarm', data.get(logbook.ATTR_NAME))
        self.assertEqual('is triggered', data.get(logbook.ATTR_MESSAGE))
        self.assertEqual('switch', data.get(logbook.ATTR_DOMAIN))
        self.assertEqual('test_switch', data.get(logbook.ATTR_ENTITY_ID))

    def test_home_assistant_start_stop_grouped(self):
        """Test if HA start and stop events are grouped.

        Events that are occuring in the same minute.
        """
        entries = list(logbook.humanify((
            ha.Event(EVENT_HOMEASSISTANT_STOP),
            ha.Event(EVENT_HOMEASSISTANT_START),
            )))

        self.assertEqual(1, len(entries))
        self.assert_entry(
            entries[0], name='Home Assistant', message='restarted',
            domain=ha.DOMAIN)

    def test_process_custom_logbook_entries(self):
        """Test if custom log book entries get added as an entry."""
        name = 'Nice name'
        message = 'has a custom entry'
        entity_id = 'sun.sun'

        entries = list(logbook.humanify((
            ha.Event(logbook.EVENT_LOGBOOK_ENTRY, {
                logbook.ATTR_NAME: name,
                logbook.ATTR_MESSAGE: message,
                logbook.ATTR_ENTITY_ID: entity_id,
                }),
            )))

        self.assertEqual(1, len(entries))
        self.assert_entry(
            entries[0], name=name, message=message,
            domain='sun', entity_id=entity_id)

    def assert_entry(self, entry, when=None, name=None, message=None,
                     domain=None, entity_id=None):
        """Assert an entry is what is expected."""
        if when:
            self.assertEqual(when, entry.when)

        if name:
            self.assertEqual(name, entry.name)

        if message:
            self.assertEqual(message, entry.message)

        if domain:
            self.assertEqual(domain, entry.domain)

        if entity_id:
            self.assertEqual(entity_id, entry.entity_id)

    def create_state_changed_event(self, event_time_fired, entity_id, state):
        """Create state changed event."""
        # Logbook only cares about state change events that
        # contain an old state but will not actually act on it.
        state = ha.State(entity_id, state).as_dict()

        return ha.Event(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': state,
            'new_state': state,
        }, time_fired=event_time_fired)
