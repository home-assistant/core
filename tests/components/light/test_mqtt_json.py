"""The tests for the MQTT JSON light platform.

Configuration for RGB Version with brightness:

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
"""
import json
import unittest

from homeassistant.bootstrap import _setup_component
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ASSUMED_STATE
import homeassistant.components.light as light
from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message)


class TestLightMQTTJSON(unittest.TestCase):
    """Test the MQTT JSON light."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_fail_setup_if_no_command_topic(self):
        """Test if setup fails with no command topic."""
        self.hass.config.components = ['mqtt']
        assert not _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
            }
        })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_no_color_or_brightness_if_no_config(self):
        """Test if there is no color and brightness if they aren't defined."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))

        fire_mqtt_message(self.hass, 'test_light_rgb', '{"state":"ON"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))

    def test_controlling_state_via_topic(self):
        """Test the controlling of the state via topic."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'rgb': True,
                'qos': '0'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"color":{"r":255,"g":255,"b":255},' +
                          '"brightness":255}'
                          )
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))

        # Turn the light off
        fire_mqtt_message(self.hass, 'test_light_rgb', '{"state":"OFF"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"brightness":100}'
                          )
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100,
                         light_state.attributes['brightness'])

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"color":{"r":125,"g":125,"b":125}}'
                          )
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([125, 125, 125],
                         light_state.attributes.get('rgb_color'))

    def test_sending_mqtt_commands_and_optimistic(self):
        """Test the sending of command in optimistic mode."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'rgb': True,
                'qos': 2
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', '{"state": "ON"}', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', '{"state": "OFF"}', 2, False),
                         self.mock_publish.mock_calls[-1][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        light.turn_on(self.hass, 'light.test', rgb_color=[75, 75, 75],
                      brightness=50)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-1][1][0])
        self.assertEqual(2, self.mock_publish.mock_calls[-1][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-1][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(50, message_json["brightness"])
        self.assertEqual(75, message_json["color"]["r"])
        self.assertEqual(75, message_json["color"]["g"])
        self.assertEqual(75, message_json["color"]["b"])
        self.assertEqual("ON", message_json["state"])

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual((75, 75, 75), state.attributes['rgb_color'])
        self.assertEqual(50, state.attributes['brightness'])

    def test_flash_short_and_long(self):
        """Test for flash length being sent when included."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
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

        light.turn_on(self.hass, 'light.test', flash="short")
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-1][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-1][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-1][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(5, message_json["flash"])
        self.assertEqual("ON", message_json["state"])

        light.turn_on(self.hass, 'light.test', flash="long")
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-1][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-1][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-1][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(15, message_json["flash"])
        self.assertEqual("ON", message_json["state"])

    def test_transition(self):
        """Test for transition time being sent when included."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
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

        light.turn_on(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-1][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-1][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-1][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(10, message_json["transition"])
        self.assertEqual("ON", message_json["state"])

        # Transition back off
        light.turn_off(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-1][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-1][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-1][1][3])
        # Get the sent message
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(10, message_json["transition"])
        self.assertEqual("OFF", message_json["state"])

    def test_invalid_color_and_brightness_values(self):
        """Test that invalid color/brightness values are ignored."""
        self.hass.config.components = ['mqtt']
        assert _setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'rgb': True,
                'qos': '0'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"color":{"r":255,"g":255,"b":255},' +
                          '"brightness": 255}'
                          )
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))

        # Bad color values
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"color":{"r":"bad","g":"val","b":"test"}}'
                          )
        self.hass.block_till_done()

        # Color should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))

        # Bad brightness values
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",' +
                          '"brightness": "badValue"}'
                          )
        self.hass.block_till_done()

        # Brightness should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))
