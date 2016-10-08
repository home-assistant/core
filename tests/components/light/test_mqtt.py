"""The tests for the MQTT light platform.

Configuration for RGB Version with brightness:

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

config for RGB Version with brightness and scale:

light:
  platform: mqtt
  name: "Office Light RGB"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  brightness_scale: 99
  rgb_state_topic: "office/rgb1/rgb/status"
  rgb_command_topic: "office/rgb1/rgb/set"
  rgb_scale: 99
  qos: 0
  payload_on: "on"
  payload_off: "off"

config with brightness and color temp

light:
  platform: mqtt
  name: "Office Light Color Temp"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  brightness_scale: 99
  color_temp_state_topic: "office/rgb1/color_temp/status"
  color_temp_command_topic: "office/rgb1/color_temp/set"
  qos: 0
  payload_on: "on"
  payload_off: "off"

"""
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ASSUMED_STATE
import homeassistant.components.light as light
from tests.common import (
  get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestLightMQTT(unittest.TestCase):
    """Test the MQTT light."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_fail_setup_if_no_command_topic(self):
        """Test if command fails with command topic."""
        self.hass.config.components = ['mqtt']
        assert not _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
            }
        })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_no_color_or_brightness_or_color_temp_if_no_topics(self):
        """Test if there is no color and brightness if no topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test_light_rgb/status',
                'command_topic': 'test_light_rgb/set',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))

    def test_controlling_state_via_topic(self):
        """Test the controlling of the state via topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test_light_rgb/status',
                'command_topic': 'test_light_rgb/set',
                'brightness_state_topic': 'test_light_rgb/brightness/status',
                'brightness_command_topic': 'test_light_rgb/brightness/set',
                'rgb_state_topic': 'test_light_rgb/rgb/status',
                'rgb_command_topic': 'test_light_rgb/rgb/set',
                'color_temp_state_topic': 'test_light_rgb/color_temp/status',
                'color_temp_command_topic': 'test_light_rgb/color_temp/set',
                'qos': '0',
                'payload_on': 1,
                'payload_off': 0
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(150, state.attributes.get('color_temp'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '0')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '1')
        self.hass.block_till_done()

        fire_mqtt_message(self.hass, 'test_light_rgb/brightness/status', '100')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100,
                         light_state.attributes['brightness'])

        fire_mqtt_message(self.hass, 'test_light_rgb/color_temp/status', '300')
        self.hass.block_till_done()
        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(300, light_state.attributes['color_temp'])

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '1')
        self.hass.block_till_done()

        fire_mqtt_message(self.hass, 'test_light_rgb/rgb/status',
                          '125,125,125')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([125, 125, 125],
                         light_state.attributes.get('rgb_color'))

    def test_controlling_scale(self):
        """Test the controlling scale."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test_scale/status',
                'command_topic': 'test_scale/set',
                'brightness_state_topic': 'test_scale/brightness/status',
                'brightness_command_topic': 'test_scale/brightness/set',
                'brightness_scale': '99',
                'qos': 0,
                'payload_on': 'on',
                'payload_off': 'off'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'test_scale/status', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))

        fire_mqtt_message(self.hass, 'test_scale/status', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_scale/status', 'on')
        self.hass.block_till_done()

        fire_mqtt_message(self.hass, 'test_scale/brightness/status', '99')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(255,
                         light_state.attributes['brightness'])

    def test_controlling_state_via_topic_with_templates(self):
        """Test the setting og the state with a template."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'state_topic': 'test_light_rgb/status',
                'command_topic': 'test_light_rgb/set',
                'brightness_state_topic': 'test_light_rgb/brightness/status',
                'color_temp_state_topic': 'test_light_rgb/color_temp/status',
                'rgb_state_topic': 'test_light_rgb/rgb/status',
                'state_value_template': '{{ value_json.hello }}',
                'brightness_value_template': '{{ value_json.hello }}',
                'color_temp_value_template': '{{ value_json.hello }}',
                'rgb_value_template': '{{ value_json.hello | join(",") }}',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('rgb_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb/rgb/status',
                          '{"hello": [1, 2, 3]}')
        fire_mqtt_message(self.hass, 'test_light_rgb/status',
                          '{"hello": "ON"}')
        fire_mqtt_message(self.hass, 'test_light_rgb/brightness/status',
                          '{"hello": "50"}')
        fire_mqtt_message(self.hass, 'test_light_rgb/color_temp/status',
                          '{"hello": "300"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(50, state.attributes.get('brightness'))
        self.assertEqual([1, 2, 3], state.attributes.get('rgb_color'))
        self.assertEqual(300, state.attributes.get('color_temp'))

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending of command in optimistic mode."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness_command_topic': 'test_light_rgb/brightness/set',
                'rgb_command_topic': 'test_light_rgb/rgb/set',
                'color_temp_command_topic': 'test_light_rgb/color_temp/set',
                'qos': 2,
                'payload_on': 'on',
                'payload_off': 'off'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'on', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'off', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test', rgb_color=[75, 75, 75],
                      brightness=50)
        self.hass.block_till_done()

        # Calls are threaded so we need to reorder them
        bright_call, rgb_call, state_call = \
            sorted((call[1] for call in self.mock_publish.mock_calls[-3:]),
                   key=lambda call: call[0])

        self.assertEqual(('test_light_rgb/set', 'on', 2, False),
                         state_call)

        self.assertEqual(('test_light_rgb/rgb/set', '75,75,75', 2, False),
                         rgb_call)

        self.assertEqual(('test_light_rgb/brightness/set', 50, 2, False),
                         bright_call)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual((75, 75, 75), state.attributes['rgb_color'])
        self.assertEqual(50, state.attributes['brightness'])

    def test_show_brightness_if_only_command_topic(self):
        """Test the brightness if only a command topic is present."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'brightness_command_topic': 'test_light_rgb/brightness/set',
                'command_topic': 'test_light_rgb/set',
                'state_topic': 'test_light_rgb/status',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))

    def test_show_color_temp_only_if_command_topic(self):
        """Test the color temp only if a command topic is present."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'color_temp_command_topic': 'test_light_rgb/brightness/set',
                'command_topic': 'test_light_rgb/set',
                'state_topic': 'test_light_rgb/status'
              }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('color_temp'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(150, state.attributes.get('color_temp'))
