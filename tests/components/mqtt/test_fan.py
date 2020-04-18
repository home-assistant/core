"""Test MQTT fans."""
from homeassistant.components import fan
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
)
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

from tests.common import async_fire_mqtt_message
from tests.components.fan import common

DEFAULT_CONFIG = {
    fan.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "state-topic",
        "command_topic": "command-topic",
    }
}


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if command fails with command topic."""
    assert await async_setup_component(
        hass, fan.DOMAIN, {fan.DOMAIN: {"platform": "mqtt", "name": "test"}}
    )
    assert hass.states.get("fan.test") is None


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_off": "StAtE_OfF",
                "payload_on": "StAtE_On",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "payload_oscillation_off": "OsC_OfF",
                "payload_oscillation_on": "OsC_On",
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "payload_off_speed": "speed_OfF",
                "payload_low_speed": "speed_lOw",
                "payload_medium_speed": "speed_mEdium",
                "payload_high_speed": "speed_High",
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "oscillation-state-topic", "OsC_On")
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    async_fire_mqtt_message(hass, "oscillation-state-topic", "OsC_OfF")
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False

    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_lOw")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_LOW

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_mEdium")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_MEDIUM

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_High")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_HIGH

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_OfF")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_OFF


async def test_controlling_state_via_topic_and_json_message(hass, mqtt_mock):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "state_value_template": "{{ value_json.val }}",
                "oscillation_value_template": "{{ value_json.val }}",
                "speed_value_template": "{{ value_json.val }}",
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", '{"val":"ON"}')
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"OFF"}')
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "oscillation-state-topic", '{"val":"oscillate_on"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    async_fire_mqtt_message(hass, "oscillation-state-topic", '{"val":"oscillate_off"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False

    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "speed-state-topic", '{"val":"low"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_LOW

    async_fire_mqtt_message(hass, "speed-state-topic", '{"val":"medium"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_MEDIUM

    async_fire_mqtt_message(hass, "speed-state-topic", '{"val":"high"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_HIGH

    async_fire_mqtt_message(hass, "speed-state-topic", '{"val":"off"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_OFF


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "payload_off": "StAtE_OfF",
                "payload_on": "StAtE_On",
                "oscillation_command_topic": "oscillation-command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "payload_oscillation_off": "OsC_OfF",
                "payload_oscillation_on": "OsC_On",
                "speed_command_topic": "speed-command-topic",
                "speed_state_topic": "speed-state-topic",
                "payload_off_speed": "speed_OfF",
                "payload_low_speed": "speed_lOw",
                "payload_medium_speed": "speed_mEdium",
                "payload_high_speed": "speed_High",
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_On", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", True)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "OsC_On", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", False)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "OsC_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_lOw", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_mEdium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_High", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_on_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test on with speed."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "speed_command_topic": "speed-command-topic",
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", speed="low")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "low", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "low"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None


async def test_sending_mqtt_commands_and_explicit_optimistic(hass, mqtt_mock):
    """Test optimistic mode with state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "optimistic": True,
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", True)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "oscillate_on", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", False)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "oscillate_off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "low", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "high", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", "cUsToM")
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "cUsToM", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_attributes(hass, mqtt_mock):
    """Test attributes."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "speed_command_topic": "speed-command-topic",
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(fan.ATTR_SPEED_LIST) == ["off", "low", "medium", "high"]

    await common.async_turn_on(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state is STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None

    await common.async_turn_off(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None

    await common.async_oscillate(hass, "fan.test", True)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is True

    await common.async_oscillate(hass, "fan.test", False)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "low"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "medium"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "high"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "off"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", "cUsToM")
    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "cUsToM"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False


async def test_custom_speed_list(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "speed_command_topic": "speed-command-topic",
                "speed_state_topic": "speed-state-topic",
                "speeds": ["off", "high"],
            }
        },
    )

    state = hass.states.get("fan.test")
    assert state.state is STATE_OFF
    assert state.attributes.get(fan.ATTR_SPEED_LIST) == ["off", "high"]


async def test_supported_features(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test1",
                    "command_topic": "command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test2",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test3",
                    "command_topic": "command-topic",
                    "speed_command_topic": "speed-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test4",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "speed_command_topic": "speed-command-topic",
                },
            ]
        },
    )

    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    state = hass.states.get("fan.test2")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_OSCILLATE
    state = hass.states.get("fan.test3")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_SET_SPEED
    state = hass.states.get("fan.test4")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == fan.SUPPORT_OSCILLATE | fan.SUPPORT_SET_SPEED
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG, True, "state-topic", "1"
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass):
    """Test unique_id option only creates one fan per id."""
    config = {
        fan.DOMAIN: [
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
    await help_test_unique_id(hass, fan.DOMAIN, config)


async def test_discovery_removal_fan(hass, mqtt_mock, caplog):
    """Test removal of discovered fan."""
    data = '{ "name": "test",' '  "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, fan.DOMAIN, data)


async def test_discovery_update_fan(hass, mqtt_mock, caplog):
    """Test update of discovered fan."""
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_update(hass, mqtt_mock, caplog, fan.DOMAIN, data1, data2)


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_broken(hass, mqtt_mock, caplog, fan.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )
