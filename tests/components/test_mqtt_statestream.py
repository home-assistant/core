"""The tests for the MQTT statestream component."""
from unittest.mock import patch

from homeassistant.setup import setup_component
import homeassistant.components.mqtt_statestream as statestream
from homeassistant.core import State

from tests.common import (
    get_test_home_assistant,
    mock_mqtt_component,
    mock_state_change_event
)


class TestMqttStateStream(object):
    """Test the MQTT statestream module."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_mqtt = mock_mqtt_component(self.hass)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def add_statestream(self, base_topic=None):
        """Add a mqtt_statestream component."""
        config = {}
        if base_topic:
            config['base_topic'] = base_topic
        return setup_component(self.hass, statestream.DOMAIN, {
            statestream.DOMAIN: config})

    def test_fails_with_no_base(self):
        """Setup should fail if no base_topic is set."""
        assert self.add_statestream() is False

    def test_setup_succeeds(self):
        """"Test the success of the setup with a valid base_topic."""
        assert self.add_statestream(base_topic='pub')

    @patch('homeassistant.components.mqtt.async_publish')
    @patch('homeassistant.core.dt_util.utcnow')
    def test_state_changed_event_sends_message(self, mock_utcnow, mock_pub):
        """"Test the sending of a new message if event changed."""
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

        # Make sure 'on' was published to pub/fake/entity
        mock_pub.assert_called_with(self.hass, 'pub/fake/entity', 'on', 1,
                                    True)
        assert mock_pub.called
