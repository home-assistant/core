"""
tests.components.light.test_mqtt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests mqtt light.

config for RGB Version with brightness:

light:
  platform: mqtt
  name: "Office Light RGB"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  rgb_state_topic: "office/rgb1/rgb/status"
  rgb_command_topic: "office/rgb1/rgb/set"
  qos: 0
  payload_on: "on"
  payload_off: "off"

config without RGB:

light:
  platform: mqtt
  name: "Office Light"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  qos: 0
  payload_on: "on"
  payload_off: "off"

config without RGB and brightness:

light:
  platform: mqtt
  name: "Office Light"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  qos: 0
  payload_on: "on"
  payload_off: "off"
"""
import unittest

from homeassistant.const import STATE_ON, STATE_OFF
import homeassistant.core as ha
import homeassistant.components.light as light
from tests.common import mock_mqtt_component, fire_mqtt_message


class TestLightMQTT(unittest.TestCase):
    """ Test the MQTT light. """

    def setUp(self):  # pylint: disable=invalid-name
        self.hass = ha.HomeAssistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """ Stop down stuff we started. """
        self.hass.stop()

    def test_controlling_state_via_topic(self):
        self.assertTrue(light.setup(self.hass, {
            'switch': {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test_light_rgb/status',
                'command_topic': 'test_light_rgb/set',
                'brightness_state_topic': 'test_light_rgb/brightness/status',
                'brightness_command_topic': 'test_light_rgb/brightness/set',
                'rgb_state_topic': 'test_light_rgb/rgb/status',
                'rgb_command_topic': 'test_light_rgb/rgb/set',
                'qos': 0,
                'payload_on': 'on',
                'payload_off': 'off'
            }
        }))

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test', 'on')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        fire_mqtt_message(self.hass, 'test', 'off')
        self.hass.pool.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

    def test_sending_mqtt_commands_and_optimistic(self):
        self.assertTrue(light.setup(self.hass, {
            'switch': {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness_state_topic': 'test_light_rgb/brightness/status',
                'brightness_command_topic': 'test_light_rgb/brightness/set',
                'rgb_state_topic': 'test_light_rgb/rgb/status',
                'rgb_command_topic': 'test_light_rgb/rgb/set',
                'qos': 2,
                'payload_on': 'on',
                'payload_off': 'off'
            }
        }))

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        switch.turn_on(self.hass, 'light.test')
        self.hass.pool.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'on', 2),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        switch.turn_off(self.hass, 'light.test')
        self.hass.pool.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'off', 2),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
