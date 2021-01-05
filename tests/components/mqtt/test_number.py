"""The tests for mqtt number component."""
import json
from unittest.mock import patch

import pytest

from homeassistant.components import number
from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
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
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    number.DOMAIN: {"platform": "mqtt", "name": "test", "topic": "test_topic"}
}


async def test_run_number_setup(hass, mqtt_mock):
    """Test that it fetches the given payload."""
    topic = "test/number"
    await async_setup_component(
        hass,
        "number",
        {"number": {"platform": "mqtt", "topic": topic, "name": "Test Number"}},
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "10")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "10"

    async_fire_mqtt_message(hass, topic, "20.5")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "20.5"


async def test_run_number_service(hass, mqtt_mock):
    """Test that set_value service works."""
    topic = "test/number"
    await async_setup_component(
        hass,
        "number",
        {"number": {"platform": "mqtt", "topic": topic, "name": "Test Number"}},
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 30},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, "30", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "30"


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one number per unique_id."""
    config = {
        number.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, number.DOMAIN, config)


async def test_discovery_removal_number(hass, mqtt_mock, caplog):
    """Test removal of discovered number."""
    data = json.dumps(DEFAULT_CONFIG[number.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock, caplog, number.DOMAIN, data)


async def test_discovery_update_number(hass, mqtt_mock, caplog):
    """Test update of discovered number."""
    data1 = '{ "name": "Beer", "topic": "test_topic"}'
    data2 = '{ "name": "Milk", "topic": "test_topic"}'

    await help_test_discovery_update(
        hass, mqtt_mock, caplog, number.DOMAIN, data1, data2
    )


async def test_discovery_update_unchanged_number(hass, mqtt_mock, caplog):
    """Test update of discovered number."""
    data1 = '{ "name": "Beer", "topic": "test_topic"}'
    with patch(
        "homeassistant.components.mqtt.number.MqttNumber.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, number.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "topic": "test_topic"}'

    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, number.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG, ["test_topic"]
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, number.DOMAIN, DEFAULT_CONFIG, "test_topic", b"ON"
    )
