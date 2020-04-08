"""The tests for MQTT device triggers."""
import json

import pytest

import homeassistant.components.automation as automation
from homeassistant.components.mqtt import DOMAIN
from homeassistant.components.mqtt.device_trigger import async_attach_trigger
from homeassistant.components.mqtt.discovery import async_start
from homeassistant.setup import async_setup_component

from tests.common import (
    MockConfigEntry,
    assert_lists_same,
    async_fire_mqtt_message,
    async_get_device_automations,
    async_mock_service,
    mock_device_registry,
    mock_registry,
)


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


async def test_get_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test we get the expected triggers from a discovered mqtt device."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_get_unknown_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test we don't get unknown triggers."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, [])


async def test_get_non_existing_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test getting non existing triggers."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    # Discover a sensor (without device triggers)
    data1 = (
        '{ "device":{"identifiers":["0AFFD2"]},'
        '  "state_topic": "foobar/sensor",'
        '  "unique_id": "unique" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/sensor/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, [])


async def test_discover_bad_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test bad discovery message."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    # Test sending bad data
    data0 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "payloads": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data0)
    await hass.async_block_till_done()
    assert device_reg.async_get_device({("mqtt", "0AFFD2")}, set()) is None

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

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    ]
    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers)


async def test_update_remove_triggers(hass, device_reg, entity_reg, mqtt_mock):
    """Test triggers can be updated and removed."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
        '  "payload": "short_press",'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_2" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data1)
    await hass.async_block_till_done()

    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    expected_triggers1 = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla",
            "type": "button_short_press",
            "subtype": "button_1",
        },
    ]
    expected_triggers2 = [dict(expected_triggers1[0])]
    expected_triggers2[0]["subtype"] = "button_2"

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers1)

    # Update trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data2)
    await hass.async_block_till_done()

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, expected_triggers2)

    # Remove trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", "")
    await hass.async_block_till_done()

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert_lists_same(triggers, [])


async def test_if_fires_on_mqtt_message(hass, device_reg, calls, mqtt_mock):
    """Test triggers firing."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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


async def test_if_fires_on_mqtt_message_late_discover(
    hass, device_reg, calls, mqtt_mock
):
    """Test triggers firing of MQTT device triggers discovered after setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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
    hass, device_reg, calls, mqtt_mock
):
    """Test triggers firing after update."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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
    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Update the trigger
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data2)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "")
    await hass.async_block_till_done()
    assert len(calls) == 1

    async_fire_mqtt_message(hass, "foobar/triggers/buttonOne", "")
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_not_fires_on_mqtt_message_after_remove_by_mqtt(
    hass, device_reg, calls, mqtt_mock
):
    """Test triggers not firing after removal."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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
    hass, device_reg, calls, mqtt_mock
):
    """Test triggers not firing after removal."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

    data1 = (
        '{ "automation_type":"trigger",'
        '  "device":{"identifiers":["0AFFD2"]},'
        '  "topic": "foobar/triggers/button1",'
        '  "type": "button_short_press",'
        '  "subtype": "button_1" }'
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla1/config", data1)
    await hass.async_block_till_done()
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

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

    # Remove the device
    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()

    async_fire_mqtt_message(hass, "foobar/triggers/button1", "short_press")
    await hass.async_block_till_done()
    assert len(calls) == 1


async def test_attach_remove(hass, device_reg, mqtt_mock):
    """Test attach and removal of trigger."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
        callback,
        None,
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


async def test_attach_remove_late(hass, device_reg, mqtt_mock):
    """Test attach and removal of trigger ."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
        callback,
        None,
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


async def test_attach_remove_late2(hass, device_reg, mqtt_mock):
    """Test attach and removal of trigger ."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())

    calls = []

    def callback(trigger):
        calls.append(trigger["trigger"]["payload"])

    remove = await async_attach_trigger(
        hass,
        {
            "platform": "device",
            "domain": DOMAIN,
            "device_id": device_entry.id,
            "discovery_id": "bla1",
            "type": "button_short_press",
            "subtype": "button_1",
        },
        callback,
        None,
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


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT device registry integration."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    data = json.dumps(
        {
            "automation_type": "trigger",
            "topic": "test-topic",
            "type": "foo",
            "subtype": "bar",
            "device": {
                "identifiers": ["helloworld"],
                "connections": [["mac", "02:5b:26:a8:dc:12"]],
                "manufacturer": "Whatever",
                "name": "Beer",
                "model": "Glass",
                "sw_version": "0.1-beta",
            },
        }
    )
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.identifiers == {("mqtt", "helloworld")}
    assert device.connections == {("mac", "02:5b:26:a8:dc:12")}
    assert device.manufacturer == "Whatever"
    assert device.name == "Beer"
    assert device.model == "Glass"
    assert device.sw_version == "0.1-beta"


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, entry)
    registry = await hass.helpers.device_registry.async_get_registry()

    config = {
        "automation_type": "trigger",
        "topic": "test-topic",
        "type": "foo",
        "subtype": "bar",
        "device": {
            "identifiers": ["helloworld"],
            "connections": [["mac", "02:5b:26:a8:dc:12"]],
            "manufacturer": "Whatever",
            "name": "Beer",
            "model": "Glass",
            "sw_version": "0.1-beta",
        },
    }

    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Beer"

    config["device"]["name"] = "Milk"
    data = json.dumps(config)
    async_fire_mqtt_message(hass, "homeassistant/device_automation/bla/config", data)
    await hass.async_block_till_done()

    device = registry.async_get_device({("mqtt", "helloworld")}, set())
    assert device is not None
    assert device.name == "Milk"


async def test_cleanup_device(hass, device_reg, entity_reg, mqtt_mock):
    """Test discovered device is cleaned up when removed from registry."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    await async_start(hass, "homeassistant", {}, config_entry)

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
    device_entry = device_reg.async_get_device({("mqtt", "helloworld")}, set())
    assert device_entry is not None

    triggers = await async_get_device_automations(hass, "trigger", device_entry.id)
    assert triggers[0]["type"] == "foo"

    device_reg.async_remove_device(device_entry.id)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # Verify device registry entry is cleared
    device_entry = device_reg.async_get_device({("mqtt", "0AFFD2")}, set())
    assert device_entry is None

    # Verify retained discovery topic has been cleared
    mqtt_mock.async_publish.assert_called_once_with(
        "homeassistant/device_automation/bla/config", "", 0, True
    )
