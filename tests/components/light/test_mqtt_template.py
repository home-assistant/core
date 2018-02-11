"""The tests for the MQTT Template light platform.

Configuration example with all features:

light:
  platform: mqtt_template
  name: mqtt_template_light_1
  state_topic: 'home/rgb1'
  command_topic: 'home/rgb1/set'
  command_on_template: >
    on,{{ brightness|d }},{{ red|d }}-{{ green|d }}-{{ blue|d }}
  command_off_template: 'off'
  state_template: '{{ value.split(",")[0] }}'
  brightness_template: '{{ value.split(",")[1] }}'
  color_temp_template: '{{ value.split(",")[2] }}'
  white_value_template: '{{ value.split(",")[3] }}'
  red_template: '{{ value.split(",")[4].split("-")[0] }}'
  green_template: '{{ value.split(",")[4].split("-")[1] }}'
  blue_template: '{{ value.split(",")[4].split("-")[2] }}'

If your light doesn't support brightness feature, omit `brightness_template`.

If your light doesn't support color temp feature, omit `color_temp_template`.

If your light doesn't support white value feature, omit `white_value_template`.

If your light doesn't support RGB feature, omit `(red|green|blue)_template`.
"""
import unittest

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
import homeassistant.components.light as light
from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message,
    assert_setup_component)


class TestLightMQTTTemplate(unittest.TestCase):
    """Test the MQTT Template light."""

    def setUp(self):  # pylint: disable=invalid-name
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_fails(self): \
            # pylint: disable=invalid-name
        """Test that setup fails with missing required configuration items."""
        with assert_setup_component(0, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                }
            })
        self.assertIsNone(self.hass.states.get('light.test'))

    def test_state_change_via_topic(self): \
            # pylint: disable=invalid-name
        """Test state change via topic."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'state_topic': 'test_light_rgb',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,'
                                           '{{ brightness|d }},'
                                           '{{ color_temp|d }},'
                                           '{{ white_value|d }},'
                                           '{{ red|d }}-'
                                           '{{ green|d }}-'
                                           '{{ blue|d }}',
                    'command_off_template': 'off',
                    'state_template': '{{ value.split(",")[0] }}'
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        fire_mqtt_message(self.hass, 'test_light_rgb', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('white_value'))

    def test_state_brightness_color_effect_temp_white_change_via_topic(self): \
            # pylint: disable=invalid-name
        """Test state, bri, color, effect, color temp, white val change."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'effect_list': ['rainbow', 'colorloop'],
                    'state_topic': 'test_light_rgb',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,'
                                           '{{ brightness|d }},'
                                           '{{ color_temp|d }},'
                                           '{{ white_value|d }},'
                                           '{{ red|d }}-'
                                           '{{ green|d }}-'
                                           '{{ blue|d }},'
                                           '{{ effect|d }}',
                    'command_off_template': 'off',
                    'state_template': '{{ value.split(",")[0] }}',
                    'brightness_template': '{{ value.split(",")[1] }}',
                    'color_temp_template': '{{ value.split(",")[2] }}',
                    'white_value_template': '{{ value.split(",")[3] }}',
                    'red_template': '{{ value.split(",")[4].'
                                    'split("-")[0] }}',
                    'green_template': '{{ value.split(",")[4].'
                                      'split("-")[1] }}',
                    'blue_template': '{{ value.split(",")[4].'
                                     'split("-")[2] }}',
                    'effect_template': '{{ value.split(",")[5] }}'
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        # turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,255,145,123,255-128-64,')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual([255, 128, 64], state.attributes.get('rgb_color'))
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(145, state.attributes.get('color_temp'))
        self.assertEqual(123, state.attributes.get('white_value'))
        self.assertIsNone(state.attributes.get('effect'))

        # turn the light off
        fire_mqtt_message(self.hass, 'test_light_rgb', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        # lower the brightness
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,100')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(100, light_state.attributes['brightness'])

        # change the color temp
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,195')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(195, light_state.attributes['color_temp'])

        # change the color
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,,41-42-43')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual([41, 42, 43], light_state.attributes.get('rgb_color'))

        # change the white value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,134')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        self.assertEqual(134, light_state.attributes['white_value'])

        # change the effect
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,,,,41-42-43,rainbow')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.assertEqual('rainbow', light_state.attributes.get('effect'))

    def test_optimistic(self): \
            # pylint: disable=invalid-name
        """Test optimistic mode."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,'
                                           '{{ brightness|d }},'
                                           '{{ color_temp|d }},'
                                           '{{ white_value|d }},'
                                           '{{ red|d }}-'
                                           '{{ green|d }}-'
                                           '{{ blue|d }}',
                    'command_off_template': 'off',
                    'qos': 2
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertTrue(state.attributes.get(ATTR_ASSUMED_STATE))

        # turn on the light
        light.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'on,,,,--', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        # turn the light off
        light.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.assertEqual(('test_light_rgb/set', 'off', 2, False),
                         self.mock_publish.mock_calls[-2][1])
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        # turn on the light with brightness, color
        light.turn_on(self.hass, 'light.test', brightness=50,
                      rgb_color=[75, 75, 75])
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])

        # check the payload
        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('on,50,,,75-75-75', payload)

        # turn on the light with color temp and white val
        light.turn_on(self.hass, 'light.test', color_temp=200, white_value=139)
        self.hass.block_till_done()

        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('on,,200,139,--', payload)

        self.assertEqual(2, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])

        # check the state
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual((75, 75, 75), state.attributes['rgb_color'])
        self.assertEqual(50, state.attributes['brightness'])
        self.assertEqual(200, state.attributes['color_temp'])
        self.assertEqual(139, state.attributes['white_value'])

    def test_flash(self): \
            # pylint: disable=invalid-name
        """Test flash."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,{{ flash }}',
                    'command_off_template': 'off',
                    'qos': 0
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        # short flash
        light.turn_on(self.hass, 'light.test', flash='short')
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])

        # check the payload
        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('on,short', payload)

        # long flash
        light.turn_on(self.hass, 'light.test', flash='long')
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])

        # check the payload
        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('on,long', payload)

    def test_transition(self):
        """Test for transition time being sent when included."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,{{ transition }}',
                    'command_off_template': 'off,{{ transition|d }}'
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)

        # transition on
        light.turn_on(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])

        # check the payload
        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('on,10', payload)

        # transition off
        light.turn_off(self.hass, 'light.test', transition=4)
        self.hass.block_till_done()

        self.assertEqual('test_light_rgb/set',
                         self.mock_publish.mock_calls[-2][1][0])
        self.assertEqual(0, self.mock_publish.mock_calls[-2][1][2])
        self.assertEqual(False, self.mock_publish.mock_calls[-2][1][3])

        # check the payload
        payload = self.mock_publish.mock_calls[-2][1][1]
        self.assertEqual('off,4', payload)

    def test_invalid_values(self): \
            # pylint: disable=invalid-name
        """Test that invalid values are ignored."""
        with assert_setup_component(1, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                    'effect_list': ['rainbow', 'colorloop'],
                    'state_topic': 'test_light_rgb',
                    'command_topic': 'test_light_rgb/set',
                    'command_on_template': 'on,'
                                           '{{ brightness|d }},'
                                           '{{ color_temp|d }},'
                                           '{{ red|d }}-'
                                           '{{ green|d }}-'
                                           '{{ blue|d }},'
                                           '{{ effect|d }}',
                    'command_off_template': 'off',
                    'state_template': '{{ value.split(",")[0] }}',
                    'brightness_template': '{{ value.split(",")[1] }}',
                    'color_temp_template': '{{ value.split(",")[2] }}',
                    'white_value_template': '{{ value.split(",")[3] }}',
                    'red_template': '{{ value.split(",")[4].'
                                    'split("-")[0] }}',
                    'green_template': '{{ value.split(",")[4].'
                                      'split("-")[1] }}',
                    'blue_template': '{{ value.split(",")[4].'
                                     'split("-")[2] }}',
                    'effect_template': '{{ value.split(",")[5] }}',
                }
            })

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_OFF, state.state)
        self.assertIsNone(state.attributes.get('rgb_color'))
        self.assertIsNone(state.attributes.get('brightness'))
        self.assertIsNone(state.attributes.get('color_temp'))
        self.assertIsNone(state.attributes.get('effect'))
        self.assertIsNone(state.attributes.get('white_value'))
        self.assertFalse(state.attributes.get(ATTR_ASSUMED_STATE))

        # turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,255,215,222,255-255-255,rainbow')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)
        self.assertEqual(255, state.attributes.get('brightness'))
        self.assertEqual(215, state.attributes.get('color_temp'))
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))
        self.assertEqual(222, state.attributes.get('white_value'))
        self.assertEqual('rainbow', state.attributes.get('effect'))

        # bad state value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'offf')
        self.hass.block_till_done()

        # state should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(STATE_ON, state.state)

        # bad brightness values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,off,255-255-255')
        self.hass.block_till_done()

        # brightness should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(255, state.attributes.get('brightness'))

        # bad color temp values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,off,255-255-255')
        self.hass.block_till_done()

        # color temp should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(215, state.attributes.get('color_temp'))

        # bad color values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,255,a-b-c')
        self.hass.block_till_done()

        # color should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual([255, 255, 255], state.attributes.get('rgb_color'))

        # bad white value values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,off,255-255-255')
        self.hass.block_till_done()

        # white value should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual(222, state.attributes.get('white_value'))

        # bad effect value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,255,a-b-c,white')
        self.hass.block_till_done()

        # effect should not have changed
        state = self.hass.states.get('light.test')
        self.assertEqual('rainbow', state.attributes.get('effect'))

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        self.assertTrue(setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'command_on_template': 'on,{{ transition }}',
                'command_off_template': 'off,{{ transition|d }}',
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
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'command_on_template': 'on,{{ transition }}',
                'command_off_template': 'off,{{ transition|d }}',
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
