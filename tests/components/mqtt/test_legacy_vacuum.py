"""The tests for the Legacy Mqtt vacuum platform."""
from copy import deepcopy
import json
from unittest.mock import patch

import pytest

from homeassistant.components import vacuum
from homeassistant.components.mqtt.const import CONF_COMMAND_TOPIC
from homeassistant.components.mqtt.vacuum import schema_legacy as mqttvacuum
from homeassistant.components.mqtt.vacuum.schema import services_to_strings
from homeassistant.components.mqtt.vacuum.schema_legacy import (
    ALL_SERVICES,
    CONF_BATTERY_LEVEL_TOPIC,
    CONF_CHARGING_TOPIC,
    CONF_CLEANING_TOPIC,
    CONF_DOCKED_TOPIC,
    CONF_ERROR_TOPIC,
    CONF_FAN_SPEED_TOPIC,
    CONF_SUPPORTED_FEATURES,
    MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED,
    SERVICE_TO_STRING,
)
from homeassistant.components.vacuum import (
    ATTR_BATTERY_ICON,
    ATTR_BATTERY_LEVEL,
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    ATTR_STATUS,
    VacuumEntityFeature,
)
from homeassistant.const import CONF_NAME, CONF_PLATFORM, STATE_OFF, STATE_ON, Platform
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


async def test_all_commands(hass, mqtt_mock_entry_with_yaml_config):
    """Test simple commands to the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

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


async def test_attributes_without_supported_features(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test attributes which are not supported by the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    services = mqttvacuum.STRING_TO_SERVICE["turn_on"]
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        services, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

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
    assert state.attributes.get(ATTR_BATTERY_LEVEL) is None
    assert state.attributes.get(ATTR_BATTERY_ICON) is None
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None


async def test_status(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

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


async def test_status_battery(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "battery_level": 54
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"


async def test_status_cleaning(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "cleaning": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_ON


async def test_status_docked(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "docked": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF


async def test_status_charging(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "charging": true
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-outline"


async def test_status_fan_speed(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    message = """{
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_FAN_SPEED) == "max"


async def test_status_fan_speed_list(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == ["min", "medium", "high", "max"]


async def test_status_no_fan_speed_list(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum.

    If the vacuum doesn't support fan speed, fan speed list should be None.
    """
    config = deepcopy(DEFAULT_CONFIG)
    services = ALL_SERVICES - VacuumEntityFeature.FAN_SPEED
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        services, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None


async def test_status_error(hass, mqtt_mock_entry_with_yaml_config):
    """Test status updates from the vacuum."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

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


async def test_battery_template(hass, mqtt_mock_entry_with_yaml_config):
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
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "retroroomba/battery_level", "54")
    state = hass.states.get("vacuum.mqtttest")
    assert state.attributes.get(ATTR_BATTERY_LEVEL) == 54
    assert state.attributes.get(ATTR_BATTERY_ICON) == "mdi:battery-50"


async def test_status_invalid_json(hass, mqtt_mock_entry_with_yaml_config):
    """Test to make sure nothing breaks if the vacuum sends bad JSON."""
    config = deepcopy(DEFAULT_CONFIG)
    config[mqttvacuum.CONF_SUPPORTED_FEATURES] = services_to_strings(
        ALL_SERVICES, SERVICE_TO_STRING
    )

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "vacuum/state", '{"asdfasas false}')
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_STATUS) == "Stopped"


async def test_missing_battery_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_BATTERY_LEVEL_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_charging_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_CHARGING_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_cleaning_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_CLEANING_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_docked_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_DOCKED_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_error_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_ERROR_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


async def test_missing_fan_speed_template(hass, mqtt_mock_entry_no_yaml_config):
    """Test to make sure missing template is not allowed."""
    config = deepcopy(DEFAULT_CONFIG)
    config.pop(mqttvacuum.CONF_FAN_SPEED_TEMPLATE)

    assert await async_setup_component(hass, vacuum.DOMAIN, {vacuum.DOMAIN: config})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    state = hass.states.get("vacuum.mqtttest")
    assert state is None


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
        MQTT_LEGACY_VACUUM_ATTRIBUTES_BLOCKED,
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


async def test_update_with_json_attrs_bad_JSON(
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
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, vacuum.DOMAIN, config
    )


async def test_discovery_removal_vacuum(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test removal of discovered vacuum."""
    data = json.dumps(DEFAULT_CONFIG_2[vacuum.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, data
    )


async def test_discovery_update_vacuum(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered vacuum."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, vacuum.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_vacuum(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test update of discovered vacuum."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.vacuum.schema_legacy.MqttVacuum.discovery_update"
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
    data1 = '{ "name": "Beer",' '  "command_topic": "test_topic#" }'
    data2 = '{ "name": "Milk",' '  "command_topic": "test_topic" }'
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
    await help_test_entity_id_update_subscriptions(
        hass,
        mqtt_mock_entry_with_yaml_config,
        vacuum.DOMAIN,
        config,
        ["test-topic", "avty-topic"],
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_debug_info_message(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT debug info."""
    config = {
        vacuum.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "battery_level_topic": "state-topic",
            "battery_level_template": "{{ value_json.battery_level }}",
            "command_topic": "command-topic",
            "payload_turn_on": "ON",
        }
    }
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        vacuum.DOMAIN,
        config,
        vacuum.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (
            vacuum.SERVICE_TURN_ON,
            "command_topic",
            None,
            "turn_on",
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
            vacuum.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "turn_off",
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
        "turn_on",
        "turn_off",
        "clean_spot",
        "fan_speed",
        "send_command",
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
        (CONF_BATTERY_LEVEL_TOPIC, '{ "battery_level": 60 }', "battery_level", 60),
        (CONF_CHARGING_TOPIC, '{ "charging": true }', "status", "Stopped"),
        (CONF_CLEANING_TOPIC, '{ "cleaning": true }', "status", "Cleaning"),
        (CONF_DOCKED_TOPIC, '{ "docked": true }', "status", "Docked"),
        (
            CONF_ERROR_TOPIC,
            '{ "error": "some error" }',
            "status",
            "Error: some error",
        ),
        (
            CONF_FAN_SPEED_TOPIC,
            '{ "fan_speed": "medium" }',
            "fan_speed",
            "medium",
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
    config = deepcopy(DEFAULT_CONFIG)
    config[CONF_SUPPORTED_FEATURES] = [
        "turn_on",
        "turn_off",
        "pause",
        "stop",
        "return_home",
        "battery",
        "status",
        "locate",
        "clean_spot",
        "fan_speed",
        "send_command",
    ]

    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        vacuum.DOMAIN,
        config,
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
