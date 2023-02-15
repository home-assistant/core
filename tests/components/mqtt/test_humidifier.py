"""Test MQTT humidifiers."""
import copy
from pathlib import Path
from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components import humidifier, mqtt
from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    ATTR_MODE,
    DOMAIN,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
)
from homeassistant.components.mqtt import CONFIG_SCHEMA
from homeassistant.components.mqtt.humidifier import (
    CONF_MODE_COMMAND_TOPIC,
    CONF_MODE_STATE_TOPIC,
    CONF_TARGET_HUMIDITY_STATE_TOPIC,
    MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
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
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        humidifier.DOMAIN: {
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
            "target_humidity_command_topic": "humidity-command-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def humidifer_platform_only():
    """Only setup the humidifer platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.HUMIDIFIER]):
        yield


async def async_turn_on(
    hass: HomeAssistant,
    entity_id=ENTITY_MATCH_ALL,
) -> None:
    """Turn all or specified humidifier on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified humidier off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_mode(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, mode: str = None
) -> None:
    """Set mode for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_MODE, mode)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_MODE, data, blocking=True)


async def async_set_humidity(
    hass: HomeAssistant, entity_id=ENTITY_MATCH_ALL, humidity: int = None
) -> None:
    """Set target humidity for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_HUMIDITY, humidity)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_HUMIDITY, data, blocking=True)


async def test_fail_setup_if_no_command_topic(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if command fails with command topic."""
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {mqtt.DOMAIN: {humidifier.DOMAIN: {"name": "test"}}},
    )
    assert (
        "Invalid config for [mqtt]: required key not provided @ data['mqtt']['humidifier'][0]['command_topic']. Got None"
        in caplog.text
    )


async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_off": "StAtE_OfF",
                    "payload_on": "StAtE_On",
                    "target_humidity_state_topic": "humidity-state-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_state_topic": "mode-state-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": [
                        "auto",
                        "comfort",
                        "home",
                        "eco",
                        "sleep",
                        "baby",
                    ],
                    "payload_reset_humidity": "rEset_humidity",
                    "payload_reset_mode": "rEset_mode",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "humidity-state-topic", "0")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 0

    async_fire_mqtt_message(hass, "humidity-state-topic", "25")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 25

    async_fire_mqtt_message(hass, "humidity-state-topic", "50")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 50

    async_fire_mqtt_message(hass, "humidity-state-topic", "100")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 100

    async_fire_mqtt_message(hass, "humidity-state-topic", "101")
    assert "not a valid target humidity" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "humidity-state-topic", "invalid")
    assert "not a valid target humidity" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "mode-state-topic", "low")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "mode-state-topic", "auto")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"

    async_fire_mqtt_message(hass, "mode-state-topic", "eco")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "eco"

    async_fire_mqtt_message(hass, "mode-state-topic", "baby")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "baby"

    async_fire_mqtt_message(hass, "mode-state-topic", "ModeUnknown")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "mode-state-topic", "rEset_mode")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) is None

    async_fire_mqtt_message(hass, "humidity-state-topic", "rEset_humidity")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) is None

    async_fire_mqtt_message(hass, "state-topic", "None")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN


async def test_controlling_state_via_topic_and_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "target_humidity_state_topic": "humidity-state-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_state_topic": "mode-state-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": [
                        "auto",
                        "eco",
                        "baby",
                    ],
                    "state_value_template": "{{ value_json.val }}",
                    "target_humidity_state_template": "{{ value_json.val }}",
                    "mode_state_template": "{{ value_json.val }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", '{"val":"ON"}')
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"OFF"}')
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "humidity-state-topic", '{"val": 1}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 1

    async_fire_mqtt_message(hass, "humidity-state-topic", '{"val": 100}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 100

    async_fire_mqtt_message(hass, "humidity-state-topic", '{"val": "None"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) is None

    async_fire_mqtt_message(hass, "humidity-state-topic", '{"otherval": 100}')
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) is None
    caplog.clear()

    async_fire_mqtt_message(hass, "mode-state-topic", '{"val": "low"}')
    assert "not a valid mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "mode-state-topic", '{"val": "auto"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"

    async_fire_mqtt_message(hass, "mode-state-topic", '{"val": "eco"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "eco"

    async_fire_mqtt_message(hass, "mode-state-topic", '{"val": "baby"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "baby"

    async_fire_mqtt_message(hass, "mode-state-topic", '{"val": "None"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) is None

    async_fire_mqtt_message(hass, "mode-state-topic", '{"otherval": 100}')
    assert state.attributes.get(humidifier.ATTR_MODE) is None
    caplog.clear()

    async_fire_mqtt_message(hass, "state-topic", '{"val": null}')
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN


async def test_controlling_state_via_topic_and_json_message_shared_topic(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic and JSON message using a shared topic."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "state_topic": "shared-state-topic",
                    "command_topic": "command-topic",
                    "target_humidity_state_topic": "shared-state-topic",
                    "target_humidity_command_topic": "percentage-command-topic",
                    "mode_state_topic": "shared-state-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": [
                        "auto",
                        "eco",
                        "baby",
                    ],
                    "state_value_template": "{{ value_json.state }}",
                    "target_humidity_state_template": "{{ value_json.humidity }}",
                    "mode_state_template": "{{ value_json.mode }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        '{"state":"ON","mode":"eco","humidity": 50}',
    )
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 50
    assert state.attributes.get(humidifier.ATTR_MODE) == "eco"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        '{"state":"ON","mode":"auto","humidity": 10}',
    )
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 10
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        '{"state":"OFF","mode":"auto","humidity": 0}',
    )
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 0
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        '{"humidity": 100}',
    )
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 100
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"
    caplog.clear()


async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_off": "StAtE_OfF",
                    "payload_on": "StAtE_On",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": [
                        "eco",
                        "auto",
                        "baby",
                    ],
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_On", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_off(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await async_set_humidity(hass, "humidifier.test", -1)

    with pytest.raises(MultipleInvalid):
        await async_set_humidity(hass, "humidifier.test", 101)

    await async_set_humidity(hass, "humidifier.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 0
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "low")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    await async_set_mode(hass, "humidifier.test", "auto")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "auto", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "eco")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "eco", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "eco"
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_mqtt_command_templates_(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Testing command templates with optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "command_template": "state: {{ value }}",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "target_humidity_command_template": "humidity: {{ value }}",
                    "mode_command_topic": "mode-command-topic",
                    "mode_command_template": "mode: {{ value }}",
                    "modes": [
                        "auto",
                        "eco",
                        "sleep",
                    ],
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "state: ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_off(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "state: OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await async_set_humidity(hass, "humidifier.test", -1)

    with pytest.raises(MultipleInvalid):
        await async_set_humidity(hass, "humidifier.test", 101)

    await async_set_humidity(hass, "humidifier.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "humidity: 100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "humidity: 0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) == 0
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "low")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    await async_set_mode(hass, "humidifier.test", "eco")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "mode: eco", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "eco"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "auto")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "mode: auto", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_MODE) == "auto"
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_mqtt_commands_and_explicit_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optimistic mode with state topic and turn on attributes."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "target_humidity_state_topic": "humidity-state-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "mode_state_topic": "mode-state-topic",
                    "modes": [
                        "auto",
                        "eco",
                        "baby",
                    ],
                    "optimistic": True,
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_off(hass, "humidifier.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 33)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "33", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 50)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "50", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_humidity(hass, "humidifier.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "humidity-command-topic", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await async_set_humidity(hass, "humidifier.test", 101)

    await async_set_mode(hass, "humidifier.test", "low")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    await async_set_mode(hass, "humidifier.test", "eco")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "eco", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "baby")
    mqtt_mock.async_publish.assert_called_once_with(
        "mode-command-topic", "baby", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_mode(hass, "humidifier.test", "freaking-high")
    assert "not a valid mode" in caplog.text
    caplog.clear()

    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "ON", None, "on"),
        (CONF_MODE_STATE_TOPIC, "auto", ATTR_MODE, "auto"),
        (CONF_TARGET_HUMIDITY_STATE_TOPIC, "45", ATTR_HUMIDITY, 45),
    ],
)
async def test_encoding_subscribable_topics(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    topic,
    value,
    attribute,
    attribute_value,
) -> None:
    """Test handling of incoming encoded payload."""
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][humidifier.DOMAIN])
    config["modes"] = ["eco", "auto"]
    config[CONF_MODE_COMMAND_TOPIC] = "humidifier/some_mode_command_topic"
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        humidifier.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
    )


async def test_attributes(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes."""
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "modes": [
                        "eco",
                        "baby",
                    ],
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(humidifier.ATTR_AVAILABLE_MODES) == [
        "eco",
        "baby",
    ]
    assert state.attributes.get(humidifier.ATTR_MIN_HUMIDITY) == 0
    assert state.attributes.get(humidifier.ATTR_MAX_HUMIDITY) == 100

    await async_turn_on(hass, "humidifier.test")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) is None
    assert state.attributes.get(humidifier.ATTR_MODE) is None

    await async_turn_off(hass, "humidifier.test")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(humidifier.ATTR_HUMIDITY) is None
    assert state.attributes.get(humidifier.ATTR_MODE) is None


@pytest.mark.parametrize(
    ("config", "valid"),
    [
        (
            {
                "name": "test_valid_1",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
            },
            True,
        ),
        (
            {
                "name": "test_valid_2",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "device_class": "humidifier",
            },
            True,
        ),
        (
            {
                "name": "test_valid_3",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "device_class": "dehumidifier",
            },
            True,
        ),
        (
            {
                "name": "test_invalid_device_class",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "device_class": "notsupporedSpeci@l",
            },
            False,
        ),
        (
            {
                "name": "test_mode_command_without_modes",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "mode_command_topic": "mode-command-topic",
            },
            False,
        ),
        (
            {
                "name": "test_invalid_humidity_min_max_1",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "min_humidity": 0,
                "max_humidity": 101,
            },
            False,
        ),
        (
            {
                "name": "test_invalid_humidity_min_max_2",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "max_humidity": 20,
                "min_humidity": 40,
            },
            False,
        ),
        (
            {
                "name": "test_invalid_mode_is_reset",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "mode_command_topic": "mode-command-topic",
                "modes": ["eco", "None"],
            },
            False,
        ),
    ],
)
async def test_validity_configurations(hass: HomeAssistant, config, valid) -> None:
    """Test validity of configurations."""
    assert (
        await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {mqtt.DOMAIN: {humidifier.DOMAIN: config}},
        )
        is valid
    )


@pytest.mark.parametrize(
    ("name", "config", "success", "features"),
    [
        (
            "test1",
            {
                "name": "test1",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
            },
            True,
            0,
        ),
        (
            "test2",
            {
                "name": "test2",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "mode_command_topic": "mode-command-topic",
                "modes": ["eco", "auto"],
            },
            True,
            humidifier.SUPPORT_MODES,
        ),
        (
            "test3",
            {
                "name": "test3",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
            },
            True,
            0,
        ),
        (
            "test4",
            {
                "name": "test4",
                "command_topic": "command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "mode_command_topic": "mode-command-topic",
                "modes": ["eco", "auto"],
            },
            True,
            humidifier.SUPPORT_MODES,
        ),
        (
            "test5",
            {
                "name": "test5",
                "command_topic": "command-topic",
            },
            False,
            None,
        ),
        (
            "test6",
            {
                "name": "test6",
                "target_humidity_command_topic": "humidity-command-topic",
            },
            False,
            None,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    name,
    config,
    success,
    features,
) -> None:
    """Test supported features."""
    assert (
        await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {mqtt.DOMAIN: {humidifier.DOMAIN: config}},
        )
        is success
    )
    if success:
        await hass.async_block_till_done()
        await mqtt_mock_entry_with_yaml_config()

        state = hass.states.get(f"humidifier.{name}")
        assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == features


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry_with_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        True,
        "state-topic",
        "1",
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry_with_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        True,
        "state-topic",
        "1",
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique_id option only creates one fan per id."""
    config = {
        mqtt.DOMAIN: {
            humidifier.DOMAIN: [
                {
                    "name": "Test 1",
                    "state_topic": "test-topic",
                    "command_topic": "test_topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
                {
                    "name": "Test 2",
                    "state_topic": "test-topic",
                    "command_topic": "test_topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
            ]
        }
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, config
    )


async def test_discovery_removal_humidifier(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered humidifier."""
    data = '{ "name": "test", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, humidifier.DOMAIN, data
    )


async def test_discovery_update_humidifier(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered humidifier."""
    config1 = {
        "name": "Beer",
        "command_topic": "test_topic",
        "target_humidity_command_topic": "test-topic2",
    }
    config2 = {
        "name": "Milk",
        "command_topic": "test_topic",
        "target_humidity_command_topic": "test-topic2",
    }
    await help_test_discovery_update(
        hass,
        mqtt_mock_entry_no_yaml_config,
        caplog,
        humidifier.DOMAIN,
        config1,
        config2,
    )


async def test_discovery_update_unchanged_humidifier(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered humidifier."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    with patch(
        "homeassistant.components.mqtt.fan.MqttFan.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            humidifier.DOMAIN,
            data1,
            discovery_update,
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, humidifier.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        humidifier.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            humidifier.SERVICE_TURN_ON,
            "command_topic",
            None,
            "ON",
            None,
        ),
        (
            humidifier.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "OFF",
            None,
        ),
        (
            humidifier.SERVICE_SET_MODE,
            "mode_command_topic",
            {humidifier.ATTR_MODE: "eco"},
            "eco",
            "mode_command_template",
        ),
        (
            humidifier.SERVICE_SET_HUMIDITY,
            "target_humidity_command_topic",
            {humidifier.ATTR_HUMIDITY: "45"},
            45,
            "target_humidity_command_template",
        ),
    ],
)
async def test_publishing_with_custom_encoding(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service,
    topic,
    parameters,
    payload,
    template,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)
    if topic == "mode_command_topic":
        config[mqtt.DOMAIN][domain]["modes"] = ["auto", "eco"]

    await help_test_publishing_with_custom_encoding(
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
    )


async def test_reloadable(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
) -> None:
    """Test reloading the MQTT platform."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = humidifier.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")


async def test_config_schema_validation(hass: HomeAssistant) -> None:
    """Test invalid platform options in the config schema do not pass the config validation."""
    platform = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][platform])
    config["name"] = "test"
    CONFIG_SCHEMA({mqtt.DOMAIN: {platform: config}})
    CONFIG_SCHEMA({mqtt.DOMAIN: {platform: [config]}})
    with pytest.raises(MultipleInvalid):
        CONFIG_SCHEMA({mqtt.DOMAIN: {platform: [{"bla": "bla"}]}})


async def test_unload_config_entry(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    tmp_path: Path,
) -> None:
    """Test unloading the config entry."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
