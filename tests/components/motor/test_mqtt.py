"""
tests.components.motor.test_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests mqtt motor.
"""
import unittest

from homeassistant.const import STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN
import homeassistant.core as ha
import homeassistant.components.motor as motor
from tests.common import mock_mqtt_component, fire_mqtt_message


class TestMotorMQTT(unittest.TestCase):
    """ Test the MQTT motor. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        self.assertTrue(motor.setup(self.hass, {
            'motor': {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 0,
                'payload_open': 'OPEN',
                'payload_close': 'CLOSE',
                'payload_stop': 'STOP'
            }
        }))

        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_CLOSED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '100')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_OPEN, state.state)

    def test_sending_mqtt_commands(self):
        self.assertTrue(motor.setup(self.hass, {
            'motor': {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        }))

        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        motor.call_open(self.hass, 'motor.test')
        self.hass.pool.block_till_done()

        self.assertEqual(('command-topic', 'OPEN', 2),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('motor.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_state_attributes_current_position(self):
        self.assertTrue(motor.setup(self.hass, {
            'motor': {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_open': 'OPEN',
                'payload_close': 'CLOSE',
                'payload_stop': 'STOP'
            }
        }))

        state_attributes_dict = self.hass.states.get(
            'motor.test').attributes
        self.assertFalse('current_position' in state_attributes_dict)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'motor.test').attributes['current_position']
        self.assertEqual(0, current_position)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'motor.test').attributes['current_position']
        self.assertEqual(50, current_position)

        fire_mqtt_message(self.hass, 'state-topic', '101')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'motor.test').attributes['current_position']
        self.assertEqual(50, current_position)

        fire_mqtt_message(self.hass, 'state-topic', 'non-numeric')
        self.hass.pool.block_till_done()
        current_position = self.hass.states.get(
            'motor.test').attributes['current_position']
        self.assertEqual(50, current_position)
