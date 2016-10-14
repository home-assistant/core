"""The tests for the MQTT roller shutter platform."""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.const import STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN
import homeassistant.components.rollershutter as rollershutter
from tests.common import mock_mqtt_component, fire_mqtt_message

from tests.common import get_test_home_assistant


class TestRollershutterMQTT(unittest.TestCase):
    """Test the MQTT roller shutter."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        """Test the controlling state via topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, rollershutter.DOMAIN, {
            rollershutter.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 0,
                'payload_up': 'UP',
                'payload_down': 'DOWN',
                'payload_stop': 'STOP'
            }
        })

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_CLOSED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.block_till_done()

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '100')
        self.hass.block_till_done()

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_OPEN, state.state)

    def test_send_move_up_command(self):
        """Test the sending of move_up."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, rollershutter.DOMAIN, {
            rollershutter.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        })

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        rollershutter.move_up(self.hass, 'rollershutter.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'UP', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_send_move_down_command(self):
        """Test the sending of move_down."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, rollershutter.DOMAIN, {
            rollershutter.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        })

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        rollershutter.move_down(self.hass, 'rollershutter.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'DOWN', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_send_stop_command(self):
        """Test the sending of stop."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, rollershutter.DOMAIN, {
            rollershutter.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        })

        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        rollershutter.stop(self.hass, 'rollershutter.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'STOP', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('rollershutter.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_state_attributes_current_position(self):
        """Test the current position."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, rollershutter.DOMAIN, {
            rollershutter.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_up': 'UP',
                'payload_down': 'DOWN',
                'payload_stop': 'STOP'
            }
        })

        state_attributes_dict = self.hass.states.get(
            'rollershutter.test').attributes
        self.assertFalse('current_position' in state_attributes_dict)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(0, current_position)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)

        fire_mqtt_message(self.hass, 'state-topic', '101')
        self.hass.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)

        fire_mqtt_message(self.hass, 'state-topic', 'non-numeric')
        self.hass.block_till_done()
        current_position = self.hass.states.get(
            'rollershutter.test').attributes['current_position']
        self.assertEqual(50, current_position)
