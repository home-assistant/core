"""The tests the MQTT alarm control panel component."""
import copy
import json

from homeassistant.components import alarm_control_panel
from homeassistant.const import (
    STATE_ALARM_ARMED_AWAY,
    STATE_ALARM_ARMED_HOME,
    STATE_ALARM_ARMED_NIGHT,
    STATE_ALARM_DISARMED,
    STATE_ALARM_PENDING,
    STATE_ALARM_TRIGGERED,
    STATE_UNKNOWN,
)

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

from tests.common import (
    assert_setup_component,
    async_fire_mqtt_message,
    async_setup_component,
)
from tests.components.alarm_control_panel import common

CODE_NUMBER = "1234"
CODE_TEXT = "HELLO_CODE"

DEFAULT_CONFIG = {
    alarm_control_panel.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "alarm/state",
        "command_topic": "alarm/command",
    }
}

DEFAULT_CONFIG_CODE = {
    alarm_control_panel.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "alarm/state",
        "command_topic": "alarm/command",
        "code": "1234",
        "code_arm_required": True,
    }
}


async def test_fail_setup_without_state_topic(hass, mqtt_mock):
    """Test for failing with no state topic."""
    with assert_setup_component(0) as config:
        assert await async_setup_component(
            hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "mqtt",
                    "command_topic": "alarm/command",
                }
            },
        )
        assert not config[alarm_control_panel.DOMAIN]


async def test_fail_setup_without_command_topic(hass, mqtt_mock):
    """Test failing with no command topic."""
    with assert_setup_component(0):
        assert await async_setup_component(
            hass,
            alarm_control_panel.DOMAIN,
            {
                alarm_control_panel.DOMAIN: {
                    "platform": "mqtt",
                    "state_topic": "alarm/state",
                }
            },
        )


async def test_update_state_via_state_topic(hass, mqtt_mock):
    """Test updating with via state topic."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    for state in (
        STATE_ALARM_DISARMED,
        STATE_ALARM_ARMED_HOME,
        STATE_ALARM_ARMED_AWAY,
        STATE_ALARM_ARMED_NIGHT,
        STATE_ALARM_PENDING,
        STATE_ALARM_TRIGGERED,
    ):
        async_fire_mqtt_message(hass, "alarm/state", state)
        assert hass.states.get(entity_id).state == state


async def test_ignore_update_state_if_unknown_via_state_topic(hass, mqtt_mock):
    """Test ignoring updates via state topic."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    entity_id = "alarm_control_panel.test"

    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "alarm/state", "unsupported state")
    assert hass.states.get(entity_id).state == STATE_UNKNOWN


async def test_arm_home_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    await common.async_alarm_arm_home(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_HOME", 0, False
    )


async def test_arm_home_not_publishes_mqtt_with_invalid_code_when_req(hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid.

    When code_arm_required = True
    """
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE,
    )

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_home(hass, "abcd")
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_home_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    config = copy.deepcopy(DEFAULT_CONFIG_CODE)
    config[alarm_control_panel.DOMAIN]["code_arm_required"] = False
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config,)

    await common.async_alarm_arm_home(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_HOME", 0, False
    )


async def test_arm_away_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    await common.async_alarm_arm_away(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_AWAY", 0, False
    )


async def test_arm_away_not_publishes_mqtt_with_invalid_code_when_req(hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_arm_required = True
    """
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE,
    )

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_away(hass, "abcd")
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_away_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    config = copy.deepcopy(DEFAULT_CONFIG_CODE)
    config[alarm_control_panel.DOMAIN]["code_arm_required"] = False
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config,)

    await common.async_alarm_arm_away(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_AWAY", 0, False
    )


async def test_arm_night_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while armed."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    await common.async_alarm_arm_night(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_NIGHT", 0, False
    )


async def test_arm_night_not_publishes_mqtt_with_invalid_code_when_req(hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_arm_required = True
    """
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE,
    )

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_arm_night(hass, "abcd")
    assert mqtt_mock.async_publish.call_count == call_count


async def test_arm_night_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages.

    When code_arm_required = False
    """
    config = copy.deepcopy(DEFAULT_CONFIG_CODE)
    config[alarm_control_panel.DOMAIN]["code_arm_required"] = False
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config,)

    await common.async_alarm_arm_night(hass)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", "ARM_NIGHT", 0, False
    )


async def test_disarm_publishes_mqtt(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed."""
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG,
    )

    await common.async_alarm_disarm(hass)
    mqtt_mock.async_publish.assert_called_once_with("alarm/command", "DISARM", 0, False)


async def test_disarm_publishes_mqtt_with_template(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed.

    When command_template set to output json
    """
    config = copy.deepcopy(DEFAULT_CONFIG_CODE)
    config[alarm_control_panel.DOMAIN]["code"] = "1234"
    config[alarm_control_panel.DOMAIN]["command_template"] = (
        '{"action":"{{ action }}",' '"code":"{{ code }}"}'
    )
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config,)

    await common.async_alarm_disarm(hass, 1234)
    mqtt_mock.async_publish.assert_called_once_with(
        "alarm/command", '{"action":"DISARM","code":"1234"}', 0, False
    )


async def test_disarm_publishes_mqtt_when_code_not_req(hass, mqtt_mock):
    """Test publishing of MQTT messages while disarmed.

    When code_disarm_required = False
    """
    config = copy.deepcopy(DEFAULT_CONFIG_CODE)
    config[alarm_control_panel.DOMAIN]["code"] = "1234"
    config[alarm_control_panel.DOMAIN]["code_disarm_required"] = False
    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config,)

    await common.async_alarm_disarm(hass)
    mqtt_mock.async_publish.assert_called_once_with("alarm/command", "DISARM", 0, False)


async def test_disarm_not_publishes_mqtt_with_invalid_code_when_req(hass, mqtt_mock):
    """Test not publishing of MQTT messages with invalid code.

    When code_disarm_required = True
    """
    assert await async_setup_component(
        hass, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE,
    )

    call_count = mqtt_mock.async_publish.call_count
    await common.async_alarm_disarm(hass, "abcd")
    assert mqtt_mock.async_publish.call_count == call_count


async def test_update_state_via_state_topic_template(hass, mqtt_mock):
    """Test updating with template_value via state topic."""
    assert await async_setup_component(
        hass,
        alarm_control_panel.DOMAIN,
        {
            alarm_control_panel.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "test-topic",
                "state_topic": "test-topic",
                "value_template": "\
                {% if (value | int)  == 100 %}\
                  armed_away\
                {% else %}\
                   disarmed\
                {% endif %}",
            }
        },
    )

    state = hass.states.get("alarm_control_panel.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "test-topic", "100")

    state = hass.states.get("alarm_control_panel.test")
    assert state.state == STATE_ALARM_ARMED_AWAY


async def test_attributes_code_number(hass, mqtt_mock):
    """Test attributes which are not supported by the vacuum."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config[alarm_control_panel.DOMAIN]["code"] = CODE_NUMBER

    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config)

    state = hass.states.get("alarm_control_panel.test")
    assert (
        state.attributes.get(alarm_control_panel.ATTR_CODE_FORMAT)
        == alarm_control_panel.FORMAT_NUMBER
    )


async def test_attributes_code_text(hass, mqtt_mock):
    """Test attributes which are not supported by the vacuum."""
    config = copy.deepcopy(DEFAULT_CONFIG)
    config[alarm_control_panel.DOMAIN]["code"] = CODE_TEXT

    assert await async_setup_component(hass, alarm_control_panel.DOMAIN, config)

    state = hass.states.get("alarm_control_panel.test")
    assert (
        state.attributes.get(alarm_control_panel.ATTR_CODE_FORMAT)
        == alarm_control_panel.FORMAT_TEXT
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG_CODE
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass):
    """Test unique id option only creates one alarm per unique_id."""
    config = {
        alarm_control_panel.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, alarm_control_panel.DOMAIN, config)


async def test_discovery_removal_alarm(hass, mqtt_mock, caplog):
    """Test removal of discovered alarm_control_panel."""
    data = json.dumps(DEFAULT_CONFIG[alarm_control_panel.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, data
    )


async def test_discovery_update_alarm(hass, mqtt_mock, caplog):
    """Test update of discovered alarm_control_panel."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[alarm_control_panel.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[alarm_control_panel.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, data1, data2
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
        hass, mqtt_mock, caplog, alarm_control_panel.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT alarm control panel device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT alarm control panel device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, alarm_control_panel.DOMAIN, DEFAULT_CONFIG
    )
