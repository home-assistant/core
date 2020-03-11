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

from homeassistant.components import light, mqtt
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from .common import (
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import (
    MockConfigEntry,
    assert_setup_component,
    async_fire_mqtt_message,
    mock_coro,
)

DEFAULT_CONFIG_ATTR = {
    light.DOMAIN: {
        "platform": "mqtt",
        "schema": "template",
        "name": "test",
        "command_topic": "test-topic",
        "command_on_template": "on,{{ transition }}",
        "command_off_template": "off,{{ transition|d }}",
        "json_attributes_topic": "attr-topic",
    }
}

DEFAULT_CONFIG_DEVICE_INFO = {
    "platform": "mqtt",
    "name": "Test 1",
    "schema": "template",
    "state_topic": "test-topic",
    "command_topic": "test-command-topic",
    "command_on_template": "on,{{ transition }}",
    "command_off_template": "off,{{ transition|d }}",
    "device": {
        "identifiers": ["helloworld"],
        "connections": [["mac", "02:5b:26:a8:dc:12"]],
        "manufacturer": "Whatever",
        "name": "Beer",
        "model": "Glass",
        "sw_version": "0.1-beta",
    },
    "unique_id": "veryunique",
}


async def test_setup_fails(hass, mqtt_mock):
    """Test that setup fails with missing required configuration items."""
    with assert_setup_component(0, light.DOMAIN):
        assert await async_setup_component(
            hass,
            light.DOMAIN,
            {light.DOMAIN: {"platform": "mqtt", "schema": "template", "name": "test"}},
        )
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


async def test_optimistic(hass, mqtt_mock):
    """Test optimistic mode."""
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
        return_value=mock_coro(fake_state),
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
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_flash(hass, mqtt_mock):
    """Test flash."""
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

    state = hass.states.get("light.test")
    assert state.state == STATE_OFF


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
                    "command_off_template": "off,{{ transition|d }}",
                }
            },
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


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
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
                "command_off_template": "off,{{ transition|d }}",
                "availability_topic": "availability-topic",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get("light.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get("light.test")
    assert state.state == STATE_UNAVAILABLE


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
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
                "command_off_template": "off,{{ transition|d }}",
                "availability_topic": "availability-topic",
                "payload_available": "good",
                "payload_not_available": "nogood",
            }
        },
    )

    state = hass.states.get("light.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get("light.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get("light.test")
    assert state.state == STATE_UNAVAILABLE


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, light.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, light.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    data1 = (
        '{ "name": "test",'
        '  "schema": "template",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "test",'
        '  "schema": "template",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, light.DOMAIN, data1, data2
    )


async def test_unique_id(hass):
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
    await help_test_unique_id(hass, light.DOMAIN, config)


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


async def test_discovery_deprecated(hass, mqtt_mock, caplog):
    """Test discovery of mqtt template light with deprecated option."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    await async_start(hass, "homeassistant", {"mqtt": {}}, entry)
    data = (
        '{ "name": "Beer",'
        '  "platform": "mqtt_template",'
        '  "command_topic": "test_topic",'
        '  "command_on_template": "on",'
        '  "command_off_template": "off"}'
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


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT light device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, light.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        light.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "beer",
                "schema": "template",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "command_on_template": "on,{{ transition }}",
                "command_off_template": "off,{{ transition|d }}",
                "availability_topic": "avty-topic",
                "unique_id": "TOTALLY_UNIQUE",
            }
        ]
    }
    await help_test_entity_id_update(hass, mqtt_mock, light.DOMAIN, config)
