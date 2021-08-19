"""The tests for mqtt select component."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components import select
from homeassistant.components.mqtt.select import (
    CONF_OPTIONS,
    MQTT_SELECT_ATTRIBUTES_BLOCKED,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_UNKNOWN
import homeassistant.core as ha
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
    help_test_entity_debug_info_message,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    select.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "command_topic": "test-topic",
        "options": ["milk", "beer"],
    }
}


async def test_run_select_setup(hass, mqtt_mock):
    """Test that it fetches the given payload."""
    topic = "test/select"
    await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "state_topic": topic,
                "command_topic": topic,
                "name": "Test Select",
                "options": ["milk", "beer"],
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "milk")

    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == "milk"

    async_fire_mqtt_message(hass, topic, "beer")

    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == "beer"


async def test_value_template(hass, mqtt_mock):
    """Test that it fetches the given payload with a template."""
    topic = "test/select"
    await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "state_topic": topic,
                "command_topic": topic,
                "name": "Test Select",
                "options": ["milk", "beer"],
                "value_template": "{{ value_json.val }}",
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, '{"val":"milk"}')

    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == "milk"

    async_fire_mqtt_message(hass, topic, '{"val":"beer"}')

    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == "beer"

    async_fire_mqtt_message(hass, topic, '{"val": null}')

    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == STATE_UNKNOWN


async def test_run_select_service_optimistic(hass, mqtt_mock):
    """Test that set_value service works in optimistic mode."""
    topic = "test/select"

    fake_state = ha.State("select.test", "milk")

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=fake_state,
    ):
        assert await async_setup_component(
            hass,
            select.DOMAIN,
            {
                "select": {
                    "platform": "mqtt",
                    "command_topic": topic,
                    "name": "Test Select",
                    "options": ["milk", "beer"],
                }
            },
        )
        await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.state == "milk"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_select", ATTR_OPTION: "beer"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, "beer", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("select.test_select")
    assert state.state == "beer"


async def test_run_select_service(hass, mqtt_mock):
    """Test that set_value service works in non optimistic mode."""
    cmd_topic = "test/select/set"
    state_topic = "test/select"

    assert await async_setup_component(
        hass,
        select.DOMAIN,
        {
            "select": {
                "platform": "mqtt",
                "command_topic": cmd_topic,
                "state_topic": state_topic,
                "name": "Test Select",
                "options": ["milk", "beer"],
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, state_topic, "beer")
    state = hass.states.get("select.test_select")
    assert state.state == "beer"

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: "select.test_select", ATTR_OPTION: "milk"},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(cmd_topic, "milk", 0, False)
    state = hass.states.get("select.test_select")
    assert state.state == "beer"


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG, MQTT_SELECT_ATTRIBUTES_BLOCKED
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one select per unique_id."""
    config = {
        select.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
                "options": ["milk", "beer"],
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
                "options": ["milk", "beer"],
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, select.DOMAIN, config)


async def test_discovery_removal_select(hass, mqtt_mock, caplog):
    """Test removal of discovered select."""
    data = json.dumps(DEFAULT_CONFIG[select.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock, caplog, select.DOMAIN, data)


async def test_discovery_update_select(hass, mqtt_mock, caplog):
    """Test update of discovered select."""
    data1 = '{ "name": "Beer", "state_topic": "test-topic", "command_topic": "test-topic", "options": ["milk", "beer"]}'
    data2 = '{ "name": "Milk", "state_topic": "test-topic", "command_topic": "test-topic", "options": ["milk", "beer"]}'

    await help_test_discovery_update(
        hass, mqtt_mock, caplog, select.DOMAIN, data1, data2
    )


async def test_discovery_update_unchanged_select(hass, mqtt_mock, caplog):
    """Test update of discovered select."""
    data1 = '{ "name": "Beer", "state_topic": "test-topic", "command_topic": "test-topic", "options": ["milk", "beer"]}'
    with patch(
        "homeassistant.components.mqtt.select.MqttSelect.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, select.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "state_topic": "test-topic", "command_topic": "test-topic", "options": ["milk", "beer"]}'

    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, select.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT select device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT select device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, select.DOMAIN, DEFAULT_CONFIG, payload="milk"
    )


async def test_options_attributes(hass, mqtt_mock):
    """Test options attribute."""
    topic = "test/select"
    await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "state_topic": topic,
                "command_topic": topic,
                "name": "Test select",
                "options": ["milk", "beer"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("select.test_select")
    assert state.attributes.get(ATTR_OPTIONS) == ["milk", "beer"]


async def test_invalid_options(hass, caplog, mqtt_mock):
    """Test invalid options."""
    topic = "test/select"
    await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "state_topic": topic,
                "command_topic": topic,
                "name": "Test Select",
                "options": "beer",
            }
        },
    )
    await hass.async_block_till_done()

    assert f"'{CONF_OPTIONS}' must include at least 2 options" in caplog.text


async def test_mqtt_payload_not_an_option_warning(hass, caplog, mqtt_mock):
    """Test warning for MQTT payload which is not a valid option."""
    topic = "test/select"
    await async_setup_component(
        hass,
        "select",
        {
            "select": {
                "platform": "mqtt",
                "state_topic": topic,
                "command_topic": topic,
                "name": "Test Select",
                "options": ["milk", "beer"],
            }
        },
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "öl")

    await hass.async_block_till_done()

    assert (
        "Invalid option for select.test_select: 'öl' (valid options: ['milk', 'beer'])"
        in caplog.text
    )
