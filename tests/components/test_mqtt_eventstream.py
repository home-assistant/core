"""The tests for the MQTT eventstream component."""
import json
import unittest
from unittest.mock import ANY, patch

from homeassistant.bootstrap import setup_component
import homeassistant.components.mqtt_eventstream as eventstream
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import State
from homeassistant.remote import JSONEncoder
import homeassistant.util.dt as dt_util

from tests.common import (
    get_test_home_assistant,
    mock_mqtt_component,
    fire_mqtt_message,
    mock_state_change_event,
    fire_time_changed
)


class TestMqttEventStream(unittest.TestCase):
    """Test the MQTT eventstream module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        super(TestMqttEventStream, self).setUp()
        self.hass = get_test_home_assistant()
        self.mock_mqtt = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def add_eventstream(self, sub_topic=None, pub_topic=None):
        """Add a mqtt_eventstream component."""
        config = {}
        if sub_topic:
            config['subscribe_topic'] = sub_topic
        if pub_topic:
            config['publish_topic'] = pub_topic
        return setup_component(self.hass, eventstream.DOMAIN, {
            eventstream.DOMAIN: config})

    def test_setup_succeeds(self):
        """"Test the success of the setup."""
        self.assertTrue(self.add_eventstream())

    def test_setup_with_pub(self):
        """"Test the setup with subscription."""
        # Should start off with no listeners for all events
        self.assertEqual(self.hass.bus.listeners.get('*'), None)

        self.assertTrue(self.add_eventstream(pub_topic='bar'))
        self.hass.block_till_done()

        # Verify that the event handler has been added as a listener
        self.assertEqual(self.hass.bus.listeners.get('*'), 1)

    @patch('homeassistant.components.mqtt.subscribe')
    def test_subscribe(self, mock_sub):
        """"Test the subscription."""
        sub_topic = 'foo'
        self.assertTrue(self.add_eventstream(sub_topic=sub_topic))
        self.hass.block_till_done()

        # Verify that the this entity was subscribed to the topic
        mock_sub.assert_called_with(self.hass, sub_topic, ANY)

    @patch('homeassistant.components.mqtt.publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_sends_message(self, mock_utcnow, mock_pub):
        """"Test the sending of a new message if event changed."""
        now = dt_util.as_utc(dt_util.now())
        e_id = 'fake.entity'
        pub_topic = 'bar'
        mock_utcnow.return_value = now

        # Add the eventstream component for publishing events
        self.assertTrue(self.add_eventstream(pub_topic=pub_topic))
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, 'on'))
        self.hass.block_till_done()

        # The order of the JSON is indeterminate,
        # so first just check that publish was called
        mock_pub.assert_called_with(self.hass, pub_topic, ANY)
        self.assertTrue(mock_pub.called)

        # Get the actual call to publish and make sure it was the one
        # we were looking for
        msg = mock_pub.call_args[0][2]
        event = {}
        event['event_type'] = EVENT_STATE_CHANGED
        new_state = {
            "last_updated": now.isoformat(),
            "state": "on",
            "entity_id": e_id,
            "attributes": {},
            "last_changed": now.isoformat()
        }
        event['event_data'] = {"new_state": new_state, "entity_id": e_id}

        # Verify that the message received was that expected
        self.assertEqual(json.loads(msg), event)

    @patch('homeassistant.components.mqtt.publish')
    def test_time_event_does_not_send_message(self, mock_pub):
        """"Test the sending of a new message if time event."""
        self.assertTrue(self.add_eventstream(pub_topic='bar'))
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        fire_time_changed(self.hass, dt_util.utcnow())
        self.assertFalse(mock_pub.called)

    def test_receiving_remote_event_fires_hass_event(self):
        """"Test the receiving of the remotely fired event."""
        sub_topic = 'foo'
        self.assertTrue(self.add_eventstream(sub_topic=sub_topic))
        self.hass.block_till_done()

        calls = []
        self.hass.bus.listen_once('test_event', lambda _: calls.append(1))
        self.hass.block_till_done()

        payload = json.dumps(
            {'event_type': 'test_event', 'event_data': {}},
            cls=JSONEncoder
        )
        fire_mqtt_message(self.hass, sub_topic, payload)
        self.hass.block_till_done()

        self.assertEqual(1, len(calls))
