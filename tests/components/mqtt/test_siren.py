"""The tests for the MQTT siren platform."""
import copy
from unittest.mock import patch

import pytest

from homeassistant.components import siren
from homeassistant.components.siren.const import ATTR_VOLUME_LEVEL
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
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
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    siren.DOMAIN: {"platform": "mqtt", "name": "test", "command_topic": "test-topic"}
}


async def async_turn_on(hass, entity_id=ENTITY_MATCH_ALL, parameters={}) -> None:
    """Turn all or specified siren on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data.update(parameters)

    await hass.services.async_call(siren.DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified siren off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(siren.DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def test_invalid_setup(hass, mqtt_mock, caplog):
    """Test the setup with an invalid configuration."""
    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "name": "test",
                "tone_command_topic": "tone-command-topic",
                "available_tones": [],
            }
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [siren.mqtt]: not a valid value." in caplog.text

    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "name": "test",
                "tone_command_topic": "tone-command-topic",
            }
        },
    )
    await hass.async_block_till_done()
    assert "Invalid config for [siren.mqtt]: not a valid value." in caplog.text


async def test_controlling_state_via_topic(hass, mqtt_mock):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "0")

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock):
    """Test the sending MQTT commands in optimistic mode."""
    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "payload_on": "beer on",
                "payload_off": "beer off",
                "qos": "2",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(hass, entity_id="siren.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer on", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    await async_turn_off(hass, entity_id="siren.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "beer off", 2, False
    )
    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_topic_and_json_message(hass, mqtt_mock):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
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
    await hass.async_block_till_done()

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer on"}')

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer off"}')

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    config = {
        siren.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    await help_test_default_availability_payload(
        hass, mqtt_mock, siren.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    config = {
        siren.DOMAIN: {
            "platform": "mqtt",
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "payload_on": 1,
            "payload_off": 0,
        }
    }

    await help_test_custom_availability_payload(
        hass, mqtt_mock, siren.DOMAIN, config, True, "state-topic", "1"
    )


async def test_custom_state_payload(hass, mqtt_mock):
    """Test the state payload."""
    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {
            siren.DOMAIN: {
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
    await hass.async_block_till_done()

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "HIGH")

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "LOW")

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG, {}
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique id option only creates one siren per unique_id."""
    config = {
        siren.DOMAIN: [
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
    await help_test_unique_id(hass, mqtt_mock, siren.DOMAIN, config)


async def test_discovery_removal_siren(hass, mqtt_mock, caplog):
    """Test removal of discovered siren."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock, caplog, siren.DOMAIN, data)


async def test_discovery_update_siren_topic_template(hass, mqtt_mock, caplog):
    """Test update of discovered siren."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[siren.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[siren.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "siren/state1"
    config2["state_topic"] = "siren/state2"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("siren/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("siren/state2", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("siren/state2", '{"state2":{"state":"ON"}}')], "on", None),
        ([("siren/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("siren/state1", '{"state2":{"state":"OFF"}}')], "on", None),
        ([("siren/state2", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("siren/state2", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock,
        caplog,
        siren.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_siren_template(hass, mqtt_mock, caplog):
    """Test update of discovered siren."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[siren.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[siren.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "siren/state1"
    config2["state_topic"] = "siren/state1"
    config1["value_template"] = "{{ value_json.state1.state }}"
    config2["value_template"] = "{{ value_json.state2.state }}"

    state_data1 = [
        ([("siren/state1", '{"state1":{"state":"ON"}}')], "on", None),
    ]
    state_data2 = [
        ([("siren/state1", '{"state2":{"state":"OFF"}}')], "off", None),
        ([("siren/state1", '{"state2":{"state":"ON"}}')], "on", None),
        ([("siren/state1", '{"state1":{"state":"OFF"}}')], "on", None),
        ([("siren/state1", '{"state2":{"state":"OFF"}}')], "off", None),
    ]

    await help_test_discovery_update(
        hass,
        mqtt_mock,
        caplog,
        siren.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_command_templates(hass, mqtt_mock, caplog):
    """Test siren with command templates."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[siren.DOMAIN])
    config1["name"] = "Beer"
    config1["available_tones"] = ["ping", "chimes"]
    config1["duration_command_topic"] = "duration-command-topic"
    config1["tone_command_topic"] = "tone-command-topic"
    config1["volume_command_topic"] = "volume-command-topic"
    config1[
        "command_template"
    ] = "CMD: {{ value }}, DURATION: {{ duration }}, TONE: {{ tone }}, VOLUME: {{ volume_level }}"
    config1["tone_command_template"] = "TONE: {{ value }}"
    config1["duration_command_template"] = "DURATION: {{ value }}"
    config1["volume_command_template"] = "VOLUME: {{ value }}"

    config2 = copy.deepcopy(config1)
    config2["name"] = "Milk"
    config2["command_off_template"] = "CMD_OFF: {{ value }}"

    assert await async_setup_component(
        hass,
        siren.DOMAIN,
        {siren.DOMAIN: [config1, config2]},
    )
    await hass.async_block_till_done()

    state1 = hass.states.get("siren.beer")
    assert state1.state == STATE_OFF
    assert state1.attributes.get(ATTR_ASSUMED_STATE)

    state2 = hass.states.get("siren.milk")
    assert state2.state == STATE_OFF
    assert state1.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(
        hass,
        entity_id="siren.beer",
        parameters={
            siren.ATTR_DURATION: 22,
            siren.ATTR_TONE: "ping",
            ATTR_VOLUME_LEVEL: 0.88,
        },
    )
    mqtt_mock.async_publish.assert_any_call(
        "test-topic", "CMD: ON, DURATION: 22, TONE: ping, VOLUME: 0.88", 0, False
    )
    mqtt_mock.async_publish.assert_any_call(
        "duration-command-topic", "DURATION: 22", 0, False
    )
    mqtt_mock.async_publish.assert_any_call(
        "tone-command-topic", "TONE: ping", 0, False
    )
    mqtt_mock.async_publish.assert_any_call(
        "volume-command-topic", "VOLUME: 0.88", 0, False
    )
    mqtt_mock.async_publish.call_count == 4
    mqtt_mock.reset_mock()
    await async_turn_off(
        hass,
        entity_id="siren.beer",
    )
    mqtt_mock.async_publish.assert_any_call(
        "test-topic", "CMD: OFF, DURATION: , TONE: , VOLUME:", 0, False
    )
    mqtt_mock.async_publish.call_count == 1
    mqtt_mock.reset_mock()
    await async_turn_off(
        hass,
        entity_id="siren.milk",
    )
    mqtt_mock.async_publish.assert_any_call("test-topic", "CMD_OFF: OFF", 0, False)
    mqtt_mock.async_publish.call_count == 1
    mqtt_mock.reset_mock()


async def test_discovery_update_unchanged_siren(hass, mqtt_mock, caplog):
    """Test update of discovered siren."""
    data1 = (
        '{ "name": "Beer",'
        '  "device_class": "siren",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.siren.MqttSiren.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, siren.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, siren.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT siren device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT siren device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, siren.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
    [
        (
            siren.SERVICE_TURN_ON,
            "command_topic",
            None,
            "ON",
            "command_template",
        ),
        (
            siren.SERVICE_TURN_ON,
            "duration_command_topic",
            {siren.ATTR_DURATION: 22},
            "22",
            "duration_command_template",
        ),
        (
            siren.SERVICE_TURN_ON,
            "tone_command_topic",
            {siren.ATTR_TONE: "xylophone"},
            "xylophone",
            "tone_command_template",
        ),
        (
            siren.SERVICE_TURN_ON,
            "volume_command_topic",
            {siren.ATTR_VOLUME_LEVEL: 0.88},
            "0.88",
            "volume_command_template",
        ),
        (
            siren.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "OFF",
            "command_off_template",
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass,
    mqtt_mock,
    caplog,
    service,
    topic,
    parameters,
    payload,
    template,
):
    """Test publishing MQTT payload with command templates and different encoding."""
    domain = siren.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[domain])
    config[siren.ATTR_AVAILABLE_TONES] = ["siren", "xylophone"]

    await help_test_publishing_with_custom_encoding(
        hass,
        mqtt_mock,
        caplog,
        domain,
        config,
        service,
        topic,
        parameters,
        payload,
        template,
    )


async def test_reloadable(hass, mqtt_mock, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = siren.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(hass, mqtt_mock, caplog, tmp_path, domain, config)


@pytest.mark.parametrize(
    "topic,value,attribute,attribute_value",
    [
        ("state_topic", "ON", None, "on"),
    ],
)
async def test_encoding_subscribable_topics(
    hass, mqtt_mock, caplog, topic, value, attribute, attribute_value
):
    """Test handling of incoming encoded payload."""
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock,
        caplog,
        siren.DOMAIN,
        DEFAULT_CONFIG[siren.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
    )
