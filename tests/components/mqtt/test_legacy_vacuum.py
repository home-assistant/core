"""The tests for the Legacy Mqtt vacuum platform."""
from copy import deepcopy
import json

from homeassistant.components import vacuum
from homeassistant.components.mqtt import CONF_COMMAND_TOPIC
from homeassistant.components.mqtt.vacuum import schema_legacy as mqttvacuum
from homeassistant.components.mqtt.vacuum.schema import services_to_strings
from homeassistant.components.mqtt.vacuum.schema_legacy import (
    ALL_SERVICES,
    SERVICE_TO_STRING,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    ATTR_STATUS,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_OFF, STATE_ON
from homeassistant.setup import async_setup_component

from .common import (
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.vacuum import common

DEFAULT_CONFIG = {
    CONF_PLATFORM: "mqtt",
    CONF_NAME: "mqtttest",
    CONF_COMMAND_TOPIC: "vacuum/command",
    mqttvacuum.CONF_SEND_COMMAND_TOPIC: "vacuum/send_command",
    mqttvacuum.CONF_BATTERY_LEVEL_TOPIC: "vacuum/state",
    mqttvacuum.CONF_BATTERY_LEVEL_TEMPLATE: "{{ value_json.battery_level }}",
    mqttvacuum.CONF_CHARGING_TOPIC: "vacuum/state",
    mqttvacuum.CONF_CHARGING_TEMPLATE: "{{ value_json.charging }}",
    mqttvacuum.CONF_CLEANING_TOPIC: "vacuum/state",
    mqttvacuum.CONF_CLEANING_TEMPLATE: "{{ value_json.cleaning }}",
    mqttvacuum.CONF_DOCKED_TOPIC: "vacuum/state",
    mqttvacuum.CONF_DOCKED_TEMPLATE: "{{ value_json.docked }}",
    mqttvacuum.CONF_ERROR_TOPIC: "vacuum/state",
    mqttvacuum.CONF_ERROR_TEMPLATE: "{{ value_json.error }}",
    mqttvacuum.CONF_FAN_SPEED_TOPIC: "vacuum/state",
    mqttvacuum.CONF_FAN_SPEED_TEMPLATE: "{{ value_json.fan_speed }}",
    mqttvacuum.CONF_SET_FAN_SPEED_TOPIC: "vacuum/set_fan_speed",
    mqttvacuum.CONF_FAN_SPEED_LIST: ["min", "medium", "high", "max"],
}

DEFAULT_CONFIG_2 = {vacuum.DOMAIN: {"platform": "mqtt", "name": "test"}}


async def test_default_supported_features(hass, mqtt_mock):
    """Test that the correct supported features."""
    assert await async_setup_component(
        hass, vacuum.DOMAIN, {vacuum.DOMAIN: DEFAULT_CONFIG}
    )
    entity = hass.states.get("vacuum.mqtttest")
    entity_features = entity.attributes.get(mqttvacuum.CONF_SUPPORTED_FEATURES, 0)
    assert sorted(services_to_strings(entity_features, SERVICE_TO_STRING)) == sorted(
        [
            "turn_on",
            "turn_off",
            "stop",
            "return_home",
            "battery",
            "status",
            "clean_spot",
        ]
    )


async def test_all_commands(hass, mqtt_mock):
    """Test simple commands to the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    await common.async_turn_on(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "turn_on", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "turn_off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_stop(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with("vacuum/command", "stop", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await common.async_clean_spot(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "clean_spot", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_locate(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "locate", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_start_pause(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "start_pause", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_return_to_base(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/command", "return_to_base", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "high", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/set_fan_speed", "high", 0, False
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

    await common.async_send_command(
        hass, "44 FE 93", {"key": "value"}, entity_id="vacuum.mqtttest"
    )
    assert json.loads(mqtt_mock.async_publish.mock_calls[-1][1][1]) == {
        "command": "44 FE 93",
        "key": "value",
    }


async def test_commands_without_supported_features(hass, mqtt_mock):
    """Test commands which are not supported by the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    services = mqttvacuum.STRING_TO_SERVICE["status"]
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        services, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    await common.async_turn_on(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_stop(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_clean_spot(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_locate(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_start_pause(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_return_to_base(hass, "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "high", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(hass, "44 FE 93", entity_id="vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()


async def test_attributes_without_supported_features(hass, mqtt_mock):
    """Test attributes which are not supported by the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    services = mqttvacuum.STRING_TO_SERVICE["turn_on"]
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        services, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_BATTERY_ICON) is None


async def test_status(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "battery_level": 54,
        "cleaning": true,
        "docked": false,
        "charging": false,
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_FAN_SPEED) == "max"

    message = """{
        "battery_level": 61,
        "docked": true,
        "cleaning": false,
        "charging": true,
        "fan_speed": "min"
    }"""

    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-charging-60"
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 61
    assert state.attributes.get(ATTR_FAN_SPEED) == "min"


async def test_status_battery(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "battery_level": 54
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"


async def test_status_cleaning(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "cleaning": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_ON


async def test_status_docked(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "docked": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF


async def test_status_charging(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "charging": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-outline"


async def test_status_fan_speed(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_FAN_SPEED) == "max"


async def test_status_error(hass, mqtt_mock):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    message = """{
        "error": "Error1"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_STATUS) == "Error: Error1"

    message = """{
        "error": ""
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_STATUS) == "Stopped"


async def test_battery_template(hass, mqtt_mock):
    """Test that you can use non-default templates for battery_level."""
    config = deepcopy(DEFAULT_CONFIG)
    config.update(
        {
            mqttvacuum.CONF_SUPPORTED_FEATURES: services_to_strings(
                ALL_SERVICES, SERVICE_TO_STRING
            ),
            mqttvacuum.CONF_BATTERY_LEVEL_TOPIC: "retroroomba/battery_level",
            mqttvacuum.CONF_BATTERY_LEVEL_TEMPLATE: "{{ value }}",
        }
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    async_fire_mqtt_message(hass, "retroroomba/battery_level", "54")
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"


async def test_status_invalid_json(hass, mqtt_mock):
    """Test to make sure nothing breaks if the vacuum sends bad JSON."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    async_fire_mqtt_message(hass, "vacuum/state", '{"asdfasas false}')
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_STATUS) == "Stopped"


async def test_missing_battery_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_BATTERY_LEVEL_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_charging_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_CHARGING_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_cleaning_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_CLEANING_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_docked_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_DOCKED_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_error_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_ERROR_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_fan_speed_template(hass, mqtt_mock):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_FAN_SPEED_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one vacuum per unique_id."""
    config = {
        vacuum.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, vacuum.DOMAIN, config)


async def test_discovery_removal_vacuum(hass, mqtt_mock, caplog):
    """Test removal of discovered vacuum."""
    data = json.dumps(DEFAULT_CONFIG_2[vacuum.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock, caplog, vacuum.DOMAIN, data)


async def test_discovery_update_vacuum(hass, mqtt_mock, caplog):
    """Test update of discovered vacuum."""
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, vacuum.DOMAIN, data1, data2
    )


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, vacuum.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        vacuum.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "battery_level_topic": "test-topic",
            "battery_level_template": "{{ value_json.battery_level }}",
            "command_topic": "command-topic",
            "availability_topic": "avty-topic",
        }
    }
    await help_test_entity_id_update(
        hass, mqtt_mock, vacuum.DOMAIN, config, ["test-topic", "avty-topic"]
    )
