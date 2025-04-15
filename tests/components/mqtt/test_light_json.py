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

Configuration with RGB, brightness, color temp (mireds) and effect:

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        color_temp: true
        color_temp_kelvin: false
        effect: true
        rgb: true

Configuration with RGB, brightness and color temp (Kelvin):

mqtt:
    light:
        schema: json
        name: mqtt_json_light_1
        state_topic: "home/rgb1"
        command_topic: "home/rgb1/set"
        brightness: true
        rgb: true
        color_temp: true
        color_temp_kelvin: true

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
from typing import Any
from unittest.mock import call, patch

import pytest

from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.light.schema_basic import (
    MQTT_LIGHT_ATTRIBUTES_BLOCKED,
)
from homeassistant.components.mqtt.models import PublishPayloadType
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.util.json import json_loads

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
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, mock_restore_cache
from tests.components.light import common
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        light.DOMAIN: {
            "schema": "json",
            "name": "test",
            "command_topic": "test-topic",
        }
    }
}


COLOR_MODES_CONFIG = {
    mqtt.DOMAIN: {
        light.DOMAIN: {
            "brightness": True,
            "effect": True,
            "command_topic": "test_light_rgb/set",
            "name": "test",
            "schema": "json",
            "supported_color_modes": [
                "color_temp",
                "hs",
                "rgb",
                "rgbw",
                "rgbww",
                "white",
                "xy",
            ],
            "qos": 0,
        }
    }
}


class JsonValidator:
    """Helper to compare JSON."""

    def __init__(self, jsondata: bytes | str) -> None:
        """Initialize JSON validator."""
        self.jsondata = jsondata

    def __eq__(self, other: bytes | str) -> bool:  # type:ignore[override]
        """Compare JSON data."""
        return json_loads(self.jsondata) == json_loads(other)


@pytest.mark.parametrize(
    "hass_config", [{mqtt.DOMAIN: {light.DOMAIN: {"schema": "json", "name": "test"}}}]
)
async def test_fail_setup_if_no_command_topic(
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test if setup fails with no command topic."""
    assert await mqtt_mock_entry()
    assert "required key not provided" in caplog.text


@pytest.mark.parametrize(
    ("hass_config", "error"),
    [
        (
            help_custom_config(
                light.DOMAIN,
                COLOR_MODES_CONFIG,
                ({"supported_color_modes": ["onoff", "rgb"]},),
            ),
            "Invalid supported_color_modes ['onoff', 'rgb']",
        ),
        (
            help_custom_config(
                light.DOMAIN,
                COLOR_MODES_CONFIG,
                ({"supported_color_modes": ["brightness", "rgb"]},),
            ),
            "Invalid supported_color_modes ['brightness', 'rgb']",
        ),
        (
            help_custom_config(
                light.DOMAIN,
                COLOR_MODES_CONFIG,
                ({"supported_color_modes": ["unknown"]},),
            ),
            "value must be one of [<ColorMode.",
        ),
    ],
)
async def test_fail_setup_if_color_modes_invalid(
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    error: str,
) -> None:
    """Test if setup fails if supported color modes is invalid."""
    assert await mqtt_mock_entry()
    assert error in caplog.text


@pytest.mark.parametrize("hass_config", [COLOR_MODES_CONFIG])
async def test_turn_on_with_unknown_color_mode_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup and turn with unknown color_mode in optimistic mode."""
    await mqtt_mock_entry()
    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    # Turn on the light without brightness or color_temp attributes
    await common.async_turn_on(hass, "light.test")
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == light.ColorMode.UNKNOWN
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.state == STATE_ON

    # Turn on the light with brightness or color_temp attributes
    await common.async_turn_on(
        hass, "light.test", brightness=50, color_temp_kelvin=5208
    )
    state = hass.states.get("light.test")
    assert state.attributes.get("color_mode") == light.ColorMode.COLOR_TEMP
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("color_temp_kelvin") == 5208
    assert state.state == STATE_ON


@pytest.mark.parametrize(
    "hass_config",
    [
        (
            help_custom_config(
                light.DOMAIN,
                COLOR_MODES_CONFIG,
                ({"state_topic": "test_light"},),
            )
        )
    ],
)
async def test_controlling_state_with_unknown_color_mode(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup and turn with unknown color_mode in optimistic mode."""
    await mqtt_mock_entry()
    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    # Send `on` state but omit other attributes
    async_fire_mqtt_message(
        hass,
        "test_light",
        '{"state": "ON"}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get(light.ATTR_COLOR_TEMP_KELVIN) is None
    assert state.attributes.get(light.ATTR_BRIGHTNESS) is None
    assert state.attributes.get(light.ATTR_COLOR_MODE) == light.ColorMode.UNKNOWN

    # Send complete light state
    async_fire_mqtt_message(
        hass,
        "test_light",
        '{"state": "ON", "brightness": 50, "color_mode": "color_temp", "color_temp": 192}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON

    assert state.attributes.get(light.ATTR_COLOR_TEMP_KELVIN) == 5208
    assert state.attributes.get(light.ATTR_BRIGHTNESS) == 50
    assert state.attributes.get(light.ATTR_COLOR_MODE) == light.ColorMode.COLOR_TEMP


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                }
            }
        }
    ],
)
async def test_no_color_brightness_color_temp_if_no_topics(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for no RGB, brightness, color temp, effector XY."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state": null}')

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["brightness"],
                }
            }
        },
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                }
            }
        },
    ],
)
async def test_brightness_only(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test brightness only light.

    There are two possible configurations for brightness only light:
    1) Set up "brightness" as supported color mode.
    2) Set "brightness" flag to true.
    """
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == [
        light.ColorMode.BRIGHTNESS
    ]
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "brightness": 50}')

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["color_temp"],
                }
            }
        },
    ],
)
async def test_color_temp_only(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test a light that only support color_temp as supported color mode."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == [
        light.ColorMode.COLOR_TEMP
    ]
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None

    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode": "color_temp", "color_temp": 250, "brightness": 50}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 206, 166)
    assert state.attributes.get("brightness") == 50
    assert state.attributes.get("color_temp_kelvin") == 4000
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") == (0.42, 0.365)
    assert state.attributes.get("hs_color") == (26.812, 34.87)

    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"OFF"}')

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "color_temp_kelvin": True,
                    "effect": True,
                    "supported_color_modes": ["color_temp", "hs"],
                    "qos": "0",
                }
            }
        }
    ],
)
async def test_controlling_state_color_temp_kelvin(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling of the state via topic in Kelvin mode."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    color_modes = [light.ColorMode.COLOR_TEMP, light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = (
        light.LightEntityFeature.EFFECT
        | light.LightEntityFeature.FLASH
        | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert state.attributes.get("effect") is None
    assert state.attributes.get("xy_color") is None
    assert state.attributes.get("hs_color") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"h": 44.098, "s": 2.43},'
        '"color_mode": "hs",'
        '"brightness":255,'
        '"color_temp":155,'
        '"effect":"colorloop"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (255, 253, 249)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") is None  # rgb color has priority
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("xy_color") == (0.328, 0.333)
    assert state.attributes.get("hs_color") == (44.098, 2.43)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"brightness":255,'
        '"color":null,'
        '"color_mode":"color_temp",'
        '"color_temp":6451,'  # Kelvin
        '"effect":"colorloop"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (
        255,
        253,
        249,
    )  # temp converted to color
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 6451
    assert state.attributes.get("effect") == "colorloop"
    assert state.attributes.get("xy_color") == (0.328, 0.333)  # temp converted to color
    assert state.attributes.get("hs_color") == (44.098, 2.43)  # temp converted to color


@pytest.mark.parametrize(
    ("hass_config", "expected_features"),
    [
        (
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
            light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "state_topic": "test_light_rgb",
                        "command_topic": "test_light_rgb/set",
                        "flash": True,
                        "transition": True,
                    }
                }
            },
            light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "state_topic": "test_light_rgb",
                        "command_topic": "test_light_rgb/set",
                        "flash": True,
                        "transition": False,
                    }
                }
            },
            light.LightEntityFeature.FLASH,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "state_topic": "test_light_rgb",
                        "command_topic": "test_light_rgb/set",
                        "flash": False,
                        "transition": True,
                    }
                }
            },
            light.LightEntityFeature.TRANSITION,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "state_topic": "test_light_rgb",
                        "command_topic": "test_light_rgb/set",
                        "flash": False,
                        "transition": False,
                    }
                }
            },
            light.LightEntityFeature(0),
        ),
    ],
    ids=[
        "default",
        "explicit_on",
        "flash_only",
        "transition_only",
        "no_flash_not_transition",
    ],
)
async def test_flash_and_transition_feature_flags(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    expected_features: light.LightEntityFeature,
) -> None:
    """Test for no RGB, brightness, color temp, effector XY."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            light.DOMAIN, COLOR_MODES_CONFIG, ({"state_topic": "test_light_rgb"},)
        )
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling of the state via topic for a light supporting color mode."""
    supported_color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "white", "xy"]
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.LightEntityFeature.EFFECT
        | light.LightEntityFeature.FLASH
        | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_mode") is None
    assert state.attributes.get("color_temp_kelvin") is None
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
    assert state.attributes.get("color_temp_kelvin") is None
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

    # Zero brightness value is ignored
    async_fire_mqtt_message(hass, "test_light_rgb", '{"state":"ON", "brightness":0}')
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
    assert state.attributes.get("color_temp_kelvin") == 6451

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
    assert "Invalid color mode 'col_temp' received" in caplog.text
    caplog.clear()

    # Incomplete color
    async_fire_mqtt_message(
        hass, "test_light_rgb", '{"state":"ON", "color_mode":"rgb"}'
    )
    assert (
        "Invalid or incomplete color value '{'state': 'ON', 'color_mode': 'rgb'}' received"
        in caplog.text
    )
    caplog.clear()

    # Invalid color
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_mode":"rgb", "color":{"r":64,"g":128,"b":"cow"}}',
    )
    assert (
        "Invalid or incomplete color value '{'state': 'ON', 'color_mode': 'rgb', 'color': {'r': 64, 'g': 128, 'b': 'cow'}}' received"
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "command_topic": "test_light_rgb/set",
                    "effect": True,
                    "name": "test",
                    "qos": 2,
                    "schema": "json",
                    "supported_color_modes": [
                        "color_temp",
                        "hs",
                        "rgb",
                        "rgbw",
                        "rgbww",
                        "white",
                        "xy",
                    ],
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending of command in optimistic mode for a light supporting color mode."""
    supported_color_modes = ["color_temp", "hs", "rgb", "rgbw", "rgbww", "white", "xy"]
    fake_state = State(
        "light.test",
        "on",
        {
            "brightness": 95,
            "color_temp_kelvin": 10000,
            "color_mode": "rgb",
            "effect": "random",
            "hs_color": [100, 100],
        },
    )
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    expected_features = (
        light.LightEntityFeature.EFFECT
        | light.LightEntityFeature.FLASH
        | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features
    assert state.attributes.get("brightness") == 95
    assert state.attributes.get("color_mode") == "rgb"
    assert state.attributes.get("color_temp_kelvin") is None
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
    await common.async_turn_on(hass, "light.test", color_temp_kelvin=11111)
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
    await common.async_turn_on(hass, "light.test", brightness=75, hs_color=(359, 78))
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "hs"
    assert state.attributes["hs_color"] == (359, 78)
    assert state.attributes["rgb_color"] == (255, 56, 59)
    assert state.attributes["xy_color"] == (0.654, 0.301)
    assert state.attributes["rgbw_color"] is None
    assert state.attributes["rgbww_color"] is None
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
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgb"
    assert state.attributes["hs_color"] == (30.118, 100.0)
    assert state.attributes["rgb_color"] == (255, 128, 0)
    assert state.attributes["xy_color"] == (0.611, 0.375)
    assert state.attributes["rgbw_color"] is None
    assert state.attributes["rgbww_color"] is None
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "color": {"r": 255, "g": 128, "b": 0} }'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()

    # Set rgbw color
    await common.async_turn_on(hass, "light.test", rgbw_color=(255, 128, 0, 123))
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgbw"
    assert state.attributes["rgbw_color"] == (255, 128, 0, 123)
    assert state.attributes["hs_color"] == (30.0, 67.451)
    assert state.attributes["rgb_color"] == (255, 169, 83)
    assert state.attributes["rgbww_color"] is None
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
    await common.async_turn_on(hass, "light.test", rgbww_color=(255, 128, 0, 45, 32))
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 75
    assert state.attributes["color_mode"] == "rgbww"
    assert state.attributes["rgbww_color"] == (255, 128, 0, 45, 32)
    assert state.attributes["hs_color"] == (29.872, 92.157)
    assert state.attributes["rgb_color"] == (255, 137, 20)
    assert state.attributes["rgbw_color"] is None
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
        hass, "light.test", brightness=50, xy_color=(0.123, 0.223)
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes["brightness"] == 50
    assert state.attributes["color_mode"] == "xy"
    assert state.attributes["hs_color"] == (196.471, 100.0)
    assert state.attributes["rgb_color"] == (0, 185, 255)
    assert state.attributes["xy_color"] == (0.123, 0.223)
    assert state.attributes["rgbw_color"] is None
    assert state.attributes["rgbww_color"] is None
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
    assert state.attributes["hs_color"] is None
    assert state.attributes["rgb_color"] is None
    assert state.attributes["xy_color"] is None
    assert state.attributes["rgbw_color"] is None
    assert state.attributes["rgbww_color"] is None
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
    assert state.attributes["hs_color"] is None
    assert state.attributes["rgb_color"] is None
    assert state.attributes["xy_color"] is None
    assert state.attributes["rgbw_color"] is None
    assert state.attributes["rgbww_color"] is None
    mqtt_mock.async_publish.assert_called_once_with(
        "test_light_rgb/set",
        JsonValidator('{"state": "ON", "white": 60}'),
        2,
        False,
    )
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["hs"],
                }
            }
        }
    ],
)
async def test_sending_hs_color(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends hs color parameters."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    mqtt_mock.reset_mock()
    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=(359, 78))
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["rgb"],
                }
            }
        }
    ],
)
async def test_sending_rgb_color_no_brightness(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=(359, 78))
    await common.async_turn_on(
        hass, "light.test", rgb_color=(255, 128, 0), brightness=255
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
        ],
        any_order=True,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "command_topic": "test_light_rgb/set",
                    "name": "test",
                    "schema": "json",
                    "supported_color_modes": ["rgb", "rgbw", "rgbww"],
                }
            }
        }
    ],
)
async def test_sending_rgb_color_no_brightness2(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=(359, 78))
    await common.async_turn_on(
        hass, "light.test", rgb_color=(255, 128, 0), brightness=255
    )
    await common.async_turn_on(
        hass, "light.test", rgbw_color=(128, 64, 32, 16), brightness=128
    )
    await common.async_turn_on(
        hass, "light.test", rgbww_color=(128, 64, 32, 16, 8), brightness=64
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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["rgb"],
                    "brightness": True,
                }
            }
        }
    ],
)
async def test_sending_rgb_color_with_brightness(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=(359, 78))
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 0, "g": 124, "b": 255},'
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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["rgb"],
                    "brightness": True,
                    "brightness_scale": 100,
                }
            }
        }
    ],
)
async def test_sending_rgb_color_with_scaled_brightness(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends rgb color parameters."""
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=255, hs_color=(359, 78))
    await common.async_turn_on(hass, "light.test", brightness=1)
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"r": 0, "g": 124, "b": 255},'
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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "brightness_scale": 100,
                    "supported_color_modes": ["hs", "white"],
                    "white_scale": 50,
                }
            }
        }
    ],
)
async def test_sending_scaled_white(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with scaled white."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "supported_color_modes": ["xy"],
                }
            }
        }
    ],
)
async def test_sending_xy_color(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test light.turn_on with hs color sends xy color parameters."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(
        hass, "light.test", brightness=50, xy_color=(0.123, 0.123)
    )
    await common.async_turn_on(hass, "light.test", brightness=50, hs_color=(359, 78))
    await common.async_turn_on(hass, "light.test", rgb_color=(255, 128, 0))

    mqtt_mock.async_publish.assert_has_calls(
        [
            call(
                "test_light_rgb/set",
                JsonValidator(
                    '{"state": "ON", "color": {"x": 0.123, "y": 0.123},'
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


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_effect(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for effect being sent when included."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.LightEntityFeature.EFFECT
        | light.LightEntityFeature.FLASH
        | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features

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


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_flash_short_and_long(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for flash length being sent when included."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "command_topic": "test_light_rgb/set",
                    "qos": 0,
                }
            }
        }
    ],
)
async def test_transition(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for transition time being sent when included."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features
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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_bright_scale",
                    "command_topic": "test_light_bright_scale/set",
                    "supported_color_modes": ["brightness"],
                    "brightness_scale": 99,
                }
            }
        }
    ],
)
async def test_brightness_scale(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for brightness scaling."""
    await mqtt_mock_entry()

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

    # Turn on the light with half brightness
    async_fire_mqtt_message(
        hass, "test_light_bright_scale", '{"state":"ON", "brightness": 50}'
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 129

    # Test limmiting max brightness
    async_fire_mqtt_message(
        hass, "test_light_bright_scale", '{"state":"ON", "brightness": 103}'
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("brightness") == 255


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_bright_scale",
                    "command_topic": "test_light_bright_scale/set",
                    "brightness": True,
                    "brightness_scale": 99,
                    "supported_color_modes": ["hs", "white"],
                    "white_scale": 50,
                }
            }
        }
    ],
)
async def test_white_scale(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test for white scaling."""
    await mqtt_mock_entry()

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
    assert state.attributes.get("brightness") == 129


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                light.DOMAIN: {
                    "schema": "json",
                    "name": "test",
                    "state_topic": "test_light_rgb",
                    "command_topic": "test_light_rgb/set",
                    "brightness": True,
                    "supported_color_modes": ["hs", "color_temp"],
                    "qos": "0",
                }
            }
        }
    ],
)
async def test_invalid_values(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that invalid color/brightness/etc. values are ignored."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.state == STATE_UNKNOWN
    color_modes = [light.ColorMode.COLOR_TEMP, light.ColorMode.HS]
    assert state.attributes.get(light.ATTR_SUPPORTED_COLOR_MODES) == color_modes
    expected_features = (
        light.LightEntityFeature.FLASH | light.LightEntityFeature.TRANSITION
    )
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) is expected_features
    assert state.attributes.get("rgb_color") is None
    assert state.attributes.get("brightness") is None
    assert state.attributes.get("color_temp_kelvin") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    # Turn on the light
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON",'
        '"color":{"r":255,"g":255,"b":255},'
        '"brightness": 255,'
        '"color_mode": "color_temp",'
        '"color_temp": 100,'
        '"effect": "rainbow"}',
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    # Color converttrd from color_temp to rgb
    assert state.attributes.get("rgb_color") == (202, 218, 255)
    assert state.attributes.get("brightness") == 255
    assert state.attributes.get("color_temp_kelvin") == 10000
    # Empty color value
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{}, "color_mode": "rgb"}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (202, 218, 255)

    # Bad HS color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"h":"bad","s":"val"}, "color_mode": "hs"}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (202, 218, 255)

    # Bad RGB color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"r":"bad","g":"val","b":"test"}, "color_mode": "rgb"}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (202, 218, 255)

    # Bad XY color values
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color":{"x":"bad","y":"val"}, "color_mode": "xy"}',
    )

    # Color should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("rgb_color") == (202, 218, 255)

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
        hass,
        "test_light_rgb",
        '{"state":"ON", "color": null, "color_temp": 100, "color_mode": "color_temp"}',
    )
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp_kelvin") == 10000

    # Bad color temperature
    async_fire_mqtt_message(
        hass,
        "test_light_rgb",
        '{"state":"ON", "color_temp": "badValue", "color_mode": "color_temp"}',
    )
    assert (
        "Invalid or incomplete color value '{'state': 'ON', 'color_temp': "
        "'badValue', 'color_mode': 'color_temp'}' "
        "received for entity light.test" in caplog.text
    )

    # Color temperature should not have changed
    state = hass.states.get("light.test")
    assert state.state == STATE_ON
    assert state.attributes.get("color_temp_kelvin") == 10000


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
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one light per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, light.DOMAIN)


async def test_discovery_removal(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered mqtt_json lights."""
    data = '{ "name": "test", "schema": "json", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, light.DOMAIN, data)


async def test_discovery_update_light(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
        hass, mqtt_mock_entry, light.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_light(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
        '  "schema": "json",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(hass, mqtt_mock_entry, light.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass,
        mqtt_mock_entry,
        light.DOMAIN,
        DEFAULT_CONFIG,
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
        command_payload='{"state":"ON"}',
        state_payload='{"state":"ON"}',
    )


@pytest.mark.parametrize(
    ("hass_config", "min_kelvin", "max_kelvin"),
    [
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "command_topic": "test_max_mireds/set",
                        "supported_color_modes": ["color_temp"],
                        "max_mireds": 370,  # 2702 Kelvin
                    }
                }
            },
            2702,
            light.DEFAULT_MAX_KELVIN,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "command_topic": "test_max_mireds/set",
                        "supported_color_modes": ["color_temp"],
                        "min_mireds": 150,  # 6666 Kelvin
                    }
                }
            },
            light.DEFAULT_MIN_KELVIN,
            6666,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "command_topic": "test_max_mireds/set",
                        "supported_color_modes": ["color_temp"],
                        "min_kelvin": 2702,
                    }
                }
            },
            2702,
            light.DEFAULT_MAX_KELVIN,
        ),
        (
            {
                mqtt.DOMAIN: {
                    light.DOMAIN: {
                        "schema": "json",
                        "name": "test",
                        "command_topic": "test_max_mireds/set",
                        "supported_color_modes": ["color_temp"],
                        "max_kelvin": 6666,
                    }
                }
            },
            light.DEFAULT_MIN_KELVIN,
            6666,
        ),
    ],
)
async def test_min_max_kelvin(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    min_kelvin: int,
    max_kelvin: int,
) -> None:
    """Test setting min_color_temp_kelvin and max_color_temp_kelvin."""
    await mqtt_mock_entry()

    state = hass.states.get("light.test")
    assert state.attributes.get("min_color_temp_kelvin") == min_kelvin
    assert state.attributes.get("max_color_temp_kelvin") == max_kelvin


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
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str | None,
    attribute_value: Any,
    init_payload: tuple[str, str] | None,
) -> None:
    """Test handling of incoming encoded payload."""
    config: dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][light.DOMAIN])
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
        mqtt_mock_entry,
        light.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
        init_payload,
        skip_raw_test=True,
    )


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


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            light.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "effect": True,
                    "supported_color_modes": [
                        "color_temp",
                        "hs",
                        "xy",
                        "rgb",
                        "rgbw",
                        "rgbww",
                        "white",
                    ],
                    "effect_list": ["effect1", "effect2"],
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "state_topic": "test-topic",
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
        (
            "test-topic",
            '{"state":"ON","effect":"effect1"}',
            '{"state":"ON","effect":"effect2"}',
        ),
        (
            "test-topic",
            '{"state":"ON","brightness":255}',
            '{"state":"ON","brightness":96}',
        ),
        (
            "test-topic",
            '{"state":"ON","brightness":96}',
            '{"state":"ON","color_mode":"white","brightness":96}',
        ),
        (
            "test-topic",
            '{"state":"ON","color_mode":"color_temp", "color_temp": 200}',
            '{"state":"ON","color_mode":"color_temp", "color_temp": 2400}',
        ),
        (
            "test-topic",
            '{"state":"ON","color_mode":"hs", "color": {"h":24.0,"s":100.0}}',
            '{"state":"ON","color_mode":"hs", "color": {"h":24.0,"s":90.0}}',
        ),
        (
            "test-topic",
            '{"state":"ON","color_mode":"xy","color": {"x":0.14,"y":0.131}}',
            '{"state":"ON","color_mode":"xy","color": {"x":0.16,"y": 0.100}}',
        ),
        (
            "test-topic",
            '{"state":"ON","brightness":255,"color_mode":"rgb","color":{"r":128,"g":128,"b":255}}',
            '{"state":"ON","brightness":255,"color_mode":"rgb","color": {"r":255,"g":128,"b":255}}',
        ),
        (
            "test-topic",
            '{"state":"ON","color_mode":"rgbw","color":{"r":128,"g":128,"b":255,"w":128}}',
            '{"state":"ON","color_mode":"rgbw","color": {"r":128,"g":128,"b":255,"w":255}}',
        ),
        (
            "test-topic",
            '{"state":"ON","color_mode":"rgbww","color":{"r":128,"g":128,"b":255,"c":32,"w":128}}',
            '{"state":"ON","color_mode":"rgbww","color": {"r":128,"g":128,"b":255,"c":16,"w":128}}',
        ),
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
