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
from unittest.mock import patch

from homeassistant.setup import async_setup_component
from homeassistant.const import (
    STATE_ON, STATE_OFF, STATE_UNAVAILABLE, ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES)
from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.discovery import async_start
import homeassistant.core as ha

from tests.common import mock_coro, async_fire_mqtt_message, MockConfigEntry


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if setup fails with no command topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
        }
    })
    assert hass.states.get('light.test') is None


async def test_no_color_brightness_color_temp_white_val_if_no_topics(
        hass, mqtt_mock):
    """Test for no RGB, brightness, color temp, effect, white val or XY."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert 40 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None

    async_fire_mqtt_message(hass, 'test_light_rgb', '{"state":"ON"}')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling of the state via topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'color_temp': True,
            'effect': True,
            'rgb': True,
            'white_value': True,
            'xy': True,
            'hs': True,
            'qos': '0'
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert 191 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('color_temp') is None
    assert state.attributes.get('effect') is None
    assert state.attributes.get('white_value') is None
    assert state.attributes.get('xy_color') is None
    assert state.attributes.get('hs_color') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light, full white
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":255,"g":255,"b":255},'
                            '"brightness":255,'
                            '"color_temp":155,'
                            '"effect":"colorloop",'
                            '"white_value":150}')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert (255, 255, 255) == state.attributes.get('rgb_color')
    assert 255 == state.attributes.get('brightness')
    assert 155 == state.attributes.get('color_temp')
    assert 'colorloop' == state.attributes.get('effect')
    assert 150 == state.attributes.get('white_value')
    assert (0.323, 0.329) == state.attributes.get('xy_color')
    assert (0.0, 0.0) == state.attributes.get('hs_color')

    # Turn the light off
    async_fire_mqtt_message(hass, 'test_light_rgb', '{"state":"OFF"}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "brightness":100}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')

    assert 100 == \
        light_state.attributes['brightness']

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", '
                            '"color":{"r":125,"g":125,"b":125}}')
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert (255, 255, 255) == \
        light_state.attributes.get('rgb_color')

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color":{"x":0.135,"y":0.135}}')
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert (0.141, 0.14) == \
        light_state.attributes.get('xy_color')

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color":{"h":180,"s":50}}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert (180.0, 50.0) == \
        light_state.attributes.get('hs_color')

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "color_temp":155}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 155 == light_state.attributes.get('color_temp')

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "effect":"colorloop"}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 'colorloop' == light_state.attributes.get('effect')

    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON", "white_value":155}')
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    light_state = hass.states.get('light.test')
    assert 155 == light_state.attributes.get('white_value')


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test the sending of command in optimistic mode."""
    fake_state = ha.State('light.test', 'on', {'brightness': 95,
                                               'hs_color': [100, 100],
                                               'effect': 'random',
                                               'color_temp': 100,
                                               'white_value': 50})

    with patch('homeassistant.helpers.restore_state.RestoreEntity'
               '.async_get_last_state',
               return_value=mock_coro(fake_state)):
        assert await async_setup_component(hass, light.DOMAIN, {
            light.DOMAIN: {
                'platform': 'mqtt',
                'schema': 'json',
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

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 95 == state.attributes.get('brightness')
    assert (100, 100) == state.attributes.get('hs_color')
    assert 'random' == state.attributes.get('effect')
    assert 100 == state.attributes.get('color_temp')
    assert 50 == state.attributes.get('white_value')
    assert 191 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_hs_color(hass, mqtt_mock):
    """Test light.turn_on with hs color sends hs color parameters."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'command_topic': 'test_light_rgb/set',
            'hs': True,
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state


async def test_flash_short_and_long(hass, mqtt_mock):
    """Test for flash length being sent when included."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'flash_time_short': 5,
            'flash_time_long': 15,
            'qos': 0
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert 40 == state.attributes.get(ATTR_SUPPORTED_FEATURES)


async def test_transition(hass, mqtt_mock):
    """Test for transition time being sent when included."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'qos': 0
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert 40 == state.attributes.get(ATTR_SUPPORTED_FEATURES)


async def test_brightness_scale(hass, mqtt_mock):
    """Test for brightness scaling."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_bright_scale',
            'command_topic': 'test_light_bright_scale/set',
            'brightness': True,
            'brightness_scale': 99
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert state.attributes.get('brightness') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, 'test_light_bright_scale', '{"state":"ON"}')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 255 == state.attributes.get('brightness')

    # Turn on the light with brightness
    async_fire_mqtt_message(hass, 'test_light_bright_scale',
                            '{"state":"ON", "brightness": 99}')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 255 == state.attributes.get('brightness')


async def test_invalid_color_brightness_and_white_values(hass, mqtt_mock):
    """Test that invalid color/brightness/white values are ignored."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
            'brightness': True,
            'rgb': True,
            'white_value': True,
            'qos': '0'
        }
    })

    state = hass.states.get('light.test')
    assert STATE_OFF == state.state
    assert 185 == state.attributes.get(ATTR_SUPPORTED_FEATURES)
    assert state.attributes.get('rgb_color') is None
    assert state.attributes.get('brightness') is None
    assert state.attributes.get('white_value') is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":255,"g":255,"b":255},'
                            '"brightness": 255,'
                            '"white_value": 255}')
    await hass.async_block_till_done()

    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert (255, 255, 255) == state.attributes.get('rgb_color')
    assert 255 == state.attributes.get('brightness')
    assert 255 == state.attributes.get('white_value')

    # Bad color values
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"color":{"r":"bad","g":"val","b":"test"}}')
    await hass.async_block_till_done()

    # Color should not have changed
    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert (255, 255, 255) == state.attributes.get('rgb_color')

    # Bad brightness values
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"brightness": "badValue"}')
    await hass.async_block_till_done()

    # Brightness should not have changed
    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 255 == state.attributes.get('brightness')

    # Bad white value
    async_fire_mqtt_message(hass, 'test_light_rgb',
                            '{"state":"ON",'
                            '"white_value": "badValue"}')
    await hass.async_block_till_done()

    # White value should not have changed
    state = hass.states.get('light.test')
    assert STATE_ON == state.state
    assert 255 == state.attributes.get('white_value')


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    assert await async_setup_component(hass, light.DOMAIN, {
        light.DOMAIN: {
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
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
            'platform': 'mqtt',
            'schema': 'json',
            'name': 'test',
            'state_topic': 'test_light_rgb',
            'command_topic': 'test_light_rgb/set',
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


async def test_discovery_removal(hass, mqtt_mock, caplog):
    """Test removal of discovered mqtt_json lights."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {'mqtt': {}}, entry)
    data = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "command_topic": "test_topic" }'
    )
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            '')
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is None


async def test_discovery_deprecated(hass, mqtt_mock, caplog):
    """Test discovery of mqtt_json light with deprecated platform option."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {'mqtt': {}}, entry)
    data = (
        '{ "name": "Beer",'
        '  "platform": "mqtt_json",'
        '  "command_topic": "test_topic"}'
    )
    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data)
    await hass.async_block_till_done()
    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'


async def test_discovery_update_light(hass, mqtt_mock, caplog):
    """Test removal of discovered light."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, 'homeassistant', {}, entry)

    data1 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "json",'
        '  "status_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data1)
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Beer'

    async_fire_mqtt_message(hass, 'homeassistant/light/bla/config',
                            data2)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    state = hass.states.get('light.beer')
    assert state is not None
    assert state.name == 'Milk'
    state = hass.states.get('light.milk')
    assert state is None
