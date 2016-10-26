"""The tests for the MQTT cover platform."""
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.const import STATE_OPEN, STATE_CLOSED, STATE_UNKNOWN
import homeassistant.components.cover as cover
from tests.common import mock_mqtt_component, fire_mqtt_message

from tests.common import get_test_home_assistant


class TestCoverMQTT(unittest.TestCase):
    """Test the MQTT cover."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop down everything that was started."""
        self.hass.stop()

    def test_state_via_state_topic(self):
        """Test the controlling state via topic."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
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

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_CLOSED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '100')
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', STATE_CLOSED)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_CLOSED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', STATE_OPEN)
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_OPEN, state.state)

    def test_state_via_template(self):
        """Test the controlling state via topic."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 0,
                'value_template': '{{ (value | multiply(0.01)) | int }}',
            }
        }))

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '10000')
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_OPEN, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '99')
        self.hass.block_till_done()

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_CLOSED, state.state)

    def test_optimistic_state_change(self):
        """Test changing state optimistically."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'command-topic',
                'qos': 0,
            }
        }))

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        cover.open_cover(self.hass, 'cover.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'OPEN', 0, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_OPEN, state.state)

        cover.close_cover(self.hass, 'cover.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'CLOSE', 0, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_CLOSED, state.state)

    def test_send_open_cover_command(self):
        """Test the sending of open_cover."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        }))

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        cover.open_cover(self.hass, 'cover.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'OPEN', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_send_close_cover_command(self):
        """Test the sending of close_cover."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        }))

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        cover.close_cover(self.hass, 'cover.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'CLOSE', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_send_stop__cover_command(self):
        """Test the sending of stop_cover."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'qos': 2
            }
        }))

        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

        cover.stop_cover(self.hass, 'cover.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'STOP', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('cover.test')
        self.assertEqual(STATE_UNKNOWN, state.state)

    def test_current_cover_position(self):
        """Test the current cover position."""
        self.hass.config.components = ['mqtt']
        self.assertTrue(setup_component(self.hass, cover.DOMAIN, {
            cover.DOMAIN: {
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
            'cover.test').attributes
        self.assertFalse('current_position' in state_attributes_dict)

        fire_mqtt_message(self.hass, 'state-topic', '0')
        self.hass.block_till_done()
        current_cover_position = self.hass.states.get(
            'cover.test').attributes['current_position']
        self.assertEqual(0, current_cover_position)

        fire_mqtt_message(self.hass, 'state-topic', '50')
        self.hass.block_till_done()
        current_cover_position = self.hass.states.get(
            'cover.test').attributes['current_position']
        self.assertEqual(50, current_cover_position)

        fire_mqtt_message(self.hass, 'state-topic', '101')
        self.hass.block_till_done()
        current_cover_position = self.hass.states.get(
            'cover.test').attributes['current_position']
        self.assertEqual(50, current_cover_position)

        fire_mqtt_message(self.hass, 'state-topic', 'non-numeric')
        self.hass.block_till_done()
        current_cover_position = self.hass.states.get(
            'cover.test').attributes['current_position']
        self.assertEqual(50, current_cover_position)
