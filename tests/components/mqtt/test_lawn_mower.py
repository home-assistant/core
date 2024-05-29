"""The tests for mqtt lawn_mower component."""

import copy
import json
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import lawn_mower, mqtt
from homeassistant.components.lawn_mower import (
    DOMAIN as LAWN_MOWER_DOMAIN,
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
    LawnMowerEntityFeature,
)
from homeassistant.components.mqtt.lawn_mower import MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED
from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, State

from .test_common import (
    help_custom_config,
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_setup,
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
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

ATTR_ACTIVITY = "activity"

DEFAULT_FEATURES = (
    LawnMowerEntityFeature.START_MOWING
    | LawnMowerEntityFeature.PAUSE
    | LawnMowerEntityFeature.DOCK
)

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        lawn_mower.DOMAIN: {
            "name": "test",
            "dock_command_topic": "dock-test-topic",
            "pause_command_topic": "pause-test-topic",
            "start_mowing_command_topic": "start_mowing-test-topic",
        }
    }
}


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "activity_state_topic": "test/lawn_mower_stat",
                    "dock_command_topic": "dock-test-topic",
                    "pause_command_topic": "pause-test-topic",
                    "start_mowing_command_topic": "start_mowing-test-topic",
                    "name": "Test Lawn Mower",
                }
            }
        }
    ],
)
async def test_run_lawn_mower_setup_and_state_updates(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test that it sets up correctly fetches the given payload."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", "mowing")

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "mowing"

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", "docked")

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "docked"

    # empty payloads are ignored
    async_fire_mqtt_message(hass, "test/lawn_mower_stat", "")

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "docked"


@pytest.mark.parametrize(
    ("hass_config", "expected_features"),
    [
        (
            DEFAULT_CONFIG,
            DEFAULT_FEATURES,
        ),
        (
            {
                mqtt.DOMAIN: {
                    lawn_mower.DOMAIN: {
                        "pause_command_topic": "pause-test-topic",
                        "name": "test",
                    }
                }
            },
            LawnMowerEntityFeature.PAUSE,
        ),
        (
            {
                mqtt.DOMAIN: {
                    lawn_mower.DOMAIN: {
                        "dock_command_topic": "dock-test-topic",
                        "start_mowing_command_topic": "start_mowing-test-topic",
                        "name": "test",
                    }
                }
            },
            LawnMowerEntityFeature.START_MOWING | LawnMowerEntityFeature.DOCK,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    expected_features: LawnMowerEntityFeature | None,
) -> None:
    """Test conditional enablement of supported features."""
    await mqtt_mock_entry()
    assert (
        hass.states.get("lawn_mower.test").attributes["supported_features"]
        == expected_features
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "activity_state_topic": "test/lawn_mower_stat",
                    "name": "Test Lawn Mower",
                    "activity_value_template": "{{ value_json.val }}",
                }
            }
        }
    ],
)
async def test_value_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload with a template."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", '{"val":"mowing"}')

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "mowing"

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", '{"val":"paused"}')

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "paused"

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", '{"val": null}')

    await hass.async_block_till_done()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [DEFAULT_CONFIG],
)
async def test_run_lawn_mower_service_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that service calls work in optimistic mode."""

    fake_state = State("lawn_mower.test", "docked")
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lawn_mower.test")
    assert state.state == "docked"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_START_MOWING,
        {ATTR_ENTITY_ID: "lawn_mower.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "start_mowing-test-topic", "start_mowing", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test")
    assert state.state == "mowing"

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_PAUSE,
        {ATTR_ENTITY_ID: "lawn_mower.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "pause-test-topic", "pause", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test")
    assert state.state == "paused"

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_DOCK,
        {ATTR_ENTITY_ID: "lawn_mower.test"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("dock-test-topic", "dock", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test")
    assert state.state == "docked"


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "pause_command_topic": "test/lawn_mower_pause_cmd",
                    "name": "Test Lawn Mower",
                }
            }
        }
    ],
)
async def test_restore_lawn_mower_from_invalid_state(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that restoring the state skips invalid values."""
    fake_state = State("lawn_mower.test_lawn_mower", "unknown")
    mock_restore_cache(hass, (fake_state,))

    await mqtt_mock_entry()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "name": "Test Lawn Mower",
                    "dock_command_topic": "test/lawn_mower_dock_cmd",
                    "dock_command_template": '{"action": "{{ value }}"}',
                    "pause_command_topic": "test/lawn_mower_pause_cmd",
                    "pause_command_template": '{"action": "{{ value }}"}',
                    "start_mowing_command_topic": "test/lawn_mower_start_mowing_cmd",
                    "start_mowing_command_template": '{"action": "{{ value }}"}',
                }
            }
        }
    ],
)
async def test_run_lawn_mower_service_optimistic_with_command_templates(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that service calls work in optimistic mode and with a command_template."""
    fake_state = State("lawn_mower.test_lawn_mower", "docked")
    mock_restore_cache(hass, (fake_state,))

    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "docked"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_START_MOWING,
        {ATTR_ENTITY_ID: "lawn_mower.test_lawn_mower"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "test/lawn_mower_start_mowing_cmd", '{"action": "start_mowing"}', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "mowing"

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_PAUSE,
        {ATTR_ENTITY_ID: "lawn_mower.test_lawn_mower"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "test/lawn_mower_pause_cmd", '{"action": "pause"}', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "paused"

    await hass.services.async_call(
        lawn_mower.DOMAIN,
        SERVICE_DOCK,
        {ATTR_ENTITY_ID: "lawn_mower.test_lawn_mower"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "test/lawn_mower_dock_cmd", '{"action": "dock"}', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lawn_mower.test_lawn_mower")
    assert state.state == "docked"


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        lawn_mower.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_LAWN_MOWER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry,
        caplog,
        lawn_mower.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry,
        caplog,
        lawn_mower.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry,
        caplog,
        lawn_mower.DOMAIN,
        DEFAULT_CONFIG,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: [
                    {
                        "name": "Test 1",
                        "activity_state_topic": "test-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "activity_state_topic": "test-topic",
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
    """Test unique id action only creates one lawn_mower per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, lawn_mower.DOMAIN)


async def test_discovery_removal_lawn_mower(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered lawn_mower."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][lawn_mower.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry, caplog, lawn_mower.DOMAIN, data
    )


async def test_discovery_update_lawn_mower(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered lawn_mower."""
    config1 = {
        "name": "Beer",
        "activity_state_topic": "test-topic",
        "command_topic": "test-topic",
        "actions": ["milk", "beer"],
    }
    config2 = {
        "name": "Milk",
        "activity_state_topic": "test-topic",
        "command_topic": "test-topic",
        "actions": ["milk"],
    }

    await help_test_discovery_update(
        hass, mqtt_mock_entry, caplog, lawn_mower.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_lawn_mower(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered lawn_mower."""
    data1 = '{ "name": "Beer", "activity_state_topic": "test-topic", "command_topic": "test-topic", "actions": ["milk", "beer"]}'
    with patch(
        "homeassistant.components.mqtt.lawn_mower.MqttLawnMower.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            caplog,
            lawn_mower.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "invalid" }'
    data2 = '{ "name": "Milk", "activity_state_topic": "test-topic", "pause_command_topic": "test-topic"}'

    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, lawn_mower.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT lawn_mower device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT lawn_mower device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        mqtt.DOMAIN: {
            lawn_mower.DOMAIN: {
                "name": "test",
                "activity_state_topic": "test-topic",
                "availability_topic": "avty-topic",
            }
        }
    }
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, config, ["avty-topic", "test-topic"]
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, lawn_mower.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    ("service", "command_payload", "state_payload", "state_topic", "command_topic"),
    [
        (
            SERVICE_START_MOWING,
            "start_mowing",
            "mowing",
            "test/lawn_mower_stat",
            "start_mowing-test-topic",
        ),
        (
            SERVICE_PAUSE,
            "pause",
            "paused",
            "test/lawn_mower_stat",
            "pause-test-topic",
        ),
        (
            SERVICE_DOCK,
            "dock",
            "docked",
            "test/lawn_mower_stat",
            "dock-test-topic",
        ),
    ],
)
async def test_entity_debug_info_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    service: str,
    command_payload: str,
    state_payload: str,
    state_topic: str,
    command_topic: str,
) -> None:
    """Test MQTT debug info."""
    config = {
        mqtt.DOMAIN: {
            lawn_mower.DOMAIN: {
                "activity_state_topic": "test/lawn_mower_stat",
                "dock_command_topic": "dock-test-topic",
                "pause_command_topic": "pause-test-topic",
                "start_mowing_command_topic": "start_mowing-test-topic",
                "name": "test",
            }
        }
    }
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        lawn_mower.DOMAIN,
        config,
        service=service,
        command_payload=command_payload,
        state_payload=state_payload,
        state_topic=state_topic,
        command_topic=command_topic,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "dock_command_topic": "dock-test-topic",
                    "pause_command_topic": "pause-test-topic",
                    "start_mowing_command_topic": "start_mowing-test-topic",
                    "activity_state_topic": "test/lawn_mower_stat",
                    "name": "Test Lawn Mower",
                }
            }
        }
    ],
)
async def test_mqtt_payload_not_a_valid_activity_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test warning for MQTT payload which is not a valid activity."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test/lawn_mower_stat", "painting")

    await hass.async_block_till_done()

    assert (
        "Invalid activity for lawn_mower.test_lawn_mower: 'painting' "
        "(valid activities: ['error', 'paused', 'mowing', 'docked'])" in caplog.text
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            SERVICE_START_MOWING,
            "start_mowing_command_topic",
            {},
            "start_mowing",
            "start_mowing_command_template",
        ),
        (
            SERVICE_PAUSE,
            "pause_command_topic",
            {},
            "pause",
            "pause_command_template",
        ),
        (
            SERVICE_DOCK,
            "dock_command_topic",
            {},
            "dock",
            "dock_command_template",
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
    domain = lawn_mower.DOMAIN
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
    hass: HomeAssistant,
    mqtt_client_mock: MqttMockPahoClient,
) -> None:
    """Test reloading the MQTT platform."""
    domain = lawn_mower.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("activity_state_topic", "paused", None, "paused"),
        ("activity_state_topic", "docked", None, "docked"),
        ("activity_state_topic", "mowing", None, "mowing"),
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
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][lawn_mower.DOMAIN])
    config["actions"] = ["milk", "beer"]
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        lawn_mower.DOMAIN,
        config,
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
    platform = lawn_mower.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = lawn_mower.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


async def test_persistent_state_after_reconfig(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test of the state is persistent after reconfiguring the lawn_mower activity."""
    await mqtt_mock_entry()
    discovery_data = '{ "name": "Garden", "activity_state_topic": "test-topic", "command_topic": "test-topic"}'
    await help_test_discovery_setup(hass, LAWN_MOWER_DOMAIN, discovery_data, "garden")

    # assign an initial state
    async_fire_mqtt_message(hass, "test-topic", "docked")
    state = hass.states.get("lawn_mower.garden")
    assert state.state == "docked"

    # change the config
    discovery_data = '{ "name": "Garden", "activity_state_topic": "test-topic2", "command_topic": "test-topic"}'
    await help_test_discovery_setup(hass, LAWN_MOWER_DOMAIN, discovery_data, "garden")

    # assert the state persistent
    state = hass.states.get("lawn_mower.garden")
    assert state.state == "docked"


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            lawn_mower.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "activity_state_topic": "activity-state-topic",
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
        ("activity-state-topic", "mowing", "paused"),
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
        {
            mqtt.DOMAIN: {
                lawn_mower.DOMAIN: {
                    "name": "test",
                    "activity_state_topic": "test-topic",
                    "activity_value_template": "{{ value_json.some_var * 1 }}",
                }
            }
        }
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
