"""Test MQTT fans."""
from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components import fan
from homeassistant.components.fan import NotValidPresetModeError
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
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

from tests.common import async_fire_mqtt_message
from tests.components.fan import common

DEFAULT_CONFIG = {
    fan.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "state-topic",
        "command_topic": "command-topic",
    }
}


async def test_fail_setup_if_no_command_topic(hass, mqtt_mock):
    """Test if command fails with command topic."""
    assert await async_setup_component(
        hass, fan.DOMAIN, {fan.DOMAIN: {"platform": "mqtt", "name": "test"}}
    )
    await hass.async_block_till_done()
    assert hass.states.get("fan.test") is None


async def test_controlling_state_via_topic(hass, mqtt_mock, caplog):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_off": "StAtE_OfF",
                "payload_on": "StAtE_On",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "payload_oscillation_off": "OsC_OfF",
                "payload_oscillation_on": "OsC_On",
                "percentage_state_topic": "percentage-state-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_mode_state_topic": "preset-mode-state-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_modes": [
                    "auto",
                    "smart",
                    "whoosh",
                    "eco",
                    "breeze",
                    "silent",
                ],
                "speed_range_min": 1,
                "speed_range_max": 200,
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speeds": ["off", "low"],
                "payload_off_speed": "speed_OfF",
                "payload_low_speed": "speed_lOw",
                "payload_medium_speed": "speed_mEdium",
                "payload_high_speed": "speed_High",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "oscillation-state-topic", "OsC_On")
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    async_fire_mqtt_message(hass, "oscillation-state-topic", "OsC_OfF")
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False

    assert state.attributes.get("percentage_step") == 1.0

    async_fire_mqtt_message(hass, "percentage-state-topic", "0")
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0

    async_fire_mqtt_message(hass, "percentage-state-topic", "50")
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 25

    async_fire_mqtt_message(hass, "percentage-state-topic", "100")
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 50

    async_fire_mqtt_message(hass, "percentage-state-topic", "200")
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100

    async_fire_mqtt_message(hass, "percentage-state-topic", "202")
    assert "not a valid speed within the speed range" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "percentage-state-topic", "invalid")
    assert "not a valid speed within the speed range" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "auto")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "auto"

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "eco")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "eco"

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "silent")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "silent"

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "ModeUnknown")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_lOw")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_LOW

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_mEdium")
    assert "not a valid speed" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_High")
    assert "not a valid speed" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_OfF")
    state = hass.states.get("fan.test")
    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "speed-state-topic", "speed_very_high")
    assert "not a valid speed" in caplog.text
    caplog.clear()


async def test_controlling_state_via_topic_with_different_speed_range(
    hass, mqtt_mock, caplog
):
    """Test the controlling state via topic using an alternate speed range."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test1",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic1",
                    "percentage_command_topic": "percentage-command-topic1",
                    "speed_range_min": 1,
                    "speed_range_max": 100,
                },
                {
                    "platform": "mqtt",
                    "name": "test2",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic2",
                    "percentage_command_topic": "percentage-command-topic2",
                    "speed_range_min": 1,
                    "speed_range_max": 200,
                },
                {
                    "platform": "mqtt",
                    "name": "test3",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic3",
                    "percentage_command_topic": "percentage-command-topic3",
                    "speed_range_min": 81,
                    "speed_range_max": 1023,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "percentage-state-topic1", "100")
    state = hass.states.get("fan.test1")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100

    async_fire_mqtt_message(hass, "percentage-state-topic2", "100")
    state = hass.states.get("fan.test2")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 50

    async_fire_mqtt_message(hass, "percentage-state-topic3", "1023")
    state = hass.states.get("fan.test3")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    async_fire_mqtt_message(hass, "percentage-state-topic3", "80")
    state = hass.states.get("fan.test3")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0

    state = hass.states.get("fan.test3")
    async_fire_mqtt_message(hass, "percentage-state-topic3", "79")
    assert "not a valid speed within the speed range" in caplog.text
    caplog.clear()


async def test_controlling_state_via_topic_no_percentage_topics(
    hass, mqtt_mock, caplog
):
    """Test the controlling state via topic without percentage topics."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "preset_mode_state_topic": "preset-mode-state-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_modes": [
                    "auto",
                    "smart",
                    "whoosh",
                    "eco",
                    "breeze",
                ],
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speeds": ["off", "low", "medium"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "smart")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "smart"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "auto")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "auto"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "whoosh")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "whoosh"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get("speed") == fan.SPEED_OFF

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    async_fire_mqtt_message(hass, "speed-state-topic", "medium")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "whoosh"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get("speed") == fan.SPEED_MEDIUM

    async_fire_mqtt_message(hass, "speed-state-topic", "low")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "whoosh"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 50
    assert state.attributes.get("speed") == fan.SPEED_LOW

    async_fire_mqtt_message(hass, "speed-state-topic", "off")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "whoosh"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get("speed") == fan.SPEED_OFF


async def test_controlling_state_via_topic_and_json_message(hass, mqtt_mock, caplog):
    """Test the controlling state via topic and JSON message (percentage mode)."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "percentage_state_topic": "percentage-state-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_mode_state_topic": "preset-mode-state-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_modes": [
                    "auto",
                    "smart",
                    "whoosh",
                    "eco",
                    "breeze",
                    "silent",
                ],
                "state_value_template": "{{ value_json.val }}",
                "oscillation_value_template": "{{ value_json.val }}",
                "percentage_value_template": "{{ value_json.val }}",
                "preset_mode_value_template": "{{ value_json.val }}",
                "speed_range_min": 1,
                "speed_range_max": 100,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", '{"val":"ON"}')
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"OFF"}')
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "oscillation-state-topic", '{"val":"oscillate_on"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is True

    async_fire_mqtt_message(hass, "oscillation-state-topic", '{"val":"oscillate_off"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "percentage-state-topic", '{"val": 1}')
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 1

    async_fire_mqtt_message(hass, "percentage-state-topic", '{"val": 100}')
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"val": "low"}')
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"val": "auto"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "auto"

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"val": "breeze"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "breeze"

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"val": "silent"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "silent"


async def test_sending_mqtt_commands_and_optimistic(hass, mqtt_mock, caplog):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "payload_off": "StAtE_OfF",
                "payload_on": "StAtE_On",
                "oscillation_command_topic": "oscillation-command-topic",
                "payload_oscillation_off": "OsC_OfF",
                "payload_oscillation_on": "OsC_On",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_command_topic": "speed-command-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speeds": ["off", "low", "medium"],
                "preset_modes": [
                    "whoosh",
                    "breeze",
                    "silent",
                ],
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "payload_off_speed": "speed_OfF",
                "payload_low_speed": "speed_lOw",
                "payload_medium_speed": "speed_mEdium",
                "payload_high_speed": "speed_High",
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_On", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "StAtE_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", True)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "OsC_On", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", False)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "OsC_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", -1)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    await common.async_set_percentage(hass, "fan.test", 100)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "100", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "speed-command-topic", "speed_mEdium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "0", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call(
        "speed-command-topic", "speed_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get(fan.ATTR_SPEED) == fan.SPEED_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_preset_mode(hass, "fan.test", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "whoosh")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "whoosh"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "breeze")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "breeze", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "breeze"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "silent")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "silent"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_lOw", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_mEdium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    assert "not a valid speed" in caplog.text
    caplog.clear()

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "speed_OfF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_mqtt_commands_with_alternate_speed_range(hass, mqtt_mock):
    """Test the controlling state via topic using an alternate speed range."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test1",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic1",
                    "percentage_command_topic": "percentage-command-topic1",
                    "speed_range_min": 1,
                    "speed_range_max": 3,
                },
                {
                    "platform": "mqtt",
                    "name": "test2",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic2",
                    "percentage_command_topic": "percentage-command-topic2",
                    "speed_range_min": 1,
                    "speed_range_max": 200,
                },
                {
                    "platform": "mqtt",
                    "name": "test3",
                    "command_topic": "command-topic",
                    "percentage_state_topic": "percentage-state-topic3",
                    "percentage_command_topic": "percentage-command-topic3",
                    "speed_range_min": 81,
                    "speed_range_max": 1023,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    await common.async_set_percentage(hass, "fan.test1", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic1", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test1", 33)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic1", "1", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test1", 66)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic1", "2", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test1", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic1", "3", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test2", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic2", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test2")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test2", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic2", "200", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test2")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test3", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic3", "80", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test3")
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test3", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic3", "1023", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test3")
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_mqtt_commands_and_optimistic_no_legacy(hass, mqtt_mock, caplog):
    """Test optimistic mode without state topic without legacy speed command topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_modes": [
                    "whoosh",
                    "breeze",
                    "silent",
                ],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", -1)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    await common.async_set_percentage(hass, "fan.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "auto")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "whoosh")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "whoosh"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "breeze")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "breeze", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "breeze"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "silent")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "silent"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", percentage=25)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "25", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_any_call("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", preset_mode="whoosh")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_turn_on(hass, "fan.test", preset_mode="freaking-high")


async def test_sending_mqtt_command_templates_(hass, mqtt_mock, caplog):
    """Test optimistic mode without state topic without legacy speed command topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "command_template": "state: {{ value }}",
                "oscillation_command_topic": "oscillation-command-topic",
                "oscillation_command_template": "oscillation: {{ value }}",
                "percentage_command_topic": "percentage-command-topic",
                "percentage_command_template": "percentage: {{ value }}",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_mode_command_template": "preset_mode: {{ value }}",
                "preset_modes": [
                    "whoosh",
                    "breeze",
                    "silent",
                ],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "state: ON", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "state: OFF", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", -1)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    await common.async_set_percentage(hass, "fan.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "percentage: 100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "percentage: 0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "whoosh")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "preset_mode: whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "whoosh"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "breeze")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "preset_mode: breeze", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "breeze"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "silent")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "preset_mode: silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) == "silent"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", percentage=25)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "state: ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "percentage-command-topic", "percentage: 25", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_any_call("command-topic", "state: OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", preset_mode="whoosh")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "state: ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "preset_mode: whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_turn_on(hass, "fan.test", preset_mode="low")


async def test_sending_mqtt_commands_and_optimistic_no_percentage_topic(
    hass, mqtt_mock, caplog
):
    """Test optimistic mode without state topic without percentage command topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_mode_state_topic": "preset-mode-state-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speeds": ["off", "low", "medium"],
                "preset_modes": [
                    "whoosh",
                    "breeze",
                    "silent",
                    "high",
                ],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", -1)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    await common.async_set_percentage(hass, "fan.test", 100)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "medium", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "off", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "whoosh")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "breeze")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "breeze", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "silent")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PRESET_MODE) is None
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "low", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    assert "not a valid speed" in caplog.text
    caplog.clear()
    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)

    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "off", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", speed="medium")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "medium", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_turn_on(hass, "fan.test", speed="high")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "high", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


# use of speeds is deprecated, support will be removed after a quarter (2021.7)
async def test_sending_mqtt_commands_and_optimistic_legacy_speeds_only(
    hass, mqtt_mock, caplog
):
    """Test optimistic mode without state topics with legacy speeds."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "speeds": ["off", "low", "medium", "high"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 100)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "high", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get(fan.ATTR_SPEED) == "off"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "off", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "low", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "high", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", speed="medium")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "medium", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", speed="off")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "off", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_sending_mqtt_commands_and_explicit_optimistic(hass, mqtt_mock, caplog):
    """Test optimistic mode with state topic and turn on attributes."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_state_topic": "speed-state-topic",
                "speed_command_topic": "speed-command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "percentage_state_topic": "percentage-state-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "preset_mode_state_topic": "preset-mode-state-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speeds": ["off", "low", "medium"],
                "preset_modes": [
                    "whoosh",
                    "breeze",
                    "silent",
                ],
                "optimistic": True,
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", speed=fan.SPEED_MEDIUM)
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "medium", 0, False)
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "100", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", percentage=25)
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "25", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "low", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_any_call("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    with pytest.raises(NotValidPresetModeError):
        await common.async_turn_on(hass, "fan.test", preset_mode="auto")

    await common.async_turn_on(hass, "fan.test", preset_mode="whoosh")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_any_call("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", preset_mode="silent")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", preset_mode="silent")
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_called_once_with("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", True)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "oscillate_on", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "fan.test", percentage=50)
    assert mqtt_mock.async_publish.call_count == 3
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "50", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "low", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_off(hass, "fan.test")
    mqtt_mock.async_publish.assert_any_call("command-topic", "OFF", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_oscillate(hass, "fan.test", False)
    mqtt_mock.async_publish.assert_called_once_with(
        "oscillation-command-topic", "oscillate_off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 33)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "33", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "low", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 50)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "50", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "low", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 100)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "100", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "medium", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "0", 0, False)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    mqtt_mock.async_publish.assert_any_call("speed-command-topic", "off", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    await common.async_set_preset_mode(hass, "fan.test", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    await common.async_set_preset_mode(hass, "fan.test", "whoosh")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "whoosh", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "silent")
    mqtt_mock.async_publish.assert_called_once_with(
        "preset-mode-command-topic", "silent", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_preset_mode(hass, "fan.test", "freaking-high")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    assert "not a valid speed" in caplog.text
    caplog.clear()

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    mqtt_mock.async_publish.assert_called_once_with(
        "speed-command-topic", "off", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_speed(hass, "fan.test", "cUsToM")
    assert "not a valid speed" in caplog.text
    caplog.clear()


async def test_attributes(hass, mqtt_mock, caplog):
    """Test attributes."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                "speed_command_topic": "speed-command-topic",
                "preset_mode_command_topic": "preset-mode-command-topic",
                "percentage_command_topic": "percentage-command-topic",
                "preset_modes": [
                    "breeze",
                    "silent",
                ],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(fan.ATTR_SPEED_LIST) == [
        "low",
        "medium",
        "high",
    ]

    await common.async_turn_on(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None

    await common.async_turn_off(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None

    await common.async_oscillate(hass, "fan.test", True)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is True

    await common.async_oscillate(hass, "fan.test", False)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    assert state.attributes.get(fan.ATTR_SPEED) is None
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_LOW)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "low"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
    await common.async_set_speed(hass, "fan.test", fan.SPEED_MEDIUM)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "medium"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_HIGH)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "high"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", fan.SPEED_OFF)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_SPEED) == "off"
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_speed(hass, "fan.test", "cUsToM")
    assert "not a valid speed" in caplog.text
    caplog.clear()


# use of speeds is deprecated, support will be removed after a quarter (2021.7)
async def test_custom_speed_list(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "command_topic": "command-topic",
                "oscillation_command_topic": "oscillation-command-topic",
                "oscillation_state_topic": "oscillation-state-topic",
                "speed_command_topic": "speed-command-topic",
                "speed_state_topic": "speed-state-topic",
                "speeds": ["off", "high"],
            }
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(fan.ATTR_SPEED_LIST) == ["high"]


async def test_supported_features(hass, mqtt_mock):
    """Test optimistic mode without state topic."""
    assert await async_setup_component(
        hass,
        fan.DOMAIN,
        {
            fan.DOMAIN: [
                {
                    "platform": "mqtt",
                    "name": "test1",
                    "command_topic": "command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test2",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test3a1",
                    "command_topic": "command-topic",
                    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                    "speed_command_topic": "speed-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test3a2",
                    "command_topic": "command-topic",
                    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                    "speed_command_topic": "speed-command-topic",
                    "speeds": ["low"],
                },
                {
                    "platform": "mqtt",
                    "name": "test3a3",
                    "command_topic": "command-topic",
                    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                    "speed_command_topic": "speed-command-topic",
                    "speeds": ["off"],
                },
                {
                    "platform": "mqtt",
                    "name": "test3b",
                    "command_topic": "command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test3c1",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test3c2",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": ["eco", "auto"],
                },
                {
                    "platform": "mqtt",
                    "name": "test3c3",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": ["eco", "smart", "auto"],
                },
                {
                    "platform": "mqtt",
                    "name": "test4",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    # use of speeds is deprecated, support will be removed after a quarter (2021.7)
                    "speed_command_topic": "speed-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test4pcta",
                    "command_topic": "command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test4pctb",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                },
                {
                    "platform": "mqtt",
                    "name": "test5pr_ma",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": ["Mode1", "Mode2", "Mode3"],
                },
                {
                    "platform": "mqtt",
                    "name": "test5pr_mb",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": ["whoosh", "silent", "auto"],
                },
                {
                    "platform": "mqtt",
                    "name": "test5pr_mc",
                    "command_topic": "command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": ["Mode1", "Mode2", "Mode3"],
                },
                {
                    "platform": "mqtt",
                    "name": "test6spd_range_a",
                    "command_topic": "command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "speed_range_min": 1,
                    "speed_range_max": 40,
                },
                {
                    "platform": "mqtt",
                    "name": "test6spd_range_b",
                    "command_topic": "command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "speed_range_min": 50,
                    "speed_range_max": 40,
                },
                {
                    "platform": "mqtt",
                    "name": "test6spd_range_c",
                    "command_topic": "command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "speed_range_min": 0,
                    "speed_range_max": 40,
                },
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("fan.test1")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == 0
    state = hass.states.get("fan.test2")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_OSCILLATE

    state = hass.states.get("fan.test3a1")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        and fan.SUPPORT_SET_SPEED == fan.SUPPORT_SET_SPEED
    )
    state = hass.states.get("fan.test3a2")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        and fan.SUPPORT_SET_SPEED == fan.SUPPORT_SET_SPEED
    )
    state = hass.states.get("fan.test3a3")
    assert state is None

    state = hass.states.get("fan.test3b")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_SET_SPEED

    state = hass.states.get("fan.test3c1")
    assert state is None

    state = hass.states.get("fan.test3c2")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_PRESET_MODE
    state = hass.states.get("fan.test3c3")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_PRESET_MODE

    state = hass.states.get("fan.test4")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == fan.SUPPORT_OSCILLATE | fan.SUPPORT_SET_SPEED
    )

    state = hass.states.get("fan.test4pcta")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_SET_SPEED
    state = hass.states.get("fan.test4pctb")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == fan.SUPPORT_OSCILLATE | fan.SUPPORT_SET_SPEED
    )

    state = hass.states.get("fan.test5pr_ma")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_PRESET_MODE
    state = hass.states.get("fan.test5pr_mb")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_PRESET_MODE

    state = hass.states.get("fan.test5pr_mc")
    assert (
        state.attributes.get(ATTR_SUPPORTED_FEATURES)
        == fan.SUPPORT_OSCILLATE | fan.SUPPORT_PRESET_MODE
    )

    state = hass.states.get("fan.test6spd_range_a")
    assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == fan.SUPPORT_SET_SPEED
    assert state.attributes.get("percentage_step") == 2.5
    state = hass.states.get("fan.test6spd_range_b")
    assert state is None
    state = hass.states.get("fan.test6spd_range_c")
    assert state is None


async def test_availability_when_connection_lost(hass, mqtt_mock):
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG, True, "state-topic", "1"
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG, True, "state-topic", "1"
    )


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass, mqtt_mock):
    """Test unique_id option only creates one fan per id."""
    config = {
        fan.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "test_topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, mqtt_mock, fan.DOMAIN, config)


async def test_discovery_removal_fan(hass, mqtt_mock, caplog):
    """Test removal of discovered fan."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, fan.DOMAIN, data)


async def test_discovery_update_fan(hass, mqtt_mock, caplog):
    """Test update of discovered fan."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_update(hass, mqtt_mock, caplog, fan.DOMAIN, data1, data2)


async def test_discovery_update_unchanged_fan(hass, mqtt_mock, caplog):
    """Test update of discovered fan."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.fan.MqttFan.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock, caplog, fan.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'
    await help_test_discovery_broken(hass, mqtt_mock, caplog, fan.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, fan.DOMAIN, DEFAULT_CONFIG
    )
