"""Common test objects."""

from collections.abc import Iterable
from contextlib import suppress
import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import ANY, MagicMock, patch

from freezegun import freeze_time
import pytest
import voluptuous as vol
import yaml

from homeassistant import config as module_hass_config
from homeassistant.components import mqtt
from homeassistant.components.mqtt import debug_info
from homeassistant.components.mqtt.const import (
    MQTT_CONNECTION_STATE,
    SUPPORTED_COMPONENTS,
)
from homeassistant.components.mqtt.entity import MQTT_ATTRIBUTES_BLOCKED
from homeassistant.components.mqtt.models import PublishPayloadType
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    SERVICE_RELOAD,
    STATE_UNAVAILABLE,
    EntityCategory,
)
from homeassistant.core import HassJobType, HomeAssistant
from homeassistant.generated.mqtt import MQTT
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG_DEVICE_INFO_ID = {
    "identifiers": ["helloworld"],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "model_id": "XYZ001",
    "hw_version": "rev1",
    "serial_number": "1234deadbeef",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

DEFAULT_CONFIG_DEVICE_INFO_MAC = {
    "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
    "manufacturer": "Whatever",
    "name": "Beer",
    "model": "Glass",
    "model_id": "XYZ001",
    "hw_version": "rev1",
    "serial_number": "1234deadbeef",
    "sw_version": "0.1-beta",
    "suggested_area": "default_area",
    "configuration_url": "http://example.com",
}

_SENTINEL = object()

DISCOVERY_COUNT = len(MQTT)
DEVICE_DISCOVERY_COUNT = 2

type _MqttMessageType = list[tuple[str, str]]
type _AttributesType = list[tuple[str, Any]]
type _StateDataType = (
    list[tuple[_MqttMessageType, str, _AttributesType | None]]
    | list[tuple[_MqttMessageType, str, None]]
)


def help_all_subscribe_calls(mqtt_client_mock: MqttMockPahoClient) -> list[Any]:
    """Test of a call."""
    all_calls = []
    for call_l1 in mqtt_client_mock.subscribe.mock_calls:
        if isinstance(call_l1[1][0], list):
            for call_l2 in call_l1[1]:
                all_calls.extend(call_l2)
        else:
            all_calls.append(call_l1[1])
    return all_calls


def help_custom_config(
    mqtt_entity_domain: str,
    mqtt_base_config: ConfigType,
    mqtt_entity_configs: Iterable[ConfigType],
) -> ConfigType:
    """Tweak a default config for parametrization.

    Returns a custom config to be used as parametrization for with hass_config,
    based on the supplied mqtt_base_config and updated with mqtt_entity_configs.
    For each item in mqtt_entity_configs an entity instance is added to the config.
    """
    config: ConfigType = copy.deepcopy(mqtt_base_config)
    entity_instances: list[ConfigType] = []
    for instance in mqtt_entity_configs:
        base: ConfigType = copy.deepcopy(
            mqtt_base_config[mqtt.DOMAIN][mqtt_entity_domain]
        )
        base.update(instance)
        entity_instances.append(base)
    config[mqtt.DOMAIN][mqtt_entity_domain] = entity_instances
    return config


async def help_test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, domain: str
) -> None:
    """Test availability after MQTT disconnection."""
    mqtt_mock = await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    mqtt_mock.connected = False
    async_dispatcher_send(hass, MQTT_CONNECTION_STATE, False)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE


async def help_test_availability_without_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test availability without defined availability topic."""
    assert "availability_topic" not in config[mqtt.DOMAIN][domain]
    await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_default_availability_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
    state_topic: str | None = None,
    state_message: str | None = None,
) -> None:
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic"

    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    if state_topic is not None and state_message is not None:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state and state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "online")

        state = hass.states.get(f"{domain}.test")
        assert state and state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
    state_topic: str | None = None,
    state_message: str | None = None,
) -> None:
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    if state_topic is not None and state_message is not None:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state and state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic1", "online")

        state = hass.states.get(f"{domain}.test")
        assert state and state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload_all(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
) -> None:
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_mode"] = "all"
    config[mqtt.DOMAIN][domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_default_availability_list_payload_any(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
) -> None:
    """Test availability by default payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_mode"] = "any"
    config[mqtt.DOMAIN][domain]["availability"] = [
        {"topic": "availability-topic1"},
        {"topic": "availability-topic2"},
    ]
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic2", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic2", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic1", "offline")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)


async def help_test_default_availability_list_single(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
) -> None:
    """Test availability list and availability_topic are mutually exclusive.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability"] = [
        {"topic": "availability-topic1"},
    ]
    config[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic"

    with (
        patch("homeassistant.config.load_yaml_config_file", return_value=config),
        suppress(vol.MultipleInvalid),
    ):
        await mqtt_mock_entry()

    assert (
        "two or more values in the same group of exclusion 'availability'"
        in caplog.text
    )


async def help_test_custom_availability_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    no_assumed_state: bool = False,
    state_topic: str | None = None,
    state_message: str | None = None,
) -> None:
    """Test availability by custom payload with defined topic.

    This is a test helper for the MqttAvailability mixin.
    """
    # Add availability settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic"
    config[mqtt.DOMAIN][domain]["payload_available"] = "good"
    config[mqtt.DOMAIN][domain]["payload_not_available"] = "nogood"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE
    if no_assumed_state:
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    if state_topic is not None and state_message is not None:
        async_fire_mqtt_message(hass, state_topic, state_message)

        state = hass.states.get(f"{domain}.test")
        assert state and state.state == STATE_UNAVAILABLE

        async_fire_mqtt_message(hass, "availability-topic", "good")

        state = hass.states.get(f"{domain}.test")
        assert state and state.state != STATE_UNAVAILABLE


async def help_test_discovery_update_availability(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test update of discovered MQTTAvailability.

    This is a test helper for the MQTTAvailability mixin.
    """
    await mqtt_mock_entry()
    # Add availability settings to config
    config1 = copy.deepcopy(config)
    config1[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic1"
    config2 = copy.deepcopy(config)
    config2[mqtt.DOMAIN][domain]["availability"] = [
        {"topic": "availability-topic2"},
        {"topic": "availability-topic3"},
    ]
    config3 = copy.deepcopy(config)
    config3[mqtt.DOMAIN][domain]["availability_topic"] = "availability-topic4"
    data1 = json.dumps(config1[mqtt.DOMAIN][domain])
    data2 = json.dumps(config2[mqtt.DOMAIN][domain])
    data3 = json.dumps(config3[mqtt.DOMAIN][domain])

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic1", "offline")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    # Change availability_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic1", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic2", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic3", "offline")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    # Change availability_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data3)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic2", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "availability-topic3", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "availability-topic4", "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test the setting of attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")

    assert state and state.attributes.get("val") == "100"


async def help_test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    extra_blocked_attributes: frozenset[str] | None,
) -> None:
    """Test the setting of blocked attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    await mqtt_mock_entry()
    extra_blocked_attribute_list = list(extra_blocked_attributes or [])

    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    val = "abc123"

    for attr in MQTT_ATTRIBUTES_BLOCKED:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state and state.attributes.get(attr) != val

    for attr in extra_blocked_attribute_list:
        async_fire_mqtt_message(hass, "attr-topic", json.dumps({attr: val}))
        state = hass.states.get(f"{domain}.test")
        assert state and state.attributes.get(attr) != val


async def help_test_setting_attribute_with_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test the setting of attribute via MQTT with JSON payload.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    config[mqtt.DOMAIN][domain]["json_attributes_template"] = (
        "{{ value_json['Timer1'] | tojson }}"
    )
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass, "attr-topic", json.dumps({"Timer1": {"Arm": 0, "Time": "22:18"}})
    )
    state = hass.states.get(f"{domain}.test")

    assert state is not None
    assert state.attributes.get("Arm") == 0
    assert state.attributes.get("Time") == "22:18"


async def help_test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
) -> None:
    """Test attributes get extracted from a JSON result.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", '[ "list", "of", "things"]')
    state = hass.states.get(f"{domain}.test")

    assert state and state.attributes.get("val") is None
    assert "JSON result was not a dictionary" in caplog.text


async def help_test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
) -> None:
    """Test JSON validation of attributes.

    This is a test helper for the MqttAttributes mixin.
    """
    # Add JSON attributes settings to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic"
    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "attr-topic", "This is not JSON")

    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") is None
    assert "Erroneous JSON: This is not JSON" in caplog.text


async def help_test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test update of discovered MQTTAttributes.

    This is a test helper for the MqttAttributes mixin.
    """
    await mqtt_mock_entry()
    # Add JSON attributes settings to config
    config1 = copy.deepcopy(config)
    config1[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic1"
    config2 = copy.deepcopy(config)
    config2[mqtt.DOMAIN][domain]["json_attributes_topic"] = "attr-topic2"
    data1 = json.dumps(config1[mqtt.DOMAIN][domain])
    data2 = json.dumps(config2[mqtt.DOMAIN][domain])

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "100" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") == "100"

    # Change json_attributes_topic
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data2)
    await hass.async_block_till_done()

    # Verify we are no longer subscribing to the old topic
    async_fire_mqtt_message(hass, "attr-topic1", '{ "val": "50" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") != "50"

    # Verify we are subscribing to the new topic
    async_fire_mqtt_message(hass, "attr-topic2", '{ "val": "75" }')
    state = hass.states.get(f"{domain}.test")
    assert state and state.attributes.get("val") == "75"


async def help_test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, domain: str
) -> None:
    """Test unique id option only creates one entity per unique_id."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1


async def help_test_discovery_removal(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data: str,
) -> None:
    """Test removal of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    discovery_config1: DiscoveryInfoType,
    discovery_config2: DiscoveryInfoType,
    state_data1: _StateDataType | None = None,
    state_data2: _StateDataType | None = None,
) -> None:
    """Test update of discovered component.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
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
        for mqtt_messages, expected_state, attributes in state_data1:
            for topic, data in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            assert state is not None
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for attr, value in attributes:
                    assert state.attributes.get(attr) == value

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", discovery_data2)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Milk"

    if state_data2:
        for mqtt_messages, expected_state, attributes in state_data2:
            for topic, data in mqtt_messages:
                async_fire_mqtt_message(hass, topic, data)
            state = hass.states.get(f"{domain}.beer")
            assert state is not None
            if expected_state:
                assert state.state == expected_state
            if attributes:
                for attr, value in attributes:
                    assert state.attributes.get(attr) == value

    state = hass.states.get(f"{domain}.milk")
    assert state is None


async def help_test_discovery_update_unchanged(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data1: str,
    discovery_update: MagicMock,
) -> None:
    """Test update of discovered component without changes.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.beer")
    assert state is not None
    assert state.name == "Beer"

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data1)
    await hass.async_block_till_done()

    assert not discovery_update.called


async def help_test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    data1: str,
    data2: str,
) -> None:
    """Test handling of bad discovery message."""
    await mqtt_mock_entry()
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topic: str,
    value: Any,
    attribute: str | None = None,
    attribute_value: Any = None,
    init_payload: tuple[str, str] | None = None,
    skip_raw_test: bool = False,
) -> None:
    """Test handling of incoming encoded payload."""

    async def _test_encoding(
        hass: HomeAssistant,
        entity_id,
        topic,
        encoded_value,
        attribute,
        init_payload_topic,
        init_payload_value,
    ) -> Any:
        state = hass.states.get(entity_id)

        if init_payload_value:
            # Sometimes a device needs to have an initialization pay load, e.g. to switch the device on.
            async_fire_mqtt_message(hass, init_payload_topic, init_payload_value)
            await hass.async_block_till_done()

        state = hass.states.get(entity_id)

        async_fire_mqtt_message(hass, topic, encoded_value)
        await hass.async_block_till_done()

        state = hass.states.get(entity_id)
        assert state is not None

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

    await mqtt_mock_entry()
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item1/config", json.dumps(config1)
    )
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item2/config", json.dumps(config2)
    )
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/item3/config", json.dumps(config3)
    )
    await hass.async_block_till_done()

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

    with suppress(AttributeError, TypeError, ValueError):
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


async def help_test_entity_device_info_with_identifier(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry integration.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.model_id == "XYZ001"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.suggested_area == "default_area"
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_with_connection(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry integration.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_MAC)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.model_id == "XYZ001"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"
    assert device.suggested_area == "default_area"
    assert device.configuration_url == "http://example.com"


async def help_test_entity_device_info_remove(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry remove."""
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    dev_registry = dr.async_get(hass)
    ent_registry = er.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = dev_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    device = dev_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is None
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique")


async def help_test_entity_device_info_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry update.

    This is a test helper for the MqttDiscoveryUpdate mixin.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def help_test_entity_name(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    expected_friendly_name: str | None = None,
    device_class: str | None = None,
) -> None:
    """Test device name setup with and without a device_class set.

    This is a test helper for the _setup_common_attributes_from_config mixin.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"
    expected_entity_name = "test"
    if device_class is not None:
        config["device_class"] = device_class
        # Do not set a name
        config.pop("name")
        expected_entity_name = device_class

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None

    entity_id = f"{domain}.beer_{expected_entity_name}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.name == f"Beer {expected_friendly_name}"


async def help_test_entity_id_update_subscriptions(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topics: list[str] | None = None,
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    # Add unique_id to config
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topics is None:
        # Add default topics to config
        config[mqtt.DOMAIN][domain]["availability_topic"] = "avty-topic"
        config[mqtt.DOMAIN][domain]["state_topic"] = "test-topic"
        topics = ["avty-topic", "test-topic"]
    assert len(topics) > 0
    entity_registry = er.async_get(hass)

    with patch("homeassistant.config.load_yaml_config_file", return_value=config):
        mqtt_mock = await mqtt_mock_entry()
    assert mqtt_mock is not None

    state = hass.states.get(f"{domain}.test")
    assert state is not None
    assert (
        mqtt_mock.async_subscribe.call_count
        == len(topics)
        + 2 * len(SUPPORTED_COMPONENTS)
        + DISCOVERY_COUNT
        + DEVICE_DISCOVERY_COUNT
    )
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(
            topic, ANY, ANY, ANY, HassJobType.Callback
        )
    mqtt_mock.async_subscribe.reset_mock()

    entity_registry.async_update_entity(
        f"{domain}.test", new_entity_id=f"{domain}.milk"
    )
    await hass.async_block_till_done()

    state = hass.states.get(f"{domain}.test")
    assert state is None

    state = hass.states.get(f"{domain}.milk")
    assert state is not None
    for topic in topics:
        mqtt_mock.async_subscribe.assert_any_call(
            topic, ANY, ANY, ANY, HassJobType.Callback
        )


async def help_test_entity_id_update_discovery_update(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    topic: str | None = None,
) -> None:
    """Test MQTT discovery update after entity_id is updated."""
    # Add unique_id to config
    await mqtt_mock_entry()
    config = copy.deepcopy(config)
    config[mqtt.DOMAIN][domain]["unique_id"] = "TOTALLY_UNIQUE"

    if topic is None:
        # Add default topic to config
        config[mqtt.DOMAIN][domain]["availability_topic"] = "avty-topic"
        topic = "avty-topic"

    entity_registry = er.async_get(hass)
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, topic, "online")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, topic, "offline")
    state = hass.states.get(f"{domain}.test")
    assert state and state.state == STATE_UNAVAILABLE

    entity_registry.async_update_entity(
        f"{domain}.test", new_entity_id=f"{domain}.milk"
    )
    await hass.async_block_till_done()

    config[mqtt.DOMAIN][domain]["availability_topic"] = f"{topic}_2"
    data = json.dumps(config[mqtt.DOMAIN][domain])
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids(domain)) == 1

    async_fire_mqtt_message(hass, f"{topic}_2", "online")
    state = hass.states.get(f"{domain}.milk")
    assert state and state.state != STATE_UNAVAILABLE


async def help_test_entity_debug_info(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"
    config["platform"] = "mqtt"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test debug_info message overflow.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]

    with freeze_time(start_dt := dt_util.utcnow()):
        for i in range(debug_info.STORED_MESSAGES + 1):
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    service: str | None,
    command_topic: str | None = None,
    command_payload: str | None = None,
    state_topic: str | object | None = _SENTINEL,
    state_payload: bytes | str | None = None,
    service_parameters: dict[str, Any] | None = None,
) -> None:
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    # Add device settings to config
    await mqtt_mock_entry()
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"

    if command_topic is None:
        # Add default topic to config
        config["command_topic"] = "command-topic"
        command_topic = "command-topic"

    if command_payload is None:
        command_payload = "ON"

    if state_topic is _SENTINEL:
        # Add default topic to config
        config["state_topic"] = "state-topic"
        state_topic = "state-topic"

    if state_payload is None:
        state_payload = "ON"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)

    if state_topic is not None:
        assert len(debug_info_data["entities"][0]["subscriptions"]) >= 1
        assert {"topic": state_topic, "messages": []} in debug_info_data["entities"][0][
            "subscriptions"
        ]

        with freeze_time(start_dt := dt_util.utcnow()):
            async_fire_mqtt_message(hass, str(state_topic), state_payload)

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

    with freeze_time(start_dt := dt_util.utcnow()):
        if service:
            # Trigger an outgoing MQTT message
            if service:
                service_data = {ATTR_ENTITY_ID: f"{domain}.beer_test"}
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
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"
    config["platform"] = "mqtt"

    registry = dr.async_get(hass)

    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(identifiers={("mqtt", "helloworld")})
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
    assert debug_info_data["entities"][0]["entity_id"] == f"{domain}.beer_test"
    entity_id = debug_info_data["entities"][0]["entity_id"]

    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", "")
    await hass.async_block_till_done()

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 0
    assert entity_id not in hass.data["mqtt"].debug_info_entities


async def help_test_entity_debug_info_update_entity_id(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)
    config["unique_id"] = "veryunique"
    config["platform"] = "mqtt"

    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 1
    assert (
        debug_info_data["entities"][0]["discovery_data"]["topic"]
        == f"homeassistant/{domain}/bla/config"
    )
    assert debug_info_data["entities"][0]["discovery_data"]["payload"] == config
    assert debug_info_data["entities"][0]["entity_id"] == f"{domain}.beer_test"
    assert len(debug_info_data["entities"][0]["subscriptions"]) == 1
    assert {"topic": "test-topic", "messages": []} in debug_info_data["entities"][0][
        "subscriptions"
    ]
    assert len(debug_info_data["triggers"]) == 0

    entity_registry.async_update_entity(
        f"{domain}.beer_test", new_entity_id=f"{domain}.milk"
    )
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
    assert f"{domain}.beer_test" not in hass.data["mqtt"].debug_info_entities


async def help_test_entity_disabled_by_default(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry remove."""
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
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
    assert entity_id is not None and hass.states.get(entity_id) is None
    assert dev_registry.async_get_device(identifiers={("mqtt", "helloworld")})

    # Discover an enabled entity, tied to the same device
    config["enabled_by_default"] = True
    config["unique_id"] = "veryunique2"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla2/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique2")
    assert entity_id is not None and hass.states.get(entity_id) is not None

    # Remove the enabled entity, both entities and the device should be removed
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/bla2/config", "")
    await hass.async_block_till_done()
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique1")
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, "veryunique2")
    assert not dev_registry.async_get_device(identifiers={("mqtt", "helloworld")})


async def help_test_entity_category(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
) -> None:
    """Test device registry remove."""
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)

    ent_registry = er.async_get(hass)

    # Discover an entity without entity category
    unique_id = "veryunique1"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    assert entity_id is not None and hass.states.get(entity_id)
    entry = ent_registry.async_get(entity_id)
    assert entry is not None and entry.entity_category is None

    # Discover an entity with entity category set to "diagnostic"
    unique_id = "veryunique2"
    config["entity_category"] = EntityCategory.DIAGNOSTIC
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    assert entity_id is not None and hass.states.get(entity_id)
    entry = ent_registry.async_get(entity_id)
    assert entry is not None and entry.entity_category == EntityCategory.DIAGNOSTIC

    # Discover an entity with entity category set to "no_such_category"
    unique_id = "veryunique3"
    config["entity_category"] = "no_such_category"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    assert not ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)


async def help_test_entity_icon_and_entity_picture(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: ConfigType,
    default_entity_picture: str | None = None,
) -> None:
    """Test entity picture and icon."""
    await mqtt_mock_entry()
    # Add device settings to config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    config["device"] = copy.deepcopy(DEFAULT_CONFIG_DEVICE_INFO_ID)

    ent_registry = er.async_get(hass)

    # Discover an entity without entity icon or picture
    unique_id = "veryunique1"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") is None
    assert state.attributes.get("entity_picture") == default_entity_picture

    # Discover an entity with an entity picture set
    unique_id = "veryunique2"
    config["entity_picture"] = "https://example.com/mypicture.png"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") is None
    assert state.attributes.get("entity_picture") == "https://example.com/mypicture.png"
    config.pop("entity_picture")

    # Discover an entity with an entity icon set
    unique_id = "veryunique3"
    config["icon"] = "mdi:emoji-happy-outline"
    config["unique_id"] = unique_id
    data = json.dumps(config)
    async_fire_mqtt_message(hass, f"homeassistant/{domain}/{unique_id}/config", data)
    await hass.async_block_till_done()
    entity_id = ent_registry.async_get_entity_id(domain, mqtt.DOMAIN, unique_id)
    state = hass.states.get(entity_id)
    assert entity_id is not None and state
    assert state.attributes.get("icon") == "mdi:emoji-happy-outline"
    assert state.attributes.get("entity_picture") == default_entity_picture


async def help_test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    domain: str,
    config: ConfigType,
    service: str,
    topic: str,
    parameters: dict[str, Any] | None,
    payload: str,
    template: str | None,
    tpl_par: str = "value",
    tpl_output: PublishPayloadType = None,
) -> None:
    """Test a service with publishing MQTT payload with different encoding."""
    # prepare config for tests
    test_config: dict[str, dict[str, Any]] = {
        "test1": {"encoding": None, "cmd_tpl": False},
        "test2": {"encoding": "utf-16", "cmd_tpl": False},
        "test3": {"encoding": "", "cmd_tpl": False},
        "test4": {"encoding": "invalid", "cmd_tpl": False},
        "test5": {"encoding": "", "cmd_tpl": True},
    }
    setup_config = []
    service_data = {}
    for test_id, test_data in test_config.items():
        test_config_setup: dict[str, Any] = copy.copy(config[mqtt.DOMAIN][domain])
        test_config_setup.update(
            {
                topic: f"cmd/{test_id}",
                "name": f"{test_id}",
            }
        )
        if test_data["encoding"] is not None:
            test_config_setup["encoding"] = test_data["encoding"]
        if template and test_data["cmd_tpl"]:
            test_config_setup[template] = (
                f"{{{{ (('%.1f'|format({tpl_par}))[0] if is_number({tpl_par}) else {tpl_par}[0]) | ord | pack('b') }}}}"
            )
        setup_config.append(test_config_setup)

        # setup service data
        service_data[test_id] = {ATTR_ENTITY_ID: f"{domain}.{test_id}"}
        if parameters:
            service_data[test_id].update(parameters)

    # setup test entities using discovery
    mqtt_mock = await mqtt_mock_entry()
    for item, component_config in enumerate(setup_config):
        conf = json.dumps(component_config)
        async_fire_mqtt_message(
            hass, f"homeassistant/{domain}/component_{item}/config", conf
        )
    await hass.async_block_till_done()

    # 1) test with default encoding
    await hass.services.async_call(
        domain,
        service,
        service_data["test1"],
        blocking=True,
    )
    await hass.async_block_till_done()

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


async def help_test_reload_with_config(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    config: ConfigType,
) -> None:
    """Test reloading with supplied config."""
    new_yaml_config_file = tmp_path / "configuration.yaml"
    new_yaml_config = yaml.dump(config)
    new_yaml_config_file.write_text(new_yaml_config)
    assert new_yaml_config_file.read_text() == new_yaml_config

    with patch.object(module_hass_config, "YAML_CONFIG_FILE", new_yaml_config_file):
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()


async def help_test_reloadable(
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
    domain: str,
    config: ConfigType,
) -> None:
    """Test reloading an MQTT platform."""
    # Set up with empty config
    config = copy.deepcopy(config[mqtt.DOMAIN][domain])
    # Create and test an old config of 2 entities based on the config supplied
    old_config_1 = copy.deepcopy(config)
    old_config_1["name"] = "test_old_1"
    old_config_2 = copy.deepcopy(config)
    old_config_2["name"] = "test_old_2"

    old_config = {
        mqtt.DOMAIN: {domain: [old_config_1, old_config_2]},
    }
    # Start the MQTT entry with the old config
    entry = MockConfigEntry(domain=mqtt.DOMAIN, data={mqtt.CONF_BROKER: "test-broker"})
    entry.add_to_hass(hass)
    mqtt_client_mock.connect.return_value = 0
    with patch("homeassistant.config.load_yaml_config_file", return_value=old_config):
        await hass.config_entries.async_setup(entry.entry_id)

    assert hass.states.get(f"{domain}.test_old_1")
    assert hass.states.get(f"{domain}.test_old_2")
    assert len(hass.states.async_all(domain)) == 2

    # Create temporary fixture for configuration.yaml based on the supplied config and
    # test a reload with this new config
    new_config_1 = copy.deepcopy(config)
    new_config_1["name"] = "test_new_1"
    new_config_2 = copy.deepcopy(config)
    new_config_2["name"] = "test_new_2"
    new_config_extra = copy.deepcopy(config)
    new_config_extra["name"] = "test_new_3"

    new_config = {
        mqtt.DOMAIN: {domain: [new_config_1, new_config_2, new_config_extra]},
    }
    with patch("homeassistant.config.load_yaml_config_file", return_value=new_config):
        # Reload the mqtt entry with the new config
        await hass.services.async_call(
            "mqtt",
            SERVICE_RELOAD,
            {},
            blocking=True,
        )
        await hass.async_block_till_done()

    assert len(hass.states.async_all(domain)) == 3

    assert hass.states.get(f"{domain}.test_new_1")
    assert hass.states.get(f"{domain}.test_new_2")
    assert hass.states.get(f"{domain}.test_new_3")


async def help_test_unload_config_entry(hass: HomeAssistant) -> None:
    """Test unloading the MQTT config entry."""
    mqtt_config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    assert mqtt_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mqtt_config_entry.entry_id)
    # work-a-round mypy bug https://github.com/python/mypy/issues/9005#issuecomment-1280985006
    updated_config_entry = mqtt_config_entry
    assert updated_config_entry.state is ConfigEntryState.NOT_LOADED
    await hass.async_block_till_done()


async def help_test_unload_config_entry_with_platform(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    domain: str,
    config: dict[str, dict[str, Any]],
) -> None:
    """Test unloading the MQTT config entry with a specific platform domain."""
    # prepare setup through configuration.yaml
    config_setup: dict[str, dict[str, Any]] = copy.deepcopy(config)
    config_setup[mqtt.DOMAIN][domain]["name"] = "config_setup"
    config_name = config_setup

    with patch("homeassistant.config.load_yaml_config_file", return_value=config_name):
        await mqtt_mock_entry()

    # prepare setup through discovery
    discovery_setup = copy.deepcopy(config[mqtt.DOMAIN][domain])
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

    await help_test_unload_config_entry(hass)

    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/bla/config", json.dumps(discovery_setup)
    )
    await hass.async_block_till_done()

    # check if both entities were unloaded correctly
    config_setup_entity = hass.states.get(f"{domain}.{config_name}")
    assert config_setup_entity is None

    discovery_setup_entity = hass.states.get(f"{domain}.discovery_setup")
    assert discovery_setup_entity is None


async def help_test_discovery_setup(
    hass: HomeAssistant, domain: str, discovery_data_payload: str, name: str
) -> None:
    """Test setting up an MQTT entity using discovery."""
    async_fire_mqtt_message(
        hass, f"homeassistant/{domain}/{name}/config", discovery_data_payload
    )
    await hass.async_block_till_done()
    state = hass.states.get(f"{domain}.{name}")
    assert state and state.state is not None


async def help_test_skipped_async_ha_write_state(
    hass: HomeAssistant, topic: str, payload1: str, payload2: str
) -> None:
    """Test entity.async_ha_write_state is only called on changes."""
    with patch(
        "homeassistant.components.mqtt.entity.MqttEntity.async_write_ha_state"
    ) as mock_async_ha_write_state:
        assert len(mock_async_ha_write_state.mock_calls) == 0
        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2

        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2
