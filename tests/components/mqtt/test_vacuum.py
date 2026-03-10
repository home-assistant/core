"""The tests for the State vacuum Mqtt platform."""

from copy import deepcopy
import json
from typing import Any
from unittest.mock import call, patch

import pytest

from homeassistant.components import mqtt, vacuum
from homeassistant.components.mqtt import vacuum as mqttvacuum
from homeassistant.components.mqtt.const import CONF_COMMAND_TOPIC, CONF_STATE_TOPIC
from homeassistant.components.mqtt.vacuum import (
    ALL_SERVICES,
    MQTT_VACUUM_ATTRIBUTES_BLOCKED,
    SERVICE_TO_STRING,
    services_to_strings,
)
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    ATTR_FAN_SPEED_LIST,
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_START,
    SERVICE_STOP,
    VacuumActivity,
)
from homeassistant.const import CONF_NAME, ENTITY_MATCH_ALL, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

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
    help_test_update_with_json_attrs_bad_json,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message
from tests.components.vacuum import common
from tests.typing import (
    MqttMockHAClientGenerator,
    MqttMockPahoClient,
    WebSocketGenerator,
)

COMMAND_TOPIC = "vacuum/command"
SEND_COMMAND_TOPIC = "vacuum/send_command"
STATE_TOPIC = "vacuum/state"

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        vacuum.DOMAIN: {
            CONF_NAME: "mqtttest",
            CONF_COMMAND_TOPIC: COMMAND_TOPIC,
            mqttvacuum.CONF_SEND_COMMAND_TOPIC: SEND_COMMAND_TOPIC,
            CONF_STATE_TOPIC: STATE_TOPIC,
            mqttvacuum.CONF_SET_FAN_SPEED_TOPIC: "vacuum/set_fan_speed",
            mqttvacuum.CONF_FAN_SPEED_LIST: ["min", "medium", "high", "max"],
        }
    }
}

CONFIG_CLEAN_SEGMENTS_1 = {
    mqtt.DOMAIN: {
        vacuum.DOMAIN: {
            "name": "test",
            "unique_id": "veryunique",
            "segments": ["Livingroom", "Kitchen"],
            "clean_segments_command_topic": "vacuum/clean_segment",
        }
    }
}
CONFIG_CLEAN_SEGMENTS_2 = {
    mqtt.DOMAIN: {
        vacuum.DOMAIN: {
            "name": "test",
            "unique_id": "veryunique",
            "segments": ["1.Livingroom", "2.Kitchen"],
            "clean_segments_command_topic": "vacuum/clean_segment",
        }
    }
}

DEFAULT_CONFIG_2 = {mqtt.DOMAIN: {vacuum.DOMAIN: {"name": "test"}}}

CONFIG_ALL_SERVICES = help_custom_config(
    vacuum.DOMAIN,
    DEFAULT_CONFIG,
    (
        {
            mqttvacuum.CONF_SUPPORTED_FEATURES: services_to_strings(
                mqttvacuum.ALL_SERVICES, SERVICE_TO_STRING
            )
        },
    ),
)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_default_supported_features(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that the correct supported features."""
    await mqtt_mock_entry()
    entity = hass.states.get("vacuum.mqtttest")
    entity_features = entity.attributes.get(mqttvacuum.CONF_SUPPORTED_FEATURES, 0)
    assert sorted(services_to_strings(entity_features, SERVICE_TO_STRING)) == sorted(
        ["start", "stop", "return_home", "clean_spot"]
    )


@pytest.mark.parametrize("hass_config", [CONFIG_ALL_SERVICES])
async def test_all_commands(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test simple commands send to the vacuum."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_START, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "start", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "stop", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "pause", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_called_once_with(COMMAND_TOPIC, "locate", 0, False)
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        SERVICE_CLEAN_SPOT,
        {"entity_id": ENTITY_MATCH_ALL},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        COMMAND_TOPIC, "clean_spot", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        SERVICE_RETURN_TO_BASE,
        {"entity_id": ENTITY_MATCH_ALL},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        COMMAND_TOPIC, "return_to_base", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "medium", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/set_fan_speed", "medium", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(hass, "44 FE 93", entity_id="vacuum.mqtttest")
    mqtt_mock.async_publish.assert_called_once_with(
        "vacuum/send_command", "44 FE 93", 0, False
    )
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(
        hass, "44 FE 93", {"key": "value"}, entity_id="vacuum.mqtttest"
    )
    assert json.loads(mqtt_mock.async_publish.mock_calls[-1][1][1]) == {
        "command": "44 FE 93",
        "key": "value",
    }


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            vacuum.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    mqttvacuum.CONF_SUPPORTED_FEATURES: services_to_strings(
                        mqttvacuum.STRING_TO_SERVICE["status"], SERVICE_TO_STRING
                    )
                },
            ),
        )
    ],
)
async def test_commands_without_supported_features(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test commands which are not supported by the vacuum."""
    mqtt_mock = await mqtt_mock_entry()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_START, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_PAUSE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_STOP, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        SERVICE_RETURN_TO_BASE,
        {"entity_id": ENTITY_MATCH_ALL},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN, SERVICE_LOCATE, {"entity_id": ENTITY_MATCH_ALL}, blocking=True
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        SERVICE_CLEAN_SPOT,
        {"entity_id": ENTITY_MATCH_ALL},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    with pytest.raises(HomeAssistantError):
        await common.async_set_fan_speed(hass, "medium", "vacuum.mqtttest")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    with pytest.raises(HomeAssistantError):
        await common.async_send_command(
            hass, "44 FE 93", {"key": "value"}, entity_id="vacuum.mqtttest"
        )
    mqtt_mock.async_publish.assert_not_called()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            "mqtt": {
                "vacuum": {
                    "name": "test",
                    mqttvacuum.CONF_SUPPORTED_FEATURES: services_to_strings(
                        ALL_SERVICES, SERVICE_TO_STRING
                    ),
                }
            }
        }
    ],
)
async def test_command_without_command_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test commands which are not supported by the vacuum."""
    mqtt_mock = await mqtt_mock_entry()

    await common.async_start(hass, "vacuum.test")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_set_fan_speed(hass, "low", "vacuum.test")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()

    await common.async_send_command(hass, "some command", entity_id="vacuum.test")
    mqtt_mock.async_publish.assert_not_called()
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize("hass_config", [CONFIG_CLEAN_SEGMENTS_1])
async def test_clean_segments_initial_setup_without_repair_issue(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test cleanable segments initial setup does not fire repair flow."""
    await mqtt_mock_entry()
    issue_registry = ir.async_get(hass)
    assert len(issue_registry.issues) == 0


@pytest.mark.parametrize("hass_config", [CONFIG_CLEAN_SEGMENTS_1])
async def test_clean_segments_command_without_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test cleanable segments without ID."""
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    entity_registry.async_get_or_create(
        vacuum.DOMAIN,
        mqtt.DOMAIN,
        "veryunique",
        config_entry=config_entry,
        suggested_object_id="test",
    )
    entity_registry.async_update_entity_options(
        "vacuum.test",
        vacuum.DOMAIN,
        {
            "area_mapping": {"Nabu Casa": ["Kitchen", "Livingroom"]},
            "last_seen_segments": [
                {"id": "Livingroom", "name": "Livingroom"},
                {"id": "Kitchen", "name": "Kitchen"},
            ],
        },
    )
    mqtt_mock = await mqtt_mock_entry()
    await hass.async_block_till_done()
    issue_registry = ir.async_get(hass)
    # We do not expect a repair flow
    assert len(issue_registry.issues) == 0

    state = hass.states.get("vacuum.test")
    assert state.state == STATE_UNKNOWN
    await common.async_clean_area(hass, ["Nabu Casa"], entity_id="vacuum.test")
    assert (
        call("vacuum/clean_segment", '["Kitchen","Livingroom"]', 0, False)
        in mqtt_mock.async_publish.mock_calls
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": "vacuum.test"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["segments"] == [
        {"id": "Livingroom", "name": "Livingroom", "group": None},
        {"id": "Kitchen", "name": "Kitchen", "group": None},
    ]


@pytest.mark.parametrize("hass_config", [CONFIG_CLEAN_SEGMENTS_2])
async def test_clean_segments_command_with_id(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test cleanable segments with ID."""
    mqtt_mock = await mqtt_mock_entry()
    # Set the area mapping
    entity_registry.async_update_entity_options(
        "vacuum.test",
        vacuum.DOMAIN,
        {
            "area_mapping": {"Livingroom": ["1"], "Kitchen": ["2"]},
            "last_seen_segments": [
                {"id": "1", "name": "Livingroom"},
                {"id": "2", "name": "Kitchen"},
            ],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("vacuum.test")
    assert state.state == STATE_UNKNOWN
    await common.async_clean_area(hass, ["Kitchen"], entity_id="vacuum.test")
    assert (
        call("vacuum/clean_segment", '["2"]', 0, False)
        in mqtt_mock.async_publish.mock_calls
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": "vacuum.test"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["segments"] == [
        {"id": "1", "name": "Livingroom", "group": None},
        {"id": "2", "name": "Kitchen", "group": None},
    ]


async def test_clean_segments_command_update(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test cleanable segments update via discovery."""
    # Prepare original entity config entry
    config_entry = hass.config_entries.async_entries(mqtt.DOMAIN)[0]
    entity_registry.async_get_or_create(
        vacuum.DOMAIN,
        mqtt.DOMAIN,
        "veryunique",
        config_entry=config_entry,
        suggested_object_id="test",
    )
    entity_registry.async_update_entity_options(
        "vacuum.test",
        vacuum.DOMAIN,
        {
            "area_mapping": {"Livingroom": ["1"], "Kitchen": ["2"]},
            "last_seen_segments": [
                {"id": "1", "name": "Livingroom"},
                {"id": "2", "name": "Kitchen"},
            ],
        },
    )
    await mqtt_mock_entry()
    # Do initial discovery
    config1 = CONFIG_CLEAN_SEGMENTS_2[mqtt.DOMAIN][vacuum.DOMAIN]
    payload1 = json.dumps(config1)
    config_topic = "homeassistant/vacuum/bla/config"
    async_fire_mqtt_message(hass, config_topic, payload1)
    await hass.async_block_till_done()
    state = hass.states.get("vacuum.test")
    assert state.state == STATE_UNKNOWN

    issue_registry = ir.async_get(hass)
    # We do not expect a repair flow
    assert len(issue_registry.issues) == 0

    # Update the segments
    config2 = config1.copy()
    config2["segments"] = ["1.Livingroom", "2.Kitchen", "3.Diningroom"]
    payload2 = json.dumps(config2)
    async_fire_mqtt_message(hass, config_topic, payload2)
    await hass.async_block_till_done()

    # A repair flow should start
    assert len(issue_registry.issues) == 1

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": "vacuum.test"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["segments"] == [
        {"id": "1", "name": "Livingroom", "group": None},
        {"id": "2", "name": "Kitchen", "group": None},
        {"id": "3", "name": "Diningroom", "group": None},
    ]

    # Test update with a non-unique segment list fails
    config3 = config1.copy()
    config3["segments"] = ["1.Livingroom", "2.Kitchen", "2.Diningroom"]
    payload3 = json.dumps(config3)
    async_fire_mqtt_message(hass, config_topic, payload3)
    await hass.async_block_till_done()
    assert (
        "Error 'The `segments` option contains an invalid or non-unique segment ID '2'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                vacuum.DOMAIN: {
                    "name": "test",
                    "unique_id": "veryunique",
                    "segments": ["Livingroom", "Kitchen", "Kitchen"],
                    "clean_segments_command_topic": "vacuum/clean_segment",
                }
            }
        },
        {
            mqtt.DOMAIN: {
                vacuum.DOMAIN: {
                    "name": "test",
                    "unique_id": "veryunique",
                    "segments": ["Livingroom", "Kitchen", ""],
                    "clean_segments_command_topic": "vacuum/clean_segment",
                }
            }
        },
        {
            mqtt.DOMAIN: {
                vacuum.DOMAIN: {
                    "name": "test",
                    "unique_id": "veryunique",
                    "segments": ["1.Livingroom", "1.Kitchen"],
                    "clean_segments_command_topic": "vacuum/clean_segment",
                }
            }
        },
        {
            mqtt.DOMAIN: {
                vacuum.DOMAIN: {
                    "name": "test",
                    "unique_id": "veryunique",
                    "segments": ["1.Livingroom", "1.Kitchen", ".Diningroom"],
                    "clean_segments_command_topic": "vacuum/clean_segment",
                }
            }
        },
    ],
)
async def test_non_unique_segments(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test with non-unique list of cleanable segments with valid segment IDs."""
    await mqtt_mock_entry()
    assert (
        "The `segments` option contains an invalid or non-unique segment ID"
        in caplog.text
    )


@pytest.mark.usefixtures("hass")
@pytest.mark.parametrize(
    ("hass_config", "error_message"),
    [
        (
            help_custom_config(
                vacuum.DOMAIN,
                DEFAULT_CONFIG,
                ({"clean_segments_command_topic": "test-topic"},),
            ),
            "Options `segments` and "
            "`clean_segments_command_topic` must be defined together",
        ),
        (
            help_custom_config(
                vacuum.DOMAIN,
                DEFAULT_CONFIG,
                ({"segments": ["Livingroom"]},),
            ),
            "Options `segments` and "
            "`clean_segments_command_topic` must be defined together",
        ),
        (
            help_custom_config(
                vacuum.DOMAIN,
                DEFAULT_CONFIG,
                (
                    {
                        "segments": ["Livingroom"],
                        "clean_segments_command_topic": "test-topic",
                    },
                ),
            ),
            "Option `segments` requires `unique_id` to be configured",
        ),
    ],
)
async def test_clean_segments_config_validation(
    mqtt_mock_entry: MqttMockHAClientGenerator,
    error_message: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test status clean segment config validation."""
    await mqtt_mock_entry()
    assert error_message in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            vacuum.DOMAIN,
            CONFIG_CLEAN_SEGMENTS_2,
            ({"clean_segments_command_template": "{{ ';'.join(value) }}"},),
        )
    ],
)
async def test_clean_segments_command_with_id_and_command_template(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test clean segments with command template."""
    mqtt_mock = await mqtt_mock_entry()
    entity_registry.async_update_entity_options(
        "vacuum.test",
        vacuum.DOMAIN,
        {
            "area_mapping": {"Livingroom": ["1"], "Kitchen": ["2"]},
            "last_seen_segments": [
                {"id": "1", "name": "Livingroom"},
                {"id": "2", "name": "Kitchen"},
            ],
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("vacuum.test")
    assert state.state == STATE_UNKNOWN
    await common.async_clean_area(
        hass, ["Livingroom", "Kitchen"], entity_id="vacuum.test"
    )
    assert (
        call("vacuum/clean_segment", "1;2", 0, False)
        in mqtt_mock.async_publish.mock_calls
    )

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": "vacuum.test"}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["segments"] == [
        {"id": "1", "name": "Livingroom", "group": None},
        {"id": "2", "name": "Kitchen", "group": None},
    ]


@pytest.mark.parametrize("hass_config", [CONFIG_ALL_SERVICES])
async def test_status(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test status updates from the vacuum."""
    await mqtt_mock_entry()
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN

    message = """{
        "battery_level": 54,
        "state": "cleaning",
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == VacuumActivity.CLEANING
    assert state.attributes.get(ATTR_FAN_SPEED) == "max"

    message = """{
        "battery_level": 61,
        "state": "docked",
        "fan_speed": "min"
    }"""

    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == VacuumActivity.DOCKED
    assert state.attributes.get(ATTR_FAN_SPEED) == "min"
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) == ["min", "medium", "high", "max"]

    message = '{"state":null}'
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            vacuum.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    mqttvacuum.CONF_SUPPORTED_FEATURES: services_to_strings(
                        mqttvacuum.DEFAULT_SERVICES
                        | vacuum.VacuumEntityFeature.BATTERY,
                        SERVICE_TO_STRING,
                    )
                },
            ),
        )
    ],
)
async def test_no_fan_vacuum(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test status updates from the vacuum when fan is not supported."""
    await mqtt_mock_entry()

    message = """{
        "battery_level": 54,
        "state": "cleaning"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == VacuumActivity.CLEANING
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None

    message = """{
        "battery_level": 54,
        "state": "cleaning",
        "fan_speed": "max"
    }"""
    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")

    assert state.state == VacuumActivity.CLEANING
    assert state.attributes.get(ATTR_FAN_SPEED) is None
    assert state.attributes.get(ATTR_FAN_SPEED_LIST) is None

    message = """{
        "battery_level": 61,
        "state": "docked"
    }"""

    async_fire_mqtt_message(hass, "vacuum/state", message)
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == VacuumActivity.DOCKED


@pytest.mark.parametrize("hass_config", [CONFIG_ALL_SERVICES])
@pytest.mark.no_fail_on_log_exception
async def test_status_invalid_json(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test to make sure nothing breaks if the vacuum sends bad JSON."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "vacuum/state", '{"asdfasas false}')
    state = hass.states.get("vacuum.mqtttest")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG_2])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, vacuum.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG_2])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        vacuum.DOMAIN,
        DEFAULT_CONFIG_2,
        MQTT_VACUUM_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                vacuum.DOMAIN: [
                    {
                        "name": "Test 1",
                        "command_topic": "command-topic",
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
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
    """Test unique id option only creates one vacuum per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, vacuum.DOMAIN)


async def test_discovery_removal_vacuum(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered vacuum."""
    data = '{"name": "test", "command_topic": "test_topic"}'
    await help_test_discovery_removal(hass, mqtt_mock_entry, vacuum.DOMAIN, data)


async def test_discovery_update_vacuum(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered vacuum."""
    config1 = {"name": "Beer", "command_topic": "test_topic"}
    config2 = {"name": "Milk", "command_topic": "test_topic"}
    await help_test_discovery_update(
        hass, mqtt_mock_entry, vacuum.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_vacuum(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test update of discovered vacuum."""
    data1 = '{"name": "Beer", "command_topic": "test_topic"}'
    with patch(
        "homeassistant.components.mqtt.vacuum.MqttStateVacuum.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, vacuum.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{"name": "Beer", "command_topic": "test_topic#"}'
    data2 = '{"name": "Milk", "command_topic": "test_topic"}'
    await help_test_discovery_broken(hass, mqtt_mock_entry, vacuum.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT vacuum device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, vacuum.DOMAIN, DEFAULT_CONFIG_2
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        vacuum.DOMAIN,
        DEFAULT_CONFIG_2,
        vacuum.SERVICE_START,
        command_payload="start",
        state_payload="{}",
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (vacuum.SERVICE_START, "command_topic", None, "start", None),
        (vacuum.SERVICE_CLEAN_SPOT, "command_topic", None, "clean_spot", None),
        (
            vacuum.SERVICE_SET_FAN_SPEED,
            "set_fan_speed_topic",
            {"fan_speed": "medium"},
            "medium",
            None,
        ),
        (
            vacuum.SERVICE_SEND_COMMAND,
            "send_command_topic",
            {"command": "custom command"},
            "custom command",
            None,
        ),
        (vacuum.SERVICE_STOP, "command_topic", None, "stop", None),
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
    domain = vacuum.DOMAIN
    config = deepcopy(DEFAULT_CONFIG)
    config[mqtt.DOMAIN][domain]["supported_features"] = [
        "clean_spot",
        "fan_speed",
        "locate",
        "pause",
        "return_home",
        "send_command",
        "start",
        "status",
        "stop",
    ]

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
    domain = vacuum.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        (
            "state_topic",
            '{"battery_level": 61, "state": "docked", "fan_speed": "off"}',
            None,
            "docked",
        ),
        (
            "state_topic",
            '{"battery_level": 61, "state": "cleaning", "fan_speed": "medium"}',
            None,
            "cleaning",
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
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry,
        vacuum.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][vacuum.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
        skip_raw_test=True,
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
    platform = vacuum.DOMAIN
    assert hass.states.get(f"{platform}.mqtttest")


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            vacuum.DOMAIN,
            DEFAULT_CONFIG,
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
        ("vacuum/state", '{"state": "cleaning"}', '{"state": "docked"}'),
        ("vacuum/state", '{"fan_speed": "max"}', '{"fan_speed": "min"}'),
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
