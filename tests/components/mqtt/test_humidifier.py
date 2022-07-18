"""Test MQTT humidifiers."""
import copy
from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components import humidifier
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
    help_test_reloadable_late,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_setting_attribute_with_template,
    help_test_setting_blocked_attribute_via_mqtt_json_message,
    help_test_setup_manual_entity_from_yaml,
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message

DEFAULT_CONFIG = {
    humidifier.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "state-topic",
        "command_topic": "command-topic",
        "target_humidity_command_topic": "humidity-command-topic",
    }
}


@pytest.fixture(autouse=True)
def humidifer_platform_only():
    """Only setup the humidifer platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.HUMIDIFIER]):
        yield


async def async_turn_on(
    hass,
    entity_id=ENTITY_MATCH_ALL,
) -> None:
    """Turn all or specified humidifier on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(hass, entity_id=ENTITY_MATCH_ALL) -> None:
    """Turn all or specified humidier off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


async def async_set_mode(hass, entity_id=ENTITY_MATCH_ALL, mode: str = None) -> None:
    """Set mode for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_MODE, mode)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_MODE, data, blocking=True)


async def async_set_humidity(
    hass, entity_id=ENTITY_MATCH_ALL, humidity: int = None
) -> None:
    """Set target humidity for all or specified humidifier."""
    data = {
        key: value
        for key, value in [(ATTR_ENTITY_ID, entity_id), (ATTR_HUMIDITY, humidity)]
        if value is not None
    }

    await hass.services.async_call(DOMAIN, SERVICE_SET_HUMIDITY, data, blocking=True)


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock_entry_no_yaml_config):
    """Test if command fails with command topic."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {humidifier.DOMAIN: {"platform": "mqtt", "name": "test"}},
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()
    assert hass.states.get("humidifier.test") is None


async def test_controlling_state_via_topic(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    assert "Ignoring empty target humidity from" in caplog.text
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
    assert "Ignoring empty mode from" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "state-topic", '{"val": null}')
    state = hass.states.get("humidifier.test")
    assert state.state == STATE_UNKNOWN


async def test_controlling_state_via_topic_and_json_message_shared_topic(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test the controlling state via topic and JSON message using a shared topic."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    assert "Ignoring empty mode from" in caplog.text
    assert "Ignoring empty state from" in caplog.text
    caplog.clear()


async def test_sending_mqtt_commands_and_optimistic(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Testing command templates with optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test optimistic mode with state topic and turn on attributes."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
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
    "topic,value,attribute,attribute_value",
    [
        ("state_topic", "ON", None, "on"),
        (CONF_MODE_STATE_TOPIC, "auto", ATTR_MODE, "auto"),
        (CONF_TARGET_HUMIDITY_STATE_TOPIC, "45", ATTR_HUMIDITY, 45),
    ],
)
async def test_encoding_subscribable_topics(
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    topic,
    value,
    attribute,
    attribute_value,
):
    """Test handling of incoming encoded payload."""
    config = copy.deepcopy(DEFAULT_CONFIG[humidifier.DOMAIN])
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


async def test_attributes(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test attributes."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "mode_command_topic": "mode-command-topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "modes": [
                    "eco",
                    "baby",
                ],
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


async def test_invalid_configurations(hass, mqtt_mock_entry_with_yaml_config, caplog):
    """Test invalid configurations."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test_valid_1",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test_valid_2",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "device_class": "humidifier",
                },
                {
                    "platform": "mqtt",
                    "name": "test_valid_3",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "device_class": "dehumidifier",
                },
                {
                    "platform": "mqtt",
                    "name": "test_invalid_device_class",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "device_class": "notsupporedSpeci@l",
                },
                {
                    "platform": "mqtt",
                    "name": "test_mode_command_without_modes",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test_invalid_humidity_min_max_1",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "min_humidity": 0,
                    "max_humidity": 101,
                },
                {
                    "platform": "mqtt",
                    "name": "test_invalid_humidity_min_max_2",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "max_humidity": 20,
                    "min_humidity": 40,
                },
                {
                    "platform": "mqtt",
                    "name": "test_invalid_mode_is_reset",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": ["eco", "None"],
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()
    assert hass.states.get("humidifier.test_valid_1") is not None
    assert hass.states.get("humidifier.test_valid_2") is not None
    assert hass.states.get("humidifier.test_valid_3") is not None
    assert hass.states.get("humidifier.test_invalid_device_class") is None
    assert hass.states.get("humidifier.test_mode_command_without_modes") is None
    assert "not all values in the same group of inclusion" in caplog.text
    caplog.clear()

    assert hass.states.get("humidifier.test_invalid_humidity_min_max_1") is None
    assert hass.states.get("humidifier.test_invalid_humidity_min_max_2") is None
    assert hass.states.get("humidifier.test_invalid_mode_is_reset") is None


async def test_supported_features(hass, mqtt_mock_entry_with_yaml_config):
    """Test supported features."""
    assert await async_setup_component(
        hass,
        humidifier.DOMAIN,
        {
            humidifier.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test1",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test2",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": ["eco", "auto"],
                },
                {
                    "platform": "mqtt",
                    "name": "test3",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test4",
                    "command_topic": "command-topic",
                    "target_humidity_command_topic": "humidity-command-topic",
                    "mode_command_topic": "mode-command-topic",
                    "modes": ["eco", "auto"],
                },
                {
                    "platform": "mqtt",
                    "name": "test5",
                    "command_topic": "command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test6",
                    "target_humidity_command_topic": "humidity-command-topic",
                },
            ]
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("humidifier.test1")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0

    state = hass.states.get("humidifier.test2")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == humidifier.SUPPORT_MODES

    state = hass.states.get("humidifier.test3")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0

    state = hass.states.get("humidifier.test4")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == humidifier.SUPPORT_MODES

    state = hass.states.get("humidifier.test5")
    assert state is None

    state = hass.states.get("humidifier.test6")
    assert state is None


async def test_availability_when_connection_lost(
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock_entry_with_yaml_config):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
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


async def test_custom_availability_payload(hass, mqtt_mock_entry_with_yaml_config):
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
    hass, mqtt_mock_entry_with_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass, mqtt_mock_entry_no_yaml_config
):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_HUMIDIFIER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(hass, mqtt_mock_entry_with_yaml_config):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_update_with_json_attrs_bad_json(
    hass, mqtt_mock_entry_with_yaml_config, caplog
):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry_no_yaml_config, caplog, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock_entry_with_yaml_config):
    """Test unique_id option only creates one fan per id."""
    config = {
        humidifier.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "target_humidity_command_topic": "humidity-command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, config
    )


async def test_discovery_removal_humidifier(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
    """Test removal of discovered humidifier."""
    data = '{ "name": "test", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, humidifier.DOMAIN, data
    )


async def test_discovery_update_humidifier(
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
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
    hass, mqtt_mock_entry_no_yaml_config, caplog
):
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
async def test_discovery_broken(hass, mqtt_mock_entry_no_yaml_config, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic", "target_humidity_command_topic": "test-topic2" }'
    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, humidifier.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock_entry_with_yaml_config):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, humidifier.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        humidifier.DOMAIN,
        DEFAULT_CONFIG,
        humidifier.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    "service,topic,parameters,payload,template",
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
    hass,
    mqtt_mock_entry_with_yaml_config,
    caplog,
    service,
    topic,
    parameters,
    payload,
    template,
):
    """Test publishing MQTT payload with different encoding."""
    domain = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[domain])
    if topic == "mode_command_topic":
        config["modes"] = ["auto", "eco"]

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


async def test_reloadable(hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path):
    """Test reloading the MQTT platform."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


async def test_reloadable_late(hass, mqtt_client_mock, caplog, tmp_path):
    """Test reloading the MQTT platform with late entry setup."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_reloadable_late(hass, caplog, tmp_path, domain, config)


async def test_setup_manual_entity_from_yaml(hass):
    """Test setup manual configured MQTT entity."""
    platform = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[platform])
    config["name"] = "test"
    del config["platform"]
    await help_test_setup_manual_entity_from_yaml(hass, platform, config)
    assert hass.states.get(f"{platform}.test") is not None


async def test_config_schema_validation(hass):
    """Test invalid platform options in the config schema do pass the config validation."""
    platform = humidifier.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG[platform])
    config["name"] = "test"
    del config["platform"]
    CONFIG_SCHEMA({DOMAIN: {platform: config}})
    CONFIG_SCHEMA({DOMAIN: {platform: [config]}})
    with pytest.raises(MultipleInvalid):
        CONFIG_SCHEMA({"mqtt": {"humidifier": [{"bla": "bla"}]}})


async def test_unload_config_entry(hass, mqtt_mock_entry_with_yaml_config, tmp_path):
    """Test unloading the config entry."""
    domain = humidifier.DOMAIN
    config = DEFAULT_CONFIG[domain]
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
