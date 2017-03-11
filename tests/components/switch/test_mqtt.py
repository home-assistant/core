"""The tests for the MQTT switch platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ASSUMED_STATE
import homeassistant.components.switch as switch
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)


class TestSensorMQTT(unittest.TestCase):
    """Test the MQTT switch."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop everything that was started."""
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        """Test the controlling state via topic."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_on': 1,
                'payload_off': 0
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending MQTT commands in optimistic mode."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'command-topic',
                'payload_on': 'beer on',
                'payload_off': 'beer off',
                'qos': '2'
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        switch.turn_on(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'beer on', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        switch.turn_off(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'beer off', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_controlling_state_via_topic_and_json_message(self):
        """Test the controlling state via topic and JSON message."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_on': 'beer on',
                'payload_off': 'beer off',
                'value_template': '{{ value_json.val }}'
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer on"}')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer off"}')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
