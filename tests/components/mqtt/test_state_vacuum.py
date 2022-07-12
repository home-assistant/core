"""The tests for the State vacuum Mqtt platform."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from homeassistant.components import vacuum
from homeassistant.components.mqtt.const import CONF_COMMAND_TOPIC, CONF_STATE_TOPIC
from homeassistant.components.mqtt.vacuum import CONF_SCHEMA, schema_state as mqttvacuum
from homeassistant.components.mqtt.vacuum.const import MQTT_VACUUM_ATTRIBUTES_BLOCKED
from homeassistant.components.mqtt.vacuum.schema import services_to_strings
from homeassistant.components.mqtt.vacuum.schema_state import SERVICE_TO_STRING
from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    DOMAIN,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_STOP,
    STATE_CLEANING,
    STATE_DOCKED,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PLATFORM,
    ENTITY_MATCH_ALL,
    STATE_UNKNOWN,
    Platform,
)
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
    help_test_reloadable_late,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.vacuum import common

COMMAND_TOPIC = "vacuum/command"
SEND_COMMAND_TOPIC = "vacuum/send_command"
STATE_TOPIC = "vacuum/state"

DEFAULT_CONFIG = {
    CONF_PLATFORM: "mqtt",
    CONF_SCHEMA: "state",
    CONF_NAME: "mqtttest",
    CONF_COMMAND_TOPIC: COMMAND_TOPIC,
    mqttvacuum.CONF_SEND_COMMAND_TOPIC: SEND_COMMAND_TOPIC,
    CONF_STATE_TOPIC: STATE_TOPIC,
    mqttvacuum.CONF_SET_FAN_SPEED_TOPIC: "vacuum/set_fan_speed",
    mqttvacuum.CONF_FAN_SPEED_LIST: ["min", "medium", "high", "max"],
}

DEFAULT_CONFIG_2 = {
    vacuum.DOMAIN: {"platform": "mqtt", "schema": "state", "name": "test"}
}


@pytest.fixture(autouse=True)
def vacuum_platform_only():
    """Only setup the vacuum platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.VACUUM]):
        yield


async def test_default_supported_features(hass, mqtt_mock_entry_with_yaml_config):
    """Test that the correct supported features."""
    assert await async_setup_component(
        hass, vacuum.DOMAIN, {vacuum.DOMAIN: DEFAULT_CONFIG}
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    entity = hass.states.get("vacuum.mqtttest")
    entity_features = entity.attributes.get(mqttvacuum.CONF_SUPPORTED_FEATURES, 0)
    assert sorted(services_to_strings(entity_features, SERVICE_TO_STRING)) == sorted(
        ["start", "stop", "return_home", "battery", "status", "clean_spot"]
    )


async def test_all_commands(hass, mqtt_mock_entry_with_yaml_config):
    """Test simple commands send to the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        mqttvacuum.ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "start", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "stop", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "pause", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "locate", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(
        COMMAND_TOPIC, "clean_spot", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_RETURN_TO_BASE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(
        COMMAND_TOPIC, "return_to_base", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "medium", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/set_fan_speed", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(hass, "44 FE 93", entity_id="vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/send_command", "44 FE 93", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(
        hass, "44 FE 93", {"key": "value"}, entity_id="vacuum.mqtttest"
    )
    assert json.loads(mqtt_mock.async_publish.mock_calls[-1][1][1]) == {
        "command": "44 FE 93",
        "key": "value",
    }


async def test_commands_without_supported_features(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test commands which are not supported by the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    services = mqttvacuum.STRING_TO_SERVICE["status"]
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        services, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_RETURN_TO_BASE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        DOMAIN, SERVICE_CLEAN_SPOT, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "medium", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(
        hass, "44 FE 93", {"key": "value"}, entity_id="vacuum.mqtttest"
    )
    mqtt_mock.async_publish.assert_not_called()


async def test_status(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        mqttvacuum.ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN

    message = """{
        "battery_level": 54,
        "state": "cleaning",
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_CLEANING
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"
    assert state.attributes.get(ATTR_FAN_SPEED) == "max"

    message = """{
        "battery_level": 61,
        "state": "docked",
        "fan_speed": "min"
    }"""

    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_DOCKED
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-charging-60"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 61
    assert state.attributes.get(ATTR_FAN_SPEED) == "min"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == ["min", "medium", "high", "max"]

    message = '{"state":null}'
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN


async def test_no_fan_vacuum(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum when fan is not supported."""
    config = deepcopy(DEFAULT_CONFIG)
    del config[mqttvacuum.CONF_FAN_SPEED_LIST]
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        mqttvacuum.DEFAULT_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "battery_level": 54,
        "state": "cleaning"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_CLEANING
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"

    message = """{
        "battery_level": 54,
        "state": "cleaning",
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")

    assert state.state == STATE_CLEANING
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None

    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"

    message = """{
        "battery_level": 61,
        "state": "docked"
    }"""

    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_DOCKED
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-charging-60"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 61


@pytest.mark.no_fail_on_log_exception
async def test_status_invalid_json(hass, mqtt_mock_entry_with_yaml_config):
    """Test to make sure nothing breaks if the vacuum sends bad JSON."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        mqttvacuum.ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "vacuum/state", '{"asdfasas false}')
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN


async def test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_availability_without_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_default_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_custom_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        vacuum.DOMAIN,
        DEFAULT_CONFIG_2,
        MQTT_VACUUM_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_not_dict(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry_with_yaml_config, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_bad_json(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock_entry_with_yaml_config, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_discovery_update_attr(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_unique_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test unique id option only creates one vacuum per unique_id."""
    config = {
        vacuum.DOMAIN: [
            {
                "platform": "mqtt",
                "schema": "state",
                "name": "Test 1",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "schema": "state",
                "name": "Test 2",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, config
    )


async def test_discovery_removal_vacuum(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test removal of discovered vacuum."""
    data = '{ "schema": "state", "name": "test", "command_topic": "test_topic"}'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, data
    )


async def test_discovery_update_vacuum(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered vacuum."""
    config1 = {"schema": "state", "name": "Beer", "command_topic": "test_topic"}
    config2 = {"schema": "state", "name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_vacuum(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test update of discovered vacuum."""
    data1 = '{ "schema": "state", "name": "Beer", "command_topic": "test_topic"}'
    with patch(
        "homeassistant.components.mqtt.vacuum.schema_state.MqttStateVacuum.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            vacuum.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "schema": "state", "name": "Beer", "command_topic": "test_topic#"}'
    data2 = '{ "schema": "state", "name": "Milk", "command_topic": "test_topic"}'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_remove(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock_entry_with_yaml_config):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_debug_info_message(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        vacuum.DOMAIN,
        DEFAULT_CONFIG_2,
        vacuum.SERVICE_START,
        command_payload="start",
        state_payload="{}",
    )


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (
            vacuum.SERVICE_START,
            "command_topic",
            None,
            "start",
            None,
        ),
        (
            vacuum.SERVICE_CLEAN_SPOT,
            "command_topic",
            None,
            "clean_spot",
            None,
        ),
        (
            vacuum.SERVICE_SET_FAN_SPEED,
            "set_fan_speed_topic",
            {"fan_speed": "medium"},
            "medium",
            None,
        ),
        (
            vacuum.SERVICE_SEND_COMMAND,
            "send_command_topic",
            {"command": "custom command"},
            "custom command",
            None,
        ),
        (
            vacuum.SERVICE_STOP,
            "command_topic",
            None,
            "stop",
            None,
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    service,
    topic,
    parameters,
    payload,
    template,
):
    """Test publishing MQTT payload with different encoding."""
    domain = vacuum.DOMAIN
    config = deepcopy(DEFAULT_CONFIG)
    config["supported_features"] = [
        "battery",
        "clean_spot",
        "fan_speed",
        "locate",
        "pause",
        "return_home",
        "send_command",
        "start",
        "status",
        "stop",
    ]

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
    )


async def test_reloadable(hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = vacuum.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_reloadable_late(hass, mqtt_client_mock, caplog, tmp_path):
    """Test reloading the MQTT platform with late entry setup."""
    domain = vacuum.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable_late(hass, caplog, tmp_path, domain, config)


@pytest.mark.parametrize(
    "topic,value,attribute,attribute_value",
    [
        (
            "state_topic",
            '{"battery_level": 61, "state": "docked", "fan_speed": "off"}',
            None,
            "docked",
        ),
        (
            "state_topic",
            '{"battery_level": 61, "state": "cleaning", "fan_speed": "medium"}',
            None,
            "cleaning",
        ),
    ],
)
async def test_encoding_subscribable_topics(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    topic,
    value,
    attribute,
    attribute_value,
):
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        vacuum.DOMAIN,
        DEFAULT_CONFIG,
        topic,
        value,
        attribute,
        attribute_value,
        skip_raw_test=True,
    )


async def test_setup_manual_entity_from_yaml(hass):
    """Test setup manual configured MQTT entity."""
    platform = vacuum.DOMAIN
    config = deepcopy(DEFAULT_CONFIG)
    config["name"] = "test"
    del config["platform"]
    await help_test_setup_manual_entity_from_yaml(hass, platform, config)
    assert hass.states.get(f"{platform}.test") is not None
