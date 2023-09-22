"""The tests for the MQTT siren platform."""
import copy
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, siren
from homeassistant.components.siren import ATTR_VOLUME_LEVEL
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
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
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {siren.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


@pytest.fixture(autouse=True)
def siren_platform_only():
    """Only setup the siren platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.SIREN]):
        yield


async def async_turn_on(
    hass: HomeAssistant,
    entity_id: str = ENTITY_MATCH_ALL,
    parameters: dict[str, Any] = {},
) -> None:
    """Turn all or specified siren on."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}
    data.update(parameters)

    await hass.services.async_call(siren.DOMAIN, SERVICE_TURN_ON, data, blocking=True)


async def async_turn_off(
    hass: HomeAssistant, entity_id: str = ENTITY_MATCH_ALL
) -> None:
    """Turn all or specified siren off."""
    data = {ATTR_ENTITY_ID: entity_id} if entity_id else {}

    await hass.services.async_call(siren.DOMAIN, SERVICE_TURN_OFF, data, blocking=True)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": 1,
                    "payload_off": 0,
                }
            }
        }
    ],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()

    state = hass.states.get("siren.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "0")

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "qos": "2",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending MQTT commands in optimistic mode."""
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_turn_on(hass, entity_id="siren.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{"state":"beer on"}', 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    await async_turn_off(hass, entity_id="siren.test")

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", '{"state":"beer off"}', 2, False
    )
    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "state_value_template": "{{ value_json.val }}",
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
    await mqtt_mock_entry()

    state = hass.states.get("siren.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer on"}')

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val": null }')
    state = hass.states.get("siren.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer off"}')

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "available_tones": ["ping", "siren", "bell"],
                }
            }
        }
    ],
)
async def test_controlling_state_and_attributes_with_json_message_without_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the controlling state via topic and JSON message without a value template."""
    await mqtt_mock_entry()

    state = hass.states.get("siren.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(siren.ATTR_TONE) is None
    assert state.attributes.get(siren.ATTR_DURATION) is None
    assert state.attributes.get(siren.ATTR_VOLUME_LEVEL) is None

    async_fire_mqtt_message(
        hass,
        "state-topic",
        '{"state":"beer on", "tone": "bell", "duration": 10, "volume_level": 0.5 }',
    )

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON
    assert state.attributes.get(siren.ATTR_TONE) == "bell"
    assert state.attributes.get(siren.ATTR_DURATION) == 10
    assert state.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.5

    async_fire_mqtt_message(
        hass,
        "state-topic",
        '{"state":"beer off", "duration": 5, "volume_level": 0.6}',
    )

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF
    assert state.attributes.get(siren.ATTR_TONE) == "bell"
    assert state.attributes.get(siren.ATTR_DURATION) == 5
    assert state.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.6

    # Test validation of received attributes, invalid
    async_fire_mqtt_message(
        hass,
        "state-topic",
        '{"state":"beer on", "duration": 6, "volume_level": 2 }',
    )
    state = hass.states.get("siren.test")
    assert (
        "Unable to update siren state attributes from payload '{'duration': 6, 'volume_level': 2}': value must be at most 1 for dictionary value @ data['volume_level']"
        in caplog.text
    )
    assert state.state == STATE_OFF
    assert state.attributes.get(siren.ATTR_TONE) == "bell"
    assert state.attributes.get(siren.ATTR_DURATION) == 5
    assert state.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.6

    async_fire_mqtt_message(
        hass,
        "state-topic",
        "{}",
    )
    assert state.state == STATE_OFF
    assert state.attributes.get(siren.ATTR_TONE) == "bell"
    assert state.attributes.get(siren.ATTR_DURATION) == 5
    assert state.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.6


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            siren.DOMAIN,
            {
                mqtt.DOMAIN: {
                    siren.DOMAIN: {
                        "command_topic": "command-topic",
                    }
                }
            },
            (
                {
                    "name": "test1",
                    "available_tones": ["ping", "siren", "bell"],
                    "support_duration": False,
                },
                {
                    "name": "test2",
                    "available_tones": ["ping", "siren", "bell"],
                    "support_volume_set": False,
                },
                {
                    "name": "test3",
                },
            ),
        )
    ],
)
async def test_filtering_not_supported_attributes_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting attributes with support flags optimistic."""
    await mqtt_mock_entry()

    state1 = hass.states.get("siren.test1")
    assert state1.state == STATE_OFF
    assert siren.ATTR_DURATION not in state1.attributes
    assert siren.ATTR_AVAILABLE_TONES in state1.attributes
    assert siren.ATTR_TONE in state1.attributes
    assert siren.ATTR_VOLUME_LEVEL in state1.attributes
    await async_turn_on(
        hass,
        entity_id="siren.test1",
        parameters={
            siren.ATTR_DURATION: 22,
            siren.ATTR_TONE: "ping",
            ATTR_VOLUME_LEVEL: 0.88,
        },
    )
    state1 = hass.states.get("siren.test1")
    assert state1.attributes.get(siren.ATTR_TONE) == "ping"
    assert state1.attributes.get(siren.ATTR_DURATION) is None
    assert state1.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88

    state2 = hass.states.get("siren.test2")
    assert siren.ATTR_DURATION in state2.attributes
    assert siren.ATTR_AVAILABLE_TONES in state2.attributes
    assert siren.ATTR_TONE in state2.attributes
    assert siren.ATTR_VOLUME_LEVEL not in state2.attributes
    await async_turn_on(
        hass,
        entity_id="siren.test2",
        parameters={
            siren.ATTR_DURATION: 22,
            siren.ATTR_TONE: "ping",
            ATTR_VOLUME_LEVEL: 0.88,
        },
    )
    state2 = hass.states.get("siren.test2")
    assert state2.attributes.get(siren.ATTR_TONE) == "ping"
    assert state2.attributes.get(siren.ATTR_DURATION) == 22
    assert state2.attributes.get(siren.ATTR_VOLUME_LEVEL) is None

    state3 = hass.states.get("siren.test3")
    assert siren.ATTR_DURATION in state3.attributes
    assert siren.ATTR_AVAILABLE_TONES not in state3.attributes
    assert siren.ATTR_TONE not in state3.attributes
    assert siren.ATTR_VOLUME_LEVEL in state3.attributes
    await async_turn_on(
        hass,
        entity_id="siren.test3",
        parameters={
            siren.ATTR_DURATION: 22,
            siren.ATTR_TONE: "ping",
            ATTR_VOLUME_LEVEL: 0.88,
        },
    )
    state3 = hass.states.get("siren.test3")
    assert state3.attributes.get(siren.ATTR_TONE) is None
    assert state3.attributes.get(siren.ATTR_DURATION) == 22
    assert state3.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            siren.DOMAIN,
            {
                mqtt.DOMAIN: {
                    siren.DOMAIN: {
                        "command_topic": "command-topic",
                    }
                }
            },
            (
                {
                    "name": "test1",
                    "state_topic": "state-topic1",
                    "available_tones": ["ping", "siren", "bell"],
                    "support_duration": False,
                },
                {
                    "name": "test2",
                    "state_topic": "state-topic2",
                    "available_tones": ["ping", "siren", "bell"],
                    "support_volume_set": False,
                },
                {
                    "name": "test3",
                    "state_topic": "state-topic3",
                },
            ),
        )
    ],
)
async def test_filtering_not_supported_attributes_via_state(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test setting attributes with support flags via state."""
    await mqtt_mock_entry()

    state1 = hass.states.get("siren.test1")
    assert state1.state == STATE_UNKNOWN
    assert siren.ATTR_DURATION not in state1.attributes
    assert siren.ATTR_AVAILABLE_TONES in state1.attributes
    assert siren.ATTR_TONE in state1.attributes
    assert siren.ATTR_VOLUME_LEVEL in state1.attributes
    async_fire_mqtt_message(
        hass,
        "state-topic1",
        '{"state":"ON", "duration": 22, "tone": "ping", "volume_level": 0.88}',
    )
    await hass.async_block_till_done()
    state1 = hass.states.get("siren.test1")
    assert state1.attributes.get(siren.ATTR_TONE) == "ping"
    assert state1.attributes.get(siren.ATTR_DURATION) is None
    assert state1.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88

    state2 = hass.states.get("siren.test2")
    assert siren.ATTR_DURATION in state2.attributes
    assert siren.ATTR_AVAILABLE_TONES in state2.attributes
    assert siren.ATTR_TONE in state2.attributes
    assert siren.ATTR_VOLUME_LEVEL not in state2.attributes
    async_fire_mqtt_message(
        hass,
        "state-topic2",
        '{"state":"ON", "duration": 22, "tone": "ping", "volume_level": 0.88}',
    )
    await hass.async_block_till_done()
    state2 = hass.states.get("siren.test2")
    assert state2.attributes.get(siren.ATTR_TONE) == "ping"
    assert state2.attributes.get(siren.ATTR_DURATION) == 22
    assert state2.attributes.get(siren.ATTR_VOLUME_LEVEL) is None

    state3 = hass.states.get("siren.test3")
    assert siren.ATTR_DURATION in state3.attributes
    assert siren.ATTR_AVAILABLE_TONES not in state3.attributes
    assert siren.ATTR_TONE not in state3.attributes
    assert siren.ATTR_VOLUME_LEVEL in state3.attributes
    async_fire_mqtt_message(
        hass,
        "state-topic3",
        '{"state":"ON", "duration": 22, "tone": "ping", "volume_level": 0.88}',
    )
    await hass.async_block_till_done()
    state3 = hass.states.get("siren.test3")
    assert state3.attributes.get(siren.ATTR_TONE) is None
    assert state3.attributes.get(siren.ATTR_DURATION) == 22
    assert state3.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, siren.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            siren.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        }
    }
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry,
        siren.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            siren.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        }
    }

    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry,
        siren.DOMAIN,
        config,
        True,
        "state-topic",
        "1",
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "payload_on": 1,
                    "payload_off": 0,
                    "state_on": "HIGH",
                    "state_off": "LOW",
                }
            }
        }
    ],
)
async def test_custom_state_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the state payload."""
    await mqtt_mock_entry()

    state = hass.states.get("siren.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "HIGH")

    state = hass.states.get("siren.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "LOW")

    state = hass.states.get("siren.test")
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG, {}
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
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
        siren.DOMAIN,
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
        siren.DOMAIN,
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
        siren.DOMAIN,
        DEFAULT_CONFIG,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                siren.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "command_topic": "command-topic",
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
    """Test unique id option only creates one siren per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, siren.DOMAIN)


async def test_discovery_removal_siren(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered siren."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock_entry, caplog, siren.DOMAIN, data)


async def test_discovery_update_siren_topic_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered siren."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][siren.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][siren.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "siren/state1"
    config2["state_topic"] = "siren/state2"
    config1["state_value_template"] = "{{ value_json.state1.state }}"
    config2["state_value_template"] = "{{ value_json.state2.state }}"

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
        mqtt_mock_entry,
        caplog,
        siren.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


async def test_discovery_update_siren_template(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered siren."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][siren.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[mqtt.DOMAIN][siren.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "siren/state1"
    config2["state_topic"] = "siren/state1"
    config1["state_value_template"] = "{{ value_json.state1.state }}"
    config2["state_value_template"] = "{{ value_json.state2.state }}"

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
        mqtt_mock_entry,
        caplog,
        siren.DOMAIN,
        config1,
        config2,
        state_data1=state_data1,
        state_data2=state_data2,
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            siren.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "name": "Beer",
                    "available_tones": ["ping", "chimes"],
                    "command_template": "CMD: {{ value }}, DURATION: {{ duration }},"
                    " TONE: {{ tone }}, VOLUME: {{ volume_level }}",
                },
                {
                    "name": "Milk",
                    "available_tones": ["ping", "chimes"],
                    "command_template": "CMD: {{ value }}, DURATION: {{ duration }},"
                    " TONE: {{ tone }}, VOLUME: {{ volume_level }}",
                    "command_off_template": "CMD_OFF: {{ value }}",
                },
            ),
        )
    ],
)
async def test_command_templates(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test siren with command templates optimistic."""
    mqtt_mock = await mqtt_mock_entry()

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
    state1 = hass.states.get("siren.beer")
    assert state1.attributes.get(siren.ATTR_TONE) == "ping"
    assert state1.attributes.get(siren.ATTR_DURATION) == 22
    assert state1.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88

    mqtt_mock.async_publish.assert_any_call(
        "test-topic", "CMD: ON, DURATION: 22, TONE: ping, VOLUME: 0.88", 0, False
    )
    mqtt_mock.async_publish.call_count == 1
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

    await async_turn_on(
        hass,
        entity_id="siren.milk",
        parameters={
            siren.ATTR_DURATION: 22,
            siren.ATTR_TONE: "ping",
            ATTR_VOLUME_LEVEL: 0.88,
        },
    )
    state2 = hass.states.get("siren.milk")
    assert state2.attributes.get(siren.ATTR_TONE) == "ping"
    assert state2.attributes.get(siren.ATTR_DURATION) == 22
    assert state2.attributes.get(siren.ATTR_VOLUME_LEVEL) == 0.88
    await async_turn_off(
        hass,
        entity_id="siren.milk",
    )
    mqtt_mock.async_publish.assert_any_call("test-topic", "CMD_OFF: OFF", 0, False)
    mqtt_mock.async_publish.call_count == 1
    mqtt_mock.reset_mock()


async def test_discovery_update_unchanged_siren(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
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
            hass,
            mqtt_mock_entry,
            caplog,
            siren.DOMAIN,
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
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(
        hass, mqtt_mock_entry, caplog, siren.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT siren device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT siren device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, siren.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        siren.DOMAIN,
        DEFAULT_CONFIG,
        siren.SERVICE_TURN_ON,
        command_payload='{"state":"ON"}',
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            siren.SERVICE_TURN_ON,
            "command_topic",
            None,
            '{"state":"ON"}',
            None,
        ),
        (
            siren.SERVICE_TURN_OFF,
            "command_topic",
            None,
            '{"state":"OFF"}',
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
    """Test publishing MQTT payload with command templates and different encoding."""
    domain = siren.DOMAIN
    config = copy.deepcopy(DEFAULT_CONFIG)
    config[mqtt.DOMAIN][domain][siren.ATTR_AVAILABLE_TONES] = ["siren", "xylophone"]

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
    domain = siren.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "ON", None, "on"),
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
        siren.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][siren.DOMAIN],
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
    platform = siren.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test unloading the config entry."""
    domain = siren.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )
