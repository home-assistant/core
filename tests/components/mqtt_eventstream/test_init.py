"""The tests for the MQTT eventstream component."""
import json

import pytest

import homeassistant.components.mqtt_eventstream as eventstream
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import State, callback
from homeassistant.helpers.json import JSONEncoder
from homeassistant.setup import setup_component
import homeassistant.util.dt as dt_util

from tests.async_mock import ANY, patch
from tests.common import (
    fire_mqtt_message,
    fire_time_changed,
    get_test_home_assistant,
    mock_mqtt_component,
    mock_state_change_event,
)


@pytest.fixture(autouse=True)
def mock_storage(hass_storage):
    """Autouse hass_storage for the TestCase tests."""


class TestMqttEventStream:
    """Test the MQTT eventstream module."""

    def setup_method(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_mqtt = mock_mqtt_component(self.hass)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def add_eventstream(self, sub_topic=None, pub_topic=None, ignore_event=None):
        """Add a mqtt_eventstream component."""
        config = {}
        if sub_topic:
            config["subscribe_topic"] = sub_topic
        if pub_topic:
            config["publish_topic"] = pub_topic
        if ignore_event:
            config["ignore_event"] = ignore_event
        return setup_component(
            self.hass, eventstream.DOMAIN, {eventstream.DOMAIN: config}
        )

    def test_setup_succeeds(self):
        """Test the success of the setup."""
        assert self.add_eventstream()

    def test_setup_with_pub(self):
        """Test the setup with subscription."""
        # Should start off with no listeners for all events
        assert self.hass.bus.listeners.get("*") is None

        assert self.add_eventstream(pub_topic="bar")
        self.hass.block_till_done()

        # Verify that the event handler has been added as a listener
        assert self.hass.bus.listeners.get("*") == 1

    @patch("homeassistant.components.mqtt.async_subscribe")
    def test_subscribe(self, mock_sub):
        """Test the subscription."""
        sub_topic = "foo"
        assert self.add_eventstream(sub_topic=sub_topic)
        self.hass.block_till_done()

        # Verify that the this entity was subscribed to the topic
        mock_sub.assert_called_with(self.hass, sub_topic, ANY)

    @patch("homeassistant.components.mqtt.async_publish")
    @patch("homeassistant.core.dt_util.utcnow")
    def test_state_changed_event_sends_message(self, mock_utcnow, mock_pub):
        """Test the sending of a new message if event changed."""
        now = dt_util.as_utc(dt_util.now())
        e_id = "fake.entity"
        pub_topic = "bar"
        mock_utcnow.return_value = now

        # Add the eventstream component for publishing events
        assert self.add_eventstream(pub_topic=pub_topic)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, "on"))
        self.hass.block_till_done()

        # The order of the JSON is indeterminate,
        # so first just check that publish was called
        mock_pub.assert_called_with(self.hass, pub_topic, ANY)
        assert mock_pub.called

        # Get the actual call to publish and make sure it was the one
        # we were looking for
        msg = mock_pub.call_args[0][2]
        event = {}
        event["event_type"] = EVENT_STATE_CHANGED
        new_state = {
            "last_updated": now.isoformat(),
            "state": "on",
            "entity_id": e_id,
            "attributes": {},
            "last_changed": now.isoformat(),
        }
        event["event_data"] = {"new_state": new_state, "entity_id": e_id}

        # Verify that the message received was that expected
        result = json.loads(msg)
        result["event_data"]["new_state"].pop("context")
        assert result == event

    @patch("homeassistant.components.mqtt.async_publish")
    def test_time_event_does_not_send_message(self, mock_pub):
        """Test the sending of a new message if time event."""
        assert self.add_eventstream(pub_topic="bar")
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        fire_time_changed(self.hass, dt_util.utcnow())
        assert not mock_pub.called

    def test_receiving_remote_event_fires_hass_event(self):
        """Test the receiving of the remotely fired event."""
        sub_topic = "foo"
        assert self.add_eventstream(sub_topic=sub_topic)
        self.hass.block_till_done()

        calls = []

        @callback
        def listener(_):
            calls.append(1)

        self.hass.bus.listen_once("test_event", listener)
        self.hass.block_till_done()

        payload = json.dumps(
            {"event_type": "test_event", "event_data": {}}, cls=JSONEncoder
        )
        fire_mqtt_message(self.hass, sub_topic, payload)
        self.hass.block_till_done()

        assert 1 == len(calls)

    @patch("homeassistant.components.mqtt.async_publish")
    def test_ignored_event_doesnt_send_over_stream(self, mock_pub):
        """Test the ignoring of sending events if defined."""
        assert self.add_eventstream(pub_topic="bar", ignore_event=["state_changed"])
        self.hass.block_till_done()

        e_id = "entity.test_id"
        event = {}
        event["event_type"] = EVENT_STATE_CHANGED
        new_state = {"state": "on", "entity_id": e_id, "attributes": {}}
        event["event_data"] = {"new_state": new_state, "entity_id": e_id}

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, "on"))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch("homeassistant.components.mqtt.async_publish")
    def test_wrong_ignored_event_sends_over_stream(self, mock_pub):
        """Test the ignoring of sending events if defined."""
        assert self.add_eventstream(pub_topic="bar", ignore_event=["statee_changed"])
        self.hass.block_till_done()

        e_id = "entity.test_id"
        event = {}
        event["event_type"] = EVENT_STATE_CHANGED
        new_state = {"state": "on", "entity_id": e_id, "attributes": {}}
        event["event_data"] = {"new_state": new_state, "entity_id": e_id}

        # Reset the mock because it will have already gotten calls for the
        # mqtt_eventstream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, "on"))
        self.hass.block_till_done()

        assert mock_pub.called
