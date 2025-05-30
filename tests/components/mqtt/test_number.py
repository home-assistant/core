"""The tests for mqtt number component."""

import json
from typing import Any
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
)
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_DEVICE_CLASS,
    ATTR_ENTITY_ID,
    ATTR_MODE,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

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
    help_test_entity_icon_and_entity_picture,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_entity_name,
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

from tests.common import async_fire_mqtt_message, mock_restore_cache_with_extra_data
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {number.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


@pytest.mark.parametrize(
    ("hass_config", "device_class", "unit_of_measurement", "values"),
    [
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "device_class": "temperature",
                        "unit_of_measurement": UnitOfTemperature.FAHRENHEIT.value,
                        "payload_reset": "reset!",
                    }
                }
            },
            "temperature",
            UnitOfTemperature.CELSIUS.value,
            [("10", "-12.0"), ("20.5", "-6.4")],  # 10 °F -> -12 °C
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "device_class": "temperature",
                        "unit_of_measurement": UnitOfTemperature.CELSIUS.value,
                        "payload_reset": "reset!",
                    }
                }
            },
            "temperature",
            UnitOfTemperature.CELSIUS.value,
            [("10", "10"), ("15", "15")],
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "device_class": None,
                        "unit_of_measurement": None,
                        "payload_reset": "reset!",
                    }
                }
            },
            None,
            None,
            [("10", "10"), ("20", "20")],
        ),
    ],
)
async def test_run_number_setup(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    device_class: str | None,
    unit_of_measurement: UnitOfTemperature | None,
    values: list[tuple[str, str]],
) -> None:
    """Test that it fetches the given payload."""
    await mqtt_mock_entry()

    for payload, value in values:
        async_fire_mqtt_message(hass, "test/state_number", payload)

        await hass.async_block_till_done()

        state = hass.states.get("number.test_number")
        assert state.state == value
        assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
        assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement

    async_fire_mqtt_message(hass, "test/state_number", "reset!")

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "unknown"
    assert state.attributes.get(ATTR_DEVICE_CLASS) == device_class
    assert state.attributes.get(ATTR_UNIT_OF_MEASUREMENT) == unit_of_measurement


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                    "min": 15,
                    "max": 28,
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.CELSIUS.value,
                }
            }
        }
    ],
)
async def test_native_value_validation(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state validation and native value conversion."""
    mqtt_mock = await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test/state_number", "23.5")
    state = hass.states.get("number.test_number")
    assert state is not None
    assert state.attributes.get(ATTR_MIN) == 15
    assert state.attributes.get(ATTR_MAX) == 28
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfTemperature.CELSIUS.value
    )
    assert state.state == "23.5"

    # Test out of range validation
    async_fire_mqtt_message(hass, "test/state_number", "29.5")
    state = hass.states.get("number.test_number")
    assert state is not None
    assert state.attributes.get(ATTR_MIN) == 15
    assert state.attributes.get(ATTR_MAX) == 28
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfTemperature.CELSIUS.value
    )
    assert state.state == "23.5"
    assert (
        "Invalid value for number.test_number: 29.5 (range 15.0 - 28.0)" in caplog.text
    )
    caplog.clear()

    # Check if validation still works when changing unit system
    hass.config.units = US_CUSTOMARY_SYSTEM
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "test/state_number", "24.5")
    state = hass.states.get("number.test_number")
    assert state is not None
    assert state.attributes.get(ATTR_MIN) == 59.0
    assert state.attributes.get(ATTR_MAX) == 82.4
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfTemperature.FAHRENHEIT.value
    )
    assert state.state == "76.1"

    # Test out of range validation again
    async_fire_mqtt_message(hass, "test/state_number", "29.5")
    state = hass.states.get("number.test_number")
    assert state is not None
    assert state.attributes.get(ATTR_MIN) == 59.0
    assert state.attributes.get(ATTR_MAX) == 82.4
    assert (
        state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        == UnitOfTemperature.FAHRENHEIT.value
    )
    assert state.state == "76.1"
    assert (
        "Invalid value for number.test_number: 29.5 (range 15.0 - 28.0)" in caplog.text
    )
    caplog.clear()

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: "number.test_number", ATTR_VALUE: 68},
        blocking=True,
    )

    mqtt_mock.async_publish.assert_called_once_with("test/cmd_number", "20", 0, False)
    mqtt_mock.async_publish.reset_mock()


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                    "value_template": "{{ value_json.val }}",
                }
            }
        }
    ],
)
async def test_value_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that it fetches the given payload with a template."""
    topic = "test/state_number"
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, topic, '{"val":10}')

    await hass.async_block_till_done()

    state = hass.states.get("number.test_number")
    assert state.state == "10"

    # Assert an empty value from a template is ignored
    async_fire_mqtt_message(hass, topic, '{"other_val":12}')

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": "test/number",
                    "device_class": "temperature",
                    "unit_of_measurement": UnitOfTemperature.FAHRENHEIT.value,
                    "name": "Test Number",
                }
            }
        }
    ],
)
async def test_restore_native_value(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that the stored native_value is restored."""

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
    await mqtt_mock_entry()

    state = hass.states.get("number.test_number")
    assert state.state == "37.8"
    assert state.attributes.get(ATTR_ASSUMED_STATE)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": "test/number",
                    "name": "Test Number",
                }
            }
        }
    ],
)
async def test_run_number_service_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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

    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": "test/number",
                    "name": "Test Number",
                    "command_template": '{"number": {{ value }} }',
                }
            }
        }
    ],
)
async def test_run_number_service_optimistic_with_command_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": "test/number/set",
                    "state_topic": "test/number",
                    "name": "Test Number",
                }
            }
        }
    ],
)
async def test_run_number_service(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in non optimistic mode."""
    cmd_topic = "test/number/set"
    state_topic = "test/number"

    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "command_topic": "test/number/set",
                    "state_topic": "test/number",
                    "name": "Test Number",
                    "command_template": '{"number": {{ value }} }',
                }
            }
        }
    ],
)
async def test_run_number_service_with_command_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test that set_value service works in non optimistic mode and with a command_template."""
    cmd_topic = "test/number/set"
    state_topic = "test/number"

    mqtt_mock = await mqtt_mock_entry()

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


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, number.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        number.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_NUMBER_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
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
    ],
)
async def test_unique_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unique id option only creates one number per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, number.DOMAIN)


async def test_discovery_removal_number(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered number."""
    data = json.dumps(DEFAULT_CONFIG[mqtt.DOMAIN][number.DOMAIN])
    await help_test_discovery_removal(hass, mqtt_mock_entry, number.DOMAIN, data)


async def test_discovery_update_number(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
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
        hass, mqtt_mock_entry, number.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_number(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered number."""
    data1 = (
        '{ "name": "Beer", "state_topic": "test-topic", "command_topic": "test-topic"}'
    )
    with patch(
        "homeassistant.components.mqtt.number.MqttNumber.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, number.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk", "state_topic": "test-topic", "command_topic": "test-topic"}'
    )

    await help_test_discovery_broken(hass, mqtt_mock_entry, number.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT number device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, number.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass,
        mqtt_mock_entry,
        number.DOMAIN,
        DEFAULT_CONFIG,
        SERVICE_SET_VALUE,
        service_parameters={ATTR_VALUE: 45},
        command_payload="45",
        state_payload="1",
    )


@pytest.mark.parametrize(
    ("hass_config", "min_number", "max_number", "step"),
    [
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "min": 5,
                        "max": 110,
                        "step": 20,
                    }
                }
            },
            5,
            110,
            20,
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "min": 100,
                        "max": 100,
                    }
                }
            },
            100,
            100,
            1,
        ),
    ],
)
async def test_min_max_step_attributes(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    min_number: float,
    max_number: float,
    step: float,
) -> None:
    """Test min/max/step attributes."""
    await mqtt_mock_entry()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MIN) == min_number
    assert state.attributes.get(ATTR_MAX) == max_number
    assert state.attributes.get(ATTR_STEP) == step


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                    "min": 35,
                    "max": 10,
                }
            }
        }
    ],
)
async def test_invalid_min_max_attributes(
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test invalid min/max attributes."""
    assert await mqtt_mock_entry()
    assert f"{CONF_MAX} must be >= {CONF_MIN}" in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                }
            }
        }
    ],
)
async def test_default_mode(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test default mode."""
    await mqtt_mock_entry()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MODE) == "auto"


@pytest.mark.parametrize(
    ("hass_config", "mode"),
    [
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "mode": "auto",
                    }
                }
            },
            "auto",
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "mode": "box",
                    }
                }
            },
            "box",
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "mode": "slider",
                    }
                }
            },
            "slider",
        ),
    ],
)
async def test_mode(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    mode: str,
) -> None:
    """Test mode."""
    await mqtt_mock_entry()

    state = hass.states.get("number.test_number")
    assert state.attributes.get(ATTR_MODE) == mode


@pytest.mark.parametrize(
    ("hass_config", "valid"),
    [
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "mode": "bleh",
                    }
                }
            },
            False,
        ),
        (
            {
                mqtt.DOMAIN: {
                    number.DOMAIN: {
                        "state_topic": "test/state_number",
                        "command_topic": "test/cmd_number",
                        "name": "Test Number",
                        "mode": "auto",
                    }
                }
            },
            True,
        ),
    ],
)
async def test_invalid_mode(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    valid: bool,
) -> None:
    """Test invalid mode."""
    await mqtt_mock_entry()
    state = hass.states.get("number.test_number")
    assert (state is not None) == valid


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                }
            }
        }
    ],
)
async def test_mqtt_payload_not_a_number_warning(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test warning for MQTT payload which is not a number."""
    topic = "test/state_number"

    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, topic, "not_a_number")

    await hass.async_block_till_done()

    assert "Payload 'not_a_number' is not a Number" in caplog.text


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                number.DOMAIN: {
                    "state_topic": "test/state_number",
                    "command_topic": "test/cmd_number",
                    "name": "Test Number",
                    "min": 5,
                    "max": 110,
                }
            }
        }
    ],
)
async def test_mqtt_payload_out_of_range_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test error when MQTT payload is out of min/max range."""
    topic = "test/state_number"

    await hass.async_block_till_done()
    await mqtt_mock_entry()

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
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    service: str,
    topic: str,
    parameters: dict[str, Any],
    payload: str,
    template: str | None,
) -> None:
    """Test publishing MQTT payload with different encoding."""
    domain = NUMBER_DOMAIN
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
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "10", None, "10"),
        ("state_topic", "60", None, "60"),
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
        number.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][number.DOMAIN],
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
    platform = number.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    ("expected_friendly_name", "device_class"),
    [("test", None), ("Humidity", "humidity"), ("Temperature", "temperature")],
)
async def test_entity_name(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    expected_friendly_name: str | None,
    device_class: str | None,
) -> None:
    """Test the entity name setup."""
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_entity_name(
        hass, mqtt_mock_entry, domain, config, expected_friendly_name, device_class
    )


async def test_entity_icon_and_entity_picture(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test the entity icon or picture setup."""
    domain = number.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_entity_icon_and_entity_picture(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            number.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "availability_topic": "availability-topic",
                    "json_attributes_topic": "json-attributes-topic",
                    "state_topic": "test-topic",
                },
            ),
        )
    ],
)
@pytest.mark.parametrize(
    ("topic", "payload1", "payload2"),
    [
        ("test-topic", "10", "20.7"),
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
        help_custom_config(
            number.DOMAIN,
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
