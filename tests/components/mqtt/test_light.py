"""The tests for the MQTT light platform.

Configuration for RGB Version with brightness:

mqtt:
    light:
      - name: "Office Light RGB"
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

mqtt:
    light:
      - platform: mqtt
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

mqtt:
    light:
      - name: "Office Light"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        brightness_state_topic: "office/rgb1/brightness/status"
        brightness_command_topic: "office/rgb1/brightness/set"
        qos: 0
        payload_on: "on"
        payload_off: "off"

config without RGB and brightness:

mqtt:
    light:
      - name: "Office Light"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        qos: 0
        payload_on: "on"
        payload_off: "off"

config for RGB Version with brightness and scale:

mqtt:
    light:
      - name: "Office Light RGB"
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

config with brightness and color temp (mired)

mqtt:
    light:
      - name: "Office Light Color Temp"
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

config with brightness and color temp (Kelvin)

mqtt:
    light:
      - name: "Office Light Color Temp"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        brightness_state_topic: "office/rgb1/brightness/status"
        brightness_command_topic: "office/rgb1/brightness/set"
        brightness_scale: 99
        color_temp_kelvin: true
        color_temp_state_topic: "office/rgb1/color_temp/status"
        color_temp_command_topic: "office/rgb1/color_temp/set"
        qos: 0
        payload_on: "on"
        payload_off: "off"

config with brightness and effect

mqtt:
    light:
      - name: "Office Light Color Temp"
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

config for RGB Version with RGB command template:

mqtt:
    light:
      - name: "Office Light RGB"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        rgb_state_topic: "office/rgb1/rgb/status"
        rgb_command_topic: "office/rgb1/rgb/set"
        rgb_command_template: "{{ '#%02x%02x%02x' | format(red, green, blue)}}"
        qos: 0
        payload_on: "on"
        payload_off: "off"

Configuration for HS Version with brightness:

mqtt:
    light:
      - name: "Office Light HS"
        state_topic: "office/hs1/light/status"
        command_topic: "office/hs1/light/switch"
        brightness_state_topic: "office/hs1/brightness/status"
        brightness_command_topic: "office/hs1/brightness/set"
        hs_state_topic: "office/hs1/hs/status"
        hs_command_topic: "office/hs1/hs/set"
        qos: 0
        payload_on: "on"
        payload_off: "off"

Configuration with brightness command template:

mqtt:
    light:
      - name: "Office Light"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        brightness_state_topic: "office/rgb1/brightness/status"
        brightness_command_topic: "office/rgb1/brightness/set"
        brightness_command_template: '{ "brightness": "{{ value }}" }'
        qos: 0
        payload_on: "on"
        payload_off: "off"

Configuration with effect command template:

mqtt:
    light:
      - name: "Office Light Color Temp"
        state_topic: "office/rgb1/light/status"
        command_topic: "office/rgb1/light/switch"
        effect_state_topic: "office/rgb1/effect/status"
        effect_command_topic: "office/rgb1/effect/set"
        effect_command_template: '{ "effect": "{{ value }}" }'
        effect_list:
            - rainbow
            - colorloop
        qos: 0
        payload_on: "on"
        payload_off: "off"

"""

import copy
from typing import Any
from unittest.mock import call, patch

import pytest

from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.light.schema_basic import (
    CONF_BRIGHTNESS_COMMAND_TOPIC,
    CONF_COLOR_TEMP_COMMAND_TOPIC,
    CONF_EFFECT_COMMAND_TOPIC,
    CONF_EFFECT_LIST,
    CONF_HS_COMMAND_TOPIC,
    CONF_RGB_COMMAND_TOPIC,
    CONF_RGBW_COMMAND_TOPIC,
    CONF_RGBWW_COMMAND_TOPIC,
    CONF_XY_COMMAND_TOPIC,
    MQTT_LIGHT_ATTRIBUTES_BLOCKED,
    VALUE_TEMPLATE_KEYS,
)
from homeassistant.components.mqtt.models import PublishPayloadType
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .common import (
    help_custom_config,
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_discovery_update_unchanged,
    help_test_encoding_subscribable_topics,
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_publishing_with_custom_encoding,
    help_test_reloadable,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_skipped_async_ha_write_state,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, mock_restore_cache
from tests.components.light import common
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {light.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


@pytest.mark.parametrize(
    "hass_config", [{mqtt.DOMAIN: {light.DOMAIN: {"name": "test"}}}]
)
async def test_fail_setup_if_no_command_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if command fails with command topic."""
    assert await mqtt_mock_entry()
    assert "required key not provided" in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                }
            }
        }
    ],
)
async def test_no_color_brightness_color_temp_hs_white_xy_if_no_topics(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test if there is no color and brightness if no topic."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == ["onoff"]

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "onoff"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == ["onoff"]

    async_fire_mqtt_message(hass, "test_light_rgb/status", "OFF")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb/status", "None")

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("hass_config", "min_kelvin", "max_kelvin"),
    [
        (
            help_custom_config(
                light.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "color_temp_state_topic": "test_light_rgb/color_temp/status",
                        "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    },
                ),
            ),
            light.DEFAULT_MIN_KELVIN,
            light.DEFAULT_MAX_KELVIN,
        ),
        (
            help_custom_config(
                light.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "color_temp_state_topic": "test_light_rgb/color_temp/status",
                        "color_temp_command_topic": "test_light_rgb/color_temp/set",
                        "min_mireds": 180,
                    },
                ),
            ),
            light.DEFAULT_MIN_KELVIN,
            5555,
        ),
        (
            help_custom_config(
                light.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "color_temp_state_topic": "test_light_rgb/color_temp/status",
                        "color_temp_command_topic": "test_light_rgb/color_temp/set",
                        "max_mireds": 400,
                    },
                ),
            ),
            2500,
            light.DEFAULT_MAX_KELVIN,
        ),
        (
            help_custom_config(
                light.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "color_temp_state_topic": "test_light_rgb/color_temp/status",
                        "color_temp_command_topic": "test_light_rgb/color_temp/set",
                        "max_kelvin": 5555,
                    },
                ),
            ),
            light.DEFAULT_MIN_KELVIN,
            5555,
        ),
        (
            help_custom_config(
                light.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "color_temp_state_topic": "test_light_rgb/color_temp/status",
                        "color_temp_command_topic": "test_light_rgb/color_temp/set",
                        "min_kelvin": 2500,
                    },
                ),
            ),
            2500,
            light.DEFAULT_MAX_KELVIN,
        ),
    ],
)
async def test_no_min_max_kelvin(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    min_kelvin: int,
    max_kelvin: int,
) -> None:
    """Test if there is no color and brightness if no topic."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test-topic", "ON")
    state = hass.states.get("light.test")
    assert state is not None and state.state == STATE_UNKNOWN
    assert state.attributes.get(light.ATTR_MIN_COLOR_TEMP_KELVIN) == min_kelvin
    assert state.attributes.get(light.ATTR_MAX_COLOR_TEMP_KELVIN) == max_kelvin


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                    "brightness_state_topic": "test_light_rgb/brightness/status",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "rgb_state_topic": "test_light_rgb/rgb/status",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgbw_state_topic": "test_light_rgb/rgbw/status",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbww_state_topic": "test_light_rgb/rgbww/status",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "color_temp_state_topic": "test_light_rgb/color_temp/status",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "effect_state_topic": "test_light_rgb/effect/status",
                    "effect_command_topic": "test_light_rgb/effect/set",
                    "hs_state_topic": "test_light_rgb/hs/status",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "xy_state_topic": "test_light_rgb/xy/status",
                    "xy_command_topic": "test_light_rgb/xy/set",
                    "qos": "0",
                    "payload_on": 1,
                    "payload_off": 0,
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling of the state via topic."""
    color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/status", "0")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "100")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("brightness") is None
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "300")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("brightness") == 100
    assert light_state.attributes["color_temp"] == 300
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "rainbow")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["effect"] == "rainbow"
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "125,125,125")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (125, 125, 125)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgb"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgbw/status", "80,40,20,10")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbw_color") == (80, 40, 20, 10)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgbw"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgbww/status", "80,40,20,10,8")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbww_color") == (80, 40, 20, 10, 8)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgbww"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "200,50")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (200, 50)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/xy/status", "0.675,0.322")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.675, 0.322)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "xy"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    ("hass_config", "payload", "kelvin"),
    [
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "name": "test",
                        "state_topic": "test_light_color_temp/status",
                        "command_topic": "test_light_color_temp/set",
                        "brightness_state_topic": "test_light_color_temp/brightness/status",
                        "brightness_command_topic": "test_light_color_temp/brightness/set",
                        "color_temp_state_topic": "test_light_color_temp/color_temp/status",
                        "color_temp_command_topic": "test_light_color_temp/color_temp/set",
                        "color_temp_kelvin": False,
                    }
                }
            },
            "300",
            3333,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "name": "test",
                        "state_topic": "test_light_color_temp/status",
                        "command_topic": "test_light_color_temp/set",
                        "brightness_state_topic": "test_light_color_temp/brightness/status",
                        "brightness_command_topic": "test_light_color_temp/brightness/set",
                        "color_temp_state_topic": "test_light_color_temp/color_temp/status",
                        "color_temp_command_topic": "test_light_color_temp/color_temp/set",
                        "color_temp_kelvin": True,
                    }
                }
            },
            "3333",
            3333,
        ),
    ],
    ids=["mireds", "kelvin"],
)
async def test_controlling_color_mode_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    payload: str,
    kelvin: int,
) -> None:
    """Test the controlling of the color mode state via topic."""
    color_modes = ["color_temp"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_color_temp/status", "ON")
    async_fire_mqtt_message(hass, "test_light_color_temp/brightness/status", "70")
    async_fire_mqtt_message(hass, "test_light_color_temp/color_temp/status", payload)
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("brightness") == 70
    assert light_state.attributes["color_temp_kelvin"] == kelvin
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            light.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "state_topic": "test-topic",
                    "optimistic": True,
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "color_mode_state_topic": "color-mode-state-topic",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgb_state_topic": "rgb-state-topic",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbw_state_topic": "rgbw-state-topic",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "rgbww_state_topic": "rgbww-state-topic",
                },
            ),
        )
    ],
)
async def test_received_rgbx_values_set_state_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the state is set correctly when an rgbx update is received."""
    await mqtt_mock_entry()
    state = hass.states.get("light.test")
    assert state and state.state is not None
    async_fire_mqtt_message(hass, "test-topic", "ON")
    ## Test rgb processing
    async_fire_mqtt_message(hass, "rgb-state-topic", "255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["rgb_color"] == (255, 255, 255)

    # Only update color mode
    async_fire_mqtt_message(hass, "color-mode-state-topic", "rgbww")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbww"

    # Resending same rgb value should restore color mode
    async_fire_mqtt_message(hass, "rgb-state-topic", "255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["rgb_color"] == (255, 255, 255)

    # Only update brightness
    await common.async_turn_on(hass, "light.test", brightness=128)
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 128
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["rgb_color"] == (255, 255, 255)

    # Resending same rgb value should restore brightness
    async_fire_mqtt_message(hass, "rgb-state-topic", "255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["rgb_color"] == (255, 255, 255)

    # Only change rgb value
    async_fire_mqtt_message(hass, "rgb-state-topic", "255,255,0")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["rgb_color"] == (255, 255, 0)

    ## Test rgbw processing
    async_fire_mqtt_message(hass, "rgbw-state-topic", "255,255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 255, 255, 255)

    # Only update color mode
    async_fire_mqtt_message(hass, "color-mode-state-topic", "rgb")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"

    # Resending same rgbw value should restore color mode
    async_fire_mqtt_message(hass, "rgbw-state-topic", "255,255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 255, 255, 255)

    # Only update brightness
    await common.async_turn_on(hass, "light.test", brightness=128)
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 128
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 255, 255, 255)

    # Resending same rgbw value should restore brightness
    async_fire_mqtt_message(hass, "rgbw-state-topic", "255,255,255,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 255, 255, 255)

    # Only change rgbw value
    async_fire_mqtt_message(hass, "rgbw-state-topic", "255,255,128,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 255, 128, 255)

    ## Test rgbww processing
    async_fire_mqtt_message(hass, "rgbww-state-topic", "255,255,255,32,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 255, 255, 32, 255)

    # Only update color mode
    async_fire_mqtt_message(hass, "color-mode-state-topic", "rgb")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgb"

    # Resending same rgbw value should restore color mode
    async_fire_mqtt_message(hass, "rgbww-state-topic", "255,255,255,32,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 255, 255, 32, 255)

    # Only update brightness
    await common.async_turn_on(hass, "light.test", brightness=128)
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 128
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 255, 255, 32, 255)

    # Resending same rgbww value should restore brightness
    async_fire_mqtt_message(hass, "rgbww-state-topic", "255,255,255,32,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 255, 255, 32, 255)

    # Only change rgbww value
    async_fire_mqtt_message(hass, "rgbww-state-topic", "255,255,128,32,255")
    await hass.async_block_till_done()
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 255
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 255, 128, 32, 255)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                    "brightness_state_topic": "test_light_rgb/brightness/status",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "color_mode_state_topic": "test_light_rgb/color_mode/status",
                    "rgb_state_topic": "test_light_rgb/rgb/status",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgbw_state_topic": "test_light_rgb/rgbw/status",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbww_state_topic": "test_light_rgb/rgbww/status",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "color_temp_state_topic": "test_light_rgb/color_temp/status",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "effect_state_topic": "test_light_rgb/effect/status",
                    "effect_command_topic": "test_light_rgb/effect/set",
                    "hs_state_topic": "test_light_rgb/hs/status",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "xy_state_topic": "test_light_rgb/xy/status",
                    "xy_command_topic": "test_light_rgb/xy/set",
                    "qos": "0",
                    "payload_on": 1,
                    "payload_off": 0,
                }
            }
        }
    ],
)
async def test_invalid_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of empty data via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("xy_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgb")
    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "255,255,255")
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "255")
    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "none")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") == "none"
    assert state.attributes.get("hs_color") == (0, 0)
    assert state.attributes.get("xy_color") == (0.323, 0.329)
    assert state.attributes.get("color_mode") == "rgb"

    async_fire_mqtt_message(hass, "test_light_rgb/status", "")
    light_state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 255

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "")
    light_state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "rgb"

    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["effect"] == "none"

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (255, 255, 255)

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (0, 0)

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "bad,bad")
    assert "Failed to parse hs state update" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (0, 0)

    async_fire_mqtt_message(hass, "test_light_rgb/xy/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.323, 0.329)

    async_fire_mqtt_message(hass, "test_light_rgb/rgbw/status", "255,255,255,1")
    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgbw")
    async_fire_mqtt_message(hass, "test_light_rgb/rgbw/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbw_color") == (255, 255, 255, 1)

    async_fire_mqtt_message(hass, "test_light_rgb/rgbww/status", "255,255,255,1,2")
    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgbww")
    async_fire_mqtt_message(hass, "test_light_rgb/rgbww/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbww_color") == (255, 255, 255, 1, 2)

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "153")
    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "color_temp")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 251)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 6535
    assert state.attributes.get("effect") == "none"
    assert state.attributes.get("hs_color") == (54.768, 1.6)
    assert state.attributes.get("xy_color") == (0.325, 0.333)

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["color_temp_kelvin"] == 6535


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_scale/status",
                    "command_topic": "test_scale/set",
                    "brightness_state_topic": "test_scale/brightness/status",
                    "brightness_command_topic": "test_scale/brightness/set",
                    "brightness_scale": "99",
                    "qos": 0,
                    "payload_on": "on",
                    "payload_off": "off",
                }
            }
        }
    ],
)
async def test_brightness_controlling_scale(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the brightness controlling scale."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") is None

    async_fire_mqtt_message(hass, "test_scale/status", "off")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    async_fire_mqtt_message(hass, "test_scale/brightness/status", "99")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 255


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_scale_rgb/status",
                    "command_topic": "test_scale_rgb/set",
                    "rgb_state_topic": "test_scale_rgb/rgb/status",
                    "rgb_command_topic": "test_scale_rgb/rgb/set",
                    "qos": 0,
                    "payload_on": "on",
                    "payload_off": "off",
                }
            }
        }
    ],
)
async def test_brightness_from_rgb_controlling_scale(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the brightness controlling scale."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_scale_rgb/status", "on")
    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "255,0,0")

    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 255

    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "128,64,32")

    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 128
    assert state.attributes.get("rgb_color") == (255, 128, 64)

    # Test zero rgb is ignored
    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "0,0,0")
    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 128
    assert state.attributes.get("rgb_color") == (255, 128, 64)

    mqtt_mock.async_publish.reset_mock()
    await common.async_turn_on(hass, "light.test", brightness=191)
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_scale_rgb/set", "on", 0, False),
            call("test_scale_rgb/rgb/set", "191,95,47", 0, False),
        ],
        any_order=True,
    )
    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "191,95,47")
    await hass.async_block_till_done()

    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 191
    assert state.attributes.get("rgb_color") == (255, 127, 63)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbww_command_topic": "test_light_rgb/rgbw/set",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "effect_command_topic": "test_light_rgb/effect/set",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "xy_command_topic": "test_light_rgb/xy/set",
                    "brightness_state_topic": "test_light_rgb/brightness/status",
                    "color_temp_state_topic": "test_light_rgb/color_temp/status",
                    "effect_state_topic": "test_light_rgb/effect/status",
                    "hs_state_topic": "test_light_rgb/hs/status",
                    "rgb_state_topic": "test_light_rgb/rgb/status",
                    "rgbw_state_topic": "test_light_rgb/rgbw/status",
                    "rgbww_state_topic": "test_light_rgb/rgbww/status",
                    "xy_state_topic": "test_light_rgb/xy/status",
                    "state_value_template": "{{ value_json.hello }}",
                    "brightness_value_template": "{{ value_json.hello }}",
                    "color_temp_value_template": "{{ value_json.hello }}",
                    "effect_value_template": "{{ value_json.hello }}",
                    "hs_value_template": '{{ value_json.hello | join(",") }}',
                    "rgb_value_template": '{{ value_json.hello | join(",") }}',
                    "rgbw_value_template": '{{ value_json.hello | join(",") }}',
                    "rgbww_value_template": '{{ value_json.hello | join(",") }}',
                    "xy_value_template": '{{ value_json.hello | join(",") }}',
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic_with_templates(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of the state with a template."""
    color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("rgb_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", '{"hello": [1, 2, 3]}')
    async_fire_mqtt_message(hass, "test_light_rgb/status", '{"hello": "ON"}')
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", '{"hello": "50"}')
    async_fire_mqtt_message(
        hass, "test_light_rgb/effect/status", '{"hello": "rainbow"}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("rgb_color") == (1, 2, 3)
    assert state.attributes.get("effect") == "rainbow"
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgb"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/rgbw/status", '{"hello": [1, 2, 3, 4]}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgbw_color") == (1, 2, 3, 4)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgbw"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/rgbww/status", '{"hello": [1, 2, 3, 4, 5]}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgbww_color") == (1, 2, 3, 4, 5)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgbww"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/color_temp/status", '{"hello": "300"}'
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_temp_kelvin") == 3333
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", '{"hello": [100,50]}')
    state = hass.states.get("light.test")
    assert state.attributes.get("hs_color") == (100, 50)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/xy/status", '{"hello": [0.123,0.123]}'
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("xy_color") == (0.123, 0.123)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "xy"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", '{"hello": 100}')
    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 100

    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", '{"hello": 50}')
    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 50

    # test zero brightness received is ignored
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", '{"hello": 0}')
    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 50


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "effect_command_topic": "test_light_rgb/effect/set",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "xy_command_topic": "test_light_rgb/xy/set",
                    "effect_list": ["colorloop", "random"],
                    "qos": 2,
                    "payload_on": "on",
                    "payload_off": "off",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of command in optimistic mode."""
    color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"]
    fake_state = State(
        "light.test",
        "on",
        {
            "brightness": 95,
            "hs_color": [100, 100],
            "effect": "random",
            "color_temp_kelvin": 100000,
            "color_mode": "hs",
        },
    )
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("hs_color") == (100, 100)
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "light.test", effect="colorloop")
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/effect/set", "colorloop", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "off", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(
        hass, "light.test", brightness=10, rgb_color=(80, 40, 20)
    )
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/brightness/set", "10", 2, False),
            call("test_light_rgb/rgb/set", "80,40,20", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 10
    assert state.attributes.get("rgb_color") == (80, 40, 20)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgb"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(
        hass, "light.test", brightness=20, rgbw_color=(80, 40, 20, 10)
    )
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/brightness/set", "20", 2, False),
            call("test_light_rgb/rgbw/set", "80,40,20,10", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 20
    assert state.attributes.get("rgbw_color") == (80, 40, 20, 10)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgbw"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(
        hass, "light.test", brightness=40, rgbww_color=(80, 40, 20, 10, 8)
    )
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/brightness/set", "40", 2, False),
            call("test_light_rgb/rgbww/set", "80,40,20,10,8", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 40
    assert state.attributes.get("rgbww_color") == (80, 40, 20, 10, 8)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgbww"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=(359, 78))
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/brightness/set", "50", 2, False),
            call("test_light_rgb/hs/set", "359.0,78.0", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("hs_color") == (359.0, 78.0)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(hass, "light.test", brightness=60, xy_color=(0.2, 0.3))
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/brightness/set", "60", 2, False),
            call("test_light_rgb/xy/set", "0.2,0.3", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 60
    assert state.attributes.get("xy_color") == (0.2, 0.3)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "xy"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    await common.async_turn_on(hass, "light.test", color_temp_kelvin=8000)
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/color_temp/set", "125", 2, False),
        ],
        any_order=True,
    )
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 60
    assert state.attributes.get("color_temp_kelvin") == 8000
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgb_command_template": '{{ "#%02x%02x%02x" | '
                    "format(red, green, blue)}}",
                    "payload_on": "on",
                    "payload_off": "off",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_rgb_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of RGB command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 64))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 0, False),
            call("test_light_rgb/rgb/set", "#ff8040", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["rgb_color"] == (255, 128, 64)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbw_command_template": '{{ "#%02x%02x%02x%02x" | '
                    "format(red, green, blue, white)}}",
                    "payload_on": "on",
                    "payload_off": "off",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_rgbw_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of RGBW command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", rgbw_color=(255, 128, 64, 32))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 0, False),
            call("test_light_rgb/rgbw/set", "#ff804020", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["rgbw_color"] == (255, 128, 64, 32)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "rgbww_command_template": '{{ "#%02x%02x%02x%02x%02x" | '
                    "format(red, green, blue, cold_white, warm_white)}}",
                    "payload_on": "on",
                    "payload_off": "off",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_rgbww_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of RGBWW command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", rgbww_color=(255, 128, 64, 32, 16))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 0, False),
            call("test_light_rgb/rgbww/set", "#ff80402010", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["rgbww_color"] == (255, 128, 64, 32, 16)


@pytest.mark.parametrize(
    ("hass_config", "payload"),
    [
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "name": "test",
                        "command_topic": "test_light_color_temp/set",
                        "color_temp_command_topic": "test_light_color_temp/color_temp/set",
                        "color_temp_command_template": "{{ (1000 / value) | round(0) }}",
                        "color_temp_kelvin": False,
                        "payload_on": "on",
                        "payload_off": "off",
                        "qos": 0,
                    }
                }
            },
            "10",
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "name": "test",
                        "command_topic": "test_light_color_temp/set",
                        "color_temp_command_topic": "test_light_color_temp/color_temp/set",
                        "color_temp_command_template": "{{ (0.5 * value) | round(0) }}",
                        "color_temp_kelvin": True,
                        "payload_on": "on",
                        "payload_off": "off",
                        "qos": 0,
                    }
                }
            },
            "5000",
        ),
    ],
    ids=["mireds", "kelvin"],
)
async def test_sending_mqtt_color_temp_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, payload: str
) -> None:
    """Test the sending of Color Temp command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", color_temp_kelvin=10000)

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_color_temp/set", "on", 0, False),
            call("test_light_color_temp/color_temp/set", payload, 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["color_temp_kelvin"] == 10000


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "brightness_command_topic": "test_light/bright",
                    "on_command_type": "first",
                }
            }
        }
    ],
)
async def test_on_command_first(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command being sent before brightness."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=50)

    # Should get the following MQTT messages.
    #    test_light/set: 'ON'
    #    test_light/bright: 50
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/set", "ON", 0, False),
            call("test_light/bright", "50", 0, False),
        ],
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "brightness_command_topic": "test_light/bright",
                }
            }
        }
    ],
)
async def test_on_command_last(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command being sent after brightness."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=50)

    # Should get the following MQTT messages.
    #    test_light/bright: 50
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/bright", "50", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "brightness_command_topic": "test_light/bright",
                    "rgb_command_topic": "test_light/rgb",
                    "on_command_type": "brightness",
                }
            }
        }
    ],
)
async def test_on_command_brightness(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command being sent as only brightness."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    # Turn on w/ no brightness - should set to max
    await common.async_turn_on(hass, "light.test")

    # Should get the following MQTT messages.
    #    test_light/bright: 255
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light/bright", "255", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ brightness
    await common.async_turn_on(hass, "light.test", brightness=50)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", "50", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    # Turn on w/ just a color to ensure brightness gets
    # added and sent.
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,128,0", 0, False),
            call("test_light/bright", "50", 0, False),
        ],
        any_order=True,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "brightness_command_topic": "test_light/bright",
                    "brightness_scale": 100,
                    "rgb_command_topic": "test_light/rgb",
                    "on_command_type": "brightness",
                }
            }
        }
    ],
)
async def test_on_command_brightness_scaled(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test brightness scale."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    # Turn on w/ no brightness - should set to max
    await common.async_turn_on(hass, "light.test")

    # Should get the following MQTT messages.
    #    test_light/bright: 100
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light/bright", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ brightness
    await common.async_turn_on(hass, "light.test", brightness=50)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", "20", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ max brightness
    await common.async_turn_on(hass, "light.test", brightness=255)

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light/bright", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ min brightness
    await common.async_turn_on(hass, "light.test", brightness=1)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", "1", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    # Turn on w/ just a color to ensure brightness gets
    # added and sent.
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,128,0", 0, False),
            call("test_light/bright", "1", 0, False),
        ],
        any_order=True,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgb_command_topic": "test_light/rgb",
                }
            }
        }
    ],
)
async def test_on_command_rgb(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGB brightness mode."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgb: '127,127,127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "127,127,127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgb: '255,255,255'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,255,255", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=1)

    # Should get the following MQTT messages.
    #    test_light/rgb: '1,1,1'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "1,1,1", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)

    # Ensure color gets scaled with brightness.
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "1,0,0", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgb: '255,128,0'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,128,0", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgbw_command_topic": "test_light/rgbw",
                }
            }
        }
    ],
)
async def test_on_command_rgbw(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGBW brightness mode."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgbw: '127,127,127,127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "127,127,127,127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgbw: '255,255,255,255'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "255,255,255,255", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=1)

    # Should get the following MQTT messages.
    #    test_light/rgbw: '1,1,1,1'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "1,1,1,1", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)

    # Ensure color gets scaled with brightness.
    await common.async_turn_on(hass, "light.test", rgbw_color=(255, 128, 0, 16))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "1,0,0,0", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgbw: '255,128,0'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "255,128,0,16", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgbww_command_topic": "test_light/rgbww",
                }
            }
        }
    ],
)
async def test_on_command_rgbww(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGBWW brightness mode."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgbww: '127,127,127,127,127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "127,127,127,127,127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgbww: '255,255,255,255,255'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "255,255,255,255,255", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=1)

    # Should get the following MQTT messages.
    #    test_light/rgbww: '1,1,1,1,1'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "1,1,1,1,1", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)

    # Ensure color gets scaled with brightness.
    await common.async_turn_on(hass, "light.test", rgbww_color=(255, 128, 0, 16, 32))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "1,0,0,0,0", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255)

    # Should get the following MQTT messages.
    #    test_light/rgbww: '255,128,0,16,32'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "255,128,0,16,32", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgb_command_topic": "test_light/rgb",
                    "rgb_command_template": "{{ red }}/{{ green }}/{{ blue }}",
                }
            }
        }
    ],
)
async def test_on_command_rgb_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGB brightness mode with RGB template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgb: '127/127/127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "127/127/127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgbw_command_topic": "test_light/rgbw",
                    "rgbw_command_template": "{{ red }}/{{ green }}/{{ blue }}/{{ white }}",
                }
            }
        }
    ],
)
async def test_on_command_rgbw_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGBW brightness mode with RGBW template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgb: '127/127/127/127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbw", "127/127/127/127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "rgbww_command_topic": "test_light/rgbww",
                    "rgbww_command_template": "{{ red }}/{{ green }}/{{ blue }}"
                    "/{{ cold_white }}/{{ warm_white }}",
                }
            }
        }
    ],
)
async def test_on_command_rgbww_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test on command in RGBWW brightness mode with RGBWW template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgb: '127/127/127/127/127'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgbww", "127/127/127/127/127", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "tasmota_B94927/cmnd/POWER",
                    "state_value_template": "{{ value_json.POWER }}",
                    "payload_off": "OFF",
                    "payload_on": "ON",
                    "brightness_command_topic": "tasmota_B94927/cmnd/Dimmer",
                    "brightness_scale": 100,
                    "on_command_type": "brightness",
                    "brightness_value_template": "{{ value_json.Dimmer }}",
                    "rgb_command_topic": "tasmota_B94927/cmnd/Color2",
                    "rgb_value_template": "{{value_json.Color.split(',')[0:3]|join(',')}}",
                    "white_command_topic": "tasmota_B94927/cmnd/White",
                    "white_scale": 100,
                    "color_mode_value_template": "{% if value_json.White %} white {% else %} rgb {% endif %}",
                    "qos": "0",
                }
            }
        }
    ],
)
async def test_on_command_white(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test sending commands for RGB + white light."""
    color_modes = ["rgb", "white"]

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "light.test", brightness=192)
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("tasmota_B94927/cmnd/Dimmer", "75", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", white=255)
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("tasmota_B94927/cmnd/White", "100", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", white=64)
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("tasmota_B94927/cmnd/White", "25", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("tasmota_B94927/cmnd/Dimmer", "25", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "tasmota_B94927/cmnd/POWER", "OFF", 0, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                    "color_mode_state_topic": "test_light_rgb/color_mode/status",
                    "brightness_state_topic": "test_light_rgb/brightness/status",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "rgb_state_topic": "test_light_rgb/rgb/status",
                    "rgb_command_topic": "test_light_rgb/rgb/set",
                    "rgbw_state_topic": "test_light_rgb/rgbw/status",
                    "rgbw_command_topic": "test_light_rgb/rgbw/set",
                    "rgbww_state_topic": "test_light_rgb/rgbww/status",
                    "rgbww_command_topic": "test_light_rgb/rgbww/set",
                    "color_temp_state_topic": "test_light_rgb/color_temp/status",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "effect_state_topic": "test_light_rgb/effect/status",
                    "effect_command_topic": "test_light_rgb/effect/set",
                    "hs_state_topic": "test_light_rgb/hs/status",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "xy_state_topic": "test_light_rgb/xy/status",
                    "xy_command_topic": "test_light_rgb/xy/set",
                    "qos": "0",
                    "payload_on": 1,
                    "payload_off": 0,
                }
            }
        }
    ],
)
async def test_explicit_color_mode(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test explicit color mode over mqtt."""
    color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/status", "0")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "100")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("brightness") is None
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "300")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "rainbow")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["effect"] == "rainbow"
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "125,125,125")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgbw/status", "80,40,20,10")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/rgbww/status", "80,40,20,10,8")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "200,50")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/xy/status", "0.675,0.322")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "color_temp")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgb")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (125, 125, 125)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgb"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgbw")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbw_color") == (80, 40, 20, 10)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgbw"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "rgbww")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgbww_color") == (80, 40, 20, 10, 8)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "rgbww"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "hs")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (200, 50)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_mode/status", "xy")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.675, 0.322)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "xy"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "test_light_rgb/status",
                    "command_topic": "test_light_rgb/set",
                    "color_mode_state_topic": "test_light_rgb/color_mode/status",
                    "color_mode_value_template": "{{ value_json.color_mode }}",
                    "brightness_state_topic": "test_light_rgb/brightness/status",
                    "brightness_command_topic": "test_light_rgb/brightness/set",
                    "color_temp_state_topic": "test_light_rgb/color_temp/status",
                    "color_temp_command_topic": "test_light_rgb/color_temp/set",
                    "hs_state_topic": "test_light_rgb/hs/status",
                    "hs_command_topic": "test_light_rgb/hs/set",
                    "qos": "0",
                    "payload_on": 1,
                    "payload_off": 0,
                }
            }
        }
    ],
)
async def test_explicit_color_mode_templated(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test templated explicit color mode over mqtt."""
    color_modes = ["color_temp", "hs"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/status", "0")
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "100")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("brightness") is None
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "300")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "200,50")
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "unknown"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/color_mode/status", '{"color_mode":"color_temp"}'
    )
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "color_temp"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass, "test_light_rgb/color_mode/status", '{"color_mode":"hs"}'
    )
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (200, 50)
    assert light_state.attributes.get(light.ATTR_COLOR_MODE) == "hs"
    assert light_state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "state_topic": "tasmota_B94927/tele/STATE",
                    "command_topic": "tasmota_B94927/cmnd/POWER",
                    "state_value_template": "{{ value_json.POWER }}",
                    "payload_off": "OFF",
                    "payload_on": "ON",
                    "brightness_command_topic": "tasmota_B94927/cmnd/Dimmer",
                    "brightness_state_topic": "tasmota_B94927/tele/STATE",
                    "brightness_scale": 100,
                    "on_command_type": "brightness",
                    "brightness_value_template": "{{ value_json.Dimmer }}",
                    "rgb_command_topic": "tasmota_B94927/cmnd/Color2",
                    "rgb_state_topic": "tasmota_B94927/tele/STATE",
                    "rgb_value_template": "{{value_json.Color.split(',')"
                    "[0:3]|join(',')}}",
                    "white_command_topic": "tasmota_B94927/cmnd/White",
                    "white_scale": 100,
                    "color_mode_state_topic": "tasmota_B94927/tele/STATE",
                    "color_mode_value_template": "{% if value_json.White %} white "
                    "{% else %} rgb {% endif %}",
                    "qos": "0",
                }
            }
        }
    ],
)
async def test_white_state_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test state updates for RGB + white light."""
    color_modes = ["rgb", "white"]

    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) is None
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(
        hass,
        "tasmota_B94927/tele/STATE",
        '{"POWER":"ON","Dimmer":50,"Color":"0,0,0,128","White":50}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 128
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "white"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes

    async_fire_mqtt_message(
        hass,
        "tasmota_B94927/tele/STATE",
        '{"POWER":"ON","Dimmer":50,"Color":"128,64,32,0","White":0}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 128
    assert state.attributes.get("rgb_color") == (128, 64, 32)
    assert state.attributes.get(light.ATTR_COLOR_MODE) == "rgb"
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light/set",
                    "effect_command_topic": "test_light/effect/set",
                    "effect_list": ["rainbow", "colorloop"],
                }
            }
        }
    ],
)
async def test_effect(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test effect."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", effect="rainbow")

    # Should get the following MQTT messages.
    #    test_light/effect/set: 'rainbow'
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/effect/set", "rainbow", 0, False),
            call("test_light/set", "ON", 0, False),
        ],
        any_order=True,
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, light.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_LIGHT_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "command_topic": "test_topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "command_topic": "test_topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one light per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, light.DOMAIN)


async def test_discovery_removal_light(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered light."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock_entry, light.DOMAIN, data)


async def test_discovery_ignores_extra_keys(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test discovery ignores extra keys that are not blocked."""
    await mqtt_mock_entry()
    # inserted `platform` key should be ignored
    data = '{ "name": "Beer",  "platform": "mqtt",  "command_topic": "test_topic"}'
    async_fire_mqtt_message(hass, "homeassistant/light/bla/config", data)
    await hass.async_block_till_done()
    state = hass.states.get("light.beer")
    assert state is not None
    assert state.name == "Beer"


async def test_discovery_update_light_topic_and_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered light."""
    config1 = {
        "name": "Beer",
        "state_topic": "test_light_rgb/state1",
        "command_topic": "test_light_rgb/set",
        "brightness_command_topic": "test_light_rgb/state1",
        "rgb_command_topic": "test_light_rgb/rgb/set",
        "color_temp_command_topic": "test_light_rgb/state1",
        "effect_command_topic": "test_light_rgb/effect/set",
        "hs_command_topic": "test_light_rgb/hs/set",
        "xy_command_topic": "test_light_rgb/xy/set",
        "brightness_state_topic": "test_light_rgb/state1",
        "color_temp_state_topic": "test_light_rgb/state1",
        "effect_state_topic": "test_light_rgb/state1",
        "hs_state_topic": "test_light_rgb/state1",
        "rgb_state_topic": "test_light_rgb/state1",
        "xy_state_topic": "test_light_rgb/state1",
        "state_value_template": "{{ value_json.state1.state }}",
        "brightness_value_template": "{{ value_json.state1.brightness }}",
        "color_temp_value_template": "{{ value_json.state1.ct }}",
        "effect_value_template": "{{ value_json.state1.fx }}",
        "hs_value_template": "{{ value_json.state1.hs }}",
        "rgb_value_template": "{{ value_json.state1.rgb }}",
        "xy_value_template": "{{ value_json.state1.xy }}",
    }

    config2 = {
        "name": "Milk",
        "state_topic": "test_light_rgb/state2",
        "command_topic": "test_light_rgb/set",
        "brightness_command_topic": "test_light_rgb/state2",
        "rgb_command_topic": "test_light_rgb/rgb/set",
        "color_temp_command_topic": "test_light_rgb/state2",
        "effect_command_topic": "test_light_rgb/effect/set",
        "hs_command_topic": "test_light_rgb/hs/set",
        "xy_command_topic": "test_light_rgb/xy/set",
        "brightness_state_topic": "test_light_rgb/state2",
        "color_temp_state_topic": "test_light_rgb/state2",
        "effect_state_topic": "test_light_rgb/state2",
        "hs_state_topic": "test_light_rgb/state2",
        "rgb_state_topic": "test_light_rgb/state2",
        "xy_state_topic": "test_light_rgb/state2",
        "state_value_template": "{{ value_json.state2.state }}",
        "brightness_value_template": "{{ value_json.state2.brightness }}",
        "color_temp_value_template": "{{ value_json.state2.ct }}",
        "effect_value_template": "{{ value_json.state2.fx }}",
        "hs_value_template": "{{ value_json.state2.hs }}",
        "rgb_value_template": "{{ value_json.state2.rgb }}",
        "xy_value_template": "{{ value_json.state2.xy }}",
    }
    state_data1 = [
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "brightness":100, "ct":123, "white":100, "fx":"cycle"}}',
                )
            ],
            "on",
            [
                ("brightness", 100),
                ("color_temp", 123),
                ("effect", "cycle"),
            ],
        ),
        (
            [("test_light_rgb/state1", '{"state1":{"state":"OFF"}}')],
            "off",
            None,
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "hs":"1,2", "white":0}}',
                )
            ],
            "on",
            [("hs_color", (1, 2))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"rgb":"255,127,63"}}',
                )
            ],
            "on",
            [("rgb_color", (255, 127, 63))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"xy":"0.3, 0.4"}}',
                )
            ],
            "on",
            [("xy_color", (0.3, 0.4))],
        ),
    ]
    state_data2 = [
        (
            [
                (
                    "test_light_rgb/state2",
                    '{"state2":{"state":"ON", "brightness":50, "ct":200, "white":50, "fx":"loop"}}',
                )
            ],
            "on",
            [
                ("brightness", 50),
                ("color_temp", 200),
                ("effect", "loop"),
            ],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "brightness":100, "ct":123, "fx":"cycle"}}',
                ),
                (
                    "test_light_rgb/state1",
                    '{"state2":{"state":"ON", "brightness":100, "ct":123, "fx":"cycle"}}',
                ),
                (
                    "test_light_rgb/state2",
                    '{"state1":{"state":"ON", "brightness":100, "ct":123, "fx":"cycle"}}',
                ),
            ],
            "on",
            [("brightness", 50), ("color_temp", 200), ("effect", "loop")],
        ),
        (
            [("test_light_rgb/state1", '{"state1":{"state":"OFF"}}')],
            "on",
            None,
        ),
        (
            [("test_light_rgb/state1", '{"state2":{"state":"OFF"}}')],
            "on",
            None,
        ),
        (
            [("test_light_rgb/state2", '{"state1":{"state":"OFF"}}')],
            "on",
            None,
        ),
        (
            [("test_light_rgb/state2", '{"state2":{"state":"OFF"}}')],
            "off",
            None,
        ),
        (
            [
                (
                    "test_light_rgb/state2",
                    '{"state2":{"state":"ON", "hs":"1.2,2.2", "white":0}}',
                )
            ],
            "on",
            [("hs_color", (1.2, 2.2))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "hs":"1,2"}}',
                ),
                (
                    "test_light_rgb/state1",
                    '{"state2":{"state":"ON", "hs":"1,2"}}',
                ),
                (
                    "test_light_rgb/state2",
                    '{"state1":{"state":"ON", "hs":"1,2"}}',
                ),
            ],
            "on",
            [("hs_color", (1.2, 2.2))],
        ),
        (
            [
                (
                    "test_light_rgb/state2",
                    '{"state2":{"rgb":"63,127,255"}}',
                )
            ],
            "on",
            [("rgb_color", (63, 127, 255))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"rgb":"255,127,63"}}',
                ),
                (
                    "test_light_rgb/state1",
                    '{"state2":{"rgb":"255,127,63"}}',
                ),
                (
                    "test_light_rgb/state2",
                    '{"state1":{"rgb":"255,127,63"}}',
                ),
            ],
            "on",
            [("rgb_color", (63, 127, 255))],
        ),
        (
            [
                (
                    "test_light_rgb/state2",
                    '{"state2":{"xy":"0.4, 0.3"}}',
                )
            ],
            "on",
            [("xy_color", (0.4, 0.3))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"white":50, "xy":"0.3, 0.4"}}',
                ),
                (
                    "test_light_rgb/state1",
                    '{"state2":{"white":50, "xy":"0.3, 0.4"}}',
                ),
                (
                    "test_light_rgb/state2",
                    '{"state1":{"white":50, "xy":"0.3, 0.4"}}',
                ),
            ],
            "on",
            [("xy_color", (0.4, 0.3))],
        ),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_light_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered light."""
    config1 = {
        "name": "Beer",
        "state_topic": "test_light_rgb/state1",
        "command_topic": "test_light_rgb/set",
        "brightness_command_topic": "test_light_rgb/state1",
        "rgb_command_topic": "test_light_rgb/rgb/set",
        "color_temp_command_topic": "test_light_rgb/state1",
        "effect_command_topic": "test_light_rgb/effect/set",
        "hs_command_topic": "test_light_rgb/hs/set",
        "xy_command_topic": "test_light_rgb/xy/set",
        "brightness_state_topic": "test_light_rgb/state1",
        "color_temp_state_topic": "test_light_rgb/state1",
        "effect_state_topic": "test_light_rgb/state1",
        "hs_state_topic": "test_light_rgb/state1",
        "rgb_state_topic": "test_light_rgb/state1",
        "xy_state_topic": "test_light_rgb/state1",
        "state_value_template": "{{ value_json.state1.state }}",
        "brightness_value_template": "{{ value_json.state1.brightness }}",
        "color_temp_value_template": "{{ value_json.state1.ct }}",
        "effect_value_template": "{{ value_json.state1.fx }}",
        "hs_value_template": "{{ value_json.state1.hs }}",
        "rgb_value_template": "{{ value_json.state1.rgb }}",
        "xy_value_template": "{{ value_json.state1.xy }}",
    }

    config2 = {
        "name": "Milk",
        "state_topic": "test_light_rgb/state1",
        "command_topic": "test_light_rgb/set",
        "brightness_command_topic": "test_light_rgb/state1",
        "rgb_command_topic": "test_light_rgb/rgb/set",
        "color_temp_command_topic": "test_light_rgb/state1",
        "effect_command_topic": "test_light_rgb/effect/set",
        "hs_command_topic": "test_light_rgb/hs/set",
        "xy_command_topic": "test_light_rgb/xy/set",
        "brightness_state_topic": "test_light_rgb/state1",
        "color_temp_state_topic": "test_light_rgb/state1",
        "effect_state_topic": "test_light_rgb/state1",
        "hs_state_topic": "test_light_rgb/state1",
        "rgb_state_topic": "test_light_rgb/state1",
        "xy_state_topic": "test_light_rgb/state1",
        "state_value_template": "{{ value_json.state2.state }}",
        "brightness_value_template": "{{ value_json.state2.brightness }}",
        "color_temp_value_template": "{{ value_json.state2.ct }}",
        "effect_value_template": "{{ value_json.state2.fx }}",
        "hs_value_template": "{{ value_json.state2.hs }}",
        "rgb_value_template": "{{ value_json.state2.rgb }}",
        "xy_value_template": "{{ value_json.state2.xy }}",
    }
    state_data1 = [
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "brightness":100, "ct":123, "white":100, "fx":"cycle"}}',
                )
            ],
            "on",
            [
                ("brightness", 100),
                ("color_temp", 123),
                ("effect", "cycle"),
            ],
        ),
        (
            [("test_light_rgb/state1", '{"state1":{"state":"OFF"}}')],
            "off",
            None,
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "hs":"1,2", "white":0}}',
                )
            ],
            "on",
            [("hs_color", (1, 2))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"rgb":"255,127,63"}}',
                )
            ],
            "on",
            [("rgb_color", (255, 127, 63))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"white":0, "xy":"0.3, 0.4"}}',
                )
            ],
            "on",
            [("xy_color", (0.3, 0.4))],
        ),
    ]
    state_data2 = [
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state2":{"state":"ON", "brightness":50, "ct":200, "white":50, "fx":"loop"}}',
                )
            ],
            "on",
            [
                ("brightness", 50),
                ("color_temp", 200),
                ("effect", "loop"),
            ],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "brightness":100, "ct":123, "fx":"cycle"}}',
                ),
            ],
            "on",
            [("brightness", 50), ("color_temp", 200), ("effect", "loop")],
        ),
        (
            [("test_light_rgb/state1", '{"state1":{"state":"OFF"}}')],
            "on",
            None,
        ),
        (
            [("test_light_rgb/state1", '{"state2":{"state":"OFF"}}')],
            "off",
            None,
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state2":{"state":"ON", "hs":"1.2,2.2", "white":0}}',
                )
            ],
            "on",
            [("hs_color", (1.2, 2.2))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"state":"ON", "hs":"1,2"}}',
                )
            ],
            "on",
            [("hs_color", (1.2, 2.2))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state2":{"rgb":"63,127,255"}}',
                )
            ],
            "on",
            [("rgb_color", (63, 127, 255))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"rgb":"255,127,63"}}',
                )
            ],
            "on",
            [("rgb_color", (63, 127, 255))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state2":{"xy":"0.4, 0.3"}}',
                )
            ],
            "on",
            [("xy_color", (0.4, 0.3))],
        ),
        (
            [
                (
                    "test_light_rgb/state1",
                    '{"state1":{"white":50, "xy":"0.3, 0.4"}}',
                )
            ],
            "on",
            [("xy_color", (0.4, 0.3))],
        ),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_unchanged_light(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.light.schema_basic.MqttLight.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, light.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(hass, mqtt_mock_entry, light.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
        light.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_max_mireds/set",
                    "color_temp_command_topic": "test_max_mireds/color_temp/set",
                    "max_mireds": 370,
                }
            }
        }
    ],
)
async def test_max_mireds(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting min_mireds and max_mireds."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.attributes.get("min_mireds") == 153
    assert state.attributes.get("max_mireds") == 370


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template", "tpl_par", "tpl_output"),
    [
        (
            light.SERVICE_TURN_ON,
            "command_topic",
            None,
            "ON",
            None,
            None,
            None,
        ),
        (
            light.SERVICE_TURN_ON,
            "white_command_topic",
            {"white": "255"},
            255,
            None,
            None,
            None,
        ),
        (
            light.SERVICE_TURN_ON,
            "brightness_command_topic",
            {"color_temp": "200", "brightness": "50"},
            50,
            "brightness_command_template",
            "value",
            b"5",
        ),
        (
            light.SERVICE_TURN_ON,
            "effect_command_topic",
            {"rgb_color": [255, 128, 0], "effect": "color_loop"},
            "color_loop",
            "effect_command_template",
            "value",
            b"c",
        ),
        (
            light.SERVICE_TURN_ON,
            "color_temp_command_topic",
            {"color_temp": "200"},
            200,
            "color_temp_command_template",
            "value",
            b"2",
        ),
        (
            light.SERVICE_TURN_ON,
            "rgb_command_topic",
            {"rgb_color": [255, 128, 0]},
            "255,128,0",
            "rgb_command_template",
            "red",
            b"2",
        ),
        (
            light.SERVICE_TURN_ON,
            "hs_command_topic",
            {"rgb_color": [255, 128, 0]},
            "30.118,100.0",
            "hs_command_template",
            "hue",
            b"3",
        ),
        (
            light.SERVICE_TURN_ON,
            "xy_command_topic",
            {"hs_color": [30.118, 100.0]},
            "0.611,0.375",
            "xy_command_template",
            "x * 10",
            b"6",
        ),
        (
            light.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "OFF",
            None,
            None,
            None,
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
    tpl_par: str,
    tpl_output: PublishPayloadType,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = light.DOMAIN
    config: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)
    if topic == "effect_command_topic":
        config[mqtt.DOMAIN][domain]["effect_list"] = ["random", "color_loop"]
    elif topic == "white_command_topic":
        config[mqtt.DOMAIN][domain]["rgb_command_topic"] = "some-cmd-topic"

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
        tpl_par=tpl_par,
        tpl_output=tpl_output,
    )


async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = light.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value", "init_payload"),
    [
        ("state_topic", "ON", None, "on", None),
        (
            "color_mode_state_topic",
            "rgb",
            "color_mode",
            "rgb",
            ("state_topic", "ON"),
        ),
        ("color_temp_state_topic", "200", "color_temp", 200, ("state_topic", "ON")),
        ("effect_state_topic", "random", "effect", "random", ("state_topic", "ON")),
        ("hs_state_topic", "200,50", "hs_color", (200, 50), ("state_topic", "ON")),
        (
            "xy_state_topic",
            "128,128",
            "xy_color",
            (128, 128),
            ("state_topic", "ON"),
        ),
        (
            "rgb_state_topic",
            "255,0,240",
            "rgb_color",
            (255, 0, 240),
            ("state_topic", "ON"),
        ),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str | None,
    attribute_value: Any,
    init_payload: tuple[str, str] | None,
) -> None:
    """Test handling of incoming encoded payload."""
    config: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][light.DOMAIN])
    config[CONF_EFFECT_COMMAND_TOPIC] = "light/CONF_EFFECT_COMMAND_TOPIC"
    config[CONF_RGB_COMMAND_TOPIC] = "light/CONF_RGB_COMMAND_TOPIC"
    config[CONF_BRIGHTNESS_COMMAND_TOPIC] = "light/CONF_BRIGHTNESS_COMMAND_TOPIC"
    config[CONF_COLOR_TEMP_COMMAND_TOPIC] = "light/CONF_COLOR_TEMP_COMMAND_TOPIC"
    config[CONF_HS_COMMAND_TOPIC] = "light/CONF_HS_COMMAND_TOPIC"
    config[CONF_RGB_COMMAND_TOPIC] = "light/CONF_RGB_COMMAND_TOPIC"
    config[CONF_RGBW_COMMAND_TOPIC] = "light/CONF_RGBW_COMMAND_TOPIC"
    config[CONF_RGBWW_COMMAND_TOPIC] = "light/CONF_RGBWW_COMMAND_TOPIC"
    config[CONF_XY_COMMAND_TOPIC] = "light/CONF_XY_COMMAND_TOPIC"
    config[CONF_EFFECT_LIST] = ["colorloop", "random"]

    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
        init_payload,
    )


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value", "init_payload"),
    [
        ("brightness_state_topic", "60", "brightness", 60, ("state_topic", "ON")),
    ],
)
async def test_encoding_subscribable_topics_brightness(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str,
    attribute_value: int,
    init_payload: tuple[str, str] | None,
) -> None:
    """Test handling of incoming encoded payload for a brightness only light."""
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][light.DOMAIN])
    config[CONF_BRIGHTNESS_COMMAND_TOPIC] = "light/CONF_BRIGHTNESS_COMMAND_TOPIC"

    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
        init_payload,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_brightness/set",
                    "brightness_command_topic": "test_light_brightness/brightness/set",
                    "brightness_command_template": "{{ (1000 / value) | round(0) }}",
                    "payload_on": "on",
                    "payload_off": "off",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_brightness_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of Brightness command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=100)

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_brightness/set", "on", 0, False),
            call("test_light_brightness/brightness/set", "10", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 100


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_brightness/set",
                    "brightness_command_topic": "test_light_brightness/brightness/set",
                    "effect_command_topic": "test_light_brightness/effect/set",
                    "effect_command_template": '{ "effect": "{{ value }}" }',
                    "effect_list": ["colorloop", "random"],
                    "payload_on": "on",
                    "payload_off": "off",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_effect_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of Effect command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", effect="colorloop")

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_brightness/set", "on", 0, False),
            call(
                "test_light_brightness/effect/set",
                '{ "effect": "colorloop" }',
                0,
                False,
            ),
        ],
        any_order=True,
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "colorloop"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_hs/set",
                    "hs_command_topic": "test_light_hs/hs_color/set",
                    "hs_command_template": '{"hue": {{ hue | int }}, "sat": {{ sat | int}}}',
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_hs_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of HS Color command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", hs_color=(30, 100))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_hs/set", "ON", 0, False),
            call("test_light_hs/hs_color/set", '{"hue": 30, "sat": 100}', 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["hs_color"] == (30, 100)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "name": "test",
                    "command_topic": "test_light_xy/set",
                    "xy_command_topic": "test_light_xy/xy_color/set",
                    "xy_command_template": "{"
                    '"Color": "{{ (x * 65536) | round | int }},'
                    '{{ (y * 65536) | round | int }}"'
                    "}",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_sending_mqtt_xy_command_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of XY Color command with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", xy_color=(0.151, 0.343))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_xy/set", "ON", 0, False),
            call("test_light_xy/xy_color/set", '{"Color": "9896,22479"}', 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["xy_color"] == (0.151, 0.343)


@pytest.mark.parametrize(
    "hass_config",
    [DEFAULT_CONFIG, {"mqtt": [DEFAULT_CONFIG["mqtt"]]}],
    ids=["platform_key", "listed"],
)
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = light.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = light.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            light.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "state_topic": "test-topic",
                    "state_value_template": "{{ value_json.state }}",
                    "brightness_state_topic": "brightness-state-topic",
                    "color_mode_state_topic": "color-mode-state-topic",
                    "color_temp_state_topic": "color-temp-state-topic",
                    "effect_state_topic": "effect-state-topic",
                    "effect_list": ["effect1", "effect2"],
                    "hs_state_topic": "hs-state-topic",
                    "xy_state_topic": "xy-state-topic",
                    "rgb_state_topic": "rgb-state-topic",
                    "rgbw_state_topic": "rgbw-state-topic",
                    "rgbww_state_topic": "rgbww-state-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("test-topic", '{"state":"ON"}', '{"state":"OFF"}'),
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
        ("brightness-state-topic", "50", "100"),
        ("color-mode-state-topic", "rgb", "color_temp"),
        ("color-temp-state-topic", "800", "200"),
        ("effect-state-topic", "effect1", "effect2"),
        ("hs-state-topic", "210,50", "200,50"),
        ("xy-state-topic", "128,128", "96,96"),
        ("rgb-state-topic", "128,128,128", "128,128,64"),
        ("rgbw-state-topic", "128,128,128,255", "128,128,128,128"),
        ("rgbww-state-topic", "128,128,128,32,255", "128,128,128,64,255"),
    ],
)
async def test_skipped_async_ha_write_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    payload1: str,
    payload2: str,
) -> None:
    """Test a write state command is only called when there is change."""
    await mqtt_mock_entry()
    await help_test_skipped_async_ha_write_state(hass, topic, payload1, payload2)


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            light.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    value_template.replace(
                        "state_value_template", "state_topic"
                    ).replace("_value_template", "_state_topic"): "test-topic",
                    value_template: "{{ value_json.some_var * 1 }}",
                },
            ),
        )
        for value_template in VALUE_TEMPLATE_KEYS
    ],
    ids=VALUE_TEMPLATE_KEYS,
)
async def test_value_template_fails(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the rendering of MQTT value template fails."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, "test-topic", '{"some_var": null }')
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' rendering template"
        in caplog.text
    )
