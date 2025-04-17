"""The tests for the MQTT lock platform."""

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import lock, mqtt
from homeassistant.components.lock import (
    SERVICE_LOCK,
    SERVICE_OPEN,
    SERVICE_UNLOCK,
    LockEntityFeature,
    LockState,
)
from homeassistant.components.mqtt.lock import MQTT_LOCK_ATTRIBUTES_BLOCKED
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_CODE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant

from .common import (
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

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {lock.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}

CONFIG_WITH_STATES = {
    mqtt.DOMAIN: {
        lock.DOMAIN: {
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "payload_lock": "LOCK",
            "payload_unlock": "UNLOCK",
            "state_locked": "closed",
            "state_locking": "closing",
            "state_open": "open",
            "state_opening": "opening",
            "state_unlocked": "unlocked",
            "state_unlocking": "unlocking",
        }
    }
}


@pytest.mark.parametrize(
    ("hass_config", "payload", "lock_state"),
    [
        (CONFIG_WITH_STATES, "closed", LockState.LOCKED),
        (CONFIG_WITH_STATES, "closing", LockState.LOCKING),
        (CONFIG_WITH_STATES, "open", LockState.OPEN),
        (CONFIG_WITH_STATES, "opening", LockState.OPENING),
        (CONFIG_WITH_STATES, "unlocked", LockState.UNLOCKED),
        (CONFIG_WITH_STATES, "unlocking", LockState.UNLOCKING),
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    payload: str,
    lock_state: str,
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state is STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    assert not state.attributes.get(ATTR_SUPPORTED_FEATURES)

    async_fire_mqtt_message(hass, "state-topic", payload)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == lock_state


@pytest.mark.parametrize(
    ("hass_config", "payload", "lock_state"),
    [
        (CONFIG_WITH_STATES, "closed", LockState.LOCKED),
        (CONFIG_WITH_STATES, "closing", LockState.LOCKING),
        (CONFIG_WITH_STATES, "open", LockState.OPEN),
        (CONFIG_WITH_STATES, "opening", LockState.OPENING),
        (CONFIG_WITH_STATES, "unlocked", LockState.UNLOCKED),
        (CONFIG_WITH_STATES, "unlocking", LockState.UNLOCKING),
        (CONFIG_WITH_STATES, "None", STATE_UNKNOWN),
    ],
)
async def test_controlling_non_default_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    payload: str,
    lock_state: str,
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state is STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", payload)

    state = hass.states.get("lock.test")
    assert state.state == lock_state

    # Empty state is ignored
    async_fire_mqtt_message(hass, "state-topic", "")

    state = hass.states.get("lock.test")
    assert state.state == lock_state


@pytest.mark.parametrize(
    ("hass_config", "payload", "lock_state"),
    [
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"closed"}',
            LockState.LOCKED,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"closing"}',
            LockState.LOCKING,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"unlocking"}',
            LockState.UNLOCKING,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"open"}',
            LockState.OPEN,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"opening"}',
            LockState.OPENING,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"unlocked"}',
            LockState.UNLOCKED,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":null}',
            STATE_UNKNOWN,
        ),
    ],
)
async def test_controlling_state_via_topic_and_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    payload: str,
    lock_state: str,
) -> None:
    """Test the controlling state via topic and JSON message."""
    await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state is STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", payload)

    state = hass.states.get("lock.test")
    assert state.state == lock_state


@pytest.mark.parametrize(
    ("hass_config", "payload", "lock_state"),
    [
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"closed"}',
            LockState.LOCKED,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"closing"}',
            LockState.LOCKING,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"open"}',
            LockState.OPEN,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"opening"}',
            LockState.OPENING,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"unlocked"}',
            LockState.UNLOCKED,
        ),
        (
            help_custom_config(
                lock.DOMAIN,
                CONFIG_WITH_STATES,
                ({"value_template": "{{ value_json.val }}"},),
            ),
            '{"val":"unlocking"}',
            LockState.UNLOCKING,
        ),
    ],
)
async def test_controlling_non_default_state_via_topic_and_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    payload: str,
    lock_state: str,
) -> None:
    """Test the controlling state via topic and JSON message."""
    await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state is STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", payload)

    state = hass.states.get("lock.test")
    assert state.state == lock_state


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "state_locked": "LOCKED",
                    "state_unlocked": "UNLOCKED",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test optimistic mode without state topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "UNLOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "code_format": "^\\d{4}$",
                    "command_topic": "command-topic",
                    "command_template": '{ "{{ value }}": "{{ code }}" }',
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "payload_open": "OPEN",
                    "state_locked": "LOCKED",
                    "state_unlocked": "UNLOCKED",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test sending commands with template."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN,
        SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.test", ATTR_CODE: "1234"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{ "LOCK": "1234" }', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN,
        SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.test", ATTR_CODE: "1234"},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{ "UNLOCK": "1234" }', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "state_locked": "LOCKED",
                    "state_unlocked": "UNLOCKED",
                    "optimistic": True,
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_explicit_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test optimistic mode without state topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "UNLOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "payload_open": "OPEN",
                    "state_locked": "LOCKED",
                    "state_unlocked": "UNLOCKED",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_support_open_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test open function of the lock without state topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == LockEntityFeature.OPEN

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "UNLOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.OPEN
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "payload_open": "OPEN",
                    "state_locked": "LOCKED",
                    "state_unlocked": "UNLOCKED",
                    "optimistic": True,
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_support_open_and_explicit_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test open function of the lock without state topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == LockEntityFeature.OPEN

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "UNLOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("lock.test")
    assert state.state == LockState.OPEN
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "state_topic": "state-topic",
                    "payload_lock": "LOCK",
                    "payload_unlock": "UNLOCK",
                    "payload_open": "OPEN",
                    "state_locked": "LOCKED",
                    "state_locking": "LOCKING",
                    "state_unlocked": "UNLOCKED",
                    "state_unlocking": "UNLOCKING",
                    "state_jammed": "JAMMED",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_pessimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test function of the lock with state topics."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("lock.test")
    assert state.state is STATE_UNKNOWN
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == LockEntityFeature.OPEN

    # send lock command to lock
    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # receive state from lock
    async_fire_mqtt_message(hass, "state-topic", "LOCKED")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "UNLOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # receive state from lock
    async_fire_mqtt_message(hass, "state-topic", "UNLOCKED")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN, SERVICE_OPEN, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OPEN", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # receive state from lock
    async_fire_mqtt_message(hass, "state-topic", "UNLOCKED")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.UNLOCKED

    # send lock command to lock
    await hass.services.async_call(
        lock.DOMAIN, SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.test"}, blocking=True
    )

    # Go to locking state
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "LOCK", 0, False)
    mqtt_mock.async_publish.reset_mock()

    # receive locking state from lock
    async_fire_mqtt_message(hass, "state-topic", "LOCKING")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKING

    # receive jammed state from lock
    async_fire_mqtt_message(hass, "state-topic", "JAMMED")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.JAMMED

    # receive solved state from lock
    async_fire_mqtt_message(hass, "state-topic", "LOCKED")
    await hass.async_block_till_done()

    state = hass.states.get("lock.test")
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, lock.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG, MQTT_LOCK_ATTRIBUTES_BLOCKED
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                lock.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "command_topic": "test_topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "command_topic": "test_topic",
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
    """Test unique id option only creates one lock per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, lock.DOMAIN)


async def test_discovery_removal_lock(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered lock."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, lock.DOMAIN, data)


async def test_discovery_update_lock(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered lock."""
    config1 = {
        "name": "Beer",
        "state_topic": "test_topic",
        "command_topic": "command_topic",
        "availability_topic": "availability_topic1",
    }
    config2 = {
        "name": "Milk",
        "state_topic": "test_topic2",
        "command_topic": "command_topic",
        "availability_topic": "availability_topic2",
    }
    await help_test_discovery_update(
        hass, mqtt_mock_entry, lock.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_lock(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered lock."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "command_topic" }'
    )
    with patch(
        "homeassistant.components.mqtt.lock.MqttLock.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, lock.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(hass, mqtt_mock_entry, lock.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT lock device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT lock device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, lock.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        lock.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_LOCK,
        command_payload="LOCK",
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            SERVICE_LOCK,
            "command_topic",
            None,
            "LOCK",
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
    domain = lock.DOMAIN
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
    domain = lock.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "LOCKED", None, "locked"),
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
        lock.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][lock.DOMAIN],
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
    platform = lock.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = lock.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            lock.DOMAIN,
            CONFIG_WITH_STATES,
            (
                {
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
        ("availability-topic", "online", "offline"),
        ("json-attributes-topic", '{"attr1": "val1"}', '{"attr1": "val2"}'),
        ("state-topic", "closed", "open"),
        ("state-topic", "closed", "opening"),
        ("state-topic", "open", "closing"),
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
            lock.DOMAIN,
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
