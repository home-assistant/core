"""The tests for the MQTT event platform."""

import copy
import json
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import event, mqtt
from homeassistant.components.mqtt.event import MQTT_EVENT_ATTRIBUTES_BLOCKED
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .test_common import (
    help_custom_config,
    help_test_availability_when_connection_lost,
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_list_payload,
    help_test_default_availability_list_payload_all,
    help_test_default_availability_list_payload_any,
    help_test_default_availability_list_single,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update_attr,
    help_test_discovery_update_availability,
    help_test_entity_category,
    help_test_entity_debug_info,
    help_test_entity_debug_info_message,
    help_test_entity_debug_info_remove,
    help_test_entity_debug_info_update_entity_id,
    help_test_entity_device_info_remove,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_connection,
    help_test_entity_device_info_with_identifier,
    help_test_entity_disabled_by_default,
    help_test_entity_id_update_discovery_update,
    help_test_entity_id_update_subscriptions,
    help_test_entity_name,
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

from tests.common import MockConfigEntry, async_fire_mqtt_message
from tests.typing import MqttMockHAClientGenerator, MqttMockPahoClient

DEFAULT_CONFIG = {
    mqtt.DOMAIN: {
        event.DOMAIN: {
            "name": "test",
            "state_topic": "test-topic",
            "event_types": ["press"],
        }
    }
}


@pytest.mark.freeze_time("2023-08-01 00:00:00+00:00")
@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_setting_event_value_via_mqtt_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the an MQTT event with attributes."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass, "test-topic", '{"event_type": "press", "duration": "short" }'
    )
    state = hass.states.get("event.test")

    assert state.state == "2023-08-01T00:00:00.000+00:00"
    assert state.attributes.get("duration") == "short"


@pytest.mark.freeze_time("2023-08-01 00:00:00+00:00")
@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_multiple_events_are_all_updating_the_state(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test all events are respected and trigger a state write."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.entity.MqttEntity.async_write_ha_state"
    ) as mock_async_ha_write_state:
        async_fire_mqtt_message(
            hass, "test-topic", '{"event_type": "press", "duration": "short" }'
        )
        assert len(mock_async_ha_write_state.mock_calls) == 1
        async_fire_mqtt_message(
            hass, "test-topic", '{"event_type": "press", "duration": "short" }'
        )
        assert len(mock_async_ha_write_state.mock_calls) == 2


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_handling_retained_event_payloads(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test if event messages with a retained flag are ignored."""
    await mqtt_mock_entry()
    with patch(
        "homeassistant.components.mqtt.entity.MqttEntity.async_write_ha_state"
    ) as mock_async_ha_write_state:
        async_fire_mqtt_message(
            hass,
            "test-topic",
            '{"event_type": "press", "duration": "short" }',
            retain=True,
        )
        assert len(mock_async_ha_write_state.mock_calls) == 0

        async_fire_mqtt_message(
            hass,
            "test-topic",
            '{"event_type": "press", "duration": "short" }',
            retain=False,
        )
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(
            hass,
            "test-topic",
            '{"event_type": "press", "duration": "short" }',
            retain=True,
        )
        assert len(mock_async_ha_write_state.mock_calls) == 1

        async_fire_mqtt_message(
            hass,
            "test-topic",
            '{"event_type": "press", "duration": "short" }',
            retain=False,
        )
        assert len(mock_async_ha_write_state.mock_calls) == 2


@pytest.mark.freeze_time("2023-08-01 00:00:00+00:00")
@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
@pytest.mark.parametrize(
    ("message", "log"),
    [
        (
            '{"event_type": "press", "duration": "short" ',
            "No valid JSON event payload detected",
        ),
        ('{"event_type": "invalid", "duration": "short" }', "Invalid event type"),
        ('{"event_type": 2, "duration": "short" }', "Invalid event type"),
        ('{"event_type": null, "duration": "short" }', "Invalid event type"),
        (
            '{"event": "press", "duration": "short" }',
            "`event_type` missing in JSON event payload",
        ),
    ],
)
async def test_setting_event_value_with_invalid_payload(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
    message: str,
    log: str,
) -> None:
    """Test the an MQTT event with attributes."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test-topic", message)
    state = hass.states.get("event.test")

    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert log in caplog.text


@pytest.mark.freeze_time("2023-08-01 00:00:00+00:00")
@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                event.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "event_types": ["press"],
                    "value_template": '{"event_type": "press", "val": "{{ value_json.val | is_defined }}", "par": "{{ value_json.par }}"}',
                }
            }
        }
    ],
)
async def test_setting_event_value_via_mqtt_json_message_and_default_current_state(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test processing an event via MQTT with fall back to current state."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(
        hass, "test-topic", '{ "val": "valcontent", "par": "parcontent" }'
    )
    state = hass.states.get("event.test")

    assert state.state == "2023-08-01T00:00:00.000+00:00"
    assert state.attributes.get("val") == "valcontent"
    assert state.attributes.get("par") == "parcontent"

    freezer.move_to("2023-08-01 00:00:10+00:00")

    async_fire_mqtt_message(hass, "test-topic", '{ "par": "invalidcontent" }')
    state = hass.states.get("event.test")

    assert state.state == "2023-08-01T00:00:00.000+00:00"
    assert state.attributes.get("val") == "valcontent"
    assert state.attributes.get("par") == "parcontent"

    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_when_connection_lost(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability after MQTT disconnection."""
    await help_test_availability_when_connection_lost(
        hass, mqtt_mock_entry, event.DOMAIN
    )


@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_availability_without_topic(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload_all(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload_all(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_payload_any(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_list_payload_any(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_list_single(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test availability list and availability_topic are mutually exclusive."""
    await help_test_default_availability_list_single(
        hass, mqtt_mock_entry, caplog, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_availability(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test availability discovery update."""
    await help_test_discovery_update_availability(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                event.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "event_types": ["press"],
                    "device_class": "foobarnotreal",
                }
            }
        }
    ],
)
@pytest.mark.usefixtures("hass")
async def test_invalid_device_class(
    mqtt_mock_entry: MqttMockHAClientGenerator, caplog: pytest.LogCaptureFixture
) -> None:
    """Test device_class option with invalid value."""
    assert await mqtt_mock_entry()
    assert "expected EventDeviceClass or one of" in caplog.text


async def test_setting_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_blocked_attribute_via_mqtt_json_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_blocked_attribute_via_mqtt_json_message(
        hass,
        mqtt_mock_entry,
        event.DOMAIN,
        DEFAULT_CONFIG,
        MQTT_EVENT_ATTRIBUTES_BLOCKED,
    )


async def test_setting_attribute_with_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock_entry, caplog, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_json(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_json(
        hass, mqtt_mock_entry, caplog, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                event.DOMAIN: [
                    {
                        "name": "Test 1",
                        "state_topic": "test-topic",
                        "event_types": ["press"],
                        "unique_id": "TOTALLY_UNIQUE",
                    },
                    {
                        "name": "Test 2",
                        "state_topic": "test-topic",
                        "event_types": ["press"],
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
    """Test unique id option only creates one event per unique_id."""
    await help_test_unique_id(hass, mqtt_mock_entry, event.DOMAIN)


async def test_discovery_removal_event(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test removal of discovered event."""
    data = '{ "name": "test", "state_topic": "test_topic", "event_types": ["press"] }'
    await help_test_discovery_removal(hass, mqtt_mock_entry, event.DOMAIN, data)


async def test_discovery_update_event_template(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test update of discovered mqtt event template."""
    await mqtt_mock_entry()
    config = {"name": "test", "state_topic": "test_topic", "event_types": ["press"]}
    config1 = copy.deepcopy(config)
    config2 = copy.deepcopy(config)
    config1["name"] = "Beer"
    config2["name"] = "Milk"
    config1["state_topic"] = "event/state1"
    config2["state_topic"] = "event/state1"
    config1["value_template"] = (
        '{"event_type": "press", "val": "{{ value_json.val | int }}"}'
    )
    config2["value_template"] = (
        '{"event_type": "press", "val": "{{ value_json.val | int * 2 }}"}'
    )

    async_fire_mqtt_message(hass, "homeassistant/event/bla/config", json.dumps(config1))
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "event/state1", '{"val":100}')
    await hass.async_block_till_done()
    state = hass.states.get("event.beer")
    assert state is not None
    assert state.attributes.get("val") == "100"

    async_fire_mqtt_message(hass, "homeassistant/event/bla/config", json.dumps(config2))
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "event/state1", '{"val":100}')
    await hass.async_block_till_done()
    state = hass.states.get("event.beer")
    assert state is not None
    assert state.attributes.get("val") == "200"


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer", "state_topic": "test_topic#", "event_types": ["press"] }'
    data2 = '{ "name": "Milk", "state_topic": "test_topic", "event_types": ["press"] }'
    await help_test_discovery_broken(hass, mqtt_mock_entry, event.DOMAIN, data1, data2)


async def test_entity_device_info_with_connection(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT event device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT event device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_hub(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mqtt_mock_entry: MqttMockHAClientGenerator,
) -> None:
    """Test MQTT event device registry integration."""
    await mqtt_mock_entry()
    other_config_entry = MockConfigEntry()
    other_config_entry.add_to_hass(hass)
    hub = device_registry.async_get_or_create(
        config_entry_id=other_config_entry.entry_id,
        connections=set(),
        identifiers={("mqtt", "hub-id")},
        manufacturer="manufacturer",
        model="hub",
    )

    data = json.dumps(
        {
            "name": "Test 1",
            "state_topic": "test-topic",
            "event_types": ["press"],
            "device": {"identifiers": ["helloworld"], "via_device": "hub-id"},
            "unique_id": "veryunique",
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/event/bla/config", data)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={("mqtt", "helloworld")})
    assert device is not None
    assert device.via_device_id == hub.id


async def test_entity_debug_info(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT event debug info."""
    await help_test_entity_debug_info(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG, None
    )


async def test_entity_debug_info_remove(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT event debug info."""
    await help_test_entity_debug_info_remove(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_update_entity_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test MQTT event debug info."""
    await help_test_entity_debug_info_update_entity_id(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_disabled_by_default(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test entity disabled by default."""
    await help_test_entity_disabled_by_default(
        hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG
    )


@pytest.mark.no_fail_on_log_exception
async def test_entity_category(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test entity category."""
    await help_test_entity_category(hass, mqtt_mock_entry, event.DOMAIN, DEFAULT_CONFIG)


@pytest.mark.parametrize(
    "hass_config",
    [
        {
            mqtt.DOMAIN: {
                event.DOMAIN: {
                    "name": "test",
                    "state_topic": "test-topic",
                    "event_types": ["press"],
                    "value_template": '{ "event_type": "press", "val": \
                {% if state_attr(entity_id, "friendly_name") == "test" %} \
                    "{{ value | int + 1 }}" \
                {% else %} \
                    "{{ value }}" \
                {% endif %}}',
                }
            }
        }
    ],
)
async def test_value_template_with_entity_id(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test the access to attributes in value_template via the entity_id."""
    await mqtt_mock_entry()

    async_fire_mqtt_message(hass, "test-topic", "100")
    state = hass.states.get("event.test")

    assert state.attributes.get("val") == "101"


async def test_reloadable(
    hass: HomeAssistant, mqtt_client_mock: MqttMockPahoClient
) -> None:
    """Test reloading the MQTT platform."""
    domain = event.DOMAIN
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
    platform = event.DOMAIN
    assert hass.states.get(f"{platform}.test")


async def test_unload_entry(
    hass: HomeAssistant, mqtt_mock_entry: MqttMockHAClientGenerator
) -> None:
    """Test unloading the config entry."""
    domain = event.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_unload_config_entry_with_platform(
        hass, mqtt_mock_entry, domain, config
    )


@pytest.mark.parametrize(
    ("expected_friendly_name", "device_class"),
    [("test", None), ("Doorbell", "doorbell"), ("Motion", "motion")],
)
async def test_entity_name(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    expected_friendly_name: str | None,
    device_class: str | None,
) -> None:
    """Test the entity name setup."""
    domain = event.DOMAIN
    config = DEFAULT_CONFIG
    await help_test_entity_name(
        hass, mqtt_mock_entry, domain, config, expected_friendly_name, device_class
    )


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            event.DOMAIN,
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


@pytest.mark.freeze_time("2023-09-01 00:00:00+00:00")
@pytest.mark.parametrize("hass_config", [DEFAULT_CONFIG])
async def test_skipped_async_ha_write_state2(
    hass: HomeAssistant,
    mqtt_mock_entry: MqttMockHAClientGenerator,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a write state command is only called when there is a valid event."""
    await mqtt_mock_entry()
    topic = "test-topic"
    payload1 = '{"event_type": "press"}'
    payload2 = '{"event_type": "unknown"}'
    with patch(
        "homeassistant.components.mqtt.entity.MqttEntity.async_write_ha_state"
    ) as mock_async_ha_write_state:
        assert len(mock_async_ha_write_state.mock_calls) == 0
        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 1

        freezer.move_to("2023-09-01 00:00:10+00:00")
        async_fire_mqtt_message(hass, topic, payload1)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2

        freezer.move_to("2023-09-01 00:00:20+00:00")
        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2

        freezer.move_to("2023-09-01 00:00:30+00:00")
        async_fire_mqtt_message(hass, topic, payload2)
        await hass.async_block_till_done()
        assert len(mock_async_ha_write_state.mock_calls) == 2


@pytest.mark.parametrize(
    "hass_config",
    [
        help_custom_config(
            event.DOMAIN,
            DEFAULT_CONFIG,
            (
                {
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
