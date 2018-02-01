"""The tests for the MQTT lock platform."""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_LOCKED, STATE_UNLOCKED, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
import homeassistant.components.lock as lock
from tests.common import (
    mock_mqtt_component, fire_mqtt_message, get_test_home_assistant)


class TestLockMQTT(unittest.TestCase):
    """Test the MQTT lock."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        """Test the controlling state via topic."""
        assert setup_component(self.hass, lock.DOMAIN, {
            lock.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_lock': 'LOCK',
                'payload_unlock': 'UNLOCK'
            }
        })

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'state-topic', 'LOCK')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_LOCKED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', 'UNLOCK')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending MQTT commands in optimistic mode."""
        assert setup_component(self.hass, lock.DOMAIN, {
            lock.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'command-topic',
                'payload_lock': 'LOCK',
                'payload_unlock': 'UNLOCK',
                'qos': 2
            }
        })

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        lock.lock(self.hass, 'lock.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'LOCK', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_LOCKED, state.state)

        lock.unlock(self.hass, 'lock.test')
        self.hass.block_till_done()

        self.assertEqual(('command-topic', 'UNLOCK', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)

    def test_controlling_state_via_topic_and_json_message(self):
        """Test the controlling state via topic and JSON message."""
        assert setup_component(self.hass, lock.DOMAIN, {
            lock.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_lock': 'LOCK',
                'payload_unlock': 'UNLOCK',
                'value_template': '{{ value_json.val }}'
            }
        })

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"LOCK"}')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_LOCKED, state.state)

        fire_mqtt_message(self.hass, 'state-topic', '{"val":"UNLOCK"}')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNLOCKED, state.state)

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        self.assertTrue(setup_component(self.hass, lock.DOMAIN, {
            lock.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_lock': 'LOCK',
                'payload_unlock': 'UNLOCK',
                'availability_topic': 'availability-topic'
            }
        }))

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        self.assertTrue(setup_component(self.hass, lock.DOMAIN, {
            lock.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'state-topic',
                'command_topic': 'command-topic',
                'payload_lock': 'LOCK',
                'payload_unlock': 'UNLOCK',
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        }))

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('lock.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)
