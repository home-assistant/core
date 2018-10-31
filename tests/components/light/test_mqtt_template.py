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
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE)
import homeassistant.components.light as light
import homeassistant.core as ha

from tests.common import (
    async_fire_mqtt_message, assert_setup_component, mock_coro)


async def test_setup_fails(hass, mqtt_mock):
    """Test that setup fails with missing required configuration items."""
    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
            }
        })
    assert hass.states.get('light.test') is None


async def test_state_change_via_topic(hass, mqtt_mock):
    """Test state change via topic."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
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

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('white_value') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, 'test_light_rgb', 'on')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('white_value') is None


async def test_state_brightness_color_effect_temp_white_change_via_topic(
        hass, mqtt_mock):
    """Test state, bri, color, effect, color temp, white val change."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
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

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('white_value') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # turn on the light, full white
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            'on,255,145,123,255-128-64,')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert (255, 128, 63) == state.attributes.get('rgb_color')
    assert 255 == state.attributes.get('brightness')
    assert 145 == state.attributes.get('color_temp')
    assert 123 == state.attributes.get('white_value')
    assert state.attributes.get('effect') is None

    # turn the light off
    async_fire_mqtt_message(hass, 'test_light_rgb', 'off')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state

    # lower the brightness
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,100')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 100 == light_state.attributes['brightness']

    # change the color temp
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,,195')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 195 == light_state.attributes['color_temp']

    # change the color
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,,,,41-42-43')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert (243, 249, 255) == \
        light_state.attributes.get('rgb_color')

    # change the white value
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,,,134')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 134 == light_state.attributes['white_value']

    # change the effect
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            'on,,,,41-42-43,rainbow')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 'rainbow' == light_state.attributes.get('effect')


async def test_optimistic(hass, mqtt_mock):
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
            assert await async_setup_component(hass, light.DOMAIN, {
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

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 95 == state.attributes.get('brightness')
    assert (100, 100) == state.attributes.get('hs_color')
    assert 'random' == state.attributes.get('effect')
    assert 100 == state.attributes.get('color_temp')
    assert 50 == state.attributes.get('white_value')
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_flash(hass, mqtt_mock):
    """Test flash."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'command_on_template': 'on,{{ flash }}',
                'command_off_template': 'off',
                'qos': 0
            }
        })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state


async def test_transition(hass, mqtt_mock):
    """Test for transition time being sent when included."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt_template',
                'name': 'test',
                'command_topic': 'test_light_rgb/set',
                'command_on_template': 'on,{{ transition }}',
                'command_off_template': 'off,{{ transition|d }}'
            }
        })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state


async def test_invalid_values(hass, mqtt_mock):
    """Test that invalid values are ignored."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(hass, light.DOMAIN, {
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

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # turn on the light, full white
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            'on,255,215,222,255-255-255,rainbow')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 255 == state.attributes.get('brightness')
    assert 215 == state.attributes.get('color_temp')
    assert (255, 255, 255) == state.attributes.get('rgb_color')
    assert 222 == state.attributes.get('white_value')
    assert 'rainbow' == state.attributes.get('effect')

    # bad state value
    async_fire_mqtt_message(hass, 'test_light_rgb', 'offf')
    await hass.async_block_till_done()

    # state should not have changed
    state = hass.states.get('light.test')
    assert STATE_ON == state.state

    # bad brightness values
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,off,255-255-255')
    await hass.async_block_till_done()

    # brightness should not have changed
    state = hass.states.get('light.test')
    assert 255 == state.attributes.get('brightness')

    # bad color temp values
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,,off,255-255-255')
    await hass.async_block_till_done()

    # color temp should not have changed
    state = hass.states.get('light.test')
    assert 215 == state.attributes.get('color_temp')

    # bad color values
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,255,a-b-c')
    await hass.async_block_till_done()

    # color should not have changed
    state = hass.states.get('light.test')
    assert (255, 255, 255) == state.attributes.get('rgb_color')

    # bad white value values
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,,,off,255-255-255')
    await hass.async_block_till_done()

    # white value should not have changed
    state = hass.states.get('light.test')
    assert 222 == state.attributes.get('white_value')

    # bad effect value
    async_fire_mqtt_message(hass, 'test_light_rgb', 'on,255,a-b-c,white')
    await hass.async_block_till_done()

    # effect should not have changed
    state = hass.states.get('light.test')
    assert 'rainbow' == state.attributes.get('effect')


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt_template',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'command_on_template': 'on,{{ transition }}',
            'command_off_template': 'off,{{ transition|d }}',
            'availability_topic': 'availability-topic'
        }
    })

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability-topic', 'online')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE != state.state

    async_fire_mqtt_message(hass, 'availability-topic', 'offline')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE == state.state


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
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

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE == state.state

    async_fire_mqtt_message(hass, 'availability-topic', 'good')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE != state.state

    async_fire_mqtt_message(hass, 'availability-topic', 'nogood')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_UNAVAILABLE == state.state
