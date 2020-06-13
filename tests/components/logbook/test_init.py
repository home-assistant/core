"""The tests for the logbook component."""
# pylint: disable=protected-access,invalid-name
from datetime import datetime, timedelta
from functools import partial
import logging
import unittest

import pytest
import voluptuous as vol

from homeassistant.components import logbook, recorder, sun
from homeassistant.components.alexa.smart_home import EVENT_ALEXA_SMART_HOME
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_HIDDEN,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
    EVENT_STATE_CHANGED,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component, setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import patch
from tests.common import get_test_home_assistant, init_recorder_component
from tests.components.recorder.common import trigger_db_commit

_LOGGER = logging.getLogger(__name__)


class TestComponentLogbook(unittest.TestCase):
    """Test the History component."""

    EMPTY_CONFIG = logbook.CONFIG_SCHEMA({logbook.DOMAIN: {}})

    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        init_recorder_component(self.hass)  # Force an in memory DB
        with patch("homeassistant.components.http.start_http_server_and_save_config"):
            assert setup_component(self.hass, logbook.DOMAIN, self.EMPTY_CONFIG)
        self.addCleanup(self.hass.stop)

    def test_service_call_create_logbook_entry(self):
        """Test if service call create log book entry."""
        calls = []

        @ha.callback
        def event_listener(event):
            """Append on event."""
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)
        self.hass.services.call(
            logbook.DOMAIN,
            "log",
            {
                logbook.ATTR_NAME: "Alarm",
                logbook.ATTR_MESSAGE: "is triggered",
                logbook.ATTR_DOMAIN: "switch",
                logbook.ATTR_ENTITY_ID: "switch.test_switch",
            },
            True,
        )

        # Logbook entry service call results in firing an event.
        # Our service call will unblock when the event listeners have been
        # scheduled. This means that they may not have been processed yet.
        self.hass.block_till_done()
        self.hass.data[recorder.DATA_INSTANCE].block_till_done()

        events = list(
            logbook._get_events(
                self.hass,
                {},
                dt_util.utcnow() - timedelta(hours=1),
                dt_util.utcnow() + timedelta(hours=1),
            )
        )
        assert len(events) == 1

        assert len(calls) == 1
        last_call = calls[-1]

        assert last_call.data.get(logbook.ATTR_NAME) == "Alarm"
        assert last_call.data.get(logbook.ATTR_MESSAGE) == "is triggered"
        assert last_call.data.get(logbook.ATTR_DOMAIN) == "switch"
        assert last_call.data.get(logbook.ATTR_ENTITY_ID) == "switch.test_switch"

    def test_service_call_create_log_book_entry_no_message(self):
        """Test if service call create log book entry without message."""
        calls = []

        @ha.callback
        def event_listener(event):
            """Append on event."""
            calls.append(event)

        self.hass.bus.listen(logbook.EVENT_LOGBOOK_ENTRY, event_listener)

        with pytest.raises(vol.Invalid):
            self.hass.services.call(logbook.DOMAIN, "log", {}, True)

        # Logbook entry service call results in firing an event.
        # Our service call will unblock when the event listeners have been
        # scheduled. This means that they may not have been processed yet.
        self.hass.block_till_done()

        assert len(calls) == 0

    def test_humanify_filter_sensor(self):
        """Test humanify filter too frequent sensor values."""
        entity_id = "sensor.bla"

        pointA = dt_util.utcnow().replace(minute=2)
        pointB = pointA.replace(minute=5)
        pointC = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id, 20)
        eventC = self.create_state_changed_event(pointC, entity_id, 30)

        entries = list(logbook.humanify(self.hass, (eventA, eventB, eventC)))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], pointB, "bla", domain="sensor", entity_id=entity_id
        )

        self.assert_entry(
            entries[1], pointC, "bla", domain="sensor", entity_id=entity_id
        )

    def test_filter_continuous_sensor_values(self):
        """Test remove continuous sensor events from logbook."""
        entity_id = "sensor.bla"
        pointA = dt_util.utcnow()
        attributes = {"unit_of_measurement": "foo"}
        eventA = self.create_state_changed_event(pointA, entity_id, 10, attributes)

        entries = list(logbook.humanify(self.hass, (eventA,)))

        assert len(entries) == 0

    def test_exclude_new_entities(self):
        """Test if events are excluded on first update."""
        entity_id = "sensor.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)
        eventA.data["old_state"] = None

        entities_filter = logbook._generate_filter_from_config({})
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_exclude_removed_entities(self):
        """Test if events are excluded on last update."""
        entity_id = "sensor.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)
        eventA.data["new_state"] = None

        entities_filter = logbook._generate_filter_from_config({})
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_exclude_events_hidden(self):
        """Test if events are excluded if entity is hidden."""
        entity_id = "sensor.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(
            pointA, entity_id, 10, {ATTR_HIDDEN: "true"}
        )
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        entities_filter = logbook._generate_filter_from_config({})
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_exclude_events_entity(self):
        """Test if events are filtered if entity is excluded in config."""
        entity_id = "sensor.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA(
            {
                ha.DOMAIN: {},
                logbook.DOMAIN: {
                    logbook.CONF_EXCLUDE: {logbook.CONF_ENTITIES: [entity_id]}
                },
            }
        )
        entities_filter = logbook._generate_filter_from_config(config[logbook.DOMAIN])
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_exclude_events_domain(self):
        """Test if events are filtered if domain is excluded in config."""
        entity_id = "switch.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA(
            {
                ha.DOMAIN: {},
                logbook.DOMAIN: {
                    logbook.CONF_EXCLUDE: {logbook.CONF_DOMAINS: ["switch", "alexa"]}
                },
            }
        )
        entities_filter = logbook._generate_filter_from_config(config[logbook.DOMAIN])
        events = [
            e
            for e in (
                ha.Event(EVENT_HOMEASSISTANT_START),
                ha.Event(EVENT_ALEXA_SMART_HOME),
                eventA,
                eventB,
            )
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_include_events_entity(self):
        """Test if events are filtered if entity is included in config."""
        entity_id = "sensor.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA(
            {
                ha.DOMAIN: {},
                logbook.DOMAIN: {
                    logbook.CONF_INCLUDE: {logbook.CONF_ENTITIES: [entity_id2]}
                },
            }
        )
        entities_filter = logbook._generate_filter_from_config(config[logbook.DOMAIN])
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_STOP), eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="stopped", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_include_events_domain(self):
        """Test if events are filtered if domain is included in config."""
        assert setup_component(self.hass, "alexa", {})
        entity_id = "switch.bla"
        entity_id2 = "sensor.blu"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        event_alexa = ha.Event(
            EVENT_ALEXA_SMART_HOME,
            {"request": {"namespace": "Alexa.Discovery", "name": "Discover"}},
        )

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA(
            {
                ha.DOMAIN: {},
                logbook.DOMAIN: {
                    logbook.CONF_INCLUDE: {logbook.CONF_DOMAINS: ["sensor", "alexa"]}
                },
            }
        )
        entities_filter = logbook._generate_filter_from_config(config[logbook.DOMAIN])
        events = [
            e
            for e in (ha.Event(EVENT_HOMEASSISTANT_START), event_alexa, eventA, eventB,)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 3
        self.assert_entry(
            entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
        )
        self.assert_entry(entries[1], name="Amazon Alexa", domain="alexa")
        self.assert_entry(
            entries[2], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_include_exclude_events(self):
        """Test if events are filtered if include and exclude is configured."""
        entity_id = "switch.bla"
        entity_id2 = "sensor.blu"
        entity_id3 = "sensor.bli"
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=logbook.GROUP_BY_MINUTES)

        eventA1 = self.create_state_changed_event(pointA, entity_id, 10)
        eventA2 = self.create_state_changed_event(pointA, entity_id2, 10)
        eventA3 = self.create_state_changed_event(pointA, entity_id3, 10)
        eventB1 = self.create_state_changed_event(pointB, entity_id, 20)
        eventB2 = self.create_state_changed_event(pointB, entity_id2, 20)

        config = logbook.CONFIG_SCHEMA(
            {
                ha.DOMAIN: {},
                logbook.DOMAIN: {
                    logbook.CONF_INCLUDE: {
                        logbook.CONF_DOMAINS: ["sensor"],
                        logbook.CONF_ENTITIES: ["switch.bla"],
                    },
                    logbook.CONF_EXCLUDE: {
                        logbook.CONF_DOMAINS: ["switch"],
                        logbook.CONF_ENTITIES: ["sensor.bli"],
                    },
                },
            }
        )
        entities_filter = logbook._generate_filter_from_config(config[logbook.DOMAIN])
        events = [
            e
            for e in (
                ha.Event(EVENT_HOMEASSISTANT_START),
                eventA1,
                eventA2,
                eventA3,
                eventB1,
                eventB2,
            )
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 5
        self.assert_entry(
            entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointA, "bla", domain="switch", entity_id=entity_id
        )
        self.assert_entry(
            entries[2], pointA, "blu", domain="sensor", entity_id=entity_id2
        )
        self.assert_entry(
            entries[3], pointB, "bla", domain="switch", entity_id=entity_id
        )
        self.assert_entry(
            entries[4], pointB, "blu", domain="sensor", entity_id=entity_id2
        )

    def test_exclude_auto_groups(self):
        """Test if events of automatically generated groups are filtered."""
        entity_id = "switch.bla"
        entity_id2 = "group.switches"
        pointA = dt_util.utcnow()

        eventA = self.create_state_changed_event(pointA, entity_id, 10)
        eventB = self.create_state_changed_event(pointA, entity_id2, 20, {"auto": True})

        entities_filter = logbook._generate_filter_from_config({})
        events = [
            e
            for e in (eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 1
        self.assert_entry(
            entries[0], pointA, "bla", domain="switch", entity_id=entity_id
        )

    def test_exclude_attribute_changes(self):
        """Test if events of attribute changes are filtered."""
        pointA = dt_util.utcnow()
        pointB = pointA + timedelta(minutes=1)
        pointC = pointB + timedelta(minutes=1)

        state_off = ha.State("light.kitchen", "off", {}, pointA, pointA).as_dict()
        state_100 = ha.State(
            "light.kitchen", "on", {"brightness": 100}, pointB, pointB
        ).as_dict()
        state_200 = ha.State(
            "light.kitchen", "on", {"brightness": 200}, pointB, pointC
        ).as_dict()

        eventA = ha.Event(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "light.kitchen",
                "old_state": state_off,
                "new_state": state_100,
            },
            time_fired=pointB,
        )
        eventB = ha.Event(
            EVENT_STATE_CHANGED,
            {
                "entity_id": "light.kitchen",
                "old_state": state_100,
                "new_state": state_200,
            },
            time_fired=pointC,
        )

        entities_filter = logbook._generate_filter_from_config({})
        events = [
            e
            for e in (eventA, eventB)
            if logbook._keep_event(self.hass, e, entities_filter)
        ]
        entries = list(logbook.humanify(self.hass, events))

        assert len(entries) == 1
        self.assert_entry(
            entries[0], pointB, "kitchen", domain="light", entity_id="light.kitchen"
        )

    def test_home_assistant_start_stop_grouped(self):
        """Test if HA start and stop events are grouped.

        Events that are occurring in the same minute.
        """
        entries = list(
            logbook.humanify(
                self.hass,
                (
                    ha.Event(EVENT_HOMEASSISTANT_STOP),
                    ha.Event(EVENT_HOMEASSISTANT_START),
                ),
            )
        )

        assert len(entries) == 1
        self.assert_entry(
            entries[0], name="Home Assistant", message="restarted", domain=ha.DOMAIN
        )

    def test_home_assistant_start(self):
        """Test if HA start is not filtered or converted into a restart."""
        entity_id = "switch.bla"
        pointA = dt_util.utcnow()

        entries = list(
            logbook.humanify(
                self.hass,
                (
                    ha.Event(EVENT_HOMEASSISTANT_START),
                    self.create_state_changed_event(pointA, entity_id, 10),
                ),
            )
        )

        assert len(entries) == 2
        self.assert_entry(
            entries[0], name="Home Assistant", message="started", domain=ha.DOMAIN
        )
        self.assert_entry(
            entries[1], pointA, "bla", domain="switch", entity_id=entity_id
        )

    def test_entry_message_from_state_device(self):
        """Test if logbook message is correctly created for switches.

        Especially test if the special handling for turn on/off events is done.
        """
        pointA = dt_util.utcnow()

        # message for a device state change
        eventA = self.create_state_changed_event(pointA, "switch.bla", 10)
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "changed to 10"

        # message for a switch turned on
        eventA = self.create_state_changed_event(pointA, "switch.bla", STATE_ON)
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "turned on"

        # message for a switch turned off
        eventA = self.create_state_changed_event(pointA, "switch.bla", STATE_OFF)
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "turned off"

    def test_entry_message_from_state_device_tracker(self):
        """Test if logbook message is correctly created for device tracker."""
        pointA = dt_util.utcnow()

        # message for a device tracker "not home" state
        eventA = self.create_state_changed_event(
            pointA, "device_tracker.john", STATE_NOT_HOME
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is away"

        # message for a device tracker "home" state
        eventA = self.create_state_changed_event(pointA, "device_tracker.john", "work")
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is at work"

    def test_entry_message_from_state_person(self):
        """Test if logbook message is correctly created for a person."""
        pointA = dt_util.utcnow()

        # message for a device tracker "not home" state
        eventA = self.create_state_changed_event(pointA, "person.john", STATE_NOT_HOME)
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is away"

        # message for a device tracker "home" state
        eventA = self.create_state_changed_event(pointA, "person.john", "work")
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is at work"

    def test_entry_message_from_state_sun(self):
        """Test if logbook message is correctly created for sun."""
        pointA = dt_util.utcnow()

        # message for a sun rise
        eventA = self.create_state_changed_event(
            pointA, "sun.sun", sun.STATE_ABOVE_HORIZON
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "has risen"

        # message for a sun set
        eventA = self.create_state_changed_event(
            pointA, "sun.sun", sun.STATE_BELOW_HORIZON
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "has set"

    def test_entry_message_from_state_binary_sensor_battery(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "battery"}

        # message for a binary_sensor battery "low" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.battery", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is low"

        # message for a binary_sensor battery "normal" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.battery", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is normal"

    def test_entry_message_from_state_binary_sensor_connectivity(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "connectivity"}

        # message for a binary_sensor connectivity "connected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.connectivity", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is connected"

        # message for a binary_sensor connectivity "disconnected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.connectivity", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is disconnected"

    def test_entry_message_from_state_binary_sensor_door(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "door"}

        # message for a binary_sensor door "open" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.door", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is opened"

        # message for a binary_sensor door "closed" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.door", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is closed"

    def test_entry_message_from_state_binary_sensor_garage_door(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "garage_door"}

        # message for a binary_sensor garage_door "open" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.garage_door", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is opened"

        # message for a binary_sensor garage_door "closed" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.garage_door", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is closed"

    def test_entry_message_from_state_binary_sensor_opening(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "opening"}

        # message for a binary_sensor opening "open" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.opening", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is opened"

        # message for a binary_sensor opening "closed" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.opening", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is closed"

    def test_entry_message_from_state_binary_sensor_window(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "window"}

        # message for a binary_sensor window "open" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.window", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is opened"

        # message for a binary_sensor window "closed" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.window", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is closed"

    def test_entry_message_from_state_binary_sensor_lock(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "lock"}

        # message for a binary_sensor lock "unlocked" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.lock", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is unlocked"

        # message for a binary_sensor lock "locked" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.lock", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is locked"

    def test_entry_message_from_state_binary_sensor_plug(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "plug"}

        # message for a binary_sensor plug "unpluged" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.plug", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is plugged in"

        # message for a binary_sensor plug "pluged" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.plug", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is unplugged"

    def test_entry_message_from_state_binary_sensor_presence(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "presence"}

        # message for a binary_sensor presence "home" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.presence", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is at home"

        # message for a binary_sensor presence "away" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.presence", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is away"

    def test_entry_message_from_state_binary_sensor_safety(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "safety"}

        # message for a binary_sensor safety "unsafe" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.safety", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is unsafe"

        # message for a binary_sensor safety "safe" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.safety", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "is safe"

    def test_entry_message_from_state_binary_sensor_cold(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "cold"}

        # message for a binary_sensor cold "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.cold", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected cold"

        # message for a binary_sensori cold "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.cold", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no cold detected)"

    def test_entry_message_from_state_binary_sensor_gas(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "gas"}

        # message for a binary_sensor gas "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.gas", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected gas"

        # message for a binary_sensori gas "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.gas", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no gas detected)"

    def test_entry_message_from_state_binary_sensor_heat(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "heat"}

        # message for a binary_sensor heat "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.heat", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected heat"

        # message for a binary_sensori heat "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.heat", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no heat detected)"

    def test_entry_message_from_state_binary_sensor_light(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "light"}

        # message for a binary_sensor light "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.light", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected light"

        # message for a binary_sensori light "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.light", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no light detected)"

    def test_entry_message_from_state_binary_sensor_moisture(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "moisture"}

        # message for a binary_sensor moisture "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.moisture", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected moisture"

        # message for a binary_sensori moisture "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.moisture", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no moisture detected)"

    def test_entry_message_from_state_binary_sensor_motion(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "motion"}

        # message for a binary_sensor motion "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.motion", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected motion"

        # message for a binary_sensori motion "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.motion", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no motion detected)"

    def test_entry_message_from_state_binary_sensor_occupancy(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "occupancy"}

        # message for a binary_sensor occupancy "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.occupancy", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected occupancy"

        # message for a binary_sensori occupancy "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.occupancy", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no occupancy detected)"

    def test_entry_message_from_state_binary_sensor_power(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "power"}

        # message for a binary_sensor power "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.power", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected power"

        # message for a binary_sensori power "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.power", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no power detected)"

    def test_entry_message_from_state_binary_sensor_problem(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "problem"}

        # message for a binary_sensor problem "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.problem", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected problem"

        # message for a binary_sensori problem "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.problem", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no problem detected)"

    def test_entry_message_from_state_binary_sensor_smoke(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "smoke"}

        # message for a binary_sensor smoke "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.smoke", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected smoke"

        # message for a binary_sensori smoke "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.smoke", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no smoke detected)"

    def test_entry_message_from_state_binary_sensor_sound(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "sound"}

        # message for a binary_sensor sound "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.sound", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected sound"

        # message for a binary_sensori sound "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.sound", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no sound detected)"

    def test_entry_message_from_state_binary_sensor_vibration(self):
        """Test if logbook message is correctly created for a binary_sensor."""
        pointA = dt_util.utcnow()
        attributes = {"device_class": "vibration"}

        # message for a binary_sensor vibration "detected" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.vibration", STATE_ON, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "detected vibration"

        # message for a binary_sensori vibration "cleared" state
        eventA = self.create_state_changed_event(
            pointA, "binary_sensor.vibration", STATE_OFF, attributes
        )
        to_state = ha.State.from_dict(eventA.data.get("new_state"))
        message = logbook._entry_message_from_state(to_state.domain, to_state)
        assert message == "cleared (no vibration detected)"

    def test_process_custom_logbook_entries(self):
        """Test if custom log book entries get added as an entry."""
        name = "Nice name"
        message = "has a custom entry"
        entity_id = "sun.sun"

        entries = list(
            logbook.humanify(
                self.hass,
                (
                    ha.Event(
                        logbook.EVENT_LOGBOOK_ENTRY,
                        {
                            logbook.ATTR_NAME: name,
                            logbook.ATTR_MESSAGE: message,
                            logbook.ATTR_ENTITY_ID: entity_id,
                        },
                    ),
                ),
            )
        )

        assert len(entries) == 1
        self.assert_entry(
            entries[0], name=name, message=message, domain="sun", entity_id=entity_id
        )

    def assert_entry(
        self, entry, when=None, name=None, message=None, domain=None, entity_id=None
    ):
        """Assert an entry is what is expected."""
        if when:
            assert when == entry["when"]

        if name:
            assert name == entry["name"]

        if message:
            assert message == entry["message"]

        if domain:
            assert domain == entry["domain"]

        if entity_id:
            assert entity_id == entry["entity_id"]

    def create_state_changed_event(
        self,
        event_time_fired,
        entity_id,
        state,
        attributes=None,
        last_changed=None,
        last_updated=None,
    ):
        """Create state changed event."""
        old_state = ha.State(
            entity_id, "old", attributes, last_changed, last_updated
        ).as_dict()
        new_state = ha.State(
            entity_id, state, attributes, last_changed, last_updated
        ).as_dict()

        return ha.Event(
            EVENT_STATE_CHANGED,
            {"entity_id": entity_id, "old_state": old_state, "new_state": new_state},
            time_fired=event_time_fired,
        )


async def test_logbook_view(hass, hass_client):
    """Test the logbook view."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)
    client = await hass_client()
    response = await client.get(f"/api/logbook/{dt_util.utcnow().isoformat()}")
    assert response.status == 200


async def test_logbook_view_period_entity(hass, hass_client):
    """Test the logbook view with period and entity."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await hass.async_add_job(partial(trigger_db_commit, hass))
    await hass.async_block_till_done()
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    json = await response.json()
    assert len(json) == 2
    assert json[0]["entity_id"] == entity_id_test
    assert json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by period
    response = await client.get(f"/api/logbook/{start_date.isoformat()}?period=1")
    assert response.status == 200
    json = await response.json()
    assert len(json) == 2
    assert json[0]["entity_id"] == entity_id_test
    assert json[1]["entity_id"] == entity_id_second

    # Test today entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == entity_id_test

    # Test entries for 3 days with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = (dt_util.utcnow() + timedelta(days=1)).date()
    start_date = datetime(start.year, start.month, start.day)

    # Test tomorrow entries without filters
    response = await client.get(f"/api/logbook/{start_date.isoformat()}")
    assert response.status == 200
    json = await response.json()
    assert len(json) == 0

    # Test tomorrow entries with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 0

    # Test entries from tomorrow to 3 days ago with filter by entity_id
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?period=3&entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == entity_id_test


async def test_logbook_describe_event(hass, hass_client):
    """Test teaching logbook about a new event."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    assert await async_setup_component(hass, "logbook", {})
    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=dt_util.utcnow() - timedelta(seconds=5),
    ):
        hass.bus.async_fire("some_event")
        await hass.async_block_till_done()
        await hass.async_add_executor_job(
            hass.data[recorder.DATA_INSTANCE].block_till_done
        )

    def _describe(event):
        """Describe an event."""
        return {"name": "Test Name", "message": "tested a message"}

    hass.components.logbook.async_describe_event("test_domain", "some_event", _describe)

    client = await hass_client()
    response = await client.get("/api/logbook")
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["message"] == "tested a message"
    assert event["domain"] == "test_domain"


async def test_exclude_described_event(hass, hass_client):
    """Test exclusions of events that are described by another integration."""
    name = "My Automation Rule"
    entity_id = "automation.excluded_rule"
    entity_id2 = "automation.included_rule"
    entity_id3 = "sensor.excluded_domain"

    await hass.async_add_executor_job(init_recorder_component, hass)
    assert await async_setup_component(
        hass,
        logbook.DOMAIN,
        {
            logbook.DOMAIN: {
                logbook.CONF_EXCLUDE: {
                    logbook.CONF_DOMAINS: ["sensor"],
                    logbook.CONF_ENTITIES: [entity_id],
                }
            }
        },
    )

    with patch(
        "homeassistant.util.dt.utcnow",
        return_value=dt_util.utcnow() - timedelta(seconds=5),
    ):
        hass.bus.async_fire(
            "some_automation_event",
            {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id},
        )
        hass.bus.async_fire(
            "some_automation_event",
            {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id2},
        )
        hass.bus.async_fire(
            "some_event", {logbook.ATTR_NAME: name, logbook.ATTR_ENTITY_ID: entity_id3}
        )
        await hass.async_block_till_done()
        await hass.async_add_executor_job(
            hass.data[recorder.DATA_INSTANCE].block_till_done
        )

    def _describe(event):
        """Describe an event."""
        return {
            "name": "Test Name",
            "message": "tested a message",
            "entity_id": event.data.get(ATTR_ENTITY_ID),
        }

    hass.components.logbook.async_describe_event(
        "automation", "some_automation_event", _describe
    )
    hass.components.logbook.async_describe_event("sensor", "some_event", _describe)

    client = await hass_client()
    response = await client.get("/api/logbook")
    results = await response.json()
    assert len(results) == 1
    event = results[0]
    assert event["name"] == "Test Name"
    assert event["message"] == "tested a message"
    assert event["domain"] == "automation"
    assert event["entity_id"] == "automation.included_rule"


async def test_logbook_view_end_time_entity(hass, hass_client):
    """Test the logbook view with end_time and entity."""
    await hass.async_add_executor_job(init_recorder_component, hass)
    await async_setup_component(hass, "logbook", {})
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    entity_id_test = "switch.test"
    hass.states.async_set(entity_id_test, STATE_OFF)
    hass.states.async_set(entity_id_test, STATE_ON)
    entity_id_second = "switch.second"
    hass.states.async_set(entity_id_second, STATE_OFF)
    hass.states.async_set(entity_id_second, STATE_ON)
    await hass.async_add_job(partial(trigger_db_commit, hass))
    await hass.async_block_till_done()
    await hass.async_add_job(hass.data[recorder.DATA_INSTANCE].block_till_done)

    client = await hass_client()

    # Today time 00:00:00
    start = dt_util.utcnow().date()
    start_date = datetime(start.year, start.month, start.day)

    # Test today entries with filter by end_time
    end_time = start + timedelta(hours=24)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 2
    assert json[0]["entity_id"] == entity_id_test
    assert json[1]["entity_id"] == entity_id_second

    # Test entries for 3 days with filter by entity_id
    end_time = start + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == entity_id_test

    # Tomorrow time 00:00:00
    start = dt_util.utcnow()
    start_date = datetime(start.year, start.month, start.day)

    # Test entries from today to 3 days with filter by entity_id
    end_time = start_date + timedelta(hours=72)
    response = await client.get(
        f"/api/logbook/{start_date.isoformat()}?end_time={end_time}&entity=switch.test"
    )
    assert response.status == 200
    json = await response.json()
    assert len(json) == 1
    assert json[0]["entity_id"] == entity_id_test
