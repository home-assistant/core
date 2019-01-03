"""The tests for the logbook component."""
# pylint: disable=protected-access,invalid-name
import logging
from datetime import (timedelta, datetime)
import unittest

import pytest
import voluptuous as vol

from homeassistant.components import sun
import homeassistant.core as ha
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_SERVICE, ATTR_NAME,
    EVENT_STATE_CHANGED, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP,
    EVENT_AUTOMATION_TRIGGERED, EVENT_SCRIPT_STARTED, ATTR_HIDDEN,
    STATE_NOT_HOME, STATE_ON, STATE_OFF)
import homeassistant.util.dt as dt_util
from homeassistant.components import logbook, recorder
from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
from homeassistant.components.homekit.const import (
    ATTR_DISPLAY_NAME, ATTR_VALUE, DOMAIN as DOMAIN_HOMEKIT,
    EVENT_HOMEKIT_CHANGED)
from homeassistant.setup import setup_component, async_setup_component

from tests.common import (
    init_recorder_component, get_test_home_assistant)


_LOGGER = logging.getLogger(__name__)


class TestComponentLogbook(unittest.TestCase):
    """Test the History component."""

    EMPTY_CONFIG = logbook.CONFIG_SCHEMA({logbook.DOMAIN: {}})

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)  # Force an in memory DB
        assert setup_component(self.hass, logbook.DOMAIN, self.EMPTY_CONFIG)
        self.hass.start()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_service_call_create_logbook_entry(self):
        """Test if service call create log book entry."""
        calls = []

        @ha.callback
        def event_listener(event):
            """Append on event."""
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
        self.hass.services.call(logbook.DOMAIN, 'log', {
            logbook.ATTR_NAME: 'Alarm',
            logbook.ATTR_MESSAGE: 'is triggered',
            logbook.ATTR_DOMAIN: 'switch',
            logbook.ATTR_ENTITY_ID: 'switch.test_switch'
        }, True)

        # Logbook entry service call results in firing an event.
        # Our service call will unblock when the event listeners have been
        # scheduled. This means that they may not have been processed yet.
        self.hass.block_till_done()
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()

        events = list(logbook._get_events(
            self.hass, {}, dt_util.utcnow() - timedelta(hours=1),
            dt_util.utcnow() + timedelta(hours=1)))
        assert len(events) == 2

        assert 1 == len(calls)
        last_call = calls[-1]

        assert 'Alarm' == last_call.data.get(logbook.ATTR_NAME)
        assert 'is triggered' == last_call.data.get(
            logbook.ATTR_MESSAGE)
        assert 'switch' == last_call.data.get(logbook.ATTR_DOMAIN)
        assert 'switch.test_switch' == last_call.data.get(
            logbook.ATTR_ENTITY_ID)

    def test_service_call_create_log_book_entry_no_message(self):
        """Test if service call create log book entry without message."""
        calls = []

        @ha.callback
        def event_listener(event):
            """Append on event."""
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)

        with pytest.raises(vol.Invalid):
            self.hass.services.call(logbook.DOMAIN, 'log', {}, True)

        # Logbook entry service call results in firing an event.
        # Our service call will unblock when the event listeners have been
        # scheduled. This means that they may not have been processed yet.
        self.hass.block_till_done()

        assert 0 == len(calls)

    def test_humanify_filter_sensor(self):
        """Test humanify filter too frequent sensor values."""
        entity_id = 'sensor.bla'

        pointA = dt_util.utcnow().replace(minute=2)
        pointB = pointA.replace(minute=5)
        pointC = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id, 20)
        eventC = self.create_state_changed_event(pointC, entity_id, 30)

        entries = list(logbook.humanify(self.hass, (eventA, eventB, eventC)))

        assert 2 == len(entries)
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

        entries = list(logbook.humanify(self.hass, (eventA,)))

        assert 0 == len(entries)

    def test_exclude_new_entities(self):
        """Test if events are excluded on first update."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)
        eventA.data['old_state'] = None

        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP),
             eventA, eventB),
            logbook._generate_filter_from_config({}))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], pointB, 'blu', domain='sensor', entity_id=entity_id2)

    def test_exclude_removed_entities(self):
        """Test if events are excluded on last update."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)
        eventA.data['new_state'] = None

        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP),
             eventA, eventB),
            logbook._generate_filter_from_config({}))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], pointB, 'blu', domain='sensor', entity_id=entity_id2)

    def test_exclude_events_hidden(self):
        """Test if events are excluded if entity is hidden."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10,
                                                 {ATTR_HIDDEN: 'true'})
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP),
             eventA, eventB),
            logbook._generate_filter_from_config({}))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
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
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
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
                logbook.CONF_DOMAINS: ['switch', 'alexa', DOMAIN_HOMEKIT]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_START),
             ha.Event(EVENT_ALEXA_SMART_HOME),
             ha.Event(EVENT_HOMEKIT_CHANGED), eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(entries[0], name='Home Assistant', message='started',
                          domain=ha.DOMAIN)
        self.assert_entry(entries[1], pointB, 'blu', domain='sensor',
                          entity_id=entity_id2)

    def test_exclude_automation_events(self):
        """Test if automation entries can be excluded by entity_id."""
        name = 'My Automation Rule'
        domain = 'automation'
        entity_id = 'automation.my_automation_rule'
        entity_id2 = 'automation.my_automation_rule_2'
        entity_id2 = 'sensor.blu'

        eventA = ha.Event(logbook.EVENT_AUTOMATION_TRIGGERED, {
            logbook.ATTR_NAME: name,
            logbook.ATTR_ENTITY_ID: entity_id,
        })
        eventB = ha.Event(logbook.EVENT_AUTOMATION_TRIGGERED, {
            logbook.ATTR_NAME: name,
            logbook.ATTR_ENTITY_ID: entity_id2,
        })

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_EXCLUDE: {
                logbook.CONF_ENTITIES: [entity_id, ]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], name=name, domain=domain, entity_id=entity_id2)

    def test_exclude_script_events(self):
        """Test if script start can be excluded by entity_id."""
        name = 'My Script Rule'
        domain = 'script'
        entity_id = 'script.my_script'
        entity_id2 = 'script.my_script_2'
        entity_id2 = 'sensor.blu'

        eventA = ha.Event(logbook.EVENT_SCRIPT_STARTED, {
            logbook.ATTR_NAME: name,
            logbook.ATTR_ENTITY_ID: entity_id,
        })
        eventB = ha.Event(logbook.EVENT_SCRIPT_STARTED, {
            logbook.ATTR_NAME: name,
            logbook.ATTR_ENTITY_ID: entity_id2,
        })

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_EXCLUDE: {
                logbook.CONF_ENTITIES: [entity_id, ]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], name=name, domain=domain, entity_id=entity_id2)

    def test_include_events_entity(self):
        """Test if events are filtered if entity is included in config."""
        entity_id = 'sensor.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_INCLUDE: {
                logbook.CONF_ENTITIES: [entity_id2, ]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 2 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='stopped',
            domain=ha.DOMAIN)
        self.assert_entry(
            entries[1], pointB, 'blu', domain='sensor', entity_id=entity_id2)

    def test_include_events_domain(self):
        """Test if events are filtered if domain is included in config."""
        entity_id = 'switch.bla'
        entity_id2 = 'sensor.blu'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        event_alexa = ha.Event(EVENT_ALEXA_SMART_HOME, {'request': {
            'namespace': 'Alexa.Discovery',
            'name': 'Discover',
        }})
        event_homekit = ha.Event(EVENT_HOMEKIT_CHANGED, {
            ATTR_ENTITY_ID: 'lock.front_door',
            ATTR_DISPLAY_NAME: 'Front Door',
            ATTR_SERVICE: 'lock',
        })

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {logbook.CONF_INCLUDE: {
                logbook.CONF_DOMAINS: ['sensor', 'alexa', DOMAIN_HOMEKIT]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_START),
             event_alexa, event_homekit, eventA, eventB),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 4 == len(entries)
        self.assert_entry(entries[0], name='Home Assistant', message='started',
                          domain=ha.DOMAIN)
        self.assert_entry(entries[1], name='Amazon Alexa', domain='alexa')
        self.assert_entry(entries[2], name='HomeKit', domain=DOMAIN_HOMEKIT)
        self.assert_entry(entries[3], pointB, 'blu', domain='sensor',
                          entity_id=entity_id2)

    def test_include_exclude_events(self):
        """Test if events are filtered if include and exclude is configured."""
        entity_id = 'switch.bla'
        entity_id2 = 'sensor.blu'
        entity_id3 = 'sensor.bli'
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA1 = self.create_state_changed_event(pointA, entity_id, 10)
        eventA2 = self.create_state_changed_event(pointA, entity_id2, 10)
        eventA3 = self.create_state_changed_event(pointA, entity_id3, 10)
        eventB1 = self.create_state_changed_event(pointB, entity_id, 20)
        eventB2 = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA({
            ha.DOMAIN: {},
            logbook.DOMAIN: {
                logbook.CONF_INCLUDE: {
                    logbook.CONF_DOMAINS: ['sensor', ],
                    logbook.CONF_ENTITIES: ['switch.bla', ]},
                logbook.CONF_EXCLUDE: {
                    logbook.CONF_DOMAINS: ['switch', ],
                    logbook.CONF_ENTITIES: ['sensor.bli', ]}}})
        events = logbook._exclude_events(
            (ha.Event(EVENT_HOMEASSISTANT_START), eventA1, eventA2, eventA3,
             eventB1, eventB2),
            logbook._generate_filter_from_config(config[logbook.DOMAIN]))
        entries = list(logbook.humanify(self.hass, events))

        assert 5 == len(entries)
        self.assert_entry(entries[0], name='Home Assistant', message='started',
                          domain=ha.DOMAIN)
        self.assert_entry(entries[1], pointA, 'bla', domain='switch',
                          entity_id=entity_id)
        self.assert_entry(entries[2], pointA, 'blu', domain='sensor',
                          entity_id=entity_id2)
        self.assert_entry(entries[3], pointB, 'bla', domain='switch',
                          entity_id=entity_id)
        self.assert_entry(entries[4], pointB, 'blu', domain='sensor',
                          entity_id=entity_id2)

    def test_exclude_auto_groups(self):
        """Test if events of automatically generated groups are filtered."""
        entity_id = 'switch.bla'
        entity_id2 = 'group.switches'
        pointA = dt_util.utcnow()

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointA, entity_id2, 20,
                                                 {'auto': True})

        events = logbook._exclude_events(
            (eventA, eventB),
            logbook._generate_filter_from_config({}))
        entries = list(logbook.humanify(self.hass, events))

        assert 1 == len(entries)
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

        events = logbook._exclude_events(
            (eventA, eventB),
            logbook._generate_filter_from_config({}))
        entries = list(logbook.humanify(self.hass, events))

        assert 1 == len(entries)
        self.assert_entry(entries[0], pointA, 'bla', domain='switch',
                          entity_id=entity_id)

    def test_home_assistant_start_stop_grouped(self):
        """Test if HA start and stop events are grouped.

        Events that are occurring in the same minute.
        """
        entries = list(logbook.humanify(self.hass, (
            ha.Event(EVENT_HOMEASSISTANT_STOP),
            ha.Event(EVENT_HOMEASSISTANT_START),
            )))

        assert 1 == len(entries)
        self.assert_entry(
            entries[0], name='Home Assistant', message='restarted',
            domain=ha.DOMAIN)

    def test_home_assistant_start(self):
        """Test if HA start is not filtered or converted into a restart."""
        entity_id = 'switch.bla'
        pointA = dt_util.utcnow()

        entries = list(logbook.humanify(self.hass, (
            ha.Event(EVENT_HOMEASSISTANT_START),
            self.create_state_changed_event(pointA, entity_id, 10)
            )))

        assert 2 == len(entries)
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
        assert 'changed to 10' == message

        # message for a switch turned on
        eventA = self.create_state_changed_event(pointA, 'switch.bla',
                                                 STATE_ON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'turned on' == message

        # message for a switch turned off
        eventA = self.create_state_changed_event(pointA, 'switch.bla',
                                                 STATE_OFF)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'turned off' == message

    def test_entry_message_from_state_device_tracker(self):
        """Test if logbook message is correctly created for device tracker."""
        pointA = dt_util.utcnow()

        # message for a device tracker "not home" state
        eventA = self.create_state_changed_event(pointA, 'device_tracker.john',
                                                 STATE_NOT_HOME)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'is away' == message

        # message for a device tracker "home" state
        eventA = self.create_state_changed_event(pointA, 'device_tracker.john',
                                                 'work')
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'is at work' == message

    def test_entry_message_from_state_sun(self):
        """Test if logbook message is correctly created for sun."""
        pointA = dt_util.utcnow()

        # message for a sun rise
        eventA = self.create_state_changed_event(pointA, 'sun.sun',
                                                 sun.STATE_ABOVE_HORIZON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'has risen' == message

        # message for a sun set
        eventA = self.create_state_changed_event(pointA, 'sun.sun',
                                                 sun.STATE_BELOW_HORIZON)
        to_state = ha.State.from_dict(eventA.data.get('new_state'))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert 'has set' == message

    def test_process_custom_logbook_entries(self):
        """Test if custom log book entries get added as an entry."""
        name = 'Nice name'
        message = 'has a custom entry'
        entity_id = 'sun.sun'

        entries = list(logbook.humanify(self.hass, (
            ha.Event(logbook.EVENT_LOGBOOK_ENTRY, {
                logbook.ATTR_NAME: name,
                logbook.ATTR_MESSAGE: message,
                logbook.ATTR_ENTITY_ID: entity_id,
                }),
            )))

        assert 1 == len(entries)
        self.assert_entry(
            entries[0], name=name, message=message,
            domain='sun', entity_id=entity_id)

    def assert_entry(self, entry, when=None, name=None, message=None,
                     domain=None, entity_id=None):
        """Assert an entry is what is expected."""
        if when:
            assert when == entry['when']

        if name:
            assert name == entry['name']

        if message:
            assert message == entry['message']

        if domain:
            assert domain == entry['domain']

        if entity_id:
            assert entity_id == entry['entity_id']

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


async def test_logbook_view(hass, hass_client):
    """Test the logbook view."""
    await hass.async_add_job(init_recorder_component, hass)
    await async_setup_component(hass, 'logbook', {})
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    client = await hass_client()
    response = await client.get(
        '/api/logbook/{}'.format(dt_util.utcnow().isoformat()))
    assert response.status == 200


async def test_logbook_view_period_entity(hass, hass_client):
    """Test the logbook view with period and entity."""
    await hass.async_add_job(init_recorder_component, hass)
    await async_setup_component(hass, 'logbook', {})
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = 'switch.test'
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = 'switch.second'
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await hass.async_block_till_done()
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(
        '/api/logbook/{}'.format(start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 2
    assert json[0]['entity_id'] == entity_id_test
    assert json[1]['entity_id'] == entity_id_second

    # Test today entries with filter by period
    response = await client.get(
        '/api/logbook/{}?period=1'.format(start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 2
    assert json[0]['entity_id'] == entity_id_test
    assert json[1]['entity_id'] == entity_id_second

    # Test today entries with filter by entity_id
    response = await client.get(
        '/api/logbook/{}?entity=switch.test'.format(
            start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]['entity_id'] == entity_id_test

    # Test entries for 3 days with filter by entity_id
    response = await client.get(
        '/api/logbook/{}?period=3&entity=switch.test'.format(
            start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]['entity_id'] == entity_id_test

    # Tomorrow time 00:00:00
    start = (dt_util.utcnow() + timedelta(days=1)).date()
    start_date = datetime(start.year, start.month, start.day)

    # Test tomorrow entries without filters
    response = await client.get(
        '/api/logbook/{}'.format(start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 0

    # Test tomorrow entries with filter by entity_id
    response = await client.get(
        '/api/logbook/{}?entity=switch.test'.format(
            start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 0

    # Test entries from tomorrow to 3 days ago with filter by entity_id
    response = await client.get(
        '/api/logbook/{}?period=3&entity=switch.test'.format(
            start_date.isoformat()))
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]['entity_id'] == entity_id_test


async def test_humanify_alexa_event(hass):
    """Test humanifying Alexa event."""
    hass.states.async_set('light.kitchen', 'on', {
        'friendly_name': 'Kitchen Light'
    })

    results = list(logbook.humanify(hass, [
        ha.Event(EVENT_ALEXA_SMART_HOME, {'request': {
            'namespace': 'Alexa.Discovery',
            'name': 'Discover',
        }}),
        ha.Event(EVENT_ALEXA_SMART_HOME, {'request': {
            'namespace': 'Alexa.PowerController',
            'name': 'TurnOn',
            'entity_id': 'light.kitchen'
        }}),
        ha.Event(EVENT_ALEXA_SMART_HOME, {'request': {
            'namespace': 'Alexa.PowerController',
            'name': 'TurnOn',
            'entity_id': 'light.non_existing'
        }}),

    ]))

    event1, event2, event3 = results

    assert event1['name'] == 'Amazon Alexa'
    assert event1['message'] == 'send command Alexa.Discovery/Discover'
    assert event1['entity_id'] is None

    assert event2['name'] == 'Amazon Alexa'
    assert event2['message'] == \
        'send command Alexa.PowerController/TurnOn for Kitchen Light'
    assert event2['entity_id'] == 'light.kitchen'

    assert event3['name'] == 'Amazon Alexa'
    assert event3['message'] == \
        'send command Alexa.PowerController/TurnOn for light.non_existing'
    assert event3['entity_id'] == 'light.non_existing'


async def test_humanify_homekit_changed_event(hass):
    """Test humanifying HomeKit changed event."""
    event1, event2 = list(logbook.humanify(hass, [
        ha.Event(EVENT_HOMEKIT_CHANGED, {
            ATTR_ENTITY_ID: 'lock.front_door',
            ATTR_DISPLAY_NAME: 'Front Door',
            ATTR_SERVICE: 'lock',
        }),
        ha.Event(EVENT_HOMEKIT_CHANGED, {
            ATTR_ENTITY_ID: 'cover.window',
            ATTR_DISPLAY_NAME: 'Window',
            ATTR_SERVICE: 'set_cover_position',
            ATTR_VALUE: 75,
        }),
    ]))

    assert event1['name'] == 'HomeKit'
    assert event1['domain'] == DOMAIN_HOMEKIT
    assert event1['message'] == 'send command lock for Front Door'
    assert event1['entity_id'] == 'lock.front_door'

    assert event2['name'] == 'HomeKit'
    assert event2['domain'] == DOMAIN_HOMEKIT
    assert event2['message'] == \
        'send command set_cover_position to 75 for Window'
    assert event2['entity_id'] == 'cover.window'


async def test_humanify_automation_triggered_event(hass):
    """Test humanifying Automation Trigger event."""
    event1, event2 = list(logbook.humanify(hass, [
        ha.Event(EVENT_AUTOMATION_TRIGGERED, {
            ATTR_ENTITY_ID: 'automation.hello',
            ATTR_NAME: 'Hello Automation',
        }),
        ha.Event(EVENT_AUTOMATION_TRIGGERED, {
            ATTR_ENTITY_ID: 'automation.bye',
            ATTR_NAME: 'Bye Automation',
        }),
    ]))

    assert event1['name'] == 'Hello Automation'
    assert event1['domain'] == 'automation'
    assert event1['message'] == 'has been triggered'
    assert event1['entity_id'] == 'automation.hello'

    assert event2['name'] == 'Bye Automation'
    assert event2['domain'] == 'automation'
    assert event2['message'] == 'has been triggered'
    assert event2['entity_id'] == 'automation.bye'


async def test_humanify_script_started_event(hass):
    """Test humanifying Script Run event."""
    event1, event2 = list(logbook.humanify(hass, [
        ha.Event(EVENT_SCRIPT_STARTED, {
            ATTR_ENTITY_ID: 'script.hello',
            ATTR_NAME: 'Hello Script'
        }),
        ha.Event(EVENT_SCRIPT_STARTED, {
            ATTR_ENTITY_ID: 'script.bye',
            ATTR_NAME: 'Bye Script'
        }),
    ]))

    assert event1['name'] == 'Hello Script'
    assert event1['domain'] == 'script'
    assert event1['message'] == 'started'
    assert event1['entity_id'] == 'script.hello'

    assert event2['name'] == 'Bye Script'
    assert event2['domain'] == 'script'
    assert event2['message'] == 'started'
    assert event2['entity_id'] == 'script.bye'
