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

Configuration for XY Version with brightness:

light:
  platform: mqtt
  name: "Office Light XY"
  state_topic: "office/xy1/light/status"
  command_topic: "office/xy1/light/switch"
  brightness_state_topic: "office/xy1/brightness/status"
  brightness_command_topic: "office/xy1/brightness/set"
  xy_state_topic: "office/xy1/xy/status"
  xy_command_topic: "office/xy1/xy/set"
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

config with brightness and effect

light:
  platform: mqtt
  name: "Office Light Color Temp"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  brightness_state_topic: "office/rgb1/brightness/status"
  brightness_command_topic: "office/rgb1/brightness/set"
  brightness_scale: 99
  effect_state_topic: "office/rgb1/effect/status"
  effect_command_topic: "office/rgb1/effect/set"
  effect_list:
    - rainbow
    - colorloop
  qos: 0
  payload_on: "on"
  payload_off: "off"

config for RGB Version with white value and scale:

light:
  platform: mqtt
  name: "Office Light RGB"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  white_value_state_topic: "office/rgb1/white_value/status"
  white_value_command_topic: "office/rgb1/white_value/set"
  white_value_scale: 99
  rgb_state_topic: "office/rgb1/rgb/status"
  rgb_command_topic: "office/rgb1/rgb/set"
  rgb_scale: 99
  qos: 0
  payload_on: "on"
  payload_off: "off"

config for RGB Version with RGB command template:

light:
  platform: mqtt
  name: "Office Light RGB"
  state_topic: "office/rgb1/light/status"
  command_topic: "office/rgb1/light/switch"
  rgb_state_topic: "office/rgb1/rgb/status"
  rgb_command_topic: "office/rgb1/rgb/set"
  rgb_command_template: "{{ '#%02x%02x%02x' | format(red, green, blue)}}"
  qos: 0
  payload_on: "on"
  payload_off: "off"

"""
import unittest
from unittest import mock

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
import homeassistant.components.light as light
from tests.common import (
    assert_setup_component, get_test_home_assistant, mock_mqtt_component,
    fire_mqtt_message)


class TestLightMQTT(unittest.TestCase):
    """Test the MQTT light."""

    # pylint: disable=invalid-name

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_fail_setup_if_no_command_topic(self):
        """Test if command fails with command topic."""
        with assert_setup_component(0, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt',
                    'name': 'test',
                }
            })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_no_color_brightness_color_temp_white_xy_if_no_topics(self): \
            # pylint: disable=invalid-name
        """Test if there is no color and brightness if no topic."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
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
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))

    def test_controlling_state_via_topic(self): \
            # pylint: disable=invalid-name
        """Test the controlling of the state via topic."""
        config = {light.DOMAIN: {
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
            'effect_state_topic': 'test_light_rgb/effect/status',
            'effect_command_topic': 'test_light_rgb/effect/set',
            'white_value_state_topic': 'test_light_rgb/white_value/status',
            'white_value_command_topic': 'test_light_rgb/white_value/set',
            'xy_state_topic': 'test_light_rgb/xy/status',
            'xy_command_topic': 'test_light_rgb/xy/set',
            'qos': '0',
            'payload_on': 1,
            'payload_off': 0
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '1')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(150, state.attributes.get('color_temp'))
        self.assertEqual('none', state.attributes.get('effect'))
        self.assertEqual(255, state.attributes.get('white_value'))
        self.assertEqual([1, 1], state.attributes.get('xy_color'))

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

        fire_mqtt_message(self.hass, 'test_light_rgb/effect/status', 'rainbow')
        self.hass.block_till_done()
        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual('rainbow', light_state.attributes['effect'])

        fire_mqtt_message(self.hass, 'test_light_rgb/white_value/status',
                          '100')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100,
                         light_state.attributes['white_value'])

        fire_mqtt_message(self.hass, 'test_light_rgb/status', '1')
        self.hass.block_till_done()

        fire_mqtt_message(self.hass, 'test_light_rgb/rgb/status',
                          '125,125,125')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([125, 125, 125],
                         light_state.attributes.get('rgb_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb/xy/status',
                          '0.675,0.322')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([0.675, 0.322],
                         light_state.attributes.get('xy_color'))

    def test_brightness_controlling_scale(self):
        """Test the brightness controlling scale."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
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
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

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

    def test_white_value_controlling_scale(self):
        """Test the white_value controlling scale."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt',
                    'name': 'test',
                    'state_topic': 'test_scale/status',
                    'command_topic': 'test_scale/set',
                    'white_value_state_topic': 'test_scale/white_value/status',
                    'white_value_command_topic': 'test_scale/white_value/set',
                    'white_value_scale': '99',
                    'qos': 0,
                    'payload_on': 'on',
                    'payload_off': 'off'
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'test_scale/status', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('white_value'))

        fire_mqtt_message(self.hass, 'test_scale/status', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_scale/status', 'on')
        self.hass.block_till_done()

        fire_mqtt_message(self.hass, 'test_scale/white_value/status', '99')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(255,
                         light_state.attributes['white_value'])

    def test_controlling_state_via_topic_with_templates(self): \
            # pylint: disable=invalid-name
        """Test the setting og the state with a template."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'state_topic': 'test_light_rgb/status',
            'command_topic': 'test_light_rgb/set',
            'brightness_state_topic': 'test_light_rgb/brightness/status',
            'color_temp_state_topic': 'test_light_rgb/color_temp/status',
            'effect_state_topic': 'test_light_rgb/effect/status',
            'rgb_state_topic': 'test_light_rgb/rgb/status',
            'white_value_state_topic': 'test_light_rgb/white_value/status',
            'xy_state_topic': 'test_light_rgb/xy/status',
            'state_value_template': '{{ value_json.hello }}',
            'brightness_value_template': '{{ value_json.hello }}',
            'color_temp_value_template': '{{ value_json.hello }}',
            'effect_value_template': '{{ value_json.hello }}',
            'rgb_value_template': '{{ value_json.hello | join(",") }}',
            'white_value_template': '{{ value_json.hello }}',
            'xy_value_template': '{{ value_json.hello | join(",") }}',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

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
        fire_mqtt_message(self.hass, 'test_light_rgb/effect/status',
                          '{"hello": "rainbow"}')
        fire_mqtt_message(self.hass, 'test_light_rgb/white_value/status',
                          '{"hello": "75"}')
        fire_mqtt_message(self.hass, 'test_light_rgb/xy/status',
                          '{"hello": [0.123,0.123]}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(50, state.attributes.get('brightness'))
        self.assertEqual([1, 2, 3], state.attributes.get('rgb_color'))
        self.assertEqual(300, state.attributes.get('color_temp'))
        self.assertEqual('rainbow', state.attributes.get('effect'))
        self.assertEqual(75, state.attributes.get('white_value'))
        self.assertEqual([0.123, 0.123], state.attributes.get('xy_color'))

    def test_sending_mqtt_commands_and_optimistic(self): \
            # pylint: disable=invalid-name
        """Test the sending of command in optimistic mode."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'brightness_command_topic': 'test_light_rgb/brightness/set',
            'rgb_command_topic': 'test_light_rgb/rgb/set',
            'color_temp_command_topic': 'test_light_rgb/color_temp/set',
            'effect_command_topic': 'test_light_rgb/effect/set',
            'white_value_command_topic': 'test_light_rgb/white_value/set',
            'xy_command_topic': 'test_light_rgb/xy/set',
            'qos': 2,
            'payload_on': 'on',
            'payload_off': 'off'
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'on', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'off', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        self.mock_publish.reset_mock()
        light.turn_on(self.hass, 'light.test',
                      brightness=50, xy_color=[0.123, 0.123])
        light.turn_on(self.hass, 'light.test', rgb_color=[75, 75, 75],
                      white_value=80)
        self.hass.block_till_done()

        self.mock_publish().async_publish.assert_has_calls([
            mock.call('test_light_rgb/set', 'on', 2, False),
            mock.call('test_light_rgb/rgb/set', '75,75,75', 2, False),
            mock.call('test_light_rgb/brightness/set', 50, 2, False),
            mock.call('test_light_rgb/white_value/set', 80, 2, False),
            mock.call('test_light_rgb/xy/set', '0.123,0.123', 2, False),
        ], any_order=True)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual((75, 75, 75), state.attributes['rgb_color'])
        self.assertEqual(50, state.attributes['brightness'])
        self.assertEqual(80, state.attributes['white_value'])
        self.assertEqual((0.123, 0.123), state.attributes['xy_color'])

    def test_sending_mqtt_rgb_command_with_template(self):
        """Test the sending of RGB command with template."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'rgb_command_topic': 'test_light_rgb/rgb/set',
            'rgb_command_template': '{{ "#%02x%02x%02x" | '
                                    'format(red, green, blue)}}',
            'payload_on': 'on',
            'payload_off': 'off',
            'qos': 0
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test', rgb_color=[255, 128, 64])
        self.hass.block_till_done()

        self.mock_publish().async_publish.assert_has_calls([
            mock.call('test_light_rgb/set', 'on', 0, False),
            mock.call('test_light_rgb/rgb/set', '#ff8040', 0, False),
        ], any_order=True)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual((255, 128, 64), state.attributes['rgb_color'])

    def test_show_brightness_if_only_command_topic(self):
        """Test the brightness if only a command topic is present."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'brightness_command_topic': 'test_light_rgb/brightness/set',
            'command_topic': 'test_light_rgb/set',
            'state_topic': 'test_light_rgb/status',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

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
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'color_temp_command_topic': 'test_light_rgb/brightness/set',
            'command_topic': 'test_light_rgb/set',
            'state_topic': 'test_light_rgb/status'
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('color_temp'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(150, state.attributes.get('color_temp'))

    def test_show_effect_only_if_command_topic(self):
        """Test the color temp only if a command topic is present."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'effect_command_topic': 'test_light_rgb/effect/set',
            'command_topic': 'test_light_rgb/set',
            'state_topic': 'test_light_rgb/status'
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('effect'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual('none', state.attributes.get('effect'))

    def test_show_white_value_if_only_command_topic(self):
        """Test the white_value if only a command topic is present."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'white_value_command_topic': 'test_light_rgb/white_value/set',
            'command_topic': 'test_light_rgb/set',
            'state_topic': 'test_light_rgb/status',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('white_value'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('white_value'))

    def test_show_xy_if_only_command_topic(self):
        """Test the xy if only a command topic is present."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'xy_command_topic': 'test_light_rgb/xy/set',
            'command_topic': 'test_light_rgb/set',
            'state_topic': 'test_light_rgb/status',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('xy_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb/status', 'ON')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([1, 1], state.attributes.get('xy_color'))

    def test_on_command_first(self):
        """Test on command being sent before brightness."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test_light/set',
            'brightness_command_topic': 'test_light/bright',
            'on_command_type': 'first',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test', brightness=50)
        self.hass.block_till_done()

        # Should get the following MQTT messages.
        #    test_light/set: 'ON'
        #    test_light/bright: 50
        self.assertEqual(('test_light/set', 'ON', 0, False),
                         self.mock_publish.mock_calls[-4][1])
        self.assertEqual(('test_light/bright', 50, 0, False),
                         self.mock_publish.mock_calls[-2][1])

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light/set', 'OFF', 0, False),
                         self.mock_publish.mock_calls[-2][1])

    def test_on_command_last(self):
        """Test on command being sent after brightness."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test_light/set',
            'brightness_command_topic': 'test_light/bright',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test', brightness=50)
        self.hass.block_till_done()

        # Should get the following MQTT messages.
        #    test_light/bright: 50
        #    test_light/set: 'ON'
        self.assertEqual(('test_light/bright', 50, 0, False),
                         self.mock_publish.mock_calls[-4][1])
        self.assertEqual(('test_light/set', 'ON', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light/set', 'OFF', 0, False),
                         self.mock_publish.mock_calls[-2][1])

    def test_on_command_brightness(self):
        """Test on command being sent as only brightness."""
        config = {light.DOMAIN: {
            'platform': 'mqtt',
            'name': 'test',
            'command_topic': 'test_light/set',
            'brightness_command_topic': 'test_light/bright',
            'rgb_command_topic': "test_light/rgb",
            'on_command_type': 'brightness',
        }}

        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, config)

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        # Turn on w/ no brightness - should set to max
        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        # Should get the following MQTT messages.
        #    test_light/bright: 255
        self.assertEqual(('test_light/bright', 255, 0, False),
                         self.mock_publish.mock_calls[-2][1])

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light/set', 'OFF', 0, False),
                         self.mock_publish.mock_calls[-2][1])

        # Turn on w/ brightness
        light.turn_on(self.hass, 'light.test', brightness=50)
        self.hass.block_till_done()

        self.assertEqual(('test_light/bright', 50, 0, False),
                         self.mock_publish.mock_calls[-2][1])

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        # Turn on w/ just a color to insure brightness gets
        # added and sent.
        light.turn_on(self.hass, 'light.test', rgb_color=[75, 75, 75])
        self.hass.block_till_done()

        self.assertEqual(('test_light/rgb', '75,75,75', 0, False),
                         self.mock_publish.mock_calls[-4][1])
        self.assertEqual(('test_light/bright', 50, 0, False),
                         self.mock_publish.mock_calls[-2][1])

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'test_light/set',
                'brightness_command_topic': 'test_light/bright',
                'rgb_command_topic': "test_light/rgb",
                'availability_topic': 'availability-topic'
            }
        }))

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'name': 'test',
                'command_topic': 'test_light/set',
                'brightness_command_topic': 'test_light/bright',
                'rgb_command_topic': "test_light/rgb",
                'availability_topic': 'availability-topic',
                'payload_available': 'good',
                'payload_not_available': 'nogood'
            }
        }))

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertNotEqual(STATE_UNAVAILABLE, state.state)

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_UNAVAILABLE, state.state)
