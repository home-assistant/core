"""The tests for the MQTT JSON light platform.

Configuration example with all features:

light:
  platform: mqtt_json
  name: "Office Light"
  state_topic: "office/light/status"
  command_topic: "office/light/set"
  brightness: true
  color_space: rgb
  color_temp: true
  transition: true
  flash: true
  flash_time_short: 2
  flash_time_long: 10
  effect_list:
    - colorloop
    - random
    - white

If your light doesn't support brightness, omit `brightness` or set it to false.
Same goes for `color_temp`, `transition` and `flash`.

If your light only supports xy color values, set `color_space` to `xy`.

If your light doesn't support effects, omit `effect_list`.
"""
import json
import unittest

from homeassistant.bootstrap import setup_component
from homeassistant.const import STATE_ON, STATE_OFF, ATTR_ASSUMED_STATE
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
        self.hass.config.components = set(['mqtt'])
        with assert_setup_component(0):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_json',
                    'name': 'test',
                }
            })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_no_features_if_no_config(self): \
            # pylint: disable=invalid-name
        """Test if there are no state attributes if the features aren't enabled
        """
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light',
                'command_topic': 'test_light/set',
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))

        fire_mqtt_message(self.hass, 'test_light', '{"state":"ON"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))

    def test_controlling_state_via_topic(self): \
            # pylint: disable=invalid-name
        """Test the controlling of the state via topic."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_space': 'rgb',
                'qos': '0'
            }
        })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('xy_color'))
        self.assertIsNone(state.attributes.get(ATTR_ASSUMED_STATE))

        # Turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255},'
                          '"brightness":255}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))

        # Turn the light off
        fire_mqtt_message(self.hass, 'test_light_rgb', '{"state":"OFF"}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"brightness":100}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100, state.attributes['brightness'])

        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":125,"g":125,"b":125}}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual([125, 125, 125], state.attributes.get('rgb_color'))

    def test_sending_mqtt_commands_and_optimistic(self): \
            # pylint: disable=invalid-name
        """Test the sending of command in optimistic mode."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_space': 'rgb',
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

        light.turn_on(self.hass, 'light.test', rgb_color=(75, 75, 75),
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
        self.assertEqual([75, 75, 75], state.attributes['rgb_color'])
        self.assertEqual(50, state.attributes['brightness'])

    def test_rgb_color_conversion(self):
        """Test for color conversion of rgb light."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test_rgb',
                'command_topic': 'test_light_rgb/set',
                'color_space': 'rgb'
            }
        })

        # check rgb white
        light.turn_on(self.hass, 'light.test_rgb', rgb_color=[255, 255, 255])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_rgb')
        self.assertEqual([255, 255, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.32, 0.336],
                         state.attributes.get('xy_color'))

        # check rgb color
        light.turn_on(self.hass, 'light.test_rgb', rgb_color=[24, 108, 243])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_rgb')
        self.assertEqual([24, 108, 243],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.144, 0.12],
                         state.attributes.get('xy_color'))

        # check xy color
        light.turn_on(self.hass, 'light.test_rgb', xy_color=[0.16, 0.11])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_rgb')
        self.assertEqual([46, 120, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.16, 0.11],
                         state.attributes.get('xy_color'))

        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(46, message_json["color"]["r"])
        self.assertEqual(120, message_json["color"]["g"])
        self.assertEqual(255, message_json["color"]["b"])

    def test_rgb_mqtt_message_color_conversion(self): \
            # pylint: disable=invalid-name
        """Test for MQTT color conversion of rgb light."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test_rgb',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'color_space': 'rgb'
            }
        })

        # check rgb white from light
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255}}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_rgb')
        self.assertEqual([255, 255, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.32, 0.336],
                         state.attributes.get('xy_color'))

        # check xy color from light
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          '{"state":"ON",'
                          '"color":{"x":0.16,"y":0.11}}')
        self.hass.block_till_done()

        # color should not have changed
        state = self.hass.states.get('light.test_rgb')
        self.assertEqual([255, 255, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.32, 0.336],
                         state.attributes.get('xy_color'))

    def test_xy_color_conversion(self):
        """Test for color conversion of xy light."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test_xy',
                'command_topic': 'test_light_xy/set',
                'color_space': 'xy',
                'qos': 2
            }
        })

        # check xy color
        light.turn_on(self.hass, 'light.test_xy', xy_color=[0.16, 0.11])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_xy')
        self.assertEqual([46, 120, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.16, 0.11],
                         state.attributes.get('xy_color'))

        # check rgb white
        light.turn_on(self.hass, 'light.test_xy', rgb_color=[255, 255, 255])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_xy')
        self.assertEqual([255, 255, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.32, 0.336],
                         state.attributes.get('xy_color'))

        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(0.32, message_json["color"]["x"])
        self.assertEqual(0.336, message_json["color"]["y"])

        # check rgb color
        light.turn_on(self.hass, 'light.test_xy', rgb_color=[24, 108, 243])
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_xy')
        self.assertEqual([24, 108, 243],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.144, 0.12],
                         state.attributes.get('xy_color'))

        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(0.144, message_json["color"]["x"])
        self.assertEqual(0.12, message_json["color"]["y"])

    def test_xy_mqtt_message_color_conversion(self): \
            # pylint: disable=invalid-name
        """Test for MQTT color conversion of xy light."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test_xy',
                'state_topic': 'test_light_xy',
                'command_topic': 'test_light_xy/set',
                'color_space': 'xy'
            }
        })

        # check xy color from light
        fire_mqtt_message(self.hass, 'test_light_xy',
                          '{"state":"ON",'
                          '"color":{"x":0.16,"y":0.11}}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test_xy')
        self.assertEqual([46, 120, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.16, 0.11],
                         state.attributes.get('xy_color'))

        # check rgb white from light
        fire_mqtt_message(self.hass, 'test_light_xy',
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255}}')
        self.hass.block_till_done()

        # color should not have changed
        state = self.hass.states.get('light.test_xy')
        self.assertEqual([46, 120, 255],
                         state.attributes.get('rgb_color'))
        self.assertEqual([0.16, 0.11],
                         state.attributes.get('xy_color'))

    def test_flash_short_and_long(self):
        """Test for flash length being sent when included."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'flash': True,
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
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'transition': True,
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

    def test_color_temp(self):
        """Test for color_temp beign sent when included."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'color_space': 'rgb',
                'color_temp': True,
            }
        })

        light.turn_on(self.hass, 'light.test', color_temp=254)
        self.hass.block_till_done()

        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual(254, message_json["color_temp"])

    def test_effect(self):
        """Test for effect beign sent when included."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'effect_list': ['random']
            }
        })

        # test valid effect
        light.turn_on(self.hass, 'light.test', effect='random')
        self.hass.block_till_done()

        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertEqual('random', message_json["effect"])

        # test invalid effect
        light.turn_on(self.hass, 'light.test', effect='colorloop')
        self.hass.block_till_done()

        # effect should have been reset
        message_json = json.loads(self.mock_publish.mock_calls[-1][1][1])
        self.assertIsNone(message_json.get("effect"))

    def test_invalid_rgb_and_brightness_values(self): \
            # pylint: disable=invalid-name
        """Test that invalid rgb/brightness values are ignored."""
        self.hass.config.components = set(['mqtt'])
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_json',
                'name': 'test',
                'state_topic': 'test_light_rgb',
                'command_topic': 'test_light_rgb/set',
                'brightness': True,
                'color_space': 'rgb',
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
                          '{"state":"ON",'
                          '"color":{"r":255,"g":255,"b":255},'
                          '"brightness": 255}')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))

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
