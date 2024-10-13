"""Test MQTT humidifiers."""

import copy
from typing import Any
from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components import humidifier, mqtt
from homeassistant.components.humidifier import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_HUMIDITY,
    ATTR_MODE,
    SERVICE_SET_HUMIDITY,
    SERVICE_SET_MODE,
    HumidifierAction,
)
from homeassistant.components.mqtt.const import CONF_CURRENT_HUMIDITY_TOPIC
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
)
from homeassistant.core import HomeAssistant

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

from tests.common import async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

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


async def async_turn_on(hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL) -> None:
    """Turn all or specified humidifier on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(
        humidifier.DOMAIN, SERVICE_TURN_ON, data, blocking=True
    )


async def async_turn_off(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Turn all or specified humidier off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(
        humidifier.DOMAIN, SERVICE_TURN_OFF, data, blocking=True
    )


async def async_set_mode(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL, mode: str | None = None
) -> None:
    """Set mode for all or specified humidifier."""
    data = {
        key: value
        for key, value in ((ATTR_ENTITY_ID, entity_id), (ATTR_MODE, mode))
        if value is not None
    }

    await hass.services.async_call(
        humidifier.DOMAIN, SERVICE_SET_MODE, data, blocking=True
    )


async def async_set_humidity(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL, humidity: int | None = None
) -> None:
    """Set target humidity for all or specified humidifier."""
    data = {
        key: value
        for key, value in ((ATTR_ENTITY_ID, entity_id), (ATTR_HUMIDITY, humidity))
        if value is not None
    }

    await hass.services.async_call(
        humidifier.DOMAIN, SERVICE_SET_HUMIDITY, data, blocking=True
    )


@pytest.mark.parametrize(
    "hass_config", [{mqtt.DOMAIN: {humidifier.DOMAIN: {"name": "test"}}}]
)
@pytest.mark.usefixtures("hass")
async def test_fail_setup_if_no_command_topic(
    mqtt_mock_entry: MqttMockHAClientGenerator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test if command fails with command topic."""
    assert await mqtt_mock_entry()
    assert "required key not provided" in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "action_topic": "action-topic",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "current_humidity_topic": "current-humidity-topic",
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
        }
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)
    assert not state.attributes.get(humidifier.ATTR_ACTION)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert not state.attributes.get(humidifier.ATTR_ACTION)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(humidifier.ATTR_ACTION)

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

    async_fire_mqtt_message(hass, "current-humidity-topic", "48")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 48

    async_fire_mqtt_message(hass, "current-humidity-topic", "101")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 48

    async_fire_mqtt_message(hass, "current-humidity-topic", "-1.6")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 48

    async_fire_mqtt_message(hass, "current-humidity-topic", "43.6")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 44

    async_fire_mqtt_message(hass, "current-humidity-topic", "invalid")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 44

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
    assert not state.attributes.get(humidifier.ATTR_ACTION)

    # Turn un the humidifier
    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON
    assert not state.attributes.get(humidifier.ATTR_ACTION)

    async_fire_mqtt_message(hass, "action-topic", HumidifierAction.DRYING.value)
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.DRYING

    async_fire_mqtt_message(hass, "action-topic", HumidifierAction.HUMIDIFYING.value)
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "action-topic", HumidifierAction.HUMIDIFYING.value)
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "action-topic", "invalid_action")
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                humidifier.DOMAIN: {
                    "name": "test",
                    "action_topic": "action-topic",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "current_humidity_topic": "current-humidity-topic",
                    "target_humidity_state_topic": "humidity-state-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_state_topic": "mode-state-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": [
                        "auto",
                        "eco",
                        "baby",
                    ],
                    "current_humidity_template": "{{ value_json.val }}",
                    "action_template": "{{ value_json.val }}",
                    "state_value_template": "{{ value_json.val }}",
                    "target_humidity_state_template": "{{ value_json.val }}",
                    "mode_state_template": "{{ value_json.val }}",
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic_and_json_message(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic and JSON message."""
    await hass.async_block_till_done()
    await mqtt_mock_entry()

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

    async_fire_mqtt_message(hass, "current-humidity-topic", '{"val": 1}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 1

    async_fire_mqtt_message(hass, "current-humidity-topic", '{"val": 100}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) == 100

    async_fire_mqtt_message(hass, "current-humidity-topic", '{"val": "None"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) is None

    async_fire_mqtt_message(hass, "current-humidity-topic", '{"otherval": 100}')
    assert state.attributes.get(humidifier.ATTR_CURRENT_HUMIDITY) is None
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

    # Make sure the humidifier is ON
    async_fire_mqtt_message(hass, "state-topic", '{"val":"ON"}')
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "action-topic", '{"val": "drying"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.DRYING

    async_fire_mqtt_message(hass, "action-topic", '{"val": "humidifying"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "action-topic", '{"val": null}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "action-topic", '{"otherval": "idle"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.HUMIDIFYING

    async_fire_mqtt_message(hass, "action-topic", '{"val": "idle"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.IDLE

    async_fire_mqtt_message(hass, "action-topic", '{"val": "off"}')
    state = hass.states.get("humidifier.test")
    assert state.attributes.get(humidifier.ATTR_ACTION) == HumidifierAction.OFF


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_controlling_state_via_topic_and_json_message_shared_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic and JSON message using a shared topic."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optimistic mode without state topic."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_sending_mqtt_command_templates_(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Testing command templates with optimistic mode without state topic."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_sending_mqtt_commands_and_explicit_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optimistic mode with state topic and turn on attributes."""
    mqtt_mock = await mqtt_mock_entry()

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
        (CONF_CURRENT_HUMIDITY_TOPIC, "39", ATTR_CURRENT_HUMIDITY, 39),
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
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][humidifier.DOMAIN])
    config["modes"] = ["eco", "auto"]
    config[CONF_MODE_COMMAND_TOPIC] = "humidifier/some_mode_command_topic"
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        humidifier.DOMAIN,
        config,
        topic,
        value,
        attribute,
        attribute_value,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
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
        }
    ],
)
async def test_attributes(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test attributes."""
    await mqtt_mock_entry()

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
    ("hass_config", "valid"),
    [
        (  # test valid case 1
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                    }
                }
            },
            True,
        ),
        (  # test valid case 2
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "device_class": "humidifier",
                    }
                }
            },
            True,
        ),
        (  # test valid case 3
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "device_class": "dehumidifier",
                    }
                }
            },
            True,
        ),
        (  # test valid case 4
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "device_class": None,
                    }
                }
            },
            True,
        ),
        (  # test invalid device_class
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "device_class": "notsupporedSpeci@l",
                    }
                }
            },
            False,
        ),
        (  # test mode_command_topic without modes
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "mode_command_topic": "mode-command-topic",
                    }
                }
            },
            False,
        ),
        (  # test invalid humidity min max case 1
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "min_humidity": 0,
                        "max_humidity": 101,
                    }
                }
            },
            False,
        ),
        (  # test invalid humidity min max case 2
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "max_humidity": 20,
                        "min_humidity": 40,
                    }
                }
            },
            False,
        ),
        (  # test invalid mode, is reset payload
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "mode_command_topic": "mode-command-topic",
                        "modes": ["eco", "None"],
                    }
                }
            },
            False,
        ),
    ],
)
async def test_validity_configurations(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, valid: bool
) -> None:
    """Test validity of configurations."""
    await mqtt_mock_entry()
    state = hass.states.get("humidifier.test")
    assert (state is not None) == valid


@pytest.mark.parametrize(
    ("name", "hass_config", "success", "features"),
    [
        (
            "test1",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test1",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                    }
                }
            },
            True,
            0,
        ),
        (
            "test2",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test2",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "mode_command_topic": "mode-command-topic",
                        "modes": ["eco", "auto"],
                    }
                }
            },
            True,
            humidifier.HumidifierEntityFeature.MODES,
        ),
        (
            "test3",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test3",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                    }
                }
            },
            True,
            0,
        ),
        (
            "test4",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test4",
                        "command_topic": "command-topic",
                        "target_humidity_command_topic": "humidity-command-topic",
                        "mode_command_topic": "mode-command-topic",
                        "modes": ["eco", "auto"],
                    }
                }
            },
            True,
            humidifier.HumidifierEntityFeature.MODES,
        ),
        (
            "test5",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test5",
                        "command_topic": "command-topic",
                    }
                }
            },
            False,
            None,
        ),
        (
            "test6",
            {
                mqtt.DOMAIN: {
                    humidifier.DOMAIN: {
                        "name": "test6",
                        "target_humidity_command_topic": "humidity-command-topic",
                    }
                }
            },
            False,
            None,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    name: str,
    success: bool,
    features: humidifier.HumidifierEntityFeature | None,
) -> None:
    """Test supported features."""
    await mqtt_mock_entry()
    state = hass.states.get(f"humidifier.{name}")
    assert (state is not None) == success
    if success:
        assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == features


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, humidifier.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        True,
        "state-topic",
        "1",
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        True,
        "state-topic",
        "1",
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
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
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique_id option only creates one fan per id."""
    await help_test_unique_id(hass, mqtt_mock_entry, humidifier.DOMAIN)


async def test_discovery_removal_humidifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered humidifier."""
    data = '{ "name": "test", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, humidifier.DOMAIN, data)


async def test_discovery_update_humidifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
        hass, mqtt_mock_entry, humidifier.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_humidifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered humidifier."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    with patch(
        "homeassistant.components.mqtt.fan.MqttFan.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, humidifier.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry, humidifier.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
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
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)
    if topic == "mode_command_topic":
        config[mqtt.DOMAIN][domain]["modes"] = ["auto", "eco"]

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
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


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
    platform = humidifier.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_config_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            humidifier.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "action_topic": "action-topic",
                    "target_humidity_state_topic": "target-humidity-state-topic",
                    "current_humidity_topic": "current-humidity-topic",
                    "mode_command_topic": "mode-command-topic",
                    "mode_state_topic": "mode-state-topic",
                    "modes": [
                        "comfort",
                        "eco",
                    ],
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
        ("state-topic", "ON", "OFF"),
        ("action-topic", "idle", "humidifying"),
        ("current-humidity-topic", "31", "32"),
        ("target-humidity-state-topic", "30", "40"),
        ("mode-state-topic", "comfort", "eco"),
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


VALUE_TEMPLATES = {
    "state_value_template": "state_topic",
    "action_template": "action_topic",
    "mode_state_template": "mode_state_topic",
    "current_humidity_template": "current_humidity_topic",
    "target_humidity_state_template": "target_humidity_state_topic",
}


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            humidifier.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "mode_command_topic": "preset-mode-command-topic",
                    "modes": [
                        "auto",
                    ],
                    topic: "test-topic",
                    value_template: "{{ value_json.some_var * 1 }}",
                },
            ),
        )
        for value_template, topic in VALUE_TEMPLATES.items()
    ],
    ids=VALUE_TEMPLATES,
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
