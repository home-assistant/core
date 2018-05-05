"""The tests for the MQTT switch platform."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import STATE_ON, STATE_OFF, STATE_UNAVAILABLE,\
    ATTR_ASSUMED_STATE
import homeassistant.core as ha
import homeassistant.components.switch as switch
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant, mock_coro)


class TestSwitchMQTT(unittest.TestCase):
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
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

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
        fake_state = ha.State('switch.test', 'on')

        with patch('homeassistant.components.switch.mqtt.async_get_last_state',
                   return_value=mock_coro(fake_state)):
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
        self.assertEqual(STATE_ON, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        switch.turn_on(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'beer on', 2, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

        switch.turn_off(self.hass, 'switch.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'command-topic', 'beer off', 2, False)
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

    def test_controlling_availability(self):
        """Test the controlling state via topic."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'availability_topic': 'availability_topic',
                'payload_on': 1,
                'payload_off': 0,
                'payload_available': 1,
                'payload_not_available': 0
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

    def test_default_availability_payload(self):
        """Test the availability payload."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'availability_topic': 'availability_topic',
                'payload_on': 1,
                'payload_off': 0
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)

    def test_custom_availability_payload(self):
        """Test the availability payload."""
        assert setup_component(self.hass, switch.DOMAIN, {
            switch.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'availability_topic': 'availability_topic',
                'payload_on': 1,
                'payload_off': 0,
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        })

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'availability_topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability_topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('switch.test')
        self.assertEqual(STATE_ON, state.state)
