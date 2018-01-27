"""The tests for the MQTT JSON light platform.

Configuration with RGB, brightness, color temp, effect, white value and XY:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true
  white_value: true
  xy: true

Configuration with RGB, brightness, color temp, effect, white value:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true
  white_value: true

Configuration with RGB, brightness, color temp and effect:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  color_temp: true
  effect: true
  rgb: true

Configuration with RGB, brightness and color temp:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  rgb: true
  color_temp: true

Configuration with RGB, brightness:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true
  rgb: true

Config without RGB:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"
  brightness: true

Config without RGB and brightness:

light:
  platform: mqtt_json
  name: mqtt_json_light_1
  state_topic: "home/rgb1"
  command_topic: "home/rgb1/set"

Config with brightness and scale:

light:
  platform: mqtt_json
  name: test
  state_topic: "mqtt_json_light_1"
  command_topic: "mqtt_json_light_1/set"
  brightness: true
  brightness_scale: 99
"""

import json
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES)
import homeassistant.components.light as light
from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message,
    assert_setup_component)


class TestLightMQTTJSON(unittest.TestCase):
    """Test the MQTT JSON light."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_fail_setup_if_no_command_topic(self): \
            # pylint: disable=invalid-name
        """Test if setup fails with no command topic."""
        with assert_setup_component(0, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_json',
                    'name': 'test',
                }
            })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_no_color_brightness_color_temp_white_val_if_no_topics(self): \
            # pylint: disable=invalid-name
        """Test for no RGB, brightness, color temp, effect, white val or XY."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(40, state.attributes.get(ATTR_SUPPORTED_FEATURES))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb', '{"state":"ON"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))

    def test_controlling_state_via_topic(self): \
            # pylint: disable=invalid-name
        """Test the controlling of the state via topic."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_temp': True,
                'effect': True,
                'rgb': True,
                'white_value': True,
                'xy': True,
                'qos': '0'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(255, state.attributes.get(ATTR_SUPPORTED_FEATURES))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255,'
                          '"x":0.123,"y":0.123},'
                          '"brightness":255,'
                          '"color_temp":155,'
                          '"effect":"colorloop",'
                          '"white_value":150}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(155, state.attributes.get('color_temp'))
        self.assertEqual('colorloop', state.attributes.get('effect'))
        self.assertEqual(150, state.attributes.get('white_value'))
        self.assertEqual([0.123, 0.123], state.attributes.get('xy_color'))

        # Turn the light off
        fire_mqtt_message(self.hass, 'test_light_rgb', '{"state":"OFF"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"brightness":100}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100,
                         light_state.attributes['brightness'])

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":125,"g":125,"b":125}}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([125, 125, 125],
                         light_state.attributes.get('rgb_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"x":0.135,"y":0.135}}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([0.135, 0.135],
                         light_state.attributes.get('xy_color'))

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color_temp":155}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual(155, light_state.attributes.get('color_temp'))

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"effect":"colorloop"}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual('colorloop', light_state.attributes.get('effect'))

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"white_value":155}')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual(155, light_state.attributes.get('white_value'))

    def test_sending_mqtt_commands_and_optimistic(self): \
            # pylint: disable=invalid-name
        """Test the sending of command in optimistic mode."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_temp': True,
                'effect': True,
                'rgb': True,
                'white_value': True,
                'qos': 2
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(191, state.attributes.get(ATTR_SUPPORTED_FEATURES))
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', '{"state": "ON"}', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', '{"state": "OFF"}', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test',
                      brightness=50, color_temp=155, effect='colorloop',
                      white_value=170)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(2, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-2][1][1])
        self.assertEqual(50, message_json["brightness"])
        self.assertEqual(155, message_json["color_temp"])
        self.assertEqual('colorloop', message_json["effect"])
        self.assertEqual(170, message_json["white_value"])
        self.assertEqual("ON", message_json["state"])

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(50, state.attributes['brightness'])
        self.assertEqual(155, state.attributes['color_temp'])
        self.assertEqual('colorloop', state.attributes['effect'])
        self.assertEqual(170, state.attributes['white_value'])

    def test_flash_short_and_long(self): \
            # pylint: disable=invalid-name
        """Test for flash length being sent when included."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'flash_time_short': 5,
                'flash_time_long': 15,
                'qos': 0
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(40, state.attributes.get(ATTR_SUPPORTED_FEATURES))

        light.turn_on(self.hass, 'light.test', flash="short")
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-2][1][1])
        self.assertEqual(5, message_json["flash"])
        self.assertEqual("ON", message_json["state"])

        light.turn_on(self.hass, 'light.test', flash="long")
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-2][1][1])
        self.assertEqual(15, message_json["flash"])
        self.assertEqual("ON", message_json["state"])

    def test_transition(self):
        """Test for transition time being sent when included."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'qos': 0
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(40, state.attributes.get(ATTR_SUPPORTED_FEATURES))

        light.turn_on(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-2][1][1])
        self.assertEqual(10, message_json["transition"])
        self.assertEqual("ON", message_json["state"])

        # Transition back off
        light.turn_off(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-2][1][1])
        self.assertEqual(10, message_json["transition"])
        self.assertEqual("OFF", message_json["state"])

    def test_brightness_scale(self):
        """Test for brightness scaling."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_bright_scale',
                'command_topic': 'test_light_bright_scale/set',
                'brightness': True,
                'brightness_scale': 99
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light
        fire_mqtt_message(self.hass, 'test_light_bright_scale',
                          '{"state":"ON"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))

        # Turn on the light with brightness
        fire_mqtt_message(self.hass, 'test_light_bright_scale',
                          '{"state":"ON",'
                          '"brightness": 99}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))

    def test_invalid_color_brightness_and_white_values(self): \
            # pylint: disable=invalid-name
        """Test that invalid color/brightness/white values are ignored."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'rgb': True,
                'white_value': True,
                'qos': '0'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertEqual(185, state.attributes.get(ATTR_SUPPORTED_FEATURES))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255},'
                          '"brightness": 255,'
                          '"white_value": 255}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(255, state.attributes.get('white_value'))

        # Bad color values
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":"bad","g":"val","b":"test"}}')
        self.hass.block_till_done()

        # Color should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))

        # Bad brightness values
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"brightness": "badValue"}')
        self.hass.block_till_done()

        # Brightness should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))

        # Bad white value
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"white_value": "badValue"}')
        self.hass.block_till_done()

        # White value should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('white_value'))

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
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
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
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
