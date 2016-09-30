"""The tests for the logbook component."""
# pylint: disable=protected-access,too-many-public-methods
from datetime import timedelta
import unittest
from unittest.mock import patch

from homeassistant.components import sun
import homeassistant.core as ha
from homeassistant.const import (
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    ATTR_HIDDEN, STATE_NOT_HOME, STATE_ON, STATE_OFF)
import homeassistant.util.dt as dt_util
from homeassistant.components import logbook
from homeassistant.bootstrap import setup_component

from tests.common import mock_http_component, get_test_home_assistant


class TestComponentLogbook(unittest.TestCase):
    """Test the History component."""

    EMPTY_CONFIG = logbook.CONFIG_SCHEMA({logbook.DOMAIN: {}})

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_http_component(self.hass)
        self.hass.config.components += ['frontend', 'recorder', 'api']
        with patch('homeassistant.components.logbook.'
                   'register_built_in_panel'):
            assert setup_component(self.hass, logbook.DOMAIN,
                                   self.EMPTY_CONFIG)

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

    def test_filter_continuous_sensor_values(self):
        """Test remove continuous sensor events from logbook."""
        entity_id = 'sensor.bla'
        pointA = dt_util.utcnow()
        attributes = {'unit_of_measurement': 'foo'}
        eventA = self.create_state_changed_event(
            pointA, entity_id, 10, attributes)

        entries = list(logbook.humanify((eventA,)))

        self.assertEqual(0, len(entries))

    def test_exclude_events_hidden(self):
        """Test if events are excluded if entity is hidden."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10,
                                                 {ATTR_HIDDEN: 'true'})
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        events = logbook._exclude_events((ha.Event(EVENT_HOMEASSISTANT_STOP),
                                          eventA, eventB), self.EMPTY_CONFIG)
        entries = list(logbook.humanify(events))

        self.assertEqual(2, len(entries))
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], pointB, 'blu', domain='sensor', entity_id=entity_id2)

    def test_exclude_events_entity(self):
        """Test if events are filtered if entity is excluded in config."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_EXCLUDE: {
                logbook.CONF_ENTITIES: [entity_id, ]}}})
        events = logbook._exclude_events((ha.Event(EVENT_HOMEASSISTANT_STOP),
                                          eventA, eventB), config)
        entries = list(logbook.humanify(events))

        self.assertEqual(2, len(entries))
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], pointB, 'blu', domain='sensor', entity_id=entity_id2)

    def test_exclude_events_domain(self):
        """Test if events are filtered if domain is excluded in config."""
        entity_id = 'switch.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_EXCLUDE: {
                logbook.CONF_DOMAINS: ['switch', ]}}})
        events = logbook._exclude_events((ha.Event(EVENT_HOMEASSISTANT_START),
                                          eventA, eventB), config)
        entries = list(logbook.humanify(events))

        self.assertEqual(2, len(entries))
        self.assert_entry(entries[0], name='Home Assistant', message='started',
                          domain=ha.DOMAIN)
        self.assert_entry(entries[1], pointB, 'blu', domain='sensor',
                          entity_id=entity_id2)

    def test_exclude_auto_groups(self):
        """Test if events of automatically generated groups are filtered."""
        entity_id = 'switch.bla'
        entity_id2 = 'group.switches'
        pointA = dt_util.utcnow()

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointA, entity_id2, 20,
                                                 {'auto': True})

        entries = list(logbook.humanify((eventA, eventB)))

        self.assertEqual(1, len(entries))
        self.assert_entry(entries[0], pointA, 'bla', domain='switch',
                          entity_id=entity_id)

    def test_exclude_attribute_changes(self):
        """Test if events of attribute changes are filtered."""
        entity_id = 'switch.bla'
        entity_id2 = 'switch.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=1)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(
            pointA, entity_id2, 20, last_changed=pointA, last_updated=pointB)

        entries = list(logbook.humanify((eventA, eventB)))

        self.assertEqual(1, len(entries))
        self.assert_entry(entries[0], pointA, 'bla', domain='switch',
                          entity_id=entity_id)

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

    def test_home_assistant_start(self):
        """Test if HA start is not filtered or converted into a restart."""
        entity_id = 'switch.bla'
        pointA = dt_util.utcnow()

        entries = list(logbook.humanify((
            ha.Event(EVENT_HOMEASSISTANT_START),
            self.create_state_changed_event(pointA, entity_id, 10)
            )))

        self.assertEqual(2, len(entries))
        self.assert_entry(
            entries[0], name='Home Assistant', message='started',
            domain=ha.DOMAIN)
        self.assert_entry(entries[1], pointA, 'bla', domain='switch',
                          entity_id=entity_id)

    def test_entry_message_from_state_device(self):
        """Test if logbook message is correctly created for switches.

        Especially test if the special handling for turn on/off events is done.
        """
        pointA = dt_util.utcnow()

        # message for a device state change
        eventA = self.create_state_changed_event(pointA, 'switch.bla', 10)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('changed to 10', message)

        # message for a switch turned on
        eventA = self.create_state_changed_event(pointA, 'switch.bla',
                                                 STATE_ON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('turned on', message)

        # message for a switch turned off
        eventA = self.create_state_changed_event(pointA, 'switch.bla',
                                                 STATE_OFF)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('turned off', message)

    def test_entry_message_from_state_device_tracker(self):
        """Test if logbook message is correctly created for device tracker."""
        pointA = dt_util.utcnow()

        # message for a device tracker "not home" state
        eventA = self.create_state_changed_event(pointA, 'device_tracker.john',
                                                 STATE_NOT_HOME)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('is away', message)

        # message for a device tracker "home" state
        eventA = self.create_state_changed_event(pointA, 'device_tracker.john',
                                                 'work')
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('is at work', message)

    def test_entry_message_from_state_sun(self):
        """Test if logbook message is correctly created for sun."""
        pointA = dt_util.utcnow()

        # message for a sun rise
        eventA = self.create_state_changed_event(pointA, 'sun.sun',
                                                 sun.STATE_ABOVE_HORIZON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('has risen', message)

        # message for a sun set
        eventA = self.create_state_changed_event(pointA, 'sun.sun',
                                                 sun.STATE_BELOW_HORIZON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        self.assertEqual('has set', message)

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

    def create_state_changed_event(self, event_time_fired, entity_id, state,
                                   attributes=None, last_changed=None,
                                   last_updated=None):
        """Create state changed event."""
        # Logbook only cares about state change events that
        # contain an old state but will not actually act on it.
        state = ha.State(entity_id, state, attributes, last_changed,
                         last_updated).as_dict()

        return ha.Event(EVENT_STATE_CHANGED, {
            'entity_id': entity_id,
            'old_state': state,
            'new_state': state,
        }, time_fired=event_time_fired)
