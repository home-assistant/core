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

Configuration for HS Version with brightness:

light:
  platform: mqtt
  name: "Office Light HS"
  state_topic: "office/hs1/light/status"
  command_topic: "office/hs1/light/switch"
  brightness_state_topic: "office/hs1/brightness/status"
  brightness_command_topic: "office/hs1/brightness/set"
  hs_state_topic: "office/hs1/hs/status"
  hs_command_topic: "office/hs1/hs/set"
  qos: 0
  payload_on: "on"
  payload_off: "off"

"""
from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from .test_common import (
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
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

from tests.async_mock import call, patch
from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_fire_mqtt_message,
)
from tests.components.light import common

DEFAULT_CONFIG = {
    light.DOMAIN: {"platform": "mqtt", "name": "test", "command_topic": "test-topic"}
}


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if command fails with command topic."""
    assert await async_setup_component(
        hass, light.DOMAIN, {light.DOMAIN: {"platform": "mqtt", "name": "test"}}
    )
    assert hass.states.get("light.test") is None


async def test_no_color_brightness_color_temp_hs_white_xy_if_no_topics(hass, mqtt_mock):
    """Test if there is no color and brightness if no topic."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test_light_rgb/status",
                "command_topic": "test_light_rgb/set",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling of the state via topic."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "test_light_rgb/status",
            "command_topic": "test_light_rgb/set",
            "brightness_state_topic": "test_light_rgb/brightness/status",
            "brightness_command_topic": "test_light_rgb/brightness/set",
            "rgb_state_topic": "test_light_rgb/rgb/status",
            "rgb_command_topic": "test_light_rgb/rgb/set",
            "color_temp_state_topic": "test_light_rgb/color_temp/status",
            "color_temp_command_topic": "test_light_rgb/color_temp/set",
            "effect_state_topic": "test_light_rgb/effect/status",
            "effect_command_topic": "test_light_rgb/effect/set",
            "hs_state_topic": "test_light_rgb/hs/status",
            "hs_command_topic": "test_light_rgb/hs/set",
            "white_value_state_topic": "test_light_rgb/white_value/status",
            "white_value_command_topic": "test_light_rgb/white_value/set",
            "xy_state_topic": "test_light_rgb/xy/status",
            "xy_command_topic": "test_light_rgb/xy/set",
            "qos": "0",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 150
    assert state.attributes.get("effect") == "none"
    assert state.attributes.get("hs_color") == (0, 0)
    assert state.attributes.get("white_value") == 255
    assert state.attributes.get("xy_color") == (0.323, 0.329)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "0")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")

    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "100")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 100

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "300")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["color_temp"] == 300

    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "rainbow")
    light_state = hass.states.get("light.test")
    assert light_state.attributes["effect"] == "rainbow"

    async_fire_mqtt_message(hass, "test_light_rgb/white_value/status", "100")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["white_value"] == 100

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "125,125,125")

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (255, 255, 255)

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "200,50")

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (200, 50)

    async_fire_mqtt_message(hass, "test_light_rgb/xy/status", "0.675,0.322")

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.672, 0.324)


async def test_invalid_state_via_topic(hass, mqtt_mock, caplog):
    """Test handling of empty data via topic."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "test_light_rgb/status",
            "command_topic": "test_light_rgb/set",
            "brightness_state_topic": "test_light_rgb/brightness/status",
            "brightness_command_topic": "test_light_rgb/brightness/set",
            "rgb_state_topic": "test_light_rgb/rgb/status",
            "rgb_command_topic": "test_light_rgb/rgb/set",
            "color_temp_state_topic": "test_light_rgb/color_temp/status",
            "color_temp_command_topic": "test_light_rgb/color_temp/set",
            "effect_state_topic": "test_light_rgb/effect/status",
            "effect_command_topic": "test_light_rgb/effect/set",
            "hs_state_topic": "test_light_rgb/hs/status",
            "hs_command_topic": "test_light_rgb/hs/set",
            "white_value_state_topic": "test_light_rgb/white_value/status",
            "white_value_command_topic": "test_light_rgb/white_value/set",
            "xy_state_topic": "test_light_rgb/xy/status",
            "xy_command_topic": "test_light_rgb/xy/set",
            "qos": "0",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "1")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 150
    assert state.attributes.get("effect") == "none"
    assert state.attributes.get("hs_color") == (0, 0)
    assert state.attributes.get("white_value") == 255
    assert state.attributes.get("xy_color") == (0.323, 0.329)

    async_fire_mqtt_message(hass, "test_light_rgb/status", "")
    assert "Ignoring empty state message" in caplog.text
    light_state = hass.states.get("light.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", "")
    assert "Ignoring empty brightness message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 255

    async_fire_mqtt_message(hass, "test_light_rgb/color_temp/status", "")
    assert "Ignoring empty color temp message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes["color_temp"] == 150

    async_fire_mqtt_message(hass, "test_light_rgb/effect/status", "")
    assert "Ignoring empty effect message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes["effect"] == "none"

    async_fire_mqtt_message(hass, "test_light_rgb/white_value/status", "")
    assert "Ignoring empty white value message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes["white_value"] == 255

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", "")
    assert "Ignoring empty rgb message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (255, 255, 255)

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "")
    assert "Ignoring empty hs message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (0, 0)

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", "bad,bad")
    assert "Failed to parse hs state update" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (0, 0)

    async_fire_mqtt_message(hass, "test_light_rgb/xy/status", "")
    assert "Ignoring empty xy-color message" in caplog.text
    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.323, 0.329)


async def test_brightness_controlling_scale(hass, mqtt_mock):
    """Test the brightness controlling scale."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
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
            },
        )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    async_fire_mqtt_message(hass, "test_scale/status", "off")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    async_fire_mqtt_message(hass, "test_scale/brightness/status", "99")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["brightness"] == 255


async def test_brightness_from_rgb_controlling_scale(hass, mqtt_mock):
    """Test the brightness controlling scale."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "name": "test",
                    "state_topic": "test_scale_rgb/status",
                    "command_topic": "test_scale_rgb/set",
                    "rgb_state_topic": "test_scale_rgb/rgb/status",
                    "rgb_command_topic": "test_scale_rgb/rgb/set",
                    "qos": 0,
                    "payload_on": "on",
                    "payload_off": "off",
                }
            },
        )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_scale_rgb/status", "on")
    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "255,0,0")

    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 255

    async_fire_mqtt_message(hass, "test_scale_rgb/rgb/status", "127,0,0")

    state = hass.states.get("light.test")
    assert state.attributes.get("brightness") == 127


async def test_white_value_controlling_scale(hass, mqtt_mock):
    """Test the white_value controlling scale."""
    with assert_setup_component(1, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "name": "test",
                    "state_topic": "test_scale/status",
                    "command_topic": "test_scale/set",
                    "white_value_state_topic": "test_scale/white_value/status",
                    "white_value_command_topic": "test_scale/white_value/set",
                    "white_value_scale": "99",
                    "qos": 0,
                    "payload_on": "on",
                    "payload_off": "off",
                }
            },
        )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("white_value") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 255

    async_fire_mqtt_message(hass, "test_scale/status", "off")

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_scale/status", "on")

    async_fire_mqtt_message(hass, "test_scale/white_value/status", "99")

    light_state = hass.states.get("light.test")
    assert light_state.attributes["white_value"] == 255


async def test_controlling_state_via_topic_with_templates(hass, mqtt_mock):
    """Test the setting of the state with a template."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "test_light_rgb/status",
            "command_topic": "test_light_rgb/set",
            "brightness_command_topic": "test_light_rgb/brightness/set",
            "rgb_command_topic": "test_light_rgb/rgb/set",
            "color_temp_command_topic": "test_light_rgb/color_temp/set",
            "effect_command_topic": "test_light_rgb/effect/set",
            "hs_command_topic": "test_light_rgb/hs/set",
            "white_value_command_topic": "test_light_rgb/white_value/set",
            "xy_command_topic": "test_light_rgb/xy/set",
            "brightness_state_topic": "test_light_rgb/brightness/status",
            "color_temp_state_topic": "test_light_rgb/color_temp/status",
            "effect_state_topic": "test_light_rgb/effect/status",
            "hs_state_topic": "test_light_rgb/hs/status",
            "rgb_state_topic": "test_light_rgb/rgb/status",
            "white_value_state_topic": "test_light_rgb/white_value/status",
            "xy_state_topic": "test_light_rgb/xy/status",
            "state_value_template": "{{ value_json.hello }}",
            "brightness_value_template": "{{ value_json.hello }}",
            "color_temp_value_template": "{{ value_json.hello }}",
            "effect_value_template": "{{ value_json.hello }}",
            "hs_value_template": '{{ value_json.hello | join(",") }}',
            "rgb_value_template": '{{ value_json.hello | join(",") }}',
            "white_value_template": "{{ value_json.hello }}",
            "xy_value_template": '{{ value_json.hello | join(",") }}',
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("rgb_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb/rgb/status", '{"hello": [1, 2, 3]}')
    async_fire_mqtt_message(hass, "test_light_rgb/status", '{"hello": "ON"}')
    async_fire_mqtt_message(hass, "test_light_rgb/brightness/status", '{"hello": "50"}')
    async_fire_mqtt_message(
        hass, "test_light_rgb/color_temp/status", '{"hello": "300"}'
    )
    async_fire_mqtt_message(
        hass, "test_light_rgb/effect/status", '{"hello": "rainbow"}'
    )
    async_fire_mqtt_message(
        hass, "test_light_rgb/white_value/status", '{"hello": "75"}'
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("rgb_color") == (84, 169, 255)
    assert state.attributes.get("color_temp") == 300
    assert state.attributes.get("effect") == "rainbow"
    assert state.attributes.get("white_value") == 75

    async_fire_mqtt_message(hass, "test_light_rgb/hs/status", '{"hello": [100,50]}')

    state = hass.states.get("light.test")
    assert state.attributes.get("hs_color") == (100, 50)

    async_fire_mqtt_message(
        hass, "test_light_rgb/xy/status", '{"hello": [0.123,0.123]}'
    )

    state = hass.states.get("light.test")
    assert state.attributes.get("xy_color") == (0.14, 0.131)


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test the sending of command in optimistic mode."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light_rgb/set",
            "brightness_command_topic": "test_light_rgb/brightness/set",
            "rgb_command_topic": "test_light_rgb/rgb/set",
            "color_temp_command_topic": "test_light_rgb/color_temp/set",
            "effect_command_topic": "test_light_rgb/effect/set",
            "hs_command_topic": "test_light_rgb/hs/set",
            "white_value_command_topic": "test_light_rgb/white_value/set",
            "xy_command_topic": "test_light_rgb/xy/set",
            "effect_list": ["colorloop", "random"],
            "qos": 2,
            "payload_on": "on",
            "payload_off": "off",
        }
    }
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
            assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("hs_color") == (100, 100)
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("color_temp") == 100
    assert state.attributes.get("white_value") == 50
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "on", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", "off", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    mqtt_mock.reset_mock()
    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 2, False),
            call("test_light_rgb/rgb/set", "255,128,0", 2, False),
            call("test_light_rgb/brightness/set", 50, 2, False),
            call("test_light_rgb/hs/set", "359.0,78.0", 2, False),
            call("test_light_rgb/white_value/set", 80, 2, False),
            call("test_light_rgb/xy/set", "0.14,0.131", 2, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["rgb_color"] == (255, 128, 0)
    assert state.attributes["brightness"] == 50
    assert state.attributes["hs_color"] == (30.118, 100)
    assert state.attributes["white_value"] == 80
    assert state.attributes["xy_color"] == (0.611, 0.375)


async def test_sending_mqtt_rgb_command_with_template(hass, mqtt_mock):
    """Test the sending of RGB command with template."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
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

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 64])

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_rgb/set", "on", 0, False),
            call("test_light_rgb/rgb/set", "#ff803f", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["rgb_color"] == (255, 128, 63)


async def test_sending_mqtt_color_temp_command_with_template(hass, mqtt_mock):
    """Test the sending of Color Temp command with template."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light_color_temp/set",
            "color_temp_command_topic": "test_light_color_temp/color_temp/set",
            "color_temp_command_template": "{{ (1000 / value) | round(0) }}",
            "payload_on": "on",
            "payload_off": "off",
            "qos": 0,
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test", color_temp=100)

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light_color_temp/set", "on", 0, False),
            call("test_light_color_temp/color_temp/set", "10", 0, False),
        ],
        any_order=True,
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["color_temp"] == 100


async def test_show_brightness_if_only_command_topic(hass, mqtt_mock):
    """Test the brightness if only a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "brightness_command_topic": "test_light_rgb/brightness/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255


async def test_show_color_temp_only_if_command_topic(hass, mqtt_mock):
    """Test the color temp only if a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "color_temp_command_topic": "test_light_rgb/brightness/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("color_temp") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 150


async def test_show_effect_only_if_command_topic(hass, mqtt_mock):
    """Test the effect only if a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "effect_command_topic": "test_light_rgb/effect/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("effect") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "none"


async def test_show_hs_if_only_command_topic(hass, mqtt_mock):
    """Test the hs if only a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "hs_command_topic": "test_light_rgb/hs/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("hs_color") == (0, 0)


async def test_show_white_value_if_only_command_topic(hass, mqtt_mock):
    """Test the white_value if only a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "white_value_command_topic": "test_light_rgb/white_value/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("white_value") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 255


async def test_show_xy_if_only_command_topic(hass, mqtt_mock):
    """Test the xy if only a command topic is present."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "xy_command_topic": "test_light_rgb/xy/set",
            "command_topic": "test_light_rgb/set",
            "state_topic": "test_light_rgb/status",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("xy_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb/status", "ON")

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("xy_color") == (0.323, 0.329)


async def test_on_command_first(hass, mqtt_mock):
    """Test on command being sent before brightness."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "brightness_command_topic": "test_light/bright",
            "on_command_type": "first",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test", brightness=50)

    # Should get the following MQTT messages.
    #    test_light/set: 'ON'
    #    test_light/bright: 50
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/set", "ON", 0, False),
            call("test_light/bright", 50, 0, False),
        ],
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


async def test_on_command_last(hass, mqtt_mock):
    """Test on command being sent after brightness."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "brightness_command_topic": "test_light/bright",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test", brightness=50)

    # Should get the following MQTT messages.
    #    test_light/bright: 50
    #    test_light/set: 'ON'
    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/bright", 50, 0, False),
            call("test_light/set", "ON", 0, False),
        ],
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)


async def test_on_command_brightness(hass, mqtt_mock):
    """Test on command being sent as only brightness."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "brightness_command_topic": "test_light/bright",
            "rgb_command_topic": "test_light/rgb",
            "on_command_type": "brightness",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn on w/ no brightness - should set to max
    await common.async_turn_on(hass, "light.test")

    # Should get the following MQTT messages.
    #    test_light/bright: 255
    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 255, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ brightness
    await common.async_turn_on(hass, "light.test", brightness=50)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 50, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    # Turn on w/ just a color to ensure brightness gets
    # added and sent.
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,128,0", 0, False),
            call("test_light/bright", 50, 0, False),
        ],
        any_order=True,
    )


async def test_on_command_brightness_scaled(hass, mqtt_mock):
    """Test brightness scale."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "brightness_command_topic": "test_light/bright",
            "brightness_scale": 100,
            "rgb_command_topic": "test_light/rgb",
            "on_command_type": "brightness",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Turn on w/ no brightness - should set to max
    await common.async_turn_on(hass, "light.test")

    # Should get the following MQTT messages.
    #    test_light/bright: 100
    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 100, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with("test_light/set", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ brightness
    await common.async_turn_on(hass, "light.test", brightness=50)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 20, 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ max brightness
    await common.async_turn_on(hass, "light.test", brightness=255)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 100, 0, False)
    mqtt_mock.async_publish.reset_mock()

    # Turn on w/ min brightness
    await common.async_turn_on(hass, "light.test", brightness=1)

    mqtt_mock.async_publish.assert_called_once_with("test_light/bright", 1, 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "light.test")

    # Turn on w/ just a color to ensure brightness gets
    # added and sent.
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

    mqtt_mock.async_publish.assert_has_calls(
        [
            call("test_light/rgb", "255,128,0", 0, False),
            call("test_light/bright", 1, 0, False),
        ],
        any_order=True,
    )


async def test_on_command_rgb(hass, mqtt_mock):
    """Test on command in RGB brightness mode."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "rgb_command_topic": "test_light/rgb",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

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
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

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


async def test_on_command_rgb_template(hass, mqtt_mock):
    """Test on command in RGB brightness mode with RGB template."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "rgb_command_topic": "test_light/rgb",
            "rgb_command_template": "{{ red }}/{{ green }}/{{ blue }}",
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(hass, "light.test", brightness=127)

    # Should get the following MQTT messages.
    #    test_light/rgb: '127,127,127'
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


async def test_effect(hass, mqtt_mock):
    """Test effect."""
    config = {
        light.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "test_light/set",
            "effect_command_topic": "test_light/effect/set",
            "effect_list": ["rainbow", "colorloop"],
        }
    }

    assert await async_setup_component(hass, light.DOMAIN, config)

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

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


async def test_unique_id(hass):
    """Test unique id option only creates one light per unique_id."""
    config = {
        light.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, light.DOMAIN, config)


async def test_discovery_removal_light(hass, mqtt_mock, caplog):
    """Test removal of discovered light."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock, caplog, light.DOMAIN, data)


async def test_discovery_deprecated(hass, mqtt_mock, caplog):
    """Test discovery of mqtt light with deprecated platform option."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {"mqtt": {}}, entry)
    data = (
        '{ "name": "Beer",' '  "platform": "mqtt",' '  "command_topic": "test_topic"}'
    )
    async_fire_mqtt_message(hass, "homeassistant/light/bla/config", data)
    await hass.async_block_till_done()
    state = hass.states.get("light.beer")
    assert state is not None
    assert state.name == "Beer"


async def test_discovery_update_light(hass, mqtt_mock, caplog):
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, light.DOMAIN, data1, data2
    )


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
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
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG
    )
