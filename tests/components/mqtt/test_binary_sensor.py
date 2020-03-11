"""The tests for the  MQTT binary sensor platform."""
import copy
from datetime import datetime, timedelta
import json
from unittest.mock import patch

from homeassistant.components import binary_sensor
from homeassistant.const import (
    EVENT_STATE_CHANGED,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .common import (
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, async_fire_time_changed

DEFAULT_CONFIG = {
    binary_sensor.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "test-topic",
    }
}

DEFAULT_CONFIG_ATTR = {
    binary_sensor.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "state_topic": "test-topic",
        "json_attributes_topic": "attr-topic",
    }
}

DEFAULT_CONFIG_DEVICE_INFO = {
    "platform": "mqtt",
    "name": "test",
    "state_topic": "test-topic",
    "device": {
        "identifiers": ["helloworld"],
        "connections": [["mac", "02:5b:26:a8:dc:12"]],
        "manufacturer": "Whatever",
        "name": "Beer",
        "model": "Glass",
        "sw_version": "0.1-beta",
    },
    "unique_id": "veryunique",
}


async def test_setting_sensor_value_expires_availability_topic(hass, mqtt_mock, caplog):
    """Test the expiration of the value."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "expire_after": 4,
                "force_update": True,
                "availability_topic": "availability-topic",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get("binary_sensor.test")
    assert state.state != STATE_UNAVAILABLE

    await expires_helper(hass, mqtt_mock, caplog)


async def test_setting_sensor_value_expires(hass, mqtt_mock, caplog):
    """Test the expiration of the value."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "expire_after": 4,
                "force_update": True,
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    await expires_helper(hass, mqtt_mock, caplog)


async def expires_helper(hass, mqtt_mock, caplog):
    """Run the basic expiry code."""

    now = datetime(2017, 1, 1, 1, tzinfo=dt_util.UTC)
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "ON")
        await hass.async_block_till_done()

    # Value was set correctly.
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    # Next message resets timer
    with patch(("homeassistant.helpers.event.dt_util.utcnow"), return_value=now):
        async_fire_time_changed(hass, now)
        async_fire_mqtt_message(hass, "test-topic", "OFF")
        await hass.async_block_till_done()

    # Value was updated correctly.
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    # Time jump +3s
    now = now + timedelta(seconds=3)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is not yet expired
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    # Time jump +2s
    now = now + timedelta(seconds=2)
    async_fire_time_changed(hass, now)
    await hass.async_block_till_done()

    # Value is expired now
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_setting_sensor_value_via_mqtt_message(hass, mqtt_mock):
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")

    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test-topic", "ON")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "OFF")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF


async def test_setting_sensor_value_via_mqtt_message_and_template(hass, mqtt_mock):
    """Test the setting of the value via MQTT."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "value_template": '{%if is_state(entity_id,"on")-%}OFF'
                "{%-else-%}ON{%-endif%}",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "test-topic", "")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "test-topic", "")
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF


async def test_valid_device_class(hass, mqtt_mock):
    """Test the setting of a valid sensor class."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "device_class": "motion",
                "state_topic": "test-topic",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.attributes.get("device_class") == "motion"


async def test_invalid_device_class(hass, mqtt_mock):
    """Test the setting of an invalid sensor class."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "device_class": "abc123",
                "state_topic": "test-topic",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state is None


async def test_availability_without_topic(hass, mqtt_mock):
    """Test availability without defined availability topic."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state != STATE_UNAVAILABLE


async def test_availability_by_defaults(hass, mqtt_mock):
    """Test availability by defaults with defined topic."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "availability_topic": "availability-topic",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "online")

    state = hass.states.get("binary_sensor.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "offline")

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_availability_by_custom_payload(hass, mqtt_mock):
    """Test availability by custom payload with defined topic."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "availability_topic": "availability-topic",
                "payload_available": "good",
                "payload_not_available": "nogood",
            }
        },
    )

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "good")

    state = hass.states.get("binary_sensor.test")
    assert state.state != STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability-topic", "nogood")

    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_UNAVAILABLE


async def test_force_update_disabled(hass, mqtt_mock):
    """Test force update option."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
            }
        },
    )

    events = []

    @ha.callback
    def callback(event):
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1


async def test_force_update_enabled(hass, mqtt_mock):
    """Test force update option."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "force_update": True,
            }
        },
    )

    events = []

    @ha.callback
    def callback(event):
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    assert len(events) == 2


async def test_off_delay(hass, mqtt_mock):
    """Test off_delay option."""
    assert await async_setup_component(
        hass,
        binary_sensor.DOMAIN,
        {
            binary_sensor.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "test-topic",
                "payload_on": "ON",
                "payload_off": "OFF",
                "off_delay": 30,
                "force_update": True,
            }
        },
    )

    events = []

    @ha.callback
    def callback(event):
        """Verify event got called."""
        events.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, callback)

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    assert len(events) == 1

    async_fire_mqtt_message(hass, "test-topic", "ON")
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_ON
    assert len(events) == 2

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=30))
    await hass.async_block_till_done()
    state = hass.states.get("binary_sensor.test")
    assert state.state == STATE_OFF
    assert len(events) == 3


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, binary_sensor.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    config1 = copy.deepcopy(DEFAULT_CONFIG_ATTR[binary_sensor.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG_ATTR[binary_sensor.DOMAIN])
    config1["json_attributes_topic"] = "attr-topic1"
    config2["json_attributes_topic"] = "attr-topic2"
    data1 = json.dumps(config1)
    data2 = json.dumps(config2)

    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, data1, data2
    )


async def test_unique_id(hass):
    """Test unique id option only creates one sensor per unique_id."""
    config = {
        binary_sensor.DOMAIN: [
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
    await help_test_unique_id(hass, binary_sensor.DOMAIN, config)


async def test_discovery_removal_binary_sensor(hass, mqtt_mock, caplog):
    """Test removal of discovered binary_sensor."""
    data = json.dumps(DEFAULT_CONFIG[binary_sensor.DOMAIN])
    await help_test_discovery_removal(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, data
    )


async def test_discovery_update_binary_sensor(hass, mqtt_mock, caplog):
    """Test update of discovered binary_sensor."""
    config1 = copy.deepcopy(DEFAULT_CONFIG[binary_sensor.DOMAIN])
    config2 = copy.deepcopy(DEFAULT_CONFIG[binary_sensor.DOMAIN])
    config1["name"] = "Beer"
    config2["name"] = "Milk"

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, data1, data2
    )


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer",' '  "off_delay": -1 }'
    data2 = '{ "name": "Milk",' '  "state_topic": "test_topic" }'
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, binary_sensor.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT binary sensor device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, binary_sensor.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, binary_sensor.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        binary_sensor.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "beer",
                "state_topic": "test-topic",
                "availability_topic": "avty-topic",
                "unique_id": "TOTALLY_UNIQUE",
            }
        ]
    }
    await help_test_entity_id_update(hass, mqtt_mock, binary_sensor.DOMAIN, config)
