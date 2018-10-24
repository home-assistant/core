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
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
import homeassistant.components.light as light
import homeassistant.core as ha

from tests.common import (
    get_test_home_assistant, mock_mqtt_component, fire_mqtt_message,
    assert_setup_component, mock_coro)
from tests.components.light import common


class TestLightMQTTTemplate(unittest.TestCase):
    """Test the MQTT Template light."""

    def setUp(self):  # pylint: disable=invalid-name
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.mock_publish = mock_mqtt_component(self.hass)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_fails(self):
        """Test that setup fails with missing required configuration items."""
        with assert_setup_component(0, light.DOMAIN):
            assert setup_component(self.hass, light.DOMAIN, {
                light.DOMAIN: {
                    'platform': 'mqtt_template',
                    'name': 'test',
                }
            })
        assert self.hass.states.get('light.test') is None

    def test_state_change_via_topic(self):
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
        assert STATE_OFF == state.state
        assert state.attributes.get('rgb_color') is None
        assert state.attributes.get('brightness') is None
        assert state.attributes.get('color_temp') is None
        assert state.attributes.get('white_value') is None
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

        fire_mqtt_message(self.hass, 'test_light_rgb', 'on')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state
        assert state.attributes.get('rgb_color') is None
        assert state.attributes.get('brightness') is None
        assert state.attributes.get('color_temp') is None
        assert state.attributes.get('white_value') is None

    def test_state_brightness_color_effect_temp_white_change_via_topic(self):
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
        assert STATE_OFF == state.state
        assert state.attributes.get('rgb_color') is None
        assert state.attributes.get('brightness') is None
        assert state.attributes.get('effect') is None
        assert state.attributes.get('color_temp') is None
        assert state.attributes.get('white_value') is None
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

        # turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,255,145,123,255-128-64,')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state
        assert (255, 128, 63) == state.attributes.get('rgb_color')
        assert 255 == state.attributes.get('brightness')
        assert 145 == state.attributes.get('color_temp')
        assert 123 == state.attributes.get('white_value')
        assert state.attributes.get('effect') is None

        # turn the light off
        fire_mqtt_message(self.hass, 'test_light_rgb', 'off')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_OFF == state.state

        # lower the brightness
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,100')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        assert 100 == light_state.attributes['brightness']

        # change the color temp
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,195')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        assert 195 == light_state.attributes['color_temp']

        # change the color
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,,41-42-43')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        assert (243, 249, 255) == \
            light_state.attributes.get('rgb_color')

        # change the white value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,134')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        self.hass.block_till_done()
        assert 134 == light_state.attributes['white_value']

        # change the effect
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,,,,41-42-43,rainbow')
        self.hass.block_till_done()

        light_state = self.hass.states.get('light.test')
        assert 'rainbow' == light_state.attributes.get('effect')

    def test_optimistic(self):
        """Test optimistic mode."""
        fake_state = ha.State('light.test', 'on', {'brightness': 95,
                                                   'hs_color': [100, 100],
                                                   'effect': 'random',
                                                   'color_temp': 100,
                                                   'white_value': 50})

        with patch('homeassistant.components.light.mqtt_template'
                   '.async_get_last_state',
                   return_value=mock_coro(fake_state)):
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
                        'effect_list': ['colorloop', 'random'],
                        'effect_command_topic': 'test_light_rgb/effect/set',
                        'qos': 2
                    }
                })

        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state
        assert 95 == state.attributes.get('brightness')
        assert (100, 100) == state.attributes.get('hs_color')
        assert 'random' == state.attributes.get('effect')
        assert 100 == state.attributes.get('color_temp')
        assert 50 == state.attributes.get('white_value')
        assert state.attributes.get(ATTR_ASSUMED_STATE)

        # turn on the light
        common.turn_on(self.hass, 'light.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,,,,--', 2, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state

        # turn the light off
        common.turn_off(self.hass, 'light.test')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'off', 2, False)
        self.mock_publish.async_publish.reset_mock()
        state = self.hass.states.get('light.test')
        assert STATE_OFF == state.state

        # turn on the light with brightness, color
        common.turn_on(self.hass, 'light.test', brightness=50,
                       rgb_color=[75, 75, 75])
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,50,,,50-50-50', 2, False)
        self.mock_publish.async_publish.reset_mock()

        # turn on the light with color temp and white val
        common.turn_on(self.hass, 'light.test',
                       color_temp=200, white_value=139)
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,,200,139,--', 2, False)

        # check the state
        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state
        assert (255, 255, 255) == state.attributes['rgb_color']
        assert 50 == state.attributes['brightness']
        assert 200 == state.attributes['color_temp']
        assert 139 == state.attributes['white_value']

    def test_flash(self):
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
        assert STATE_OFF == state.state

        # short flash
        common.turn_on(self.hass, 'light.test', flash='short')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,short', 0, False)
        self.mock_publish.async_publish.reset_mock()

        # long flash
        common.turn_on(self.hass, 'light.test', flash='long')
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,long', 0, False)

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
        assert STATE_OFF == state.state

        # transition on
        common.turn_on(self.hass, 'light.test', transition=10)
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'on,10', 0, False)
        self.mock_publish.async_publish.reset_mock()

        # transition off
        common.turn_off(self.hass, 'light.test', transition=4)
        self.hass.block_till_done()

        self.mock_publish.async_publish.assert_called_once_with(
            'test_light_rgb/set', 'off,4', 0, False)

    def test_invalid_values(self):
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
        assert STATE_OFF == state.state
        assert state.attributes.get('rgb_color') is None
        assert state.attributes.get('brightness') is None
        assert state.attributes.get('color_temp') is None
        assert state.attributes.get('effect') is None
        assert state.attributes.get('white_value') is None
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

        # turn on the light, full white
        fire_mqtt_message(self.hass, 'test_light_rgb',
                          'on,255,215,222,255-255-255,rainbow')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state
        assert 255 == state.attributes.get('brightness')
        assert 215 == state.attributes.get('color_temp')
        assert (255, 255, 255) == state.attributes.get('rgb_color')
        assert 222 == state.attributes.get('white_value')
        assert 'rainbow' == state.attributes.get('effect')

        # bad state value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'offf')
        self.hass.block_till_done()

        # state should not have changed
        state = self.hass.states.get('light.test')
        assert STATE_ON == state.state

        # bad brightness values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,off,255-255-255')
        self.hass.block_till_done()

        # brightness should not have changed
        state = self.hass.states.get('light.test')
        assert 255 == state.attributes.get('brightness')

        # bad color temp values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,off,255-255-255')
        self.hass.block_till_done()

        # color temp should not have changed
        state = self.hass.states.get('light.test')
        assert 215 == state.attributes.get('color_temp')

        # bad color values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,255,a-b-c')
        self.hass.block_till_done()

        # color should not have changed
        state = self.hass.states.get('light.test')
        assert (255, 255, 255) == state.attributes.get('rgb_color')

        # bad white value values
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,,,off,255-255-255')
        self.hass.block_till_done()

        # white value should not have changed
        state = self.hass.states.get('light.test')
        assert 222 == state.attributes.get('white_value')

        # bad effect value
        fire_mqtt_message(self.hass, 'test_light_rgb', 'on,255,a-b-c,white')
        self.hass.block_till_done()

        # effect should not have changed
        state = self.hass.states.get('light.test')
        assert 'rainbow' == state.attributes.get('effect')

    def test_default_availability_payload(self):
        """Test availability by default payload with defined topic."""
        assert setup_component(self.hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'command_on_template': 'on,{{ transition }}',
                'command_off_template': 'off,{{ transition|d }}',
                'availability_topic': 'availability-topic'
            }
        })

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'online')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'offline')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE == state.state

    def test_custom_availability_payload(self):
        """Test availability by custom payload with defined topic."""
        assert setup_component(self.hass, light.DOMAIN, {
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
        })

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE == state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'good')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE != state.state

        fire_mqtt_message(self.hass, 'availability-topic', 'nogood')
        self.hass.block_till_done()

        state = self.hass.states.get('light.test')
        assert STATE_UNAVAILABLE == state.state
