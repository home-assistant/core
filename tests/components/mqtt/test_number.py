"""The tests for mqtt number component."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from homeassistant.components import mqtt, number
from homeassistant.components.mqtt.number import (
    CONF_MAX,
    CONF_MIN,
    MQTT_NUMBER_ATTRIBUTES_BLOCKED,
)
from homeassistant.components.number import (
    ATTR_MAX,
    ATTR_MIN,
    ATTR_STEP,
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
    NumberDeviceClass,
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_UNIT_OF_MEASUREMENT,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
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

from tests.common import async_fire_mqtt_message, mock_restore_cache_with_extra_data
from tests.typing import MqttMockHAClientGenerator

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {number.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


@pytest.fixture(autouse=True)
def number_platform_only():
    """Only setup the number platform to speed up tests."""
    with patch("homeassistant.components.mqtt.PLATFORMS", [Platform.NUMBER]):
        yield


async def test_run_number_setup(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    "payload_reset": "reset!",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, topic, "10")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "-12.0"  # 10 °F -> -12 °C
    assert state.attributes.get(ATTR_DEVICE_CLASS) == NumberDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "°C"

    async_fire_mqtt_message(hass, topic, "20.5")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "-6.4"  # 20.5 °F -> -6.4 °C
    assert state.attributes.get(ATTR_DEVICE_CLASS) == NumberDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "°C"

    async_fire_mqtt_message(hass, topic, "reset!")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "unknown"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == NumberDeviceClass.TEMPERATURE
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == "°C"


async def test_value_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload with a template."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "value_template": "{{ value_json.val }}",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, topic, '{"val":10}')

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "10"

    async_fire_mqtt_message(hass, topic, '{"val":20.5}')

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "20.5"

    async_fire_mqtt_message(hass, topic, '{"val":null}')

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "unknown"


async def test_restore_native_value(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that the stored native_value is restored."""
    topic = "test/number"

    RESTORE_DATA = {
        "native_max_value": None,  # Ignored by MQTT number
        "native_min_value": None,  # Ignored by MQTT number
        "native_step": None,  # Ignored by MQTT number
        "native_unit_of_measurement": None,  # Ignored by MQTT number
        "native_value": 100.0,
    }

    mock_restore_cache_with_extra_data(
        hass, ((State("number.test_number", "abc"), RESTORE_DATA),)
    )
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": topic,
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.FAHRENHEIT,
                    "name": "Test Number",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.state == "37.8"
    assert state.attributes.get(ATTR_ASSUMED_STATE)


async def test_run_number_service_optimistic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in optimistic mode."""
    topic = "test/number"

    RESTORE_DATA = {
        "native_max_value": None,  # Ignored by MQTT number
        "native_min_value": None,  # Ignored by MQTT number
        "native_step": None,  # Ignored by MQTT number
        "native_unit_of_measurement": None,  # Ignored by MQTT number
        "native_value": 3,
    }

    mock_restore_cache_with_extra_data(
        hass, ((State("number.test_number", "abc"), RESTORE_DATA),)
    )
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": topic,
                    "name": "Test Number",
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.state == "3"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # Integer
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 30},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, "30", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "30"

    # Float with no decimal -> integer
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 42.0},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, "42", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "42"

    # Float with decimal -> float
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 42.1},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, "42.1", 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "42.1"


async def test_run_number_service_optimistic_with_command_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in optimistic mode and with a command_template."""
    topic = "test/number"

    RESTORE_DATA = {
        "native_max_value": None,  # Ignored by MQTT number
        "native_min_value": None,  # Ignored by MQTT number
        "native_step": None,  # Ignored by MQTT number
        "native_unit_of_measurement": None,  # Ignored by MQTT number
        "native_value": 3,
    }

    mock_restore_cache_with_extra_data(
        hass, ((State("number.test_number", "abc"), RESTORE_DATA),)
    )
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": topic,
                    "name": "Test Number",
                    "command_template": '{"number": {{ value }} }',
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.state == "3"
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    # Integer
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 30},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, '{"number": 30 }', 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "30"

    # Float with no decimal -> integer
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 42.0},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(topic, '{"number": 42 }', 0, False)
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "42"

    # Float with decimal -> float
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 42.1},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with(
        topic, '{"number": 42.1 }', 0, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("number.test_number")
    assert state.state == "42.1"


async def test_run_number_service(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in non optimistic mode."""
    cmd_topic = "test/number/set"
    state_topic = "test/number"

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": cmd_topic,
                    "state_topic": state_topic,
                    "name": "Test Number",
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, state_topic, "32")
    state = hass.states.get("number.test_number")
    assert state.state == "32"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 30},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(cmd_topic, "30", 0, False)
    state = hass.states.get("number.test_number")
    assert state.state == "32"


async def test_run_number_service_with_command_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in non optimistic mode and with a command_template."""
    cmd_topic = "test/number/set"
    state_topic = "test/number"

    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": cmd_topic,
                    "state_topic": state_topic,
                    "name": "Test Number",
                    "command_template": '{"number": {{ value }} }',
                }
            }
        },
    )
    await hass.async_block_till_done()
    mqtt_mock = await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, state_topic, "32")
    state = hass.states.get("number.test_number")
    assert state.state == "32"

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 30},
        blocking=True,
    )
    mqtt_mock.async_publish.assert_called_once_with(
        cmd_topic, '{"number": 30 }', 0, False
    )
    state = hass.states.get("number.test_number")
    assert state.state == "32"


async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        number.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_NUMBER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
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
        number.DOMAIN,
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
        number.DOMAIN,
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
        number.DOMAIN,
        DEFAULT_CONFIG,
    )


async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one number per unique_id."""
    config = {
        mqtt.DOMAIN: {
            number.DOMAIN: [
                {
                    "name": "Test 1",
                    "state_topic": "test-topic",
                    "command_topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
                {
                    "name": "Test 2",
                    "state_topic": "test-topic",
                    "command_topic": "test-topic",
                    "unique_id": "TOTALLY_UNIQUE",
                },
            ]
        }
    }
    await help_test_unique_id(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, config
    )


async def test_discovery_removal_number(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test removal of discovered number."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][number.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock_entry_no_yaml_config, caplog, number.DOMAIN, data
    )


async def test_discovery_update_number(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered number."""
    config1 = {
        "name": "Beer",
        "state_topic": "test-topic",
        "command_topic": "test-topic",
    }
    config2 = {
        "name": "Milk",
        "state_topic": "test-topic",
        "command_topic": "test-topic",
    }

    await help_test_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, caplog, number.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_number(
    hass: HomeAssistant,
    mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test update of discovered number."""
    data1 = (
        '{ "name": "Beer", "state_topic": "test-topic", "command_topic": "test-topic"}'
    )
    with patch(
        "homeassistant.components.mqtt.number.MqttNumber.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass,
            mqtt_mock_entry_no_yaml_config,
            caplog,
            number.DOMAIN,
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
    data2 = (
        '{ "name": "Milk", "state_topic": "test-topic", "command_topic": "test-topic"}'
    )

    await help_test_discovery_broken(
        hass, mqtt_mock_entry_no_yaml_config, caplog, number.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry_no_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry_no_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry_no_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry_no_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry_with_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry_no_yaml_config, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry_no_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry_no_yaml_config,
        number.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_SET_VALUE,
        service_parameters={ATTR_VALUE: 45},
        command_payload="45",
        state_payload="1",
    )


async def test_min_max_step_attributes(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test min/max/step attributes."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "min": 5,
                    "max": 110,
                    "step": 20,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MIN) == 5
    assert state.attributes.get(ATTR_MAX) == 110
    assert state.attributes.get(ATTR_STEP) == 20


async def test_invalid_min_max_attributes(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test invalid min/max attributes."""
    topic = "test/number"
    assert not await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "min": 35,
                    "max": 10,
                }
            }
        },
    )

    assert f"'{CONF_MAX}' must be > '{CONF_MIN}'" in caplog.text


async def test_default_mode(
    hass: HomeAssistant, mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator
) -> None:
    """Test default mode."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MODE) == "auto"


@pytest.mark.parametrize("mode", ("auto", "box", "slider"))
async def test_mode(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    mode,
) -> None:
    """Test mode."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "mode": mode,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MODE) == mode


@pytest.mark.parametrize(("mode", "valid"), [("bleh", False), ("auto", True)])
async def test_invalid_mode(hass: HomeAssistant, mode, valid) -> None:
    """Test invalid mode."""
    topic = "test/number"
    assert (
        await async_setup_component(
            hass,
            mqtt.DOMAIN,
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": topic,
                        "command_topic": topic,
                        "name": "Test Number",
                        "mode": mode,
                    }
                }
            },
        )
        is valid
    )


async def test_mqtt_payload_not_a_number_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test warning for MQTT payload which is not a number."""
    topic = "test/number"
    assert await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, topic, "not_a_number")

    await hass.async_block_till_done()

    assert "Payload 'not_a_number' is not a Number" in caplog.text


async def test_mqtt_payload_out_of_range_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
) -> None:
    """Test error when MQTT payload is out of min/max range."""
    topic = "test/number"
    await async_setup_component(
        hass,
        mqtt.DOMAIN,
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": topic,
                    "command_topic": topic,
                    "name": "Test Number",
                    "min": 5,
                    "max": 110,
                }
            }
        },
    )
    await hass.async_block_till_done()
    await mqtt_mock_entry_with_yaml_config()

    async_fire_mqtt_message(hass, topic, "115.5")

    await hass.async_block_till_done()

    assert (
        "Invalid value for number.test_number: 115.5 (range 5.0 - 110.0)" in caplog.text
    )


@pytest.mark.parametrize(
    ("service", "topic", "parameters", "payload", "template"),
    [
        (
            SERVICE_SET_VALUE,
            "command_topic",
            {ATTR_VALUE: "45"},
            45,
            "command_template",
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
    domain = NUMBER_DOMAIN
    config = DEFAULT_CONFIG

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
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(
        hass, mqtt_mock_entry_with_yaml_config, caplog, tmp_path, domain, config
    )


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "10", None, "10"),
        ("state_topic", "60", None, "60"),
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
    await help_test_encoding_subscribable_topics(
        hass,
        mqtt_mock_entry_with_yaml_config,
        caplog,
        number.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][number.DOMAIN],
        topic,
        value,
        attribute,
        attribute_value,
    )


async def test_setup_manual_entity_from_yaml(hass: HomeAssistant) -> None:
    """Test setup manual configured MQTT entity."""
    platform = number.DOMAIN
    await help_test_setup_manual_entity_from_yaml(hass, DEFAULT_CONFIG)
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant,
    mqtt_mock_entry_with_yaml_config: MqttMockHAClientGenerator,
    tmp_path: Path,
) -> None:
    """Test unloading the config entry."""
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry_with_yaml_config, tmp_path, domain, config
    )
