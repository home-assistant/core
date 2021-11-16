"""The tests for the MQTT button platform."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components import button
from homeassistant.const import ATTR_ENTITY_ID, ATTR_FRIENDLY_NAME, STATE_UNKNOWN
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
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update_discovery_update,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

DEFAULT_CONFIG = {
    button.DOMAIN: {"platform": "mqtt", "name": "test", "command_topic": "test-topic"}
}


@pytest.mark.freeze_time("2021-11-08 13:31:44+00:00")
async def test_sending_mqtt_commands(hass, mqtt_mock):
    """Test the sending MQTT commands."""
    assert await async_setup_component(
        hass,
        button.DOMAIN,
        {
            button.DOMAIN: {
                "command_topic": "command-topic",
                "name": "test",
                "object_id": "test_button",
                "payload_press": "beer press",
                "platform": "mqtt",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("button.test_button")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "test"

    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: "button.test_button"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer press", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("button.test_button")
    assert state.state == "2021-11-08T13:31:44+00:00"


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    config = {
        button.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "command-topic",
            "payload_press": 1,
        }
    }

    await help_test_default_availability_payload(
        hass, mqtt_mock, button.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    config = {
        button.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "command_topic": "command-topic",
            "payload_press": 1,
        }
    }

    await help_test_custom_availability_payload(
        hass, mqtt_mock, button.DOMAIN, config, True, "state-topic", "1"
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG, None
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one button per unique_id."""
    config = {
        button.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, button.DOMAIN, config)


async def test_discovery_removal_button(hass, mqtt_mock, caplog):
    """Test removal of discovered button."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, button.DOMAIN, data)


async def test_discovery_update_button(hass, mqtt_mock, caplog):
    """Test update of discovered button."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[button.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[button.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"

    await help_test_discovery_update(
        hass,
        mqtt_mock,
        caplog,
        button.DOMAIN,
        config1,
        config2,
    )


async def test_discovery_update_unchanged_button(hass, mqtt_mock, caplog):
    """Test update of discovered button."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.button.MqttButton.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, button.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, button.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT button device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT button device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, button.DOMAIN, DEFAULT_CONFIG
    )
