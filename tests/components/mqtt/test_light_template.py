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

import pytest

from homeassistant.components import light
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import assert_setup_component, async_fire_mqtt_message
from tests.components.light import common

DEFAULT_CONFIG = {
    light.DOMAIN: {
        "platform": "mqtt",
        "schema": "template",
        "name": "test",
        "command_topic": "test-topic",
        "command_on_template": "on,{{ transition }}",
        "command_off_template": "off,{{ transition|d }}",
    }
}


async def test_setup_fails(hass, mqtt_mock):
    """Test that setup fails with missing required configuration items."""
    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {light.DOMAIN: {"platform": "mqtt", "schema": "template", "name": "test"}},
        )
        await hass.async_block_till_done()
    assert hass.states.get("light.test") is None

    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "command_topic": "test_topic",
                }
            },
        )
        await hass.async_block_till_done()
    assert hass.states.get("light.test") is None

    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "command_topic": "test_topic",
                    "command_on_template": "on",
                }
            },
        )
        await hass.async_block_till_done()
    assert hass.states.get("light.test") is None

    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "command_topic": "test_topic",
                    "command_off_template": "off",
                }
            },
        )
        await hass.async_block_till_done()
    assert hass.states.get("light.test") is None


async def test_state_change_via_topic(hass, mqtt_mock):
    """Test state change via topic."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,"
                    "{{ brightness|d }},"
                    "{{ color_temp|d }},"
                    "{{ white_value|d }},"
                    "{{ red|d }}-"
                    "{{ green|d }}-"
                    "{{ blue|d }}",
                    "command_off_template": "off",
                    "state_template": '{{ value.split(",")[0] }}',
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("white_value") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb", "on")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("white_value") is None


async def test_state_brightness_color_effect_temp_white_change_via_topic(
    hass, mqtt_mock
):
    """Test state, bri, color, effect, color temp, white val change."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "effect_list": ["rainbow", "colorloop"],
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,"
                    "{{ brightness|d }},"
                    "{{ color_temp|d }},"
                    "{{ white_value|d }},"
                    "{{ red|d }}-"
                    "{{ green|d }}-"
                    "{{ blue|d }},"
                    "{{ effect|d }}",
                    "command_off_template": "off",
                    "state_template": '{{ value.split(",")[0] }}',
                    "brightness_template": '{{ value.split(",")[1] }}',
                    "color_temp_template": '{{ value.split(",")[2] }}',
                    "white_value_template": '{{ value.split(",")[3] }}',
                    "red_template": '{{ value.split(",")[4].' 'split("-")[0] }}',
                    "green_template": '{{ value.split(",")[4].' 'split("-")[1] }}',
                    "blue_template": '{{ value.split(",")[4].' 'split("-")[2] }}',
                    "effect_template": '{{ value.split(",")[5] }}',
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("white_value") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # turn on the light, full white
    async_fire_mqtt_message(hass, "test_light_rgb", "on,255,145,123,255-128-64,")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 128, 63)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 145
    assert state.attributes.get("white_value") == 123
    assert state.attributes.get("effect") is None

    # turn the light off
    async_fire_mqtt_message(hass, "test_light_rgb", "off")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # lower the brightness
    async_fire_mqtt_message(hass, "test_light_rgb", "on,100")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 100

    # change the color temp
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,195")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["color_temp"] == 195

    # change the color
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,,,41-42-43")

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (243, 249, 255)

    # change the white value
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,,134")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["white_value"] == 134

    # change the effect
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,,,41-42-43,rainbow")

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("effect") == "rainbow"


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test the sending of command in optimistic mode."""
    fake_state = ha.State(
        "light.test",
        "on",
        {
            "brightness": 95,
            "hs_color": [100, 100],
            "effect": "random",
            "color_temp": 100,
            "white_value": 50,
        },
    )

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=fake_state,
    ):
        with assert_setup_component(1, light.DOMAIN):
            assert await async_setup_component(
                hass,
                light.DOMAIN,
                {
                    light.DOMAIN: {
                        "platform": "mqtt",
                        "schema": "template",
                        "name": "test",
                        "command_topic": "test_light_rgb/set",
                        "command_on_template": "on,"
                        "{{ brightness|d }},"
                        "{{ color_temp|d }},"
                        "{{ white_value|d }},"
                        "{{ red|d }}-"
                        "{{ green|d }}-"
                        "{{ blue|d }}",
                        "command_off_template": "off",
                        "effect_list": ["colorloop", "random"],
                        "optimistic": True,
                        "state_template": '{{ value.split(",")[0] }}',
                        "color_temp_template": '{{ value.split(",")[2] }}',
                        "white_value_template": '{{ value.split(",")[3] }}',
                        "red_template": '{{ value.split(",")[4].' 'split("-")[0] }}',
                        "green_template": '{{ value.split(",")[4].' 'split("-")[1] }}',
                        "blue_template": '{{ value.split(",")[4].' 'split("-")[2] }}',
                        "effect_template": '{{ value.split(",")[5] }}',
                        "qos": 2,
                    }
                },
            )
            await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("hs_color") == (100, 100)
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("color_temp") == 100
    assert state.attributes.get("white_value") == 50
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "off", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,,--", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # Set color_temp
    await common.async_turn_on(hass, "light.test", color_temp=70)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,70,,--", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 70

    # Set full brightness
    await common.async_turn_on(hass, "light.test", brightness=255)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,255,,,--", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # Full brightness - no scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,80,255-128-0", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 80
    assert state.attributes.get("rgb_color") == (255, 128, 0)

    # Full brightness - normalization of RGB values sent over MQTT
    await common.async_turn_on(hass, "light.test", rgb_color=[128, 64, 0])
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,,255-127-0", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 127, 0)

    # Set half brightness
    await common.async_turn_on(hass, "light.test", brightness=128)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,128,,,--", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # Half brightness - scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[0, 255, 128], white_value=40
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,40,0-128-64", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 40
    assert state.attributes.get("rgb_color") == (0, 255, 128)

    # Half brightness - normalization+scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[0, 32, 16], white_value=40
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,40,0-128-64", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 40
    assert state.attributes.get("rgb_color") == (0, 255, 127)


async def test_sending_mqtt_commands_non_optimistic_brightness_template(
    hass, mqtt_mock
):
    """Test the sending of command in optimistic mode."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "effect_list": ["rainbow", "colorloop"],
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,"
                    "{{ brightness|d }},"
                    "{{ color_temp|d }},"
                    "{{ white_value|d }},"
                    "{{ red|d }}-"
                    "{{ green|d }}-"
                    "{{ blue|d }}",
                    "command_off_template": "off",
                    "state_template": '{{ value.split(",")[0] }}',
                    "brightness_template": '{{ value.split(",")[1] }}',
                    "color_temp_template": '{{ value.split(",")[2] }}',
                    "white_value_template": '{{ value.split(",")[3] }}',
                    "red_template": '{{ value.split(",")[4].' 'split("-")[0] }}',
                    "green_template": '{{ value.split(",")[4].' 'split("-")[1] }}',
                    "blue_template": '{{ value.split(",")[4].' 'split("-")[2] }}',
                    "effect_template": '{{ value.split(",")[5] }}',
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get("brightness")
    assert not state.attributes.get("hs_color")
    assert not state.attributes.get("effect")
    assert not state.attributes.get("color_temp")
    assert not state.attributes.get("white_value")
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,,--", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Set color_temp
    await common.async_turn_on(hass, "light.test", color_temp=70)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,70,,--", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get("color_temp")

    # Set full brightness
    await common.async_turn_on(hass, "light.test", brightness=255)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,255,,,--", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get("brightness")

    # Full brightness - no scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,80,255-128-0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get("white_value")
    assert not state.attributes.get("rgb_color")

    # Full brightness - normalization of RGB values sent over MQTT
    await common.async_turn_on(hass, "light.test", rgb_color=[128, 64, 0])
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,,255-127-0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Set half brightness
    await common.async_turn_on(hass, "light.test", brightness=128)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,128,,,--", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Half brightness - no scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[0, 255, 128], white_value=40
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,40,0-255-128", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")

    # Half brightness - normalization but no scaling of RGB values sent over MQTT
    await common.async_turn_on(
        hass, "light.test", rgb_color=[0, 32, 16], white_value=40
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,,,40,0-255-127", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")


async def test_effect(hass, mqtt_mock):
    """Test effect sent over MQTT in optimistic mode."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "effect_list": ["rainbow", "colorloop"],
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,{{ effect }}",
                    "command_off_template": "off",
                    "qos": 0,
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 44

    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert not state.attributes.get("effect")

    await common.async_turn_on(hass, "light.test", effect="rainbow")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,rainbow", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "rainbow"

    await common.async_turn_on(hass, "light.test", effect="colorloop")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,colorloop", 0, False
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "colorloop"


async def test_flash(hass, mqtt_mock):
    """Test flash sent over MQTT in optimistic mode."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,{{ flash }}",
                    "command_off_template": "off",
                    "qos": 0,
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_on(hass, "light.test", flash="short")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,short", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_on(hass, "light.test", flash="long")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,long", 0, False
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON


async def test_transition(hass, mqtt_mock):
    """Test for transition time being sent when included."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,{{ transition }}",
                    "command_off_template": "off,{{ transition|int|d }}",
                    "qos": 1,
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, "light.test", transition=10.0)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on,10.0", 1, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "light.test", transition=20.0)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "off,20", 1, False
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_invalid_values(hass, mqtt_mock):
    """Test that invalid values are ignored."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "template",
                    "name": "test",
                    "effect_list": ["rainbow", "colorloop"],
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "command_on_template": "on,"
                    "{{ brightness|d }},"
                    "{{ color_temp|d }},"
                    "{{ red|d }}-"
                    "{{ green|d }}-"
                    "{{ blue|d }},"
                    "{{ effect|d }}",
                    "command_off_template": "off",
                    "state_template": '{{ value.split(",")[0] }}',
                    "brightness_template": '{{ value.split(",")[1] }}',
                    "color_temp_template": '{{ value.split(",")[2] }}',
                    "white_value_template": '{{ value.split(",")[3] }}',
                    "red_template": '{{ value.split(",")[4].' 'split("-")[0] }}',
                    "green_template": '{{ value.split(",")[4].' 'split("-")[1] }}',
                    "blue_template": '{{ value.split(",")[4].' 'split("-")[2] }}',
                    "effect_template": '{{ value.split(",")[5] }}',
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("white_value") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # turn on the light, full white
    async_fire_mqtt_message(
        hass, "test_light_rgb", "on,255,215,222,255-255-255,rainbow"
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 215
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("white_value") == 222
    assert state.attributes.get("effect") == "rainbow"

    # bad state value
    async_fire_mqtt_message(hass, "test_light_rgb", "offf")

    # state should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # bad brightness values
    async_fire_mqtt_message(hass, "test_light_rgb", "on,off,255-255-255")

    # brightness should not have changed
    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 255

    # bad color temp values
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,off,255-255-255")

    # color temp should not have changed
    state = hass.states.get("light.test")
    assert state.attributes.get("color_temp") == 215

    # bad color values
    async_fire_mqtt_message(hass, "test_light_rgb", "on,255,a-b-c")

    # color should not have changed
    state = hass.states.get("light.test")
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # bad white value values
    async_fire_mqtt_message(hass, "test_light_rgb", "on,,,off,255-255-255")

    # white value should not have changed
    state = hass.states.get("light.test")
    assert state.attributes.get("white_value") == 222

    # bad effect value
    async_fire_mqtt_message(hass, "test_light_rgb", "on,255,a-b-c,white")

    # effect should not have changed
    state = hass.states.get("light.test")
    assert state.attributes.get("effect") == "rainbow"


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one light per unique_id."""
    config = {
        light.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "schema": "template",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "command_on_template": "on,{{ transition }}",
                "command_off_template": "off,{{ transition|d }}",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "schema": "template",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, light.DOMAIN, config)


async def test_discovery_removal(hass, mqtt_mock, caplog):
    """Test removal of discovered mqtt_json lights."""
    data = (
        '{ "name": "test",'
        '  "schema": "template",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
    )
    await help_test_discovery_removal(hass, mqtt_mock, caplog, light.DOMAIN, data)


async def test_discovery_update_light(hass, mqtt_mock, caplog):
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "schema": "template",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "template",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
    )
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, light.DOMAIN, data1, data2
    )


async def test_discovery_update_unchanged_light(hass, mqtt_mock, caplog):
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "schema": "template",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
    )
    with patch(
        "homeassistant.components.mqtt.light.schema_template.MqttLightTemplate.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, light.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "template",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
    )
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, light.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "schema": "template",
            "name": "test",
            "command_topic": "test-topic",
            "command_on_template": "on,{{ transition }}",
            "command_off_template": "off,{{ transition|d }}",
            "state_template": '{{ value.split(",")[0] }}',
        }
    }
    await help_test_entity_debug_info_message(hass, mqtt_mock, light.DOMAIN, config)


async def test_max_mireds(hass, mqtt_mock):
    """Test setting min_mireds and max_mireds."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "schema": "template",
            "name": "test",
            "command_topic": "test_max_mireds/set",
            "command_on_template": "on",
            "command_off_template": "off",
            "color_temp_template": "{{ value }}",
            "max_mireds": 370,
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.attributes.get("min_mireds") == 153
    assert state.attributes.get("max_mireds") == 370
