"""The tests for the MQTT switch platform."""
import pytest

from homeassistant.components import switch
from homeassistant.const import ATTR_ASSUMED_STATE, STATE_OFF, STATE_ON
import homeassistant.core as ha
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

from tests.async_mock import patch
from tests.common import async_fire_mqtt_message, async_mock_mqtt_component
from tests.components.switch import common

DEFAULT_CONFIG = {
    switch.DOMAIN: {"platform": "mqtt", "name": "test", "command_topic": "test-topic"}
}


@pytest.fixture
def mock_publish(hass):
    """Initialize components."""
    yield hass.loop.run_until_complete(async_mock_mqtt_component(hass))


async def test_controlling_state_via_topic(hass, mock_publish):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "0")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands_and_optimistic(hass, mock_publish):
    """Test the sending MQTT commands in optimistic mode."""
    fake_state = ha.State("switch.test", "on")

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=fake_state,
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "mqtt",
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "qos": "2",
                }
            },
        )

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "switch.test")

    mock_publish.async_publish.assert_called_once_with(
        "command-topic", "beer on", 2, False
    )
    mock_publish.async_publish.reset_mock()
    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "switch.test")

    mock_publish.async_publish.assert_called_once_with(
        "command-topic", "beer off", 2, False
    )
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_topic_and_json_message(hass, mock_publish):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": "beer on",
                "payload_off": "beer off",
                "value_template": "{{ value_json.val }}",
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer on"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer off"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    config = {
        switch.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    await help_test_default_availability_payload(
        hass, mqtt_mock, switch.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    config = {
        switch.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    await help_test_custom_availability_payload(
        hass, mqtt_mock, switch.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_state_payload(hass, mock_publish):
    """Test the state payload."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
                "state_on": "HIGH",
                "state_off": "LOW",
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "HIGH")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "LOW")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass):
    """Test unique id option only creates one switch per unique_id."""
    config = {
        switch.DOMAIN: [
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
    await help_test_unique_id(hass, switch.DOMAIN, config)


async def test_discovery_removal_switch(hass, mqtt_mock, caplog):
    """Test removal of discovered switch."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock, caplog, switch.DOMAIN, data)


async def test_discovery_update_switch(hass, mqtt_mock, caplog):
    """Test update of discovered switch."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, switch.DOMAIN, data1, data2
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
        hass, mqtt_mock, caplog, switch.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT switch device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT switch device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG
    )
