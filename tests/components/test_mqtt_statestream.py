"""The tests for the MQTT statestream component."""
from unittest.mock import ANY, call, patch

from homeassistant.setup import setup_component
import homeassistant.components.mqtt_statestream as statestream
from homeassistant.core import State

from tests.common import (
    get_test_home_assistant,
    mock_mqtt_component,
    mock_state_change_event
)


class TestMqttStateStream:
    """Test the MQTT statestream module."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_mqtt = mock_mqtt_component(self.hass)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def add_statestream(self, base_topic=None, publish_attributes=None,
                        publish_timestamps=None, publish_include=None,
                        publish_exclude=None):
        """Add a mqtt_statestream component."""
        config = {}
        if base_topic:
            config['base_topic'] = base_topic
        if publish_attributes:
            config['publish_attributes'] = publish_attributes
        if publish_timestamps:
            config['publish_timestamps'] = publish_timestamps
        if publish_include:
            config['include'] = publish_include
        if publish_exclude:
            config['exclude'] = publish_exclude
        return setup_component(self.hass, statestream.DOMAIN, {
            statestream.DOMAIN: config})

    def test_fails_with_no_base(self):
        """Setup should fail if no base_topic is set."""
        assert self.add_statestream() is False

    def test_setup_succeeds_without_attributes(self):
        """Test the success of the setup with a valid base_topic."""
        assert self.add_statestream(base_topic='pub')

    def test_setup_succeeds_with_attributes(self):
        """Test setup with a valid base_topic and publish_attributes."""
        assert self.add_statestream(base_topic='pub', publish_attributes=True)

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_sends_message(self, mock_utcnow, mock_pub):
        """Test the sending of a new message if event changed."""
        e_id = 'fake.entity'
        base_topic = 'pub'

        # Add the statestream component for publishing state updates
        assert self.add_statestream(base_topic=base_topic)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_sends_message_and_timestamp(
            self,
            mock_utcnow,
            mock_pub):
        """Test the sending of a message and timestamps if event changed."""
        e_id = 'another.entity'
        base_topic = 'pub'

        # Add the statestream component for publishing state updates
        assert self.add_statestream(base_topic=base_topic,
                                    publish_attributes=None,
                                    publish_timestamps=True)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        calls = [
            call.async_publish(self.hass, 'pub/another/entity/state', 'on', 1,
                               True),
            call.async_publish(self.hass, 'pub/another/entity/last_changed',
                               ANY, 1, True),
            call.async_publish(self.hass, 'pub/another/entity/last_updated',
                               ANY, 1, True),
        ]

        mock_pub.assert_has_calls(calls, any_order=True)
        assert mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_attr_sends_message(self, mock_utcnow, mock_pub):
        """Test the sending of a new message if attribute changed."""
        e_id = 'fake.entity'
        base_topic = 'pub'

        # Add the statestream component for publishing state updates
        assert self.add_statestream(base_topic=base_topic,
                                    publish_attributes=True)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        test_attributes = {
            "testing": "YES",
            "list": ["a", "b", "c"],
            "bool": False
        }

        # Set a state of an entity
        mock_state_change_event(self.hass, State(e_id, 'off',
                                                 attributes=test_attributes))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        calls = [
            call.async_publish(self.hass, 'pub/fake/entity/state', 'off', 1,
                               True),
            call.async_publish(self.hass, 'pub/fake/entity/testing', '"YES"',
                               1, True),
            call.async_publish(self.hass, 'pub/fake/entity/list',
                               '["a", "b", "c"]', 1, True),
            call.async_publish(self.hass, 'pub/fake/entity/bool', "false",
                               1, True)
        ]

        mock_pub.assert_has_calls(calls, any_order=True)
        assert mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_include_domain(self, mock_utcnow, mock_pub):
        """Test that filtering on included domain works as expected."""
        base_topic = 'pub'

        incl = {
            'domains': ['fake']
        }
        excl = {}

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake2.entity', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_include_entity(self, mock_utcnow, mock_pub):
        """Test that filtering on included entity works as expected."""
        base_topic = 'pub'

        incl = {
            'entities': ['fake.entity']
        }
        excl = {}

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake.entity2', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_exclude_domain(self, mock_utcnow, mock_pub):
        """Test that filtering on excluded domain works as expected."""
        base_topic = 'pub'

        incl = {}
        excl = {
            'domains': ['fake2']
        }

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake2.entity', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_exclude_entity(self, mock_utcnow, mock_pub):
        """Test that filtering on excluded entity works as expected."""
        base_topic = 'pub'

        incl = {}
        excl = {
            'entities': ['fake.entity2']
        }

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake.entity2', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_exclude_domain_include_entity(
            self, mock_utcnow, mock_pub):
        """Test filtering with excluded domain and included entity."""
        base_topic = 'pub'

        incl = {
            'entities': ['fake.entity']
        }
        excl = {
            'domains': ['fake']
        }

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake.entity2', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_include_domain_exclude_entity(
            self, mock_utcnow, mock_pub):
        """Test filtering with included domain and excluded entity."""
        base_topic = 'pub'

        incl = {
            'domains': ['fake']
        }
        excl = {
            'entities': ['fake.entity2']
        }

        # Add the statestream component for publishing state updates
        # Set the filter to allow fake.* items
        assert self.add_statestream(base_topic=base_topic,
                                    publish_include=incl,
                                    publish_exclude=excl)
        self.hass.block_till_done()

        # Reset the mock because it will have already gotten calls for the
        # mqtt_statestream state change on initialization, etc.
        mock_pub.reset_mock()

        # Set a state of an entity
        mock_state_change_event(self.hass, State('fake.entity', 'on'))
        self.hass.block_till_done()

        # Make sure 'on' was published to pub/fake/entity/state
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity/state', 'on',
                                    1, True)
        assert mock_pub.called

        mock_pub.reset_mock()
        # Set a state of an entity that shouldn't be included
        mock_state_change_event(self.hass, State('fake.entity2', 'on'))
        self.hass.block_till_done()

        assert not mock_pub.called
