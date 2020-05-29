"""The tests for the MQTT sensor platform."""
from datetime import datetime, timedelta
import json

import pytest

from homeassistant.components import mqtt
from homeassistant.components.mqtt.discovery import async_start
import homeassistant.components.sensor as sensor
from homeassistant.const import EVENT_STATE_CHANGED
import homeassistant.core as ha
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .test_common import (
    help_test_availability_without_topic,
    help_test_custom_availability_payload,
    help_test_default_availability_payload,
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_debug_info,
    help_test_entity_debug_info_max_messages,
    help_test_entity_debug_info_message,
    help_test_entity_debug_info_remove,
    help_test_entity_debug_info_update_entity_id,
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

from tests.async_mock import patch
from tests.common import (
    MockConfigEntry,
    async_fire_mqtt_message,
    async_fire_time_changed,
)

DEFAULT_CONFIG = {
    sensor.DOMAIN: {"platform": "mqtt", "name": "test", "state_topic": "test-topic"}
}


async def test_setting_sensor_value_via_mqtt_message(hass, mqtt_mock):
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "unit_of_measurement": "fav unit",
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", "100")
    state = hass.states.get("sensor.test")

    assert state.state == "100"
    assert state.attributes.get("unit_of_measurement") == "fav unit"


async def test_setting_sensor_value_expires(hass, mqtt_mock, caplog):
    """Test the expiration of the value."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "unit_of_measurement": "fav unit",
                "expire_after": "4",
                "force_update": True,
            }
        },
    )

    state = hass.states.get("sensor.test")
    assert state.state == "unknown"

    now = datetime(2017, 1, 1, 1, tzinfo=dt_util.UTC)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "100")
        await hass.async_block_till_done()

    # Value was set correctly.
    state = hass.states.get("sensor.test")
    assert state.state == "100"

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("sensor.test")
    assert state.state == "100"

    # Next message resets timer
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "101")
        await hass.async_block_till_done()

    # Value was updated correctly.
    state = hass.states.get("sensor.test")
    assert state.state == "101"

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("sensor.test")
    assert state.state == "101"

    # Time jump +2s
    now = now + timedelta(seconds=2)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is expired now
    state = hass.states.get("sensor.test")
    assert state.state == "unknown"


async def test_setting_sensor_value_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of the value via MQTT with JSON payload."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "unit_of_measurement": "fav unit",
                "value_template": "{{ value_json.val }}",
            }
        },
    )

    async_fire_mqtt_message(hass, "test-topic", '{ "val": "100" }')
    state = hass.states.get("sensor.test")

    assert state.state == "100"


async def test_force_update_disabled(hass, mqtt_mock):
    """Test force update option."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "unit_of_measurement": "fav unit",
            }
        },
    )

    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_force_update_enabled(hass, mqtt_mock):
    """Test force update option."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "unit_of_measurement": "fav unit",
                "force_update": True,
            }
        },
    )

    events = []

    @ha.callback
    def callback(event):
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "100")
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    await help_test_availability_without_topic(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_default_availability_payload(hass, mqtt_mock):
    """Test availability by default payload with defined topic."""
    await help_test_default_availability_payload(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_custom_availability_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    await help_test_custom_availability_payload(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_invalid_device_class(hass, mqtt_mock):
    """Test device_class option with invalid value."""
    assert await async_setup_component(
        hass,
        sensor.DOMAIN,
        {
            sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "device_class": "foobarnotreal",
            }
        },
    )

    state = hass.states.get("sensor.test")
    assert state is None


async def test_valid_device_class(hass, mqtt_mock):
    """Test device_class option with valid values."""
    assert await async_setup_component(
        hass,
        "sensor",
        {
            "sensor": [
                {
                    "platform": "mqtt",
                    "name": "Test 1",
                    "state_topic": "test-topic",
                    "device_class": "temperature",
                },
                {"platform": "mqtt", "name": "Test 2", "state_topic": "test-topic"},
            ]
        },
    )
    await hass.async_block_till_done()

    state = hass.states.get("sensor.test_1")
    assert state.attributes["device_class"] == "temperature"
    state = hass.states.get("sensor.test_2")
    assert "device_class" not in state.attributes


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_setting_attribute_with_template(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_with_template(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_unique_id(hass):
    """Test unique id option only creates one sensor per unique_id."""
    config = {
        sensor.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, sensor.DOMAIN, config)


async def test_discovery_removal_sensor(hass, mqtt_mock, caplog):
    """Test removal of discovered sensor."""
    data = '{ "name": "test",' '  "state_topic": "test_topic" }'
    await help_test_discovery_removal(hass, mqtt_mock, caplog, sensor.DOMAIN, data)


async def test_discovery_update_sensor(hass, mqtt_mock, caplog):
    """Test update of discovered sensor."""
    data1 = '{ "name": "Beer",' '  "state_topic": "test_topic" }'
    data2 = '{ "name": "Milk",' '  "state_topic": "test_topic" }'
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, sensor.DOMAIN, data1, data2
    )


@pytest.mark.no_fail_on_log_exception
async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer",' '  "state_topic": "test_topic#" }'
    data2 = '{ "name": "Milk",' '  "state_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, sensor.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_connection(hass, mqtt_mock):
    """Test MQTT sensor device registry integration."""
    await help_test_entity_device_info_with_connection(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT sensor device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_remove(hass, mqtt_mock):
    """Test device registry remove."""
    await help_test_entity_device_info_remove(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_subscriptions(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    await help_test_entity_id_update_subscriptions(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_id_update_discovery_update(hass, mqtt_mock):
    """Test MQTT discovery update when entity_id is updated."""
    await help_test_entity_id_update_discovery_update(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_device_info_with_hub(hass, mqtt_mock):
    """Test MQTT sensor device registry integration."""
    entry = MockConfigEntry(domain=mqtt.DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)

    registry = await hass.helpers.device_registry.async_get_registry()
    hub = registry.async_get_or_create(
        config_entry_id="123",
        connections=set(),
        identifiers={("mqtt", "hub-id")},
        manufacturer="manufacturer",
        model="hub",
    )

    data = json.dumps(
        {
            "platform": "mqtt",
            "name": "Test 1",
            "state_topic": "test-topic",
            "device": {"identifiers": ["helloworld"], "via_device": "hub-id"},
            "unique_id": "veryunique",
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.via_device_id == hub.id


async def test_entity_debug_info(hass, mqtt_mock):
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info(hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG)


async def test_entity_debug_info_max_messages(hass, mqtt_mock):
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_max_messages(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_message(hass, mqtt_mock):
    """Test MQTT debug info."""
    await help_test_entity_debug_info_message(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_remove(hass, mqtt_mock):
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_remove(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )


async def test_entity_debug_info_update_entity_id(hass, mqtt_mock):
    """Test MQTT sensor debug info."""
    await help_test_entity_debug_info_update_entity_id(
        hass, mqtt_mock, sensor.DOMAIN, DEFAULT_CONFIG
    )
