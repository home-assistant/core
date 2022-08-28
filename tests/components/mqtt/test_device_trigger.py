"""The tests for MQTT device triggers."""
import json
from unittest.mock import patch

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.mqtt import _LOGGER, DOMAIN, debug_info
from homeassistant.const import Platform
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import async_initialize_triggers
from homeassistant.setup import async_setup_component

from .test_common import help_test_unload_config_entry

from tests.common import (
    assert_lists_same,
    async_fire_mqtt_message,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)
from tests.components.blueprint.conftest import stub_blueprint_populate  # noqa: F401


@pytest.fixture
def device_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_device_registry(hass)


@pytest.fixture
def entity_reg(hass):
    """Return an empty, loaded, registry."""
    return mock_registry(hass)


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


@pytest.fixture(autouse=True)
def binary_sensor_and_sensor_only():
    """Only setup the binary_sensor and sensor platform to speed up tests."""
    with patch(
        "homeassistant.components.mqtt.PLATFORMS",
        [Platform.BINARY_SENSOR, Platform.SENSOR],
    ):
        yield


async def test_get_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test we get the expected triggers from a discovered mqtt device."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_get_unknown_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test we don't get unknown triggers."""
    await mqtt_mock_entry_no_yaml_config()
    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, [])


async def test_get_non_existing_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test getting non existing triggers."""
    await mqtt_mock_entry_no_yaml_config()
    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, [])


@pytest.mark.no_fail_on_log_exception
async def test_discover_bad_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test bad discovery message."""
    await mqtt_mock_entry_no_yaml_config()
    # Test sending bad data
    data0 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payloads": "short_press",'
        '  "topics": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data0)
    await hass.async_block_till_done()
    assert device_reg.async_get_device({("mqtt", "0AFFD2")}) is None

    # Test sending correct data
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers)


async def test_update_remove_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test triggers can be updated and removed."""
    await mqtt_mock_entry_no_yaml_config()
    config1 = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"]},
        "payload": "short_press",
        "topic": "foobar/triggers/button1",
        "type": "button_short_press",
        "subtype": "button_1",
    }
    config1["some_future_option_1"] = "future_option_1"
    data1 = json.dumps(config1)

    config2 = {
        "automation_type": "trigger",
        "device": {"identifiers": ["0AFFD2"]},
        "payload": "short_press",
        "topic": "foobar/triggers/button1",
        "type": "button_short_press",
        "subtype": "button_2",
    }
    config2["topic"] = "foobar/tag_scanned2"
    data2 = json.dumps(config2)

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    expected_triggers1 = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
            "metadata": {},
        },
    ]
    expected_triggers2 = [dict(expected_triggers1[0])]
    expected_triggers2[0]["subtype"] = "button_2"

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers1)

    # Update trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data2)
    await hass.async_block_till_done()

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert_lists_same(triggers, expected_triggers2)

    # Remove trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})
    assert device_entry is None


async def test_if_fires_on_mqtt_message(
    hass, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers firing."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_1",
                        "subtype": "button_long_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_fires_on_mqtt_message_template(
    hass, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers firing."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        "  \"payload\": \"{{ 'foo_press'|regex_replace('foo', 'short') }}\","
        '  "topic": "foobar/triggers/button{{ sqrt(16)|round }}",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1",'
        '  "value_template": "{{ value_json.button }}"}'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        "  \"payload\": \"{{ 'foo_press'|regex_replace('foo', 'long') }}\","
        '  "topic": "foobar/triggers/button{{ sqrt(16)|round }}",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2",'
        '  "value_template": "{{ value_json.button }}"}'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_1",
                        "subtype": "button_long_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button4", '{"button":"short_press"}')
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button4", '{"button":"long_press"}')
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_fires_on_mqtt_message_late_discover(
    hass, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers firing of MQTT device triggers discovered after setup."""
    await mqtt_mock_entry_no_yaml_config()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "long_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla2",
                        "type": "button_1",
                        "subtype": "button_long_press",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("long_press")},
                    },
                },
            ]
        },
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "short_press"

    # Fake long press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "long_press")
    await hass.async_block_till_done()
    assert len(calls) == 2
    assert calls[1].data["some"] == "long_press"


async def test_if_fires_on_mqtt_message_after_update(
    hass, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers firing after update."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    data2 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/buttonOne",'
        '  "type": "button_long_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Update the trigger with different topic
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data2)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    async_fire_mqtt_message(hass, "foobar/triggers/buttonOne", "")
    await hass.async_block_till_done()
    assert len(calls) == 2

    # Update the trigger with same topic
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data2)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 2

    async_fire_mqtt_message(hass, "foobar/triggers/buttonOne", "")
    await hass.async_block_till_done()
    assert len(calls) == 3


async def test_no_resubscribe_same_topic(
    hass, device_reg, mqtt_mock_entry_no_yaml_config
):
    """Test subscription to topics without change."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    call_count = mqtt_mock.async_subscribe.call_count
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    assert mqtt_mock.async_subscribe.call_count == call_count


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt(
    hass, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers not firing after removal."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove the trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Rediscover the trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_not_fires_on_mqtt_message_after_remove_from_registry(
    hass, hass_ws_client, device_reg, calls, mqtt_mock_entry_no_yaml_config
):
    """Test triggers not firing after removal."""
    assert await async_setup_component(hass, "config", {})
    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    await mqtt_mock_entry_no_yaml_config()

    ws_client = await hass_ws_client(hass)

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mqtt_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove(hass, device_reg, mqtt_mock_entry_no_yaml_config):
    """Test attach and removal of trigger."""
    await mqtt_mock_entry_no_yaml_config()
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "short_press"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late(hass, device_reg, mqtt_mock_entry_no_yaml_config):
    """Test attach and removal of trigger ."""
    await mqtt_mock_entry_no_yaml_config()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    # Fake short press.
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0] == "short_press"

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove_late2(hass, device_reg, mqtt_mock_entry_no_yaml_config):
    """Test attach and removal of trigger ."""
    await mqtt_mock_entry_no_yaml_config()
    data0 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla0/config", data0)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_initialize_triggers(
        hass,
        [
            {
                "platform": "device",
                "domain": DOMAIN,
                "device_id": device_entry.id,
                "discovery_id": "bla1",
                "type": "button_short_press",
                "subtype": "button_1",
            },
        ],
        callback,
        DOMAIN,
        "mock-name",
        _LOGGER.log,
    )

    # Remove the trigger
    remove()
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()

    # Verify the triggers are no longer active
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 0


async def test_entity_device_info_with_connection(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT device registry integration."""
    await mqtt_mock_entry_no_yaml_config()
    registry = dr.async_get(hass)

    data = json.dumps(
        {
            "automation_type": "trigger",
            "topic": "test-topic",
            "type": "foo",
            "subtype": "bar",
            "device": {
                "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "hw_version": "rev1",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(
        set(), {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_with_identifier(hass, mqtt_mock_entry_no_yaml_config):
    """Test MQTT device registry integration."""
    await mqtt_mock_entry_no_yaml_config()
    registry = dr.async_get(hass)

    data = json.dumps(
        {
            "automation_type": "trigger",
            "topic": "test-topic",
            "type": "foo",
            "subtype": "bar",
            "device": {
                "identifiers": ["helloworld"],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "hw_version": "rev1",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.hw_version == "rev1"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_update(hass, mqtt_mock_entry_no_yaml_config):
    """Test device registry update."""
    await mqtt_mock_entry_no_yaml_config()
    registry = dr.async_get(hass)

    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {
            "identifiers": ["helloworld"],
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")})
    assert device is not None
    assert device.name == "Milk"


async def test_cleanup_trigger(
    hass, hass_ws_client, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test trigger discovery topic is cleaned when device is removed from registry."""
    mqtt_mock = await mqtt_mock_entry_no_yaml_config()
    assert await async_setup_component(hass, "config", {})
    ws_client = await hass_ws_client(hass)

    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers[0]["type"] == "foo"

    # Remove MQTT from the device
    mqtt_config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    await ws_client.send_json(
        {
            "id": 6,
            "type": "config/device_registry/remove_config_entry",
            "config_entry_id": mqtt_config_entry.entry_id,
            "device_id": device_entry.id,
        }
    )
    response = await ws_client.receive_json()
    assert response["success"]
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/device_automation/bla/config", "", 0, True
    )


async def test_cleanup_device(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test removal from device registry when trigger is removed."""
    await mqtt_mock_entry_no_yaml_config()
    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers[0]["type"] == "foo"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_several_triggers(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test removal from device registry when the last trigger is removed."""
    await mqtt_mock_entry_no_yaml_config()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo2",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 2
    assert triggers[0]["type"] == "foo"
    assert triggers[1]["type"] == "foo2"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1
    assert triggers[0]["type"] == "foo2"

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_with_entity1(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test removal from device registry for device with entity.

    Trigger removed first, then entity.
    """
    await mqtt_mock_entry_no_yaml_config()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 2  # 2 binary_sensor triggers

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_cleanup_device_with_entity2(
    hass, device_reg, entity_reg, mqtt_mock_entry_no_yaml_config
):
    """Test removal from device registry for device with entity.

    Entity removed first, then trigger.
    """
    await mqtt_mock_entry_no_yaml_config()
    config1 = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {"identifiers": ["helloworld"]},
    }

    config2 = {
        "name": "test_binary_sensor",
        "state_topic": "test-topic",
        "device": {"identifiers": ["helloworld"]},
        "unique_id": "veryunique",
    }

    data1 = json.dumps(config1)
    data2 = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", data2)
    await hass.async_block_till_done()

    # Verify device registry entry is created
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 3  # 2 binary_sensor triggers + device trigger

    async_fire_mqtt_message(hass, "homeassistant/binary_sensor/bla2/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is not cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is not None

    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert len(triggers) == 1  # device trigger

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")})
    assert device_entry is None


async def test_trigger_debug_info(hass, mqtt_mock_entry_no_yaml_config):
    """Test debug_info.

    This is a test helper for MQTT debug_info.
    """
    await mqtt_mock_entry_no_yaml_config()
    registry = dr.async_get(hass)

    config1 = {
        "platform": "mqtt",
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
    }
    config2 = {
        "platform": "mqtt",
        "automation_type": "trigger",
        "topic": "test-topic2",
        "type": "foo",
        "subtype": "bar",
        "device": {
            "connections": [[dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12"]],
        },
    }
    data = json.dumps(config1)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data)
    data = json.dumps(config2)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla2/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device(
        set(), {(dr.CONNECTION_NETWORK_MAC, "02:5b:26:a8:dc:12")}
    )
    assert device is not None

    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 2
    topic_map = {
        "homeassistant/device_automation/bla1/config": config1,
        "homeassistant/device_automation/bla2/config": config2,
    }
    assert (
        topic_map[debug_info_data["triggers"][0]["discovery_data"]["topic"]]
        != topic_map[debug_info_data["triggers"][1]["discovery_data"]["topic"]]
    )
    assert (
        debug_info_data["triggers"][0]["discovery_data"]["payload"]
        == topic_map[debug_info_data["triggers"][0]["discovery_data"]["topic"]]
    )
    assert (
        debug_info_data["triggers"][1]["discovery_data"]["payload"]
        == topic_map[debug_info_data["triggers"][1]["discovery_data"]["topic"]]
    )

    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", "")
    await hass.async_block_till_done()
    debug_info_data = debug_info.info_for_device(hass, device.id)
    assert len(debug_info_data["entities"]) == 0
    assert len(debug_info_data["triggers"]) == 1
    assert (
        debug_info_data["triggers"][0]["discovery_data"]["topic"]
        == "homeassistant/device_automation/bla2/config"
    )
    assert debug_info_data["triggers"][0]["discovery_data"]["payload"] == config2


async def test_unload_entry(hass, calls, device_reg, mqtt_mock, tmp_path) -> None:
    """Test unloading the MQTT entry."""

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")})

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "discovery_id": "bla1",
                        "type": "button_short_press",
                        "subtype": "button_1",
                    },
                    "action": {
                        "service": "test.automation",
                        "data_template": {"some": ("short_press")},
                    },
                },
            ]
        },
    )

    # Fake short press 1
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await help_test_unload_config_entry(hass, tmp_path, {})

    # Fake short press 2
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1
