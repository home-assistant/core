"""The tests for the MQTT Garge door platform."""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.const import STATE_OPEN, STATE_CLOSED, ATTR_ASSUMED_STATE

import homeassistant.components.garage_door as garage_door
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)


class TestGarageDoorMQTT(unittest.TestCase):
    """Test the MQTT Garage door."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """"Stop everything that was started."""
        self.hass.stop()

    def test_fail_setup_if_no_command_topic(self):
        """Test if command fails with command topic."""
        self.hass.config.components = ['mqtt']
        assert not _setup_component(self.hass, garage_door.DOMAIN, {
            garage_door.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': '/home/garage_door/door'
            }
        })
        self.assertIsNone(self.hass.states.get('garage_door.test'))

    def test_controlling_state_via_topic(self):
        """Test the controlling state via topic."""
        assert _setup_component(self.hass, garage_door.DOMAIN, {
            garage_door.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'state_open': 1,
                'state_closed': 0,
                'service_open': 1,
                'service_close': 0
            }
        })

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'state-topic', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending MQTT commands in optimistic mode."""
        assert _setup_component(self.hass, garage_door.DOMAIN, {
            garage_door.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'command-topic',
                'state_open': 'beer state open',
                'state_closed': 'beer state closed',
                'service_open': 'beer open',
                'service_close': 'beer close',
                'qos': '2'
            }
        })

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        garage_door.open_door(self.hass, 'garage_door.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'beer open', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_OPEN, state.state)

        garage_door.close_door(self.hass, 'garage_door.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'beer close', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)

    def test_controlling_state_via_topic_and_json_message(self):
        """Test the controlling state via topic and JSON message."""
        assert _setup_component(self.hass, garage_door.DOMAIN, {
            garage_door.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'state_open': 'beer open',
                'state_closed': 'beer closed',
                'service_open': 'beer service open',
                'service_close': 'beer service close',
                'value_template': '{{ value_json.val }}'
            }
        })

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer open"}')
        self.hass.block_till_done()

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"beer closed"}')
        self.hass.block_till_done()

        state = self.hass.states.get('garage_door.test')
        self.assertEqual(STATE_CLOSED, state.state)
