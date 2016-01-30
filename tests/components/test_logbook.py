"""
tests.test_component_logbook
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests the logbook component.
"""
# pylint: disable=protected-access,too-many-public-methods
import unittest
from datetime import timedelta
import homeassistant.core as ha

from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)
import homeassistant.util.dt as dt_util
from homeassistant.components import logbook

from tests.common import mock_http_component


class TestComponentHistory(unittest.TestCase):
    """ Tests homeassistant.components.history module. """

    def setUp(self):
        """ Test setup method. """
        self.hass = ha.HomeAssistant()
        mock_http_component(self.hass)
        logbook.setup(self.hass, {})

        self.calls = []

    def tearDown(self):
        self.hass.stop()

    def test_service_call_create_logbook_entry(self):
        calls = []

        def event_listener(event):
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
        self.hass.services.call('logbook', 'log', {
            logbook.ATTR_NAME: 'name',
            logbook.ATTR_MESSAGE: 'messsage',
            logbook.ATTR_DOMAIN: 'domain',
            logbook.ATTR_ENTITY_ID: 'entity_id',
        }, True)
        self.hass.pool.block_till_done()

        self.assertEqual(1, len(calls))
        last_call = calls[-1]

        self.assertEqual(last_call.data.get('name'), 'name')
        self.assertEqual(last_call.data.get('message'), 'message')
        self.assertEqual(last_call.data.get('domain'), 'domain')
        self.assertEqual(last_call.data.get('entity_id'), 'entity_id')

    def test_service_call_create_logbook_entry_missing_parameter(self):
        calls = []

        def event_listener(event):
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)

        self.hass.services.call('logbook', 'log', {
            logbook.ATTR_MESSAGE: 'test',
        })
        self.hass.pool.block_till_done()

        self.assertEqual(0, len(calls))

    def test_humanify_filter_sensor(self):
        """ Test humanify filter too frequent sensor values. """
        entity_id = 'sensor.bla'

        point_a = dt_util.strip_microseconds(
                dt_util.utcnow().replace(minute=2)
        )
        point_b = point_a.replace(minute=5)
        point_c = point_a + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        event_a = self.create_state_changed_event(point_a, entity_id, 10)
        event_b = self.create_state_changed_event(point_b, entity_id, 20)
        event_c = self.create_state_changed_event(point_c, entity_id, 30)

        entries = list(logbook.humanify((event_a, event_b, event_c)))

        self.assertEqual(2, len(entries))
        self.assert_entry(
            entries[0], point_b, 'bla', domain='sensor', entity_id=entity_id)

        self.assert_entry(
            entries[1], point_c, 'bla', domain='sensor', entity_id=entity_id)

    def test_home_assistant_start_stop_grouped(self):
        """ Tests if home assistant start and stop events are grouped if
            occuring in the same minute. """
        entries = list(logbook.humanify((
            ha.Event(EVENT_HOMEASSISTANT_STOP),
            ha.Event(EVENT_HOMEASSISTANT_START),
            )))

        self.assertEqual(1, len(entries))
        self.assert_entry(
            entries[0], name='Home Assistant', message='restarted',
            domain=ha.DOMAIN)

    def test_process_custom_logbook_entries(self):
        """ Tests if custom log book entries get added as an entry. """
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
        """ Asserts an entry is what is expected """
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
        """ Create state changed event. """

        # Logbook only cares about state change events that
        # contain an old state but will not actually act on it.
        state = ha.State(entity_id, state).as_dict()

        return ha.Event(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': state,
            'new_state': state,
        }, time_fired=event_time_fired)
