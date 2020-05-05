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
from tests.common import async_fire_mqtt_message
from tests.components.light import common

DEFAULT_CONFIG = {
    light.DOMAIN: {
        "platform": "mqtt",
        "schema": "json",
        "name": "test",
        "command_topic": "test-topic",
    }
}


class JsonValidator:
    """Helper to compare JSON."""

    def __init__(self, jsondata):
        """Initialize JSON validator."""
        self.jsondata = jsondata

    def __eq__(self, other):
        """Compare JSON data."""
        return json.loads(self.jsondata) == json.loads(other)


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if setup fails with no command topic."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {light.DOMAIN: {"platform": "mqtt", "schema": "json", "name": "test"}},
    )
    assert hass.states.get("light.test") is None


async def test_no_color_brightness_color_temp_white_val_if_no_topics(hass, mqtt_mock):
    """Test for no RGB, brightness, color temp, effect, white val or XY."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "state_topic": "test_light_rgb",
                "command_topic": "test_light_rgb/set",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling of the state via topic."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "state_topic": "test_light_rgb",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "color_temp": True,
                "effect": True,
                "rgb": True,
                "white_value": True,
                "xy": True,
                "hs": True,
                "qos": "0",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 191
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light, full white
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"r":255,"g":255,"b":255},'
        '"brightness":255,'
        '"color_temp":155,'
        '"effect":"colorloop",'
        '"white_value":150}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 155
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("white_value") == 150
    assert state.attributes.get("xy_color") == (0.323, 0.329)
    assert state.attributes.get("hs_color") == (0.0, 0.0)

    # Turn the light off
    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "brightness":100}')

    light_state = hass.states.get("light.test")

    assert light_state.attributes["brightness"] == 100

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", ' '"color":{"r":125,"g":125,"b":125}}'
    )

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("rgb_color") == (255, 255, 255)

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color":{"x":0.135,"y":0.135}}'
    )

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("xy_color") == (0.141, 0.14)

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color":{"h":180,"s":50}}'
    )

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("hs_color") == (180.0, 50.0)

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "color_temp":155}')

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("color_temp") == 155

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "effect":"colorloop"}'
    )

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("effect") == "colorloop"

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "white_value":155}')

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("white_value") == 155


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
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {
                light.DOMAIN: {
                    "platform": "mqtt",
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "color_temp": True,
                    "effect": True,
                    "hs": True,
                    "rgb": True,
                    "xy": True,
                    "white_value": True,
                    "qos": 2,
                }
            },
        )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("hs_color") == (100, 100)
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("color_temp") == 100
    assert state.attributes.get("white_value") == 50
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 191
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state": "ON"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_on(hass, "light.test", color_temp=90)

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "color_temp": 90}'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state": "OFF"}', 2, False
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
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255,'
                    ' "x": 0.14, "y": 0.131, "h": 210.824, "s": 100.0},'
                    ' "brightness": 50}'
                ),
                2,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59,'
                    ' "x": 0.654, "y": 0.301, "h": 359.0, "s": 78.0},'
                    ' "brightness": 50}'
                ),
                2,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0,'
                    ' "x": 0.611, "y": 0.375, "h": 30.118, "s": 100.0},'
                    ' "white_value": 80}'
                ),
                2,
                False,
            ),
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


async def test_sending_hs_color(hass, mqtt_mock):
    """Test light.turn_on with hs color sends hs color parameters."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "hs": True,
            }
        },
    )

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
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"h": 210.824, "s": 100.0},'
                    ' "brightness": 50}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"h": 359.0, "s": 78.0},'
                    ' "brightness": 50}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"h": 30.118, "s": 100.0},'
                    ' "white_value": 80}'
                ),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_sending_rgb_color_no_brightness(hass, mqtt_mock):
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "rgb": True,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], brightness=255
    )

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "color": {"r": 0, "g": 24, "b": 50}}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "color": {"r": 50, "g": 11, "b": 11}}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0}}'),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_sending_rgb_color_with_brightness(hass, mqtt_mock):
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "rgb": True,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255},'
                    ' "brightness": 50}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59},'
                    ' "brightness": 255}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "brightness": 1}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0},'
                    ' "white_value": 80}'
                ),
                0,
                False,
            ),
        ],
    )


async def test_sending_rgb_color_with_scaled_brightness(hass, mqtt_mock):
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "brightness_scale": 100,
                "rgb": True,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255},'
                    ' "brightness": 20}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59},'
                    ' "brightness": 100}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "brightness": 1}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0},'
                    ' "white_value": 80}'
                ),
                0,
                False,
            ),
        ],
    )


async def test_sending_xy_color(hass, mqtt_mock):
    """Test light.turn_on with hs color sends xy color parameters."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "xy": True,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], white_value=80
    )

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"x": 0.14, "y": 0.131},'
                    ' "brightness": 50}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"x": 0.654, "y": 0.301},'
                    ' "brightness": 50}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"x": 0.611, "y": 0.375},'
                    ' "white_value": 80}'
                ),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_effect(hass, mqtt_mock):
    """Test for effect being sent when included."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "effect": True,
                "qos": 0,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 44

    await common.async_turn_on(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "ON"}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "none"

    await common.async_turn_on(hass, "light.test", effect="rainbow")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "effect": "rainbow"}'),
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "rainbow"

    await common.async_turn_on(hass, "light.test", effect="colorloop")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "effect": "colorloop"}'),
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") == "colorloop"


async def test_flash_short_and_long(hass, mqtt_mock):
    """Test for flash length being sent when included."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "flash_time_short": 5,
                "flash_time_long": 15,
                "qos": 0,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, "light.test", flash="short")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "ON", "flash": 5}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_on(hass, "light.test", flash="long")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "ON", "flash": 15}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON


async def test_transition(hass, mqtt_mock):
    """Test for transition time being sent when included."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "command_topic": "test_light_rgb/set",
                "qos": 0,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 40

    await common.async_turn_on(hass, "light.test", transition=15)

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "transition": 15}'),
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "light.test", transition=30)

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "OFF", "transition": 30}'),
        0,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_brightness_scale(hass, mqtt_mock):
    """Test for brightness scaling."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "state_topic": "test_light_bright_scale",
                "command_topic": "test_light_bright_scale/set",
                "brightness": True,
                "brightness_scale": 99,
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, "test_light_bright_scale", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    # Turn on the light with brightness
    async_fire_mqtt_message(
        hass, "test_light_bright_scale", '{"state":"ON", "brightness": 99}'
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255


async def test_invalid_values(hass, mqtt_mock):
    """Test that invalid color/brightness/white/etc. values are ignored."""
    assert await async_setup_component(
        hass,
        light.DOMAIN,
        {
            light.DOMAIN: {
                "platform": "mqtt",
                "schema": "json",
                "name": "test",
                "state_topic": "test_light_rgb",
                "command_topic": "test_light_rgb/set",
                "brightness": True,
                "color_temp": True,
                "rgb": True,
                "white_value": True,
                "qos": "0",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 187
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("white_value") is None
    assert state.attributes.get("color_temp") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"r":255,"g":255,"b":255},'
        '"brightness": 255,'
        '"white_value": 255,'
        '"color_temp": 100,'
        '"effect": "rainbow"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("white_value") == 255
    assert state.attributes.get("color_temp") == 100

    # Bad HS color values
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON",' '"color":{"h":"bad","s":"val"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad RGB color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",' '"color":{"r":"bad","g":"val","b":"test"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad XY color values
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON",' '"color":{"x":"bad","y":"val"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad brightness values
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON",' '"brightness": "badValue"}'
    )

    # Brightness should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    # Bad white value
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON",' '"white_value": "badValue"}'
    )

    # White value should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("white_value") == 255

    # Bad color temperature
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON",' '"color_temp": "badValue"}'
    )

    # Color temperature should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 100


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
                "schema": "json",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "schema": "json",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, light.DOMAIN, config)


async def test_discovery_removal(hass, mqtt_mock, caplog):
    """Test removal of discovered mqtt_json lights."""
    data = '{ "name": "test",' '  "schema": "json",' '  "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, light.DOMAIN, data)


async def test_discovery_update_light(hass, mqtt_mock, caplog):
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "json",'
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
        '  "schema": "json",'
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
