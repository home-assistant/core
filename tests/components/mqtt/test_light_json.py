"""The tests for the MQTT JSON light platform.

Configuration with RGB, brightness, color temp, effect, and XY:

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        color_temp: true
        effect: true
        rgb: true
        xy: true

Configuration with RGB, brightness, color temp and effect:

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        color_temp: true
        effect: true
        rgb: true

Configuration with RGB, brightness and color temp:

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        rgb: true
        color_temp: true

Configuration with RGB, brightness:

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        rgb: true

Config without RGB:

mqtt:
    light:
        schema: json
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
import copy
from pathlib import Path
from unittest.mock import call, patch

import pytest

from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.light.schema_basic import (
    MQTT_LIGHT_ATTRIBUTES_BLOCKED,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.setup import async_setup_component
from homeassistant.util.json import JsonValueType, json_loads

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
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, mock_restore_cache
from tests.components.light import common
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        light.DOMAIN: {
            "schema": "json",
            "name": "test",
            "command_topic": "test-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def light_platform_only():
    """Only setup the light platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.LIGHT]):
        yield


class JsonValidator:
    """Helper to compare JSON."""

    def __init__(self, jsondata: JsonValueType) -> None:
        """Initialize JSON validator."""
        self.jsondata = jsondata

    def __eq__(self, other: JsonValueType) -> bool:
        """Compare JSON data."""
        return json_loads(self.jsondata) == json_loads(other)


async def test_fail_setup_if_no_command_topic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if setup fails with no command topic."""
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: {light.DOMAIN: {"schema": "json", "name": "test"}}},
    )
    assert (
        "Invalid config for [mqtt]: required key not provided @ data['mqtt']['light'][0]['command_topic']. Got None."
        in caplog.text
    )


@pytest.mark.parametrize("deprecated", ("color_temp", "hs", "rgb", "xy"))
async def test_fail_setup_if_color_mode_deprecated(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, deprecated
) -> None:
    """Test if setup fails if color mode is combined with deprecated config keys."""
    supported_color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "xy"]

    config = {
        light.DOMAIN: {
            "brightness": True,
            "color_mode": True,
            "command_topic": "test_light_rgb/set",
            "name": "test",
            "schema": "json",
            "supported_color_modes": supported_color_modes,
        }
    }
    config[light.DOMAIN][deprecated] = True
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: config},
    )
    assert (
        "Invalid config for [mqtt]: color_mode must not be combined with any of"
        in caplog.text
    )


@pytest.mark.parametrize(
    ("supported_color_modes", "error"),
    [
        (["onoff", "rgb"], "Unknown error calling mqtt CONFIG_SCHEMA"),
        (["brightness", "rgb"], "Unknown error calling mqtt CONFIG_SCHEMA"),
        (["unknown"], "Invalid config for [mqtt]: value must be one of [<ColorMode."),
    ],
)
async def test_fail_setup_if_color_modes_invalid(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture, supported_color_modes, error
) -> None:
    """Test if setup fails if supported color modes is invalid."""
    config = {
        light.DOMAIN: {
            "brightness": True,
            "color_mode": True,
            "command_topic": "test_light_rgb/set",
            "name": "test",
            "schema": "json",
            "supported_color_modes": supported_color_modes,
        }
    }
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: config},
    )
    assert error in caplog.text


async def test_legacy_rgb_light(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test legacy RGB light flags expected features and color modes."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "rgb": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    color_modes = [light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features


async def test_no_color_brightness_color_temp_if_no_topics(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for no RGB, brightness, color temp, effector XY."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state": null}')

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN


async def test_controlling_state_via_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the controlling of the state via topic."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "color_temp": True,
                    "effect": True,
                    "rgb": True,
                    "xy": True,
                    "hs": True,
                    "qos": "0",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    color_modes = [light.ColorMode.COLOR_TEMP, light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = (
        light.SUPPORT_EFFECT | light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"r":255,"g":255,"b":255},'
        '"brightness":255,'
        '"color_temp":155,'
        '"effect":"colorloop"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") is None  # rgb color has priority
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("xy_color") == (0.323, 0.329)
    assert state.attributes.get("hs_color") == (0.0, 0.0)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"brightness":255,'
        '"color":null,'
        '"color_temp":155,'
        '"effect":"colorloop"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (
        255,
        253,
        248,
    )  # temp converted to color
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") == 155
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("xy_color") == (0.328, 0.334)  # temp converted to color
    assert state.attributes.get("hs_color") == (44.098, 2.43)  # temp converted to color

    # Turn the light off
    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "brightness":100}')

    light_state = hass.states.get("light.test")

    assert light_state.attributes["brightness"] == 100

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color":{"r":125,"g":125,"b":125}}'
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

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "color":null}')

    light_state = hass.states.get("light.test")
    assert "hs_color" in light_state.attributes  # Color temp approximation

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "color_temp":155}')

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("color_temp") == 155

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "color_temp":null}')

    light_state = hass.states.get("light.test")
    assert "color_temp" not in light_state.attributes

    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "effect":"colorloop"}'
    )

    light_state = hass.states.get("light.test")
    assert light_state.attributes.get("effect") == "colorloop"


async def test_controlling_state_via_topic2(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling of the state via topic for a light supporting color mode."""
    supported_color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "white", "xy"]

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "brightness": True,
                    "color_mode": True,
                    "command_topic": "test_light_rgb/set",
                    "effect": True,
                    "name": "test",
                    "qos": "0",
                    "schema": "json",
                    "state_topic": "test_light_rgb",
                    "supported_color_modes": supported_color_modes,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.SUPPORT_EFFECT | light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_mode") is None
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("supported_color_modes") == supported_color_modes
    assert state.attributes.get("xy_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light, rgbww mode, additional values in the update
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color_mode":"rgbww",'
        '"color":{"r":255,"g":128,"b":64, "c": 32, "w": 16, "x": 1, "y": 1},'
        '"brightness":255,'
        '"color_temp":155,'
        '"effect":"colorloop"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_mode") == "rgbww"
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("hs_color") == (20.552, 70.98)
    assert state.attributes.get("rgb_color") == (255, 136, 74)
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") == (255, 128, 64, 32, 16)
    assert state.attributes.get("xy_color") == (0.571, 0.361)

    # Light turned off
    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Light turned on, brightness 100
    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "brightness":100}')
    state = hass.states.get("light.test")
    assert state.attributes["brightness"] == 100

    # RGB color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"rgb", "color":{"r":64,"g":128,"b":255}}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "rgb"
    assert state.attributes.get("rgb_color") == (64, 128, 255)

    # RGBW color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"rgbw", "color":{"r":64,"g":128,"b":255,"w":32}}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "rgbw"
    assert state.attributes.get("rgbw_color") == (64, 128, 255, 32)

    # XY color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"xy", "color":{"x":0.135,"y":0.235}}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "xy"
    assert state.attributes.get("xy_color") == (0.135, 0.235)

    # HS color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"hs", "color":{"h":180,"s":50}}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "hs"
    assert state.attributes.get("hs_color") == (180.0, 50.0)

    # Color temp
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"color_temp", "color_temp":155}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "color_temp"
    assert state.attributes.get("color_temp") == 155

    # White
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"white", "brightness":123}',
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == "white"
    assert state.attributes.get("brightness") == 123

    # Effect
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "effect":"other_effect"}'
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("effect") == "other_effect"

    # Invalid color mode
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color_mode":"col_temp"}'
    )
    assert "Invalid color mode received" in caplog.text
    caplog.clear()

    # Incomplete color
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color_mode":"rgb"}'
    )
    assert "Invalid or incomplete color value received" in caplog.text
    caplog.clear()

    # Invalid color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"rgb", "color":{"r":64,"g":128,"b":"cow"}}',
    )
    assert "Invalid or incomplete color value received" in caplog.text


async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the sending of command in optimistic mode."""
    fake_state = State(
        "light.test",
        "on",
        {
            "brightness": 95,
            "hs_color": [100, 100],
            "effect": "random",
            "color_temp": 100,
        },
    )
    mock_restore_cache(hass, (fake_state,))

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "color_temp": True,
                    "effect": True,
                    "hs": True,
                    "rgb": True,
                    "xy": True,
                    "qos": 2,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("hs_color") == (100, 100)
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("color_temp") is None  # hs_color has priority
    color_modes = [light.ColorMode.COLOR_TEMP, light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = (
        light.SUPPORT_EFFECT | light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state":"ON"}', 2, False
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
    assert state.attributes.get("color_mode") == light.ColorMode.COLOR_TEMP
    assert state.attributes.get("color_temp") == 90

    await common.async_turn_off(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state":"OFF"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    mqtt_mock.reset_mock()
    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"r": 0, "g": 123, "b": 255,'
            ' "x": 0.14, "y": 0.131, "h": 210.824, "s": 100.0},'
            ' "brightness": 50}'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == light.ColorMode.HS
    assert state.attributes["brightness"] == 50
    assert state.attributes["hs_color"] == (210.824, 100.0)
    assert state.attributes["rgb_color"] == (0, 123, 255)
    assert state.attributes["xy_color"] == (0.14, 0.131)

    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"r": 255, "g": 56, "b": 59,'
            ' "x": 0.654, "y": 0.301, "h": 359.0, "s": 78.0},'
            ' "brightness": 50}'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_mode") == light.ColorMode.HS
    assert state.attributes["brightness"] == 50
    assert state.attributes["hs_color"] == (359.0, 78.0)
    assert state.attributes["rgb_color"] == (255, 56, 59)
    assert state.attributes["xy_color"] == (0.654, 0.301)

    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0,'
            ' "x": 0.611, "y": 0.375, "h": 30.118, "s": 100.0}}'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_mode") == light.ColorMode.HS
    assert state.attributes["brightness"] == 50
    assert state.attributes["hs_color"] == (30.118, 100)
    assert state.attributes["rgb_color"] == (255, 128, 0)
    assert state.attributes["xy_color"] == (0.611, 0.375)


async def test_sending_mqtt_commands_and_optimistic2(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the sending of command in optimistic mode for a light supporting color mode."""
    supported_color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "white", "xy"]
    fake_state = State(
        "light.test",
        "on",
        {
            "brightness": 95,
            "color_temp": 100,
            "color_mode": "rgb",
            "effect": "random",
            "hs_color": [100, 100],
        },
    )
    mock_restore_cache(hass, (fake_state,))

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "brightness": True,
                    "color_mode": True,
                    "command_topic": "test_light_rgb/set",
                    "effect": True,
                    "name": "test",
                    "qos": 2,
                    "schema": "json",
                    "supported_color_modes": supported_color_modes,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    expected_features = (
        light.SUPPORT_EFFECT | light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("color_mode") == "rgb"
    assert state.attributes.get("color_temp") is None
    assert state.attributes.get("effect") == "random"
    assert state.attributes.get("hs_color") is None
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("rgbw_color") is None
    assert state.attributes.get("rgbww_color") is None
    assert state.attributes.get("supported_color_modes") == supported_color_modes
    assert state.attributes.get("white") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn the light on
    await common.async_turn_on(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state":"ON"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # Turn the light on with color temperature
    await common.async_turn_on(hass, "light.test", color_temp=90)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state":"ON","color_temp":90}'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    # Turn the light off
    await common.async_turn_off(hass, "light.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", '{"state":"OFF"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    # Set hs color
    await common.async_turn_on(hass, "light.test", brightness=75, hs_color=[359, 78])
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "hs"
    assert state.attributes["hs_color"] == (359, 78)
    assert state.attributes["rgb_color"] == (255, 56, 59)
    assert state.attributes["xy_color"] == (0.654, 0.301)
    assert "rgbw_color" not in state.attributes
    assert "rgbww_color" not in state.attributes
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"h": 359.0, "s": 78.0}, "brightness": 75}'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set rgb color
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["hs_color"] == (30.118, 100.0)
    assert state.attributes["rgb_color"] == (255, 128, 0)
    assert state.attributes["xy_color"] == (0.611, 0.375)
    assert "rgbw_color" not in state.attributes
    assert "rgbww_color" not in state.attributes
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0} }'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set rgbw color
    await common.async_turn_on(hass, "light.test", rgbw_color=[255, 128, 0, 123])
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 128, 0, 123)
    assert state.attributes["hs_color"] == (30.0, 67.451)
    assert state.attributes["rgb_color"] == (255, 169, 83)
    assert "rgbww_color" not in state.attributes
    assert state.attributes["xy_color"] == (0.526, 0.393)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0, "w": 123} }'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set rgbww color
    await common.async_turn_on(hass, "light.test", rgbww_color=[255, 128, 0, 45, 32])
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 128, 0, 45, 32)
    assert state.attributes["hs_color"] == (29.872, 92.157)
    assert state.attributes["rgb_color"] == (255, 137, 20)
    assert "rgbw_color" not in state.attributes
    assert state.attributes["xy_color"] == (0.596, 0.382)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"r": 255, "g": 128, "b": 0, "c": 45, "w": 32} }'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set xy color
    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.223]
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 50
    assert state.attributes["color_mode"] == "xy"
    assert state.attributes["hs_color"] == (196.471, 100.0)
    assert state.attributes["rgb_color"] == (0, 185, 255)
    assert state.attributes["xy_color"] == (0.123, 0.223)
    assert "rgbw_color" not in state.attributes
    assert "rgbww_color" not in state.attributes
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator(
            '{"state": "ON", "color": {"x": 0.123, "y": 0.223}, "brightness": 50}'
        ),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set to white
    await common.async_turn_on(hass, "light.test", white=75)
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "white"
    assert "hs_color" not in state.attributes
    assert "rgb_color" not in state.attributes
    assert "xy_color" not in state.attributes
    assert "rgbw_color" not in state.attributes
    assert "rgbww_color" not in state.attributes
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "white": 75}'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set to white, brightness also present in turn_on
    await common.async_turn_on(hass, "light.test", brightness=60, white=80)
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 60
    assert state.attributes["color_mode"] == "white"
    assert "hs_color" not in state.attributes
    assert "rgb_color" not in state.attributes
    assert "xy_color" not in state.attributes
    assert "rgbw_color" not in state.attributes
    assert "rgbww_color" not in state.attributes
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "white": 60}'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


async def test_sending_hs_color(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends hs color parameters."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "hs": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    mqtt_mock.reset_mock()
    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

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
                JsonValidator('{"state": "ON", "color": {"h": 30.118, "s": 100.0}}'),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_sending_rgb_color_no_brightness(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "rgb": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

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


async def test_sending_rgb_color_no_brightness2(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    supported_color_modes = ["rgb", "rgbw", "rgbww"]
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "color_mode": True,
                    "command_topic": "test_light_rgb/set",
                    "name": "test",
                    "schema": "json",
                    "supported_color_modes": supported_color_modes,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(
        hass, "light.test", rgb_color=[255, 128, 0], brightness=255
    )
    await common.async_turn_on(
        hass, "light.test", rgbw_color=[128, 64, 32, 16], brightness=128
    )
    await common.async_turn_on(
        hass, "light.test", rgbww_color=[128, 64, 32, 16, 8], brightness=64
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
                JsonValidator('{"state": "ON", "color": {"r": 50, "g": 11, "b": 12}}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0}}'),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 64, "g": 32, "b": 16, "w": 8}}'
                ),
                0,
                False,
            ),
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 32, "g": 16, "b": 8, "c": 4, "w": 2}}'
                ),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_sending_rgb_color_with_brightness(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "rgb": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

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
                JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0}}'),
                0,
                False,
            ),
        ],
    )


async def test_sending_rgb_color_with_scaled_brightness(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "brightness_scale": 100,
                    "rgb": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

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
                JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0}}'),
                0,
                False,
            ),
        ],
    )


async def test_sending_scaled_white(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with scaled white."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "brightness_scale": 100,
                    "color_mode": True,
                    "supported_color_modes": ["hs", "white"],
                    "white_scale": 50,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "light.test", brightness=128)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state":"ON", "brightness":50}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", brightness=255, white=25)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state":"ON", "white":50}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_on(hass, "light.test", white=25)
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state":"ON", "white":5}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def test_sending_xy_color(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends xy color parameters."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "xy": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=[0.123, 0.123]
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=[359, 78])
    await common.async_turn_on(hass, "light.test", rgb_color=[255, 128, 0])

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
                JsonValidator('{"state": "ON", "color": {"x": 0.611, "y": 0.375}}'),
                0,
                False,
            ),
        ],
        any_order=True,
    )


async def test_effect(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for effect being sent when included."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "effect": True,
                    "qos": 0,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.SUPPORT_EFFECT | light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features

    await common.async_turn_on(hass, "light.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "ON"}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("effect") is None

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


async def test_flash_short_and_long(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for flash length being sent when included."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "flash_time_short": 5,
                    "flash_time_long": 15,
                    "qos": 0,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features

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

    await common.async_turn_off(hass, "light.test", flash="short")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "OFF", "flash": 5}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    await common.async_turn_off(hass, "light.test", flash="long")

    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set", JsonValidator('{"state": "OFF", "flash": 15}'), 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


async def test_transition(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for transition time being sent when included."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "qos": 0,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
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


async def test_brightness_scale(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for brightness scaling."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_bright_scale",
                    "command_topic": "test_light_bright_scale/set",
                    "brightness": True,
                    "brightness_scale": 99,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, "test_light_bright_scale", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") is None

    # Turn on the light with brightness
    async_fire_mqtt_message(
        hass, "test_light_bright_scale", '{"state":"ON", "brightness": 99}'
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255


async def test_white_scale(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test for white scaling."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_bright_scale",
                    "command_topic": "test_light_bright_scale/set",
                    "brightness": True,
                    "brightness_scale": 99,
                    "color_mode": True,
                    "supported_color_modes": ["hs", "white"],
                    "white_scale": 50,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("brightness") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(hass, "test_light_bright_scale", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") is None

    # Turn on the light with brightness
    async_fire_mqtt_message(
        hass,
        "test_light_bright_scale",
        '{"state":"ON", "brightness": 99, "color_mode":"hs", "color":{"h":180,"s":50}}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    # Turn on the light with white - white_scale is NOT used
    async_fire_mqtt_message(
        hass,
        "test_light_bright_scale",
        '{"state":"ON", "color_mode":"white", "brightness": 50}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 128


async def test_invalid_values(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that invalid color/brightness/etc. values are ignored."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "color_temp": True,
                    "rgb": True,
                    "qos": "0",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    color_modes = [light.ColorMode.COLOR_TEMP, light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = light.SUPPORT_FLASH | light.SUPPORT_TRANSITION
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"r":255,"g":255,"b":255},'
        '"brightness": 255,'
        '"color_temp": 100,'
        '"effect": "rainbow"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp") is None
    # Empty color value
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad HS color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"h":"bad","s":"val"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad RGB color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"r":"bad","g":"val","b":"test"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad XY color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"x":"bad","y":"val"}}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 255, 255)

    # Bad brightness values
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "brightness": "badValue"}'
    )

    # Brightness should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255

    # Unset color and set a valid color temperature
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color": null, "color_temp": 100}'
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 100

    # Bad color temperature
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color_temp": "badValue"}'
    )

    # Color temperature should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp") == 100


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_LIGHT_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one light per unique_id."""
    config = {
        mqtt.DOMAIN: {
            light.DOMAIN: [
                {
                    "name": "Test 1",
                    "schema": "json",
                    "state_topic": "test-topic",
                    "command_topic": "test_topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
                {
                    "name": "Test 2",
                    "schema": "json",
                    "state_topic": "test-topic",
                    "command_topic": "test_topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
            ]
        }
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, config
    )


async def test_discovery_removal(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered mqtt_json lights."""
    data = '{ "name": "test", "schema": "json", "command_topic": "test_topic" }'
    await help_test_discovery_removal(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        light.DOMAIN,
        data,
    )


async def test_discovery_update_light(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered light."""
    config1 = {
        "name": "Beer",
        "schema": "json",
        "state_topic": "test_topic",
        "command_topic": "test_topic",
    }
    config2 = {
        "name": "Milk",
        "schema": "json",
        "state_topic": "test_topic",
        "command_topic": "test_topic",
    }
    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        light.DOMAIN,
        config1,
        config2,
    )


async def test_discovery_update_unchanged_light(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered light."""
    data1 = (
        '{ "name": "Beer",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.light.schema_json.MqttLightJson.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            light.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        light.DOMAIN,
        data1,
        data2,
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, light.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        light.DOMAIN,
        DEFAULT_CONFIG,
        light.SERVICE_TURN_ON,
        command_payload='{"state":"ON"}',
        state_payload='{"state":"ON"}',
    )


async def test_max_mireds(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test setting min_mireds and max_mireds."""
    config = {
        light.DOMAIN: {
            "schema": "json",
            "name": "test",
            "command_topic": "test_max_mireds/set",
            "color_temp": True,
            "max_mireds": 370,
        }
    }

    assert await async_setup_component(hass, mqtt.DOMAIN, {mqtt.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

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
            '{"state":"ON"}',
            None,
            None,
            None,
        ),
        (
            light.SERVICE_TURN_OFF,
            "command_topic",
            None,
            '{"state":"OFF"}',
            None,
            None,
            None,
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service,
    topic,
    parameters,
    payload,
    template,
    tpl_par,
    tpl_output,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = light.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)
    if topic == "effect_command_topic":
        config[mqtt.DOMAIN][domain]["effect_list"] = ["random", "color_loop"]

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry_with_yaml_config,
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
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Test reloading the MQTT platform."""
    domain = light.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value", "init_payload"),
    [
        (
            "state_topic",
            '{ "state": "ON", "brightness": 200, "color_mode":"hs", "color":{"h":180,"s":50} }',
            "brightness",
            200,
            None,
        ),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    topic,
    value,
    attribute,
    attribute_value,
    init_payload,
) -> None:
    """Test handling of incoming encoded payload."""
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][light.DOMAIN])
    config["color_mode"] = True
    config["supported_color_modes"] = [
        "color_temp",
        "hs",
        "xy",
        "rgb",
        "rgbw",
        "rgbww",
    ]
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        light.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
        init_payload,
        skip_raw_test=True,
    )


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = light.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")
