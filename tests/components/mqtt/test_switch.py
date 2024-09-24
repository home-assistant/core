"""The tests for the MQTT switch platform."""

import copy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, switch
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, State

from .test_common import (
    help_custom_config,
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
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_skipped_async_ha_write_state,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, mock_restore_cache
from tests.components.switch import common
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {switch.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


@pytest.mark.parametrize(
    ("hass_config", "device_class"),
    [
        (
            {
                mqtt.DOMAIN: {
                    switch.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                        "payload_on": 1,
                        "payload_off": 0,
                        "device_class": "switch",
                    }
                }
            },
            "switch",
        ),
        (
            {
                mqtt.DOMAIN: {
                    switch.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                        "payload_on": 1,
                        "payload_off": 0,
                        "device_class": None,
                    }
                }
            },
            None,
        ),
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_class: str | None,
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "0")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "state-topic", "None")

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "qos": "2",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending MQTT commands in optimistic mode."""
    fake_state = State("switch.test", "on")
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "switch.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer on", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "switch.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer off", 2, False
    )
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                }
            }
        }
    ],
)
async def test_sending_inital_state_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the initial state in optimistic mode."""
    await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "command_template": '{"state": "{{ value }}"}',
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "qos": "2",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_with_command_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending MQTT commands using a command template."""
    fake_state = State("switch.test", "on")
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "switch.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{"state": "beer on"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_turn_off(hass, "switch.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{"state": "beer off"}', 2, False
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "value_template": "{{ value_json.val }}",
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic_and_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic and JSON message."""
    await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer on"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer off"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "state-topic", '{"val": null}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, switch.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            switch.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        }
    }
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            switch.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        }
    }

    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": 1,
                    "payload_off": 0,
                    "state_on": "HIGH",
                    "state_off": "LOW",
                }
            }
        }
    ],
)
async def test_custom_state_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the state payload."""
    await mqtt_mock_entry()

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "HIGH")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "LOW")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG, {}
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                switch.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                ]
            }
        }
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one switch per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, switch.DOMAIN)


async def test_discovery_removal_switch(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered switch."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock_entry, switch.DOMAIN, data)


async def test_discovery_update_switch_topic_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered switch."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][switch.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][switch.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "switch/state1"
    config2["state_topic"] = "switch/state2"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("switch/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("switch/state2", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("switch/state2", '{"state2":{"state":"ON"}}')], "on", None),
        ([("switch/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("switch/state1", '{"state2":{"state":"OFF"}}')], "on", None),
        ([("switch/state2", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("switch/state2", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_switch_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered switch."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][switch.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][switch.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "switch/state1"
    config2["state_topic"] = "switch/state1"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("switch/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("switch/state1", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("switch/state1", '{"state2":{"state":"ON"}}')], "on", None),
        ([("switch/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("switch/state1", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_unchanged_switch(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered switch."""
    data1 = (
        '{ "name": "Beer",'
        '  "device_class": "switch",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.switch.MqttSwitch.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            switch.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(hass, mqtt_mock_entry, switch.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT switch device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT switch device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, switch.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        DEFAULT_CONFIG,
        switch.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            switch.SERVICE_TURN_ON,
            "command_topic",
            None,
            "ON",
            None,
        ),
        (
            switch.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "OFF",
            None,
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = switch.DOMAIN
    config = DEFAULT_CONFIG

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock_entry,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = switch.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "ON", None, "on"),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    value: str,
    attribute: str | None,
    attribute_value: Any,
) -> None:
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        switch.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][switch.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
    )


@pytest.mark.parametrize(
    "hass_config",
    [DEFAULT_CONFIG, {"mqtt": [DEFAULT_CONFIG["mqtt"]]}],
    ids=["platform_key", "listed"],
)
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = switch.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = switch.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            switch.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "state_topic": "test-topic",
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("test-topic", "ON", "OFF"),
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
    ],
)
async def test_skipped_async_ha_write_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    topic: str,
    payload1: str,
    payload2: str,
) -> None:
    """Test a write state command is only called when there is change."""
    await mqtt_mock_entry()
    await help_test_skipped_async_ha_write_state(hass, topic, payload1, payload2)


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            switch.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "state_topic": "test-topic",
                    "value_template": "{{ value_json.some_var * 1 }}",
                },
            ),
        )
    ],
)
async def test_value_template_fails(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the rendering of MQTT value template fails."""
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, "test-topic", '{"some_var": null }')
    assert (
        "TypeError: unsupported operand type(s) for *: 'NoneType' and 'int' rendering template"
        in caplog.text
    )
