"""Test MQTT fans."""
import copy
from typing import Any
from unittest.mock import patch

import pytest
from voluptuous.error import MultipleInvalid

from homeassistant.components import fan, mqtt
from homeassistant.components.fan import (
    ATTR_DIRECTION,
    ATTR_OSCILLATING,
    ATTR_PERCENTAGE,
    ATTR_PRESET_MODE,
    ATTR_PRESET_MODES,
    NotValidPresetModeError,
)
from homeassistant.components.mqtt.fan import (
    CONF_DIRECTION_COMMAND_TOPIC,
    CONF_DIRECTION_STATE_TOPIC,
    CONF_OSCILLATION_COMMAND_TOPIC,
    CONF_OSCILLATION_STATE_TOPIC,
    CONF_PERCENTAGE_COMMAND_TOPIC,
    CONF_PERCENTAGE_STATE_TOPIC,
    CONF_PRESET_MODE_COMMAND_TOPIC,
    CONF_PRESET_MODE_STATE_TOPIC,
    MQTT_FAN_ATTRIBUTES_BLOCKED,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_SUPPORTED_FEATURES,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
    Platform,
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
    help_test_unique_id,
    help_test_unload_config_entry_with_platform,
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.fan import common
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        fan.DOMAIN: {
            "name": "test",
            "state_topic": "state-topic",
            "command_topic": "command-topic",
        }
    }
}


@pytest.fixture(autouse=True)
def fan_platform_only():
    """Only setup the fan platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.FAN]):
        yield


@pytest.mark.parametrize("hass_config", [{mqtt.DOMAIN: {fan.DOMAIN: {"name": "test"}}}])
async def test_fail_setup_if_no_command_topic(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test if command fails with command topic."""
    with pytest.raises(AssertionError):
        await mqtt_mock_entry()
    assert (
        "Invalid config for [mqtt]: required key not provided @ data['mqtt']['fan'][0]['command_topic']"
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_off": "StAtE_OfF",
                    "payload_on": "StAtE_On",
                    "direction_state_topic": "direction-state-topic",
                    "direction_command_topic": "direction-command-topic",
                    "oscillation_state_topic": "oscillation-state-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
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
                    "payload_reset_percentage": "rEset_percentage",
                    "payload_reset_preset_mode": "rEset_preset_mode",
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

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "StAtE_On")
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "StAtE_OfF")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "direction-state-topic", "forward")
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "forward"

    async_fire_mqtt_message(hass, "direction-state-topic", "reverse")
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "reverse"

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

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "rEset_preset_mode")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") is None

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "ModeUnknown")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "percentage-state-topic", "rEset_percentage")
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None

    async_fire_mqtt_message(hass, "state-topic", "None")
    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            fan.DOMAIN,
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                    }
                }
            },
            (
                {
                    "name": "test1",
                    "percentage_state_topic": "percentage-state-topic1",
                    "speed_range_min": 1,
                    "speed_range_max": 100,
                },
                {
                    "name": "test2",
                    "percentage_state_topic": "percentage-state-topic2",
                    "speed_range_min": 1,
                    "speed_range_max": 200,
                },
                {
                    "name": "test3",
                    "percentage_state_topic": "percentage-state-topic3",
                    "speed_range_min": 81,
                    "speed_range_max": 1023,
                },
            ),
        ),
    ],
)
async def test_controlling_state_via_topic_with_different_speed_range(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic using an alternate speed range."""
    await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "preset_mode_state_topic": "preset-mode-state-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": [
                        "auto",
                        "smart",
                        "whoosh",
                        "eco",
                        "breeze",
                    ],
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic_no_percentage_topics(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic without percentage topics."""
    await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "smart")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "smart"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "auto")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "auto"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "whoosh")
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") == "whoosh"
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "medium")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()

    async_fire_mqtt_message(hass, "preset-mode-state-topic", "low")
    assert "not a valid preset mode" in caplog.text
    caplog.clear()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "direction_state_topic": "direction-state-topic",
                    "direction_command_topic": "direction-command-topic",
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
                    "direction_value_template": "{{ value_json.val }}",
                    "oscillation_value_template": "{{ value_json.val }}",
                    "percentage_value_template": "{{ value_json.val }}",
                    "preset_mode_value_template": "{{ value_json.val }}",
                    "speed_range_min": 1,
                    "speed_range_max": 100,
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
    """Test the controlling state via topic and JSON message (percentage mode)."""
    await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", '{"val":"ON"}')
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val": null}')
    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", '{"val":"OFF"}')
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("oscillating") is False

    async_fire_mqtt_message(hass, "direction-state-topic", '{"val":"forward"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "forward"

    async_fire_mqtt_message(hass, "direction-state-topic", '{"val":"reverse"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "reverse"

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

    async_fire_mqtt_message(hass, "percentage-state-topic", '{"val": "None"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None

    async_fire_mqtt_message(hass, "percentage-state-topic", '{"otherval": 100}')
    assert state.attributes.get(fan.ATTR_PERCENTAGE) is None
    caplog.clear()

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

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"val": "None"}')
    state = hass.states.get("fan.test")
    assert state.attributes.get("preset_mode") is None

    async_fire_mqtt_message(hass, "preset-mode-state-topic", '{"otherval": 100}')
    assert state.attributes.get("preset_mode") is None


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "state_topic": "shared-state-topic",
                    "command_topic": "command-topic",
                    "direction_state_topic": "shared-state-topic",
                    "direction_command_topic": "direction-command-topic",
                    "oscillation_state_topic": "shared-state-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "percentage_state_topic": "shared-state-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "preset_mode_state_topic": "shared-state-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": [
                        "auto",
                        "smart",
                        "whoosh",
                        "eco",
                        "breeze",
                        "silent",
                    ],
                    "state_value_template": "{{ value_json.state }}",
                    "direction_value_template": "{{ value_json.direction }}",
                    "oscillation_value_template": "{{ value_json.oscillation }}",
                    "percentage_value_template": "{{ value_json.percentage }}",
                    "preset_mode_value_template": "{{ value_json.preset_mode }}",
                    "speed_range_min": 1,
                    "speed_range_max": 100,
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

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get("direction") is None
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        """{
        "state":"ON",
        "preset_mode":"eco",
        "oscillation":"oscillate_on",
        "percentage": 50,
        "direction": "forward"
        }""",
    )
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get("direction") == "forward"
    assert state.attributes.get("oscillating") is True
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 50
    assert state.attributes.get("preset_mode") == "eco"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        """{
       "state":"ON",
       "preset_mode":"auto",
       "oscillation":"oscillate_off",
       "percentage": 10,
       "direction": "forward"
       }""",
    )
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get("direction") == "forward"
    assert state.attributes.get("oscillating") is False
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 10
    assert state.attributes.get("preset_mode") == "auto"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        """{
        "state":"OFF",
        "preset_mode":"auto",
        "oscillation":"oscillate_off",
        "percentage": 0,
        "direction": "reverse"
        }""",
    )
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get("direction") == "reverse"
    assert state.attributes.get("oscillating") is False
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 0
    assert state.attributes.get("preset_mode") == "auto"

    async_fire_mqtt_message(
        hass,
        "shared-state-topic",
        '{"percentage": 100}',
    )
    state = hass.states.get("fan.test")
    assert state.attributes.get(fan.ATTR_PERCENTAGE) == 100
    assert state.attributes.get("preset_mode") == "auto"
    caplog.clear()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_off": "StAtE_OfF",
                    "payload_on": "StAtE_On",
                    "direction_command_topic": "direction-command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "payload_oscillation_off": "OsC_OfF",
                    "payload_oscillation_on": "OsC_On",
                    "percentage_command_topic": "percentage-command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_modes": [
                        "whoosh",
                        "breeze",
                        "silent",
                    ],
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test optimistic mode without state topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
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

    await common.async_set_direction(hass, "fan.test", "forward")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "forward", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_direction(hass, "fan.test", "reverse")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "reverse", 0, False
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
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "low")

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


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            fan.DOMAIN,
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test1",
                        "command_topic": "command-topic",
                        "percentage_state_topic": "percentage-state-topic",
                        "speed_range_min": 1,
                        "speed_range_max": 3,
                    }
                }
            },
            (
                {
                    "name": "test1",
                    "percentage_command_topic": "percentage-command-topic1",
                    "speed_range_min": 1,
                    "speed_range_max": 3,
                },
                {
                    "name": "test2",
                    "percentage_command_topic": "percentage-command-topic2",
                    "speed_range_min": 1,
                    "speed_range_max": 200,
                },
                {
                    "name": "test3",
                    "percentage_command_topic": "percentage-command-topic3",
                    "speed_range_min": 81,
                    "speed_range_max": 1023,
                },
            ),
        ),
    ],
)
async def test_sending_mqtt_commands_with_alternate_speed_range(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic using an alternate speed range."""
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
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
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic_no_legacy(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test optimistic mode without state topic without legacy speed command topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
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
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "low")

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "auto")

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "command_template": "state: {{ value }}",
                    "direction_command_topic": "direction-command-topic",
                    "direction_command_template": "direction: {{ value }}",
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
            }
        }
    ],
)
async def test_sending_mqtt_command_templates_(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test optimistic mode without state topic without legacy speed command topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
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

    await common.async_set_direction(hass, "fan.test", "forward")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "direction: forward", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "forward"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_direction(hass, "fan.test", "reverse")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "direction: reverse", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.attributes.get("direction") == "reverse"
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
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "low")

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "medium")

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_mode_state_topic": "preset-mode-state-topic",
                    "preset_modes": [
                        "whoosh",
                        "breeze",
                        "silent",
                        "high",
                    ],
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic_no_percentage_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test optimistic mode without state topic without percentage command topic."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "medium")

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "direction_state_topic": "direction-state-topic",
                    "direction_command_topic": "direction-command-topic",
                    "oscillation_state_topic": "oscillation-state-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "percentage_state_topic": "percentage-state-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "preset_mode_state_topic": "preset-mode-state-topic",
                    "preset_modes": [
                        "whoosh",
                        "breeze",
                        "silent",
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
) -> None:
    """Test optimistic mode with state topic and turn on attributes."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN
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

    with pytest.raises(NotValidPresetModeError):
        await common.async_turn_on(hass, "fan.test", preset_mode="auto")
    assert mqtt_mock.async_publish.call_count == 1
    # We can turn on, but the invalid preset mode will raise
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.reset_mock()

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

    await common.async_set_direction(hass, "fan.test", "forward")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "forward", 0, False
    )
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
    assert mqtt_mock.async_publish.call_count == 2
    mqtt_mock.async_publish.assert_any_call("command-topic", "ON", 0, False)
    mqtt_mock.async_publish.assert_any_call("percentage-command-topic", "50", 0, False)
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

    await common.async_set_direction(hass, "fan.test", "reverse")
    mqtt_mock.async_publish.assert_called_once_with(
        "direction-command-topic", "reverse", 0, False
    )
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
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "33", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 50)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "50", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 100)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "100", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_set_percentage(hass, "fan.test", 0)
    mqtt_mock.async_publish.assert_called_once_with(
        "percentage-command-topic", "0", 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    with pytest.raises(MultipleInvalid):
        await common.async_set_percentage(hass, "fan.test", 101)

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "low")

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "medium")

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

    with pytest.raises(NotValidPresetModeError):
        await common.async_set_preset_mode(hass, "fan.test", "freaking-high")

    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "ON", None, "on"),
        (CONF_PRESET_MODE_STATE_TOPIC, "auto", ATTR_PRESET_MODE, "auto"),
        (CONF_PERCENTAGE_STATE_TOPIC, "60", ATTR_PERCENTAGE, 60),
        (
            CONF_OSCILLATION_STATE_TOPIC,
            "oscillate_on",
            ATTR_OSCILLATING,
            True,
        ),
        (
            CONF_DIRECTION_STATE_TOPIC,
            "reverse",
            ATTR_DIRECTION,
            "reverse",
        ),
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
    config = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][fan.DOMAIN])
    config[ATTR_PRESET_MODES] = ["eco", "auto"]
    config[CONF_PRESET_MODE_COMMAND_TOPIC] = "fan/some_preset_mode_command_topic"
    config[CONF_PERCENTAGE_COMMAND_TOPIC] = "fan/some_percentage_command_topic"
    config[CONF_DIRECTION_COMMAND_TOPIC] = "fan/some_direction_command_topic"
    config[CONF_OSCILLATION_COMMAND_TOPIC] = "fan/some_oscillation_command_topic"
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        fan.DOMAIN,
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
                fan.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "direction_command_topic": "direction-command-topic",
                    "oscillation_command_topic": "oscillation-command-topic",
                    "preset_mode_command_topic": "preset-mode-command-topic",
                    "percentage_command_topic": "percentage-command-topic",
                    "preset_modes": [
                        "breeze",
                        "silent",
                    ],
                }
            }
        }
    ],
)
async def test_attributes(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes."""
    await mqtt_mock_entry()

    state = hass.states.get("fan.test")
    assert state.state == STATE_UNKNOWN

    await common.async_turn_on(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None
    assert state.attributes.get(fan.ATTR_DIRECTION) is None

    await common.async_turn_off(hass, "fan.test")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is None
    assert state.attributes.get(fan.ATTR_DIRECTION) is None

    await common.async_oscillate(hass, "fan.test", True)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is True
    assert state.attributes.get(fan.ATTR_DIRECTION) is None

    await common.async_set_direction(hass, "fan.test", "reverse")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is True
    assert state.attributes.get(fan.ATTR_DIRECTION) == "reverse"

    await common.async_oscillate(hass, "fan.test", False)
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False

    await common.async_set_direction(hass, "fan.test", "forward")
    state = hass.states.get("fan.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)
    assert state.attributes.get(fan.ATTR_OSCILLATING) is False
    assert state.attributes.get(fan.ATTR_DIRECTION) == "forward"


@pytest.mark.parametrize(
    ("name", "hass_config", "success", "features"),
    [
        (
            "test1",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test1",
                        "command_topic": "command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature(0),
        ),
        (
            "test2",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test2",
                        "command_topic": "command-topic",
                        "oscillation_command_topic": "oscillation-command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature.OSCILLATE,
        ),
        (
            "test3",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test3",
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature.SET_SPEED,
        ),
        (
            "test4",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test4",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                    }
                }
            },
            False,
            None,
        ),
        (
            "test5",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test5",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["eco", "auto"],
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE,
        ),
        (
            "test6",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test6",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["eco", "smart", "auto"],
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE,
        ),
        (
            "test7",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test7",
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature.SET_SPEED,
        ),
        (
            "test8",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test8",
                        "command_topic": "command-topic",
                        "oscillation_command_topic": "oscillation-command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature.OSCILLATE | fan.FanEntityFeature.SET_SPEED,
        ),
        (
            "test9",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test9",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["Mode1", "Mode2", "Mode3"],
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE,
        ),
        (
            "test10",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test10",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["whoosh", "silent", "auto"],
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE,
        ),
        (
            "test11",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test11",
                        "command_topic": "command-topic",
                        "oscillation_command_topic": "oscillation-command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["Mode1", "Mode2", "Mode3"],
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE | fan.FanEntityFeature.OSCILLATE,
        ),
        (
            "test12",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test12",
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                        "speed_range_min": 1,
                        "speed_range_max": 40,
                    }
                }
            },
            True,
            fan.FanEntityFeature.SET_SPEED,
        ),
        (
            "test13",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test13",
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                        "speed_range_min": 50,
                        "speed_range_max": 40,
                    }
                }
            },
            False,
            None,
        ),
        (
            "test14",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test14",
                        "command_topic": "command-topic",
                        "percentage_command_topic": "percentage-command-topic",
                        "speed_range_min": 0,
                        "speed_range_max": 40,
                    }
                }
            },
            False,
            None,
        ),
        (
            "test15",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test7reset_payload_in_preset_modes_a",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["auto", "smart", "normal", "None"],
                    }
                }
            },
            False,
            None,
        ),
        (
            "test16",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test16",
                        "command_topic": "command-topic",
                        "preset_mode_command_topic": "preset-mode-command-topic",
                        "preset_modes": ["whoosh", "silent", "auto", "None"],
                        "payload_reset_preset_mode": "normal",
                    }
                }
            },
            True,
            fan.FanEntityFeature.PRESET_MODE,
        ),
        (
            "test17",
            {
                mqtt.DOMAIN: {
                    fan.DOMAIN: {
                        "name": "test17",
                        "command_topic": "command-topic",
                        "direction_command_topic": "direction-command-topic",
                    }
                }
            },
            True,
            fan.FanEntityFeature.DIRECTION,
        ),
    ],
)
async def test_supported_features(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    name: str,
    success: bool,
    features,
) -> None:
    """Test optimistic mode without state topic."""
    if success:
        await mqtt_mock_entry()

        state = hass.states.get(f"fan.{name}")
        assert state.attributes.get(ATTR_SUPPORTED_FEATURES) == features
        return
    with pytest.raises(AssertionError):
        await mqtt_mock_entry()


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(hass, mqtt_mock_entry, fan.DOMAIN)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry,
        fan.DOMAIN,
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
        fan.DOMAIN,
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
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        fan.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_FAN_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
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
        fan.DOMAIN,
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
        fan.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_discovery_update_attr(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, caplog, fan.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                fan.DOMAIN: [
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
    """Test unique_id option only creates one fan per id."""
    await help_test_unique_id(hass, mqtt_mock_entry, fan.DOMAIN)


async def test_discovery_removal_fan(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered fan."""
    data = '{ "name": "test", "command_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, caplog, fan.DOMAIN, data)


async def test_discovery_update_fan(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered fan."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry, caplog, fan.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_fan(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered fan."""
    data1 = '{ "name": "Beer", "command_topic": "test_topic" }'
    with patch(
        "homeassistant.components.mqtt.fan.MqttFan.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry,
            caplog,
            fan.DOMAIN,
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
    data1 = '{ "name": "Beer" }'
    data2 = '{ "name": "Milk", "command_topic": "test_topic" }'

    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, fan.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT fan device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, fan.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        fan.DOMAIN,
        DEFAULT_CONFIG,
        fan.SERVICE_TURN_ON,
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            fan.SERVICE_TURN_ON,
            "command_topic",
            None,
            "ON",
            None,
        ),
        (
            fan.SERVICE_TURN_OFF,
            "command_topic",
            None,
            "OFF",
            None,
        ),
        (
            fan.SERVICE_SET_PRESET_MODE,
            "preset_mode_command_topic",
            {fan.ATTR_PRESET_MODE: "eco"},
            "eco",
            "preset_mode_command_template",
        ),
        (
            fan.SERVICE_SET_PERCENTAGE,
            "percentage_command_topic",
            {fan.ATTR_PERCENTAGE: "45"},
            45,
            "percentage_command_template",
        ),
        (
            fan.SERVICE_OSCILLATE,
            "oscillation_command_topic",
            {fan.ATTR_OSCILLATING: "on"},
            "oscillate_on",
            "oscillation_command_template",
        ),
        (
            fan.SERVICE_SET_DIRECTION,
            "direction_command_topic",
            {fan.ATTR_DIRECTION: "forward"},
            "forward",
            "direction_command_template",
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
    domain = fan.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)
    if topic == "preset_mode_command_topic":
        config[mqtt.DOMAIN][domain]["preset_modes"] = ["auto", "eco"]

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
    domain = fan.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_setup_manual_entity_from_yaml(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setup manual configured MQTT entity."""
    await mqtt_mock_entry()
    platform = fan.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = fan.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )
