"""Common test objects."""
import copy
from datetime import datetime
import json
from unittest.mock import ANY, MagicMock, patch

import yaml

from homeassistant import config as hass_config
from homeassistant.components import mqtt
from homeassistant.components.mqtt import debug_info
from homeassistant.components.mqtt.const import MQTT_DISCONNECTED
from homeassistant.components.mqtt.mixins import MQTT_ATTRIBUTES_BLOCKED
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_mqtt_message, mock_registry

DEFAULT_CONFIG_DEVICE_INFO_ID = {
    "identifiers": ["helloworld"],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "hw_version": "rev1",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

DEFAULT_CONFIG_DEVICE_INFO_MAC = {
    "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "hw_version": "rev1",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

_SENTINEL = object()


async def help_test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config, domain, config
):
    """Test availability after MQTT disconnection."""
    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_DISCONNECTED)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE


async def help_test_availability_without_topic(
    hass, mqtt_mock_entry_with_yaml_config, domain, config
):
    """Test availability without defined availability topic."""
    assert "availability_topic" not in config[domain]
    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE


async def help_test_default_availability_payload(
    hass,
    mqtt_mock_entry_with_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability_topic"] = "availability-topic"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    if state_topic:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "online")

        state = hass.states.get(f"{domain}.test")
        assert state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload(
    hass,
    mqtt_mock_entry_with_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    if state_topic:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic1", "online")

        state = hass.states.get(f"{domain}.test")
        assert state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload_all(
    hass,
    mqtt_mock_entry_with_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability_mode"] = "all"
    config[domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload_any(
    hass,
    mqtt_mock_entry_with_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability_mode"] = "any"
    config[domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def help_test_default_availability_list_single(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability list and availability_topic are mutually exclusive.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability"] = [
        {"topic": "availability-topic1"},
    ]
    config[domain]["availability_topic"] = "availability-topic"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state is None
    assert (
        "Invalid config for [sensor.mqtt]: two or more values in the same group of exclusion 'availability'"
        in caplog.text
    )


async def help_test_custom_availability_payload(
    hass,
    mqtt_mock_entry_with_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test availability by custom payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[domain]["availability_topic"] = "availability-topic"
    config[domain]["payload_available"] = "good"
    config[domain]["payload_not_available"] = "nogood"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    if state_topic:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "good")

        state = hass.states.get(f"{domain}.test")
        assert state.state != STATE_UNAVAILABLE


async def help_test_discovery_update_availability(
    hass,
    mqtt_mock_entry_no_yaml_config,
    domain,
    config,
    no_assumed_state=False,
    state_topic=None,
    state_message=None,
):
    """Test update of discovered MQTTAvailability.

    This is a test helper for the MQTTAvailability mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add availability settings to config
    config1 = copy.deepcopy(config)
    config1[domain]["availability_topic"] = "availability-topic1"
    config2 = copy.deepcopy(config)
    config2[domain]["availability"] = [
        {"topic": "availability-topic2"},
        {"topic": "availability-topic3"},
    ]
    config3 = copy.deepcopy(config)
    config3[domain]["availability_topic"] = "availability-topic4"
    data1 = json.dumps(config1[domain])
    data2 = json.dumps(config2[domain])
    data3 = json.dumps(config3[domain])

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "offline")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Change availability_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic1", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic2", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic3", "offline")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Change availability_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data3)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic2", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic3", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic4", "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE


async def help_test_setting_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_with_yaml_config, domain, config
):
    """Test the setting of attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[domain]["json_attributes_topic"] = "attr-topic"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "attr-topic", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")

    assert state.attributes.get("val") == "100"


async def help_test_setting_blocked_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_no_yaml_config, domain, config, extra_blocked_attributes
):
    """Test the setting of blocked attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    extra_blocked_attributes = extra_blocked_attributes or []

    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[domain]["json_attributes_topic"] = "attr-topic"
    data = json.dumps(config[domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    val = "abc123"

    for attr in MQTT_ATTRIBUTES_BLOCKED:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state.attributes.get(attr) != val

    for attr in extra_blocked_attributes:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state.attributes.get(attr) != val


async def help_test_setting_attribute_with_template(
    hass, mqtt_mock_entry_with_yaml_config, domain, config
):
    """Test the setting of attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[domain]["json_attributes_topic"] = "attr-topic"
    config[domain]["json_attributes_template"] = "{{ value_json['Timer1'] | tojson }}"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(
        hass, "attr-topic", json.dumps({"Timer1": {"Arm": 0, "Time": "22:18"}})
    )
    state = hass.states.get(f"{domain}.test")

    assert state.attributes.get("Arm") == 0
    assert state.attributes.get("Time") == "22:18"


async def help_test_update_with_json_attrs_not_dict(
    hass, mqtt_mock_entry_with_yaml_config, caplog, domain, config
):
    """Test attributes get extracted from a JSON result.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[domain]["json_attributes_topic"] = "attr-topic"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "attr-topic", '[ "list", "of", "things"]')
    state = hass.states.get(f"{domain}.test")

    assert state.attributes.get("val") is None
    assert "JSON result was not a dictionary" in caplog.text


async def help_test_update_with_json_attrs_bad_JSON(
    hass, mqtt_mock_entry_with_yaml_config, caplog, domain, config
):
    """Test JSON validation of attributes.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[domain]["json_attributes_topic"] = "attr-topic"
    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, "attr-topic", "This is not JSON")

    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") is None
    assert "Erroneous JSON: This is not JSON" in caplog.text


async def help_test_discovery_update_attr(
    hass, mqtt_mock_entry_no_yaml_config, caplog, domain, config
):
    """Test update of discovered MQTTAttributes.

    This is a test helper for the MqttAttributes mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add JSON attributes settings to config
    config1 = copy.deepcopy(config)
    config1[domain]["json_attributes_topic"] = "attr-topic1"
    config2 = copy.deepcopy(config)
    config2[domain]["json_attributes_topic"] = "attr-topic2"
    data1 = json.dumps(config1[domain])
    data2 = json.dumps(config2[domain])

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "100"

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "50" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "100"

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "attr-topic2", '{ "val": "75" }')
    state = hass.states.get(f"{domain}.test")
    assert state.attributes.get("val") == "75"


async def help_test_unique_id(hass, mqtt_mock_entry_with_yaml_config, domain, config):
    """Test unique id option only creates one entity per unique_id."""
    assert await async_setup_component(hass, domain, config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    assert len(hass.states.async_entity_ids(domain)) == 1


async def help_test_discovery_removal(
    hass, mqtt_mock_entry_no_yaml_config, caplog, domain, data
):
    """Test removal of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert state.name == "test"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None


async def help_test_discovery_update(
    hass,
    mqtt_mock_entry_no_yaml_config,
    caplog,
    domain,
    discovery_config1,
    discovery_config2,
    state_data1=None,
    state_data2=None,
):
    """Test update of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add some future configuration to the configurations
    config1 = copy.deepcopy(discovery_config1)
    config1["some_future_option_1"] = "future_option_1"
    config2 = copy.deepcopy(discovery_config2)
    config2["some_future_option_2"] = "future_option_2"
    discovery_data1 = json.dumps(config1)
    discovery_data2 = json.dumps(config2)

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", discovery_data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    if state_data1:
        for (mqtt_messages, expected_state, attributes) in state_data1:
            for (topic, data) in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for (attr, value) in attributes:
                    assert state.attributes.get(attr) == value

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", discovery_data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Milk"

    if state_data2:
        for (mqtt_messages, expected_state, attributes) in state_data2:
            for (topic, data) in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for (attr, value) in attributes:
                    assert state.attributes.get(attr) == value

    state = hass.states.get(f"{domain}.milk")
    assert state is None


async def help_test_discovery_update_unchanged(
    hass, mqtt_mock_entry_no_yaml_config, caplog, domain, data1, discovery_update
):
    """Test update of discovered component without changes.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    assert not discovery_update.called


async def help_test_discovery_broken(
    hass, mqtt_mock_entry_no_yaml_config, caplog, domain, data1, data2
):
    """Test handling of bad discovery message."""
    await mqtt_mock_entry_no_yaml_config()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is None

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    assert state.name == "Milk"
    state = hass.states.get(f"{domain}.beer")
    assert state is None


async def help_test_encoding_subscribable_topics(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    domain,
    config,
    topic,
    value,
    attribute=None,
    attribute_value=None,
    init_payload=None,
    skip_raw_test=False,
):
    """Test handling of incoming encoded payload."""

    async def _test_encoding(
        hass,
        entity_id,
        topic,
        encoded_value,
        attribute,
        init_payload_topic,
        init_payload_value,
    ):
        state = hass.states.get(entity_id)

        if init_payload_value:
            # Sometimes a device needs to have an initialization pay load, e.g. to switch the device on.
            async_fire_mqtt_message(hass, init_payload_topic, init_payload_value)
            await hass.async_block_till_done()

        state = hass.states.get(entity_id)

        async_fire_mqtt_message(hass, topic, encoded_value)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)

        if attribute:
            return state.attributes.get(attribute)

        return state.state if state else None

    init_payload_value_utf8 = None
    init_payload_value_utf16 = None
    # setup test1 default encoding
    config1 = copy.deepcopy(config)
    if domain == "device_tracker":
        config1["unique_id"] = "test1"
    else:
        config1["name"] = "test1"
    config1[topic] = "topic/test1"
    # setup test2 alternate encoding
    config2 = copy.deepcopy(config)
    if domain == "device_tracker":
        config2["unique_id"] = "test2"
    else:
        config2["name"] = "test2"
    config2["encoding"] = "utf-16"
    config2[topic] = "topic/test2"
    # setup test3 raw encoding
    config3 = copy.deepcopy(config)
    if domain == "device_tracker":
        config3["unique_id"] = "test3"
    else:
        config3["name"] = "test3"
    config3["encoding"] = ""
    config3[topic] = "topic/test3"

    if init_payload:
        config1[init_payload[0]] = "topic/init_payload1"
        config2[init_payload[0]] = "topic/init_payload2"
        config3[init_payload[0]] = "topic/init_payload3"
        init_payload_value_utf8 = init_payload[1].encode("utf-8")
        init_payload_value_utf16 = init_payload[1].encode("utf-16")

    await hass.async_block_till_done()

    assert await async_setup_component(
        hass, domain, {domain: [config1, config2, config3]}
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    expected_result = attribute_value or value

    # test1 default encoding
    assert (
        await _test_encoding(
            hass,
            f"{domain}.test1",
            "topic/test1",
            value.encode("utf-8"),
            attribute,
            "topic/init_payload1",
            init_payload_value_utf8,
        )
        == expected_result
    )

    # test2 alternate encoding
    assert (
        await _test_encoding(
            hass,
            f"{domain}.test2",
            "topic/test2",
            value.encode("utf-16"),
            attribute,
            "topic/init_payload2",
            init_payload_value_utf16,
        )
        == expected_result
    )

    # test3 raw encoded input
    if skip_raw_test:
        return

    try:
        result = await _test_encoding(
            hass,
            f"{domain}.test3",
            "topic/test3",
            value.encode("utf-16"),
            attribute,
            "topic/init_payload3",
            init_payload_value_utf16,
        )
        assert result != expected_result
    except (AttributeError, TypeError, ValueError):
        pass


async def help_test_entity_device_info_with_identifier(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry integration.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.suggested_area == "default_area"
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_with_connection(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry integration.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_MAC)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(
        set(), {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.suggested_area == "default_area"
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_remove(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry remove."""
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    dev_registry = dr.async_get(hass)
    ent_registry = er.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = dev_registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    device = dev_registry.async_get_device({("mqtt", "helloworld")})
    assert device is None
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")


async def help_test_entity_device_info_update(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry update.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def help_test_entity_id_update_subscriptions(
    hass, mqtt_mock_entry_with_yaml_config, domain, config, topics=None
):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    # Add unique_id to config
    config = copy.deepcopy(config)
    config[domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topics is None:
        # Add default topics to config
        config[domain]["availability_topic"] = "avty-topic"
        config[domain]["state_topic"] = "test-topic"
        topics = ["avty-topic", "test-topic"]
    assert len(topics) > 0
    registry = mock_registry(hass, {})

    assert await async_setup_component(
        hass,
        domain,
        config,
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert mqtt_mock.async_subscribe.call_count == len(topics) + 3
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, ANY, ANY)
    mqtt_mock.async_subscribe.reset_mock()

    registry.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(topic, ANY, ANY, ANY)


async def help_test_entity_id_update_discovery_update(
    hass, mqtt_mock_entry_no_yaml_config, domain, config, topic=None
):
    """Test MQTT discovery update after entity_id is updated."""
    # Add unique_id to config
    await mqtt_mock_entry_no_yaml_config()
    config = copy.deepcopy(config)
    config[domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topic is None:
        # Add default topic to config
        config[domain]["availability_topic"] = "avty-topic"
        topic = "avty-topic"

    ent_registry = mock_registry(hass, {})

    data = json.dumps(config[domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "online")
    state = hass.states.get(f"{domain}.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, topic, "offline")
    state = hass.states.get(f"{domain}.test")
    assert state.state == STATE_UNAVAILABLE

    ent_registry.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()

    config[domain]["availability_topic"] = f"{topic}_2"
    data = json.dumps(config[domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1

    async_fire_mqtt_message(hass, f"{topic}_2", "online")
    state = hass.states.get(f"{domain}.milk")
    assert state.state != STATE_UNAVAILABLE


async def help_test_entity_debug_info(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 1
    assert (
        debug_info_data["entities"][0]["discovery_data"]["topic"]
        == f"homeassistant/{domain}/bla/config"
    )
    assert debug_info_data["entities"][0]["discovery_data"]["payload"] == config
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]
    assert debug_info_data["entities"][0]["transmitted"] == []
    assert len(debug_info_data["triggers"]) == 0


async def help_test_entity_debug_info_max_messages(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test debug_info message overflow.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    start_dt = datetime(2019, 1, 1, 0, 0, 0)
    with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
        dt_utcnow.return_value = start_dt
        for i in range(0, debug_info.STORED_MESSAGES + 1):
            async_fire_mqtt_message(hass, "test-topic", f"{i}")

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert (
        len(debug_info_data["entities"][0]["subscriptions"][0]["messages"])
        == debug_info.STORED_MESSAGES
    )
    messages = [
        {
            "payload": f"{i}",
            "qos": 0,
            "retain": False,
            "time": start_dt,
            "topic": "test-topic",
        }
        for i in range(1, debug_info.STORED_MESSAGES + 1)
    ]
    assert {"topic": "test-topic", "messages": messages} in debug_info_data["entities"][
        0
    ]["subscriptions"]


async def help_test_entity_debug_info_message(
    hass,
    mqtt_mock_entry_no_yaml_config,
    domain,
    config,
    service,
    command_topic=_SENTINEL,
    command_payload=_SENTINEL,
    state_topic=_SENTINEL,
    state_payload=_SENTINEL,
    service_parameters=None,
):
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    # Add device settings to config
    await mqtt_mock_entry_no_yaml_config()
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    if command_topic is _SENTINEL:
        # Add default topic to config
        config["command_topic"] = "command-topic"
        command_topic = "command-topic"

    if command_payload is _SENTINEL:
        command_payload = "ON"

    if state_topic is _SENTINEL:
        # Add default topic to config
        config["state_topic"] = "state-topic"
        state_topic = "state-topic"

    if state_payload is _SENTINEL:
        state_payload = "ON"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)

    start_dt = datetime(2019, 1, 1, 0, 0, 0)

    if state_topic is not None:
        assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
        assert {"topic": state_topic, "messages": []} in debug_info_data["entities"][0][
            "subscriptions"
        ]

        with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
            dt_utcnow.return_value = start_dt
            async_fire_mqtt_message(hass, state_topic, state_payload)

        debug_info_data = debug_info.info_for_device(hass, device.id)
        assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
        assert {
            "topic": state_topic,
            "messages": [
                {
                    "payload": str(state_payload),
                    "qos": 0,
                    "retain": False,
                    "time": start_dt,
                    "topic": state_topic,
                }
            ],
        } in debug_info_data["entities"][0]["subscriptions"]

    expected_transmissions = []
    if service:
        # Trigger an outgoing MQTT message
        with patch("homeassistant.util.dt.utcnow") as dt_utcnow:
            dt_utcnow.return_value = start_dt
            if service:
                service_data = {ATTR_ENTITY_ID: f"{domain}.test"}
                if service_parameters:
                    service_data.update(service_parameters)

                await hass.services.async_call(
                    domain,
                    service,
                    service_data,
                    blocking=True,
                )

        expected_transmissions = [
            {
                "topic": command_topic,
                "messages": [
                    {
                        "payload": str(command_payload),
                        "qos": 0,
                        "retain": False,
                        "time": start_dt,
                        "topic": command_topic,
                    }
                ],
            }
        ]

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert debug_info_data["entities"][0]["transmitted"] == expected_transmissions


async def help_test_entity_debug_info_remove(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 1
    assert (
        debug_info_data["entities"][0]["discovery_data"]["topic"]
        == f"homeassistant/{domain}/bla/config"
    )
    assert debug_info_data["entities"][0]["discovery_data"]["payload"] == config
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]
    assert len(debug_info_data["triggers"]) == 0
    assert debug_info_data["entities"][0]["entity_id"] == f"{domain}.test"
    entity_id = debug_info_data["entities"][0]["entity_id"]

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0
    assert entity_id not in hass.data[debug_info.DATA_MQTT_DEBUG_INFO]["entities"]


async def help_test_entity_debug_info_update_entity_id(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    dev_registry = dr.async_get(hass)
    ent_registry = mock_registry(hass, {})

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = dev_registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 1
    assert (
        debug_info_data["entities"][0]["discovery_data"]["topic"]
        == f"homeassistant/{domain}/bla/config"
    )
    assert debug_info_data["entities"][0]["discovery_data"]["payload"] == config
    assert debug_info_data["entities"][0]["entity_id"] == f"{domain}.test"
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]
    assert len(debug_info_data["triggers"]) == 0

    ent_registry.async_update_entity(f"{domain}.test", new_entity_id=f"{domain}.milk")
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 1
    assert (
        debug_info_data["entities"][0]["discovery_data"]["topic"]
        == f"homeassistant/{domain}/bla/config"
    )
    assert debug_info_data["entities"][0]["discovery_data"]["payload"] == config
    assert debug_info_data["entities"][0]["entity_id"] == f"{domain}.milk"
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]
    assert len(debug_info_data["triggers"]) == 0
    assert (
        f"{domain}.test" not in hass.data[debug_info.DATA_MQTT_DEBUG_INFO]["entities"]
    )


async def help_test_entity_disabled_by_default(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry remove."""
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["enabled_by_default"] = False
    config["unique_id"] = "veryunique1"

    dev_registry = dr.async_get(hass)
    ent_registry = er.async_get(hass)

    # Discover a disabled entity
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla1/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique1")
    assert not hass.states.get(entity_id)
    assert dev_registry.async_get_device({("mqtt", "helloworld")})

    # Discover an enabled entity, tied to the same device
    config["enabled_by_default"] = True
    config["unique_id"] = "veryunique2"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla2/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique2")
    assert hass.states.get(entity_id)

    # Remove the enabled entity, both entities and the device should be removed
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla2/config", "")
    await hass.async_block_till_done()
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique1")
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique2")
    assert not dev_registry.async_get_device({("mqtt", "helloworld")})


async def help_test_entity_category(
    hass, mqtt_mock_entry_no_yaml_config, domain, config
):
    """Test device registry remove."""
    await mqtt_mock_entry_no_yaml_config()
    # Add device settings to config
    config = copy.deepcopy(config[domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)

    ent_registry = er.async_get(hass)

    # Discover an entity without entity category
    unique_id = "veryunique1"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    assert hass.states.get(entity_id)
    entry = ent_registry.async_get(entity_id)
    assert entry.entity_category is None

    # Discover an entity with entity category set to "config"
    unique_id = "veryunique2"
    config["entity_category"] = "config"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    assert hass.states.get(entity_id)
    entry = ent_registry.async_get(entity_id)
    assert entry.entity_category == "config"

    # Discover an entity with entity category set to "no_such_category"
    unique_id = "veryunique3"
    config["entity_category"] = "no_such_category"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)


async def help_test_publishing_with_custom_encoding(
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
    tpl_par="value",
    tpl_output=None,
):
    """Test a service with publishing MQTT payload with different encoding."""
    # prepare config for tests
    test_config = {
        "test1": {"encoding": None, "cmd_tpl": False},
        "test2": {"encoding": "utf-16", "cmd_tpl": False},
        "test3": {"encoding": "", "cmd_tpl": False},
        "test4": {"encoding": "invalid", "cmd_tpl": False},
        "test5": {"encoding": "", "cmd_tpl": True},
    }
    setup_config = []
    service_data = {}
    for test_id, test_data in test_config.items():
        test_config_setup = copy.deepcopy(config)
        test_config_setup.update(
            {
                topic: f"cmd/{test_id}",
                "name": f"{test_id}",
            }
        )
        if test_data["encoding"] is not None:
            test_config_setup["encoding"] = test_data["encoding"]
        if test_data["cmd_tpl"]:
            test_config_setup[
                template
            ] = f"{{{{ (('%.1f'|format({tpl_par}))[0] if is_number({tpl_par}) else {tpl_par}[0]) | ord | pack('b') }}}}"
        setup_config.append(test_config_setup)

        # setup service data
        service_data[test_id] = {ATTR_ENTITY_ID: f"{domain}.{test_id}"}
        if parameters:
            service_data[test_id].update(parameters)

    # setup test entities
    assert await async_setup_component(
        hass,
        domain,
        {domain: setup_config},
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    # 1) test with default encoding
    await hass.services.async_call(
        domain,
        service,
        service_data["test1"],
        blocking=True,
    )

    mqtt_mock.async_publish.assert_any_call("cmd/test1", str(payload), 0, False)
    mqtt_mock.async_publish.reset_mock()

    # 2) test with utf-16 encoding
    await hass.services.async_call(
        domain,
        service,
        service_data["test2"],
        blocking=True,
    )
    mqtt_mock.async_publish.assert_any_call(
        "cmd/test2", str(payload).encode("utf-16"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    # 3) test with no encoding set should fail if payload is a string
    await hass.services.async_call(
        domain,
        service,
        service_data["test3"],
        blocking=True,
    )
    assert (
        f"Can't pass-through payload for publishing {payload} on cmd/test3 with no encoding set, need 'bytes'"
        in caplog.text
    )

    # 4) test with invalid encoding set should fail
    await hass.services.async_call(
        domain,
        service,
        service_data["test4"],
        blocking=True,
    )
    assert (
        f"Can't encode payload for publishing {payload} on cmd/test4 with encoding invalid"
        in caplog.text
    )

    # 5) test with command template and raw encoding if specified
    if not template:
        return

    await hass.services.async_call(
        domain,
        service,
        service_data["test5"],
        blocking=True,
    )
    mqtt_mock.async_publish.assert_any_call(
        "cmd/test5", tpl_output or str(payload)[0].encode("utf-8"), 0, False
    )
    mqtt_mock.async_publish.reset_mock()


async def help_test_reload_with_config(hass, caplog, tmp_path, config):
    """Test reloading with supplied config."""
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump(config)
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert "<Event event_mqtt_reloaded[L]>" in caplog.text


async def help_test_entry_reload_with_new_config(hass, tmp_path, new_config):
    """Test reloading with supplied config."""
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump(new_config)
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file), patch(
        "paho.mqtt.client.Client"
    ) as mock_client:
        mock_client().connect = lambda *args: 0
        # reload the config entry
        assert await hass.config_entries.async_reload(mqtt_config_entry.entry_id)
        assert mqtt_config_entry.state is ConfigEntryState.LOADED
        await hass.async_block_till_done()


async def help_test_reloadable(
    hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
):
    """Test reloading an MQTT platform."""
    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "test_old_1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "test_old_2"
    old_config_3 = copy.deepcopy(config)
    old_config_3["name"] = "test_old_3"
    old_config_3.pop("platform")
    old_config_4 = copy.deepcopy(config)
    old_config_4["name"] = "test_old_4"
    old_config_4.pop("platform")

    old_config = {
        domain: [old_config_1, old_config_2],
        "mqtt": {domain: [old_config_3, old_config_4]},
    }

    assert await async_setup_component(hass, domain, old_config)
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    assert hass.states.get(f"{domain}.test_old_1")
    assert hass.states.get(f"{domain}.test_old_2")
    assert hass.states.get(f"{domain}.test_old_3")
    assert hass.states.get(f"{domain}.test_old_4")
    assert len(hass.states.async_all(domain)) == 4

    # Create temporary fixture for configuration.yaml based on the supplied config and
    # test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "test_new_1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test_new_2"
    new_config_3 = copy.deepcopy(config)
    new_config_3["name"] = "test_new_3"
    new_config_3.pop("platform")
    new_config_4 = copy.deepcopy(config)
    new_config_4["name"] = "test_new_4"
    new_config_4.pop("platform")
    new_config_5 = copy.deepcopy(config)
    new_config_5["name"] = "test_new_5"
    new_config_6 = copy.deepcopy(config)
    new_config_6["name"] = "test_new_6"
    new_config_6.pop("platform")

    new_config = {
        domain: [new_config_1, new_config_2, new_config_5],
        "mqtt": {domain: [new_config_3, new_config_4, new_config_6]},
    }

    await help_test_reload_with_config(hass, caplog, tmp_path, new_config)

    assert len(hass.states.async_all(domain)) == 6

    assert hass.states.get(f"{domain}.test_new_1")
    assert hass.states.get(f"{domain}.test_new_2")
    assert hass.states.get(f"{domain}.test_new_3")
    assert hass.states.get(f"{domain}.test_new_4")
    assert hass.states.get(f"{domain}.test_new_5")
    assert hass.states.get(f"{domain}.test_new_6")


async def help_test_reloadable_late(hass, caplog, tmp_path, domain, config):
    """Test reloading an MQTT platform when config entry is setup late."""
    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "test_old_1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "test_old_2"

    old_yaml_config_file = tmp_path / "configuration.yaml"
    old_yaml_config = yaml.dump({domain: [old_config_1, old_config_2]})
    old_yaml_config_file.write_text(old_yaml_config)
    assert old_yaml_config_file.read_text() == old_yaml_config

    assert await async_setup_component(
        hass, domain, {domain: [old_config_1, old_config_2]}
    )
    await hass.async_block_till_done()

    # No MQTT config entry, there should be a warning and no entities
    assert (
        "MQTT integration is not setup, skipping setup of manually "
        f"configured MQTT {domain}"
    ) in caplog.text
    assert len(hass.states.async_all(domain)) == 0

    # User sets up a config entry, should succeed and entities will setup
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)
    with patch.object(hass_config, "YAML_CONFIG_FILE", old_yaml_config_file):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert len(hass.states.async_all(domain)) == 2

    # Create temporary fixture for configuration.yaml based on the supplied config and
    # test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "test_new_1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test_new_2"
    new_config_3 = copy.deepcopy(config)
    new_config_3["name"] = "test_new_3"

    new_config = {
        domain: [new_config_1, new_config_2, new_config_3],
    }
    await help_test_reload_with_config(hass, caplog, tmp_path, new_config)
    await hass.async_block_till_done()

    assert len(hass.states.async_all(domain)) == 3

    assert hass.states.get(f"{domain}.test_new_1")
    assert hass.states.get(f"{domain}.test_new_2")
    assert hass.states.get(f"{domain}.test_new_3")


async def help_test_setup_manual_entity_from_yaml(hass, platform, config):
    """Help to test setup from yaml through configuration entry."""
    calls = MagicMock()

    async def mock_reload(hass):
        """Mock reload."""
        calls()

    config_structure = {mqtt.DOMAIN: {platform: config}}

    await async_setup_component(hass, mqtt.DOMAIN, config_structure)
    # Mock config entry
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.mqtt.async_reload_manual_mqtt_items",
        side_effect=mock_reload,
    ), patch("paho.mqtt.client.Client") as mock_client:
        mock_client().connect = lambda *args: 0
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        calls.assert_called_once()


async def help_test_unload_config_entry(hass, tmp_path, newconfig):
    """Test unloading the MQTT config entry."""
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump(newconfig)
    new_yaml_config_file.write_text(new_yaml_config)
    with patch.object(hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
        assert mqtt_config_entry.state is ConfigEntryState.NOT_LOADED
        await hass.async_block_till_done()


async def help_test_unload_config_entry_with_platform(
    hass,
    mqtt_mock_entry_with_yaml_config,
    tmp_path,
    domain,
    config,
):
    """Test unloading the MQTT config entry with a specific platform domain."""
    # prepare setup through configuration.yaml
    config_setup = copy.deepcopy(config)
    config_setup["name"] = "config_setup"
    config_name = config_setup
    assert await async_setup_component(hass, domain, {domain: [config_setup]})
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    # prepare setup through discovery
    discovery_setup = copy.deepcopy(config)
    discovery_setup["name"] = "discovery_setup"
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/bla/config", json.dumps(discovery_setup)
    )
    await hass.async_block_till_done()

    # check if both entities were setup correctly
    config_setup_entity = hass.states.get(f"{domain}.config_setup")
    assert config_setup_entity

    discovery_setup_entity = hass.states.get(f"{domain}.discovery_setup")
    assert discovery_setup_entity

    await help_test_unload_config_entry(hass, tmp_path, config_setup)

    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/bla/config", json.dumps(discovery_setup)
    )
    await hass.async_block_till_done()

    # check if both entities were unloaded correctly
    config_setup_entity = hass.states.get(f"{domain}.{config_name}")
    assert config_setup_entity is None

    discovery_setup_entity = hass.states.get(f"{domain}.discovery_setup")
    assert discovery_setup_entity is None
