"""The tests for the MQTT datetime platform."""

import datetime as datetime_lib
from typing import Any
from unittest.mock import patch

from dateutil.tz import UTC
from freezegun import freeze_time
import pytest

from homeassistant.components import datetime, mqtt
from homeassistant.const import ATTR_ASSUMED_STATE, ATTR_ENTITY_ID, STATE_UNKNOWN
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
    mqtt.DOMAIN: {datetime.DOMAIN: {"name": "test", "command_topic": "test-topic"}}
}


async def async_set_value(
    hass: HomeAssistant, entity_id: str, value: datetime_lib.datetime | None
) -> None:
    """Set date and time value."""
    await hass.services.async_call(
        datetime.DOMAIN,
        datetime.SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, datetime.ATTR_DATETIME: value},
        blocking=True,
    )


@freeze_time("2026-04-24T12:52:00+00:00")
@pytest.mark.parametrize(
    ("hass_config", "update_state"),
    [
        (
            {
                mqtt.DOMAIN: {
                    datetime.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                    }
                }
            },
            (
                ("1/12/2025 3:00 +00:00", "2025-01-12T03:00:00+00:00"),
                ("2025-12-02 03:12:10 +00:00", "2025-12-02T03:12:10+00:00"),
                ("2025-05-02 03:12:10 +0000", "2025-05-02T03:12:10+00:00"),
            ),
        ),
        (
            {
                mqtt.DOMAIN: {
                    datetime.DOMAIN: {
                        "name": "test",
                        "state_topic": "state-topic",
                        "command_topic": "command-topic",
                        "timezone": "Europe/Amsterdam",
                    }
                }
            },
            (
                ("1/12/2025 4:00", "2025-01-12T03:00:00+00:00"),
                ("2025-04-02 04:12:10", "2025-04-02T02:12:10+00:00"),
                ("2025-05-02 05:12:10", "2025-05-02T03:12:10+00:00"),
            ),
        ),
    ],
    ids=["update_with_tz", "tz_offset_7200"],
)
async def test_controlling_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    update_state: tuple[tuple[str, str],],
) -> None:
    """Test the controlling state via topic."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()
    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    for update, state_update in update_state:
        async_fire_mqtt_message(hass, "state-topic", update)
        state = hass.states.get("datetime.test")
        assert state.state == state_update

    async_fire_mqtt_message(hass, "state-topic", "None")
    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN

    # Empty string should be ignored
    caplog.clear()
    async_fire_mqtt_message(hass, "state-topic", "")
    assert "Ignoring empty state payload" in caplog.text

    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN

    # Invalid value should show warning
    caplog.clear()
    async_fire_mqtt_message(hass, "state-topic", "No valid date/time")
    assert "Invalid received date/time expression" in caplog.text


@freeze_time("2026-04-01T10:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                datetime.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "timezone": "Europe/London",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    ("received_state", "expected_state"),
    [
        ("1 March 2025", "2025-03-01T00:00:00+00:00"),
        ("2025.03.01", "2025-03-01T00:00:00+00:00"),
        # If only time is parsed the current data is attached
        ("00:05:10", "2026-03-31T23:05:10+00:00"),
    ],
)
async def test_controlling_validation_state_via_topic(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    received_state: str,
    expected_state: str,
) -> None:
    """Test the validation of a received state."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", received_state)
    state = hass.states.get("datetime.test")
    assert state.state == expected_state


@freeze_time("2026-04-01T10:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                datetime.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "timezone": "Europe/London",
                }
            }
        }
    ],
)
@pytest.mark.parametrize(
    "received_state",
    [
        "2025-03-01T00:00:00+00:00",
        "2025-03-01 00:00:00 +0000",
        "1 March 2025 00:00:00 +0000",
    ],
)
async def test_ambiguous_date_time_state_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator, received_state: str
) -> None:
    """Test the where the state has a timezone and a timezone is defined."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN

    async_fire_mqtt_message(hass, "state-topic", received_state)
    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                datetime.DOMAIN: {
                    "name": "test",
                    "state_topic": "state-topic",
                    "command_topic": "command-topic",
                    "timezone": "Invalid",
                }
            }
        }
    ],
)
async def test_date_time_with_invalid_timezone_identifier(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test config with an invalid zimezone identifier."""
    await mqtt_mock_entry()
    await hass.async_block_till_done()

    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN

    assert (
        "Ignoring invalid timezone identifier for entity datetime.test, got 'Invalid'"
        in caplog.text
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                datetime.DOMAIN: {
                    "name": "test",
                    "command_topic": "command-topic",
                    "qos": "2",
                    "timezone": "Europe/Amsterdam",
                }
            }
        }
    ],
)
async def test_sending_mqtt_commands_and_optimistic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the sending MQTT commands in optimistic mode."""
    mqtt_mock = await mqtt_mock_entry()

    state = hass.states.get("datetime.test")
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await async_set_value(
        hass,
        "datetime.test",
        datetime_lib.datetime(
            year=2025, month=12, day=1, hour=10, minute=12, tzinfo=UTC
        ),
    )
    await hass.async_block_till_done()

    mqtt_mock.async_publish.assert_called_once_with(
        "command-topic", "2025-12-01T10:12:00+00:00", 2, False
    )
    mqtt_mock.async_publish.reset_mock()
    state = hass.states.get("datetime.test")
    assert state.state == "2025-12-01T10:12:00+00:00"


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, datetime.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            datetime.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
            }
        }
    }
    await help_test_default_availability_payload(
        hass,
        mqtt_mock_entry,
        datetime.DOMAIN,
        config,
        True,
        "state-topic",
        "2025-10-01 10:12:00",
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    config = {
        mqtt.DOMAIN: {
            datetime.DOMAIN: {
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
            }
        }
    }

    await help_test_custom_availability_payload(
        hass,
        mqtt_mock_entry,
        datetime.DOMAIN,
        config,
        True,
        "state-topic",
        "2025-10-01 10:12:00",
    )


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG, None
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                datetime.DOMAIN: [
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
    """Test unique id option only creates one datetime entity per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, datetime.DOMAIN)


async def test_discovery_removal_time(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered datetime entity."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock_entry, datetime.DOMAIN, data)


async def test_discovery_datetime_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered datetime entity."""
    config1 = {
        "name": "Beer",
        "command_topic": "command-topic",
        "state_topic": "state-topic",
    }
    config2 = {
        "name": "Milk",
        "command_topic": "command-topic",
        "state_topic": "state-topic",
    }

    await help_test_discovery_update(
        hass, mqtt_mock_entry, datetime.DOMAIN, config1, config2
    )


async def test_discovery_update_unchanged_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered update."""
    data1 = '{ "name": "Beer", "state_topic": "state-topic", "command_topic": "command-topic"}'
    with patch(
        "homeassistant.components.mqtt.datetime.MqttDateTime.discovery_update"
    ) as discovery_update:
        await help_test_discovery_update_unchanged(
            hass, mqtt_mock_entry, datetime.DOMAIN, data1, discovery_update
        )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(
        hass, mqtt_mock_entry, datetime.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT date device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT date device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock_entry, datetime.DOMAIN, DEFAULT_CONFIG, None
    )


async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = datetime.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_reloadable(hass, mqtt_client_mock, domain, config)


@pytest.mark.parametrize(
    ("topic", "value", "attribute", "attribute_value"),
    [
        ("state_topic", "2025-12-01 10:12:00 +0000", None, "2025-12-01T10:12:00+00:00"),
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
        datetime.DOMAIN,
        DEFAULT_CONFIG[mqtt.DOMAIN][datetime.DOMAIN],
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
    platform = datetime.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = datetime.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            datetime.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
                    "state_topic": "test-topic",
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
        ("test-topic", "2025-12-01 10:12:00 +0000", "2025-12-01 10:12:01 +0000"),
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
            datetime.DOMAIN,
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
